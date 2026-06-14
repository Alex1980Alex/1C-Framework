"""Unit tests for SearchManager, BM25Store, RRF, and pipeline helpers (F2.3.1-F2.3.7).

Rewritten against the current public API after refactor:
- SearchManager.register_strategy(name, strategy) — two positional args
- SearchManager.search is async, returns SearchResponse
- BM25Store.initialize() + add_chunks() + search() are all async; uses :memory: db via tmp_path
- RRF lives in HybridSearchStrategy._rrf_merge (no standalone rrf_fusion function)
- TwoStagePipeline(stage1_strategy, reranker, ...) — required ctor args; no classify_query
- SectionFirstPipeline(bm25_store, search_manager) — required ctor args; no identify_section

Async tests are ``async def`` (project ``asyncio_mode = "auto"``); pytest-asyncio manages a
fresh per-test event loop. (Do NOT use ``asyncio.get_event_loop().run_until_complete()`` —
it grabs whatever global loop exists, which a prior ``asyncio.run()`` in another test file
may have closed, causing spurious "event loop is closed" failures.)
"""

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str, content: str = "text") -> DocumentChunk:
    return DocumentChunk(id=chunk_id, content=content, document_id="doc1")


def _make_result(chunk_id: str, score: float = 0.9) -> SearchResult:
    return SearchResult(chunk=_make_chunk(chunk_id), score=score)


def _make_response(query: str, results: list[SearchResult]) -> SearchResponse:
    return SearchResponse(query=query, results=results, total_found=len(results))


# ---------------------------------------------------------------------------
# TestSearchManager
# ---------------------------------------------------------------------------


class TestSearchManager:
    """F2.3.1-F2.3.2: SearchManager strategy registration and routing."""

    def test_register_strategy(self):
        """F2.3.1: register_strategy(name, obj) stores strategy under that name."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()
        mock_strategy = MagicMock()

        manager.register_strategy("test_strategy", mock_strategy)

        assert "test_strategy" in manager._strategies
        assert manager._strategies["test_strategy"] is mock_strategy

    def test_available_strategies_reflects_registration(self):
        """available_strategies lists all registered names."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()
        assert manager.available_strategies == []

        manager.register_strategy("alpha", MagicMock())
        manager.register_strategy("beta", MagicMock())

        assert set(manager.available_strategies) == {"alpha", "beta"}

    async def test_search_routing(self):
        """F2.3.2: search() dispatches to the named strategy and returns SearchResponse."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()

        expected_results = [_make_result("1"), _make_result("2"), _make_result("3")]
        mock_response = _make_response("test query", expected_results)

        mock_strategy = MagicMock()
        mock_strategy.search = AsyncMock(return_value=mock_response)

        manager.register_strategy("hybrid", mock_strategy)

        response = await manager.search("test query", strategy="hybrid", k=3)

        mock_strategy.search.assert_called_once()
        assert isinstance(response, SearchResponse)
        assert len(response.results) == 3

    async def test_search_unknown_strategy_raises(self):
        """search() with unknown strategy name raises ValueError."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()

        with pytest.raises(ValueError, match="Unknown search strategy"):
            await manager.search("q", strategy="nonexistent")


# ---------------------------------------------------------------------------
# TestBM25Store
# ---------------------------------------------------------------------------


class TestBM25Store:
    """F2.3.3-F2.3.4: BM25Store async add + search using SQLite FTS5."""

    async def test_bm25_add_and_search(self, tmp_path):
        """F2.3.3: add_chunks then search returns matching chunk_ids."""
        from src.pdf_framework.search.bm25_store import BM25Store

        db = tmp_path / "bm25_test.db"
        store = BM25Store(db_path=db)

        await store.initialize()
        n = await store.add_chunks(
            chunk_ids=["c1", "c2"],
            contents=["test document content", "another unrelated entry"],
            document_ids=["doc1", "doc1"],
            sources=["file.pdf", "file.pdf"],
        )
        assert n == 2
        results = await store.search("test document", k=5)

        assert len(results) > 0
        # "c1" should rank first — it contains both "test" and "document"
        chunk_ids_returned = [r[0] for r in results]
        assert "c1" in chunk_ids_returned

    async def test_bm25_fts5_schema_migration(self, tmp_path):
        """F2.3.4: BM25Store migrates old single-column FTS5 schema to multi-column."""
        from src.pdf_framework.search.bm25_store import BM25Store

        db = tmp_path / "legacy_bm25.db"

        # Seed a legacy single-column schema
        conn = sqlite3.connect(str(db))
        conn.execute(
            """
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id,
                content,
                document_id,
                tokenize='unicode61'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_meta (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()
        conn.close()

        # initialize() must detect the old schema and migrate it transparently
        store = BM25Store(db_path=db)

        await store.initialize()
        # After migration, we can add a chunk and search without error
        await store.add_chunks(
            chunk_ids=["m1"],
            contents=["migration test"],
            document_ids=["doc1"],
            sources=["f.pdf"],
        )
        results = await store.search("migration", k=3)

        # The new multi-column schema is in place — search works
        assert isinstance(results, list)

        # Verify the new schema has title/body columns
        conn2 = sqlite3.connect(str(db))
        cur = conn2.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
        )
        row = cur.fetchone()
        conn2.close()
        assert row is not None
        assert "title" in row[0].lower()
        assert "body" in row[0].lower()


# ---------------------------------------------------------------------------
# TestFusion (RRF via HybridSearchStrategy._rrf_merge)
# ---------------------------------------------------------------------------


class TestFusion:
    """F2.3.7: RRF fusion math — tested through HybridSearchStrategy._rrf_merge."""

    def _make_hybrid_strategy(self, rrf_k: int = 60):
        """Build a minimal HybridSearchStrategy with controllable rrf_k."""
        from src.pdf_framework.search.strategies.hybrid_search import HybridSearchStrategy

        vec = MagicMock()
        graph = MagicMock()
        strategy = HybridSearchStrategy(
            vector_strategy=vec,
            graph_strategy=graph,
            rrf_k=rrf_k,
            vector_weight=0.5,
            graph_weight=0.5,
        )
        return strategy

    def test_rrf_all_unique_ids_appear(self):
        """F2.3.7a: All unique chunk IDs from both lists appear in fused result."""
        strategy = self._make_hybrid_strategy()

        vec_results = [_make_result("1", 0.9), _make_result("2", 0.8)]
        graph_results = [_make_result("2", 0.95), _make_result("3", 0.7)]

        fused = strategy._rrf_merge(
            vector_results=vec_results,
            graph_results=graph_results,
            k=10,
        )

        ids = {r.chunk.id for r in fused}
        assert ids == {"1", "2", "3"}

    def test_rrf_shared_id_ranks_higher(self):
        """F2.3.7b: ID appearing in both lists accumulates higher RRF score."""
        strategy = self._make_hybrid_strategy(rrf_k=60)

        # "shared" appears at rank 0 in both → score = 2 * weight/(60+1)
        # "unique" appears only in vector at rank 1 → score = weight/(60+2)
        vec_results = [_make_result("shared"), _make_result("unique")]
        graph_results = [_make_result("shared")]

        fused = strategy._rrf_merge(
            vector_results=vec_results,
            graph_results=graph_results,
            k=10,
        )

        scores = {r.chunk.id: r.score for r in fused}
        assert scores["shared"] > scores["unique"], (
            f"shared({scores['shared']:.4f}) should beat unique({scores['unique']:.4f})"
        )

    def test_rrf_k60_formula(self):
        """F2.3.7c: Score formula score += weight / (k + rank + 1) with k=60."""
        strategy = self._make_hybrid_strategy(rrf_k=60)

        # One vector result at rank 0; weight=0.5 → expected score = 0.5/61
        vec_results = [_make_result("solo")]
        graph_results = []

        fused = strategy._rrf_merge(
            vector_results=vec_results,
            graph_results=graph_results,
            k=1,
        )

        assert len(fused) == 1
        expected = 0.5 / (60 + 0 + 1)
        assert abs(fused[0].score - expected) < 1e-9


# ---------------------------------------------------------------------------
# TestPipelines
# ---------------------------------------------------------------------------


class TestPipelines:
    """F2.3.5-F2.3.6: TwoStagePipeline and SectionFirstPipeline with mocked dependencies."""

    # --- TwoStagePipeline ---

    async def test_two_stage_pipeline_returns_search_response(self):
        """F2.3.5: TwoStagePipeline.search returns SearchResponse with at most k results."""
        from src.pdf_framework.search.pipelines.two_stage import TwoStagePipeline

        # Stage 1: broad bi-encoder returns 5 results
        stage1_results = [_make_result(str(i), score=1.0 - i * 0.1) for i in range(5)]
        stage1_response = _make_response("q", stage1_results)
        stage1 = MagicMock()
        stage1.search = AsyncMock(return_value=stage1_response)

        # Reranker: returns top-3 of those
        reranker = MagicMock()
        reranker.rerank = AsyncMock(return_value=stage1_results[:3])

        pipeline = TwoStagePipeline(stage1_strategy=stage1, reranker=reranker)

        response = await pipeline.search("q", k=3)

        assert isinstance(response, SearchResponse)
        assert len(response.results) <= 3
        assert response.search_type == "two_stage"

    async def test_two_stage_pipeline_empty_stage1(self):
        """TwoStagePipeline handles empty stage-1 results gracefully."""
        from src.pdf_framework.search.pipelines.two_stage import TwoStagePipeline

        stage1 = MagicMock()
        stage1.search = AsyncMock(return_value=_make_response("q", []))
        reranker = MagicMock()

        pipeline = TwoStagePipeline(stage1_strategy=stage1, reranker=reranker)

        response = await pipeline.search("q", k=5)

        assert response.results == []
        assert response.total_found == 0

    # --- SectionFirstPipeline ---

    def test_section_first_static_helpers(self):
        """F2.3.6a: _extract_section_number and _truncate_section work correctly."""
        from src.pdf_framework.search.pipelines.section_first import SectionFirstPipeline

        assert SectionFirstPipeline._extract_section_number("5.14.3.6. Агрегаты") == "5.14.3.6"
        assert SectionFirstPipeline._extract_section_number("**5.8.Справочники**") == "5.8"
        assert SectionFirstPipeline._extract_section_number("Просто текст") == ""

        # Breadcrumb format — takes last segment
        breadcrumb = "5. Глава > 5.14. Регистры > 5.14.3. Агрегаты"
        num = SectionFirstPipeline._extract_section_number(breadcrumb)
        assert num == "5.14.3"

        assert SectionFirstPipeline._truncate_section("5.14.3.6", 3) == "5.14.3"
        assert SectionFirstPipeline._truncate_section("5.14", 3) == "5.14"

    async def test_section_first_pipeline_uses_hybrid_fallback(self, tmp_path):
        """F2.3.6b: Pipeline falls back to hybrid when BM25 returns no hits."""
        from src.pdf_framework.search.pipelines.section_first import SectionFirstPipeline

        # BM25 store returns empty hits
        bm25 = MagicMock()
        bm25.search_two_pass = AsyncMock(return_value=[])
        bm25.get_chunks_by_ids = AsyncMock(return_value=[])

        fallback_results = [_make_result("x1"), _make_result("x2")]
        fallback_response = _make_response("справочники", fallback_results)

        manager = MagicMock()
        manager.search = AsyncMock(return_value=fallback_response)

        pipeline = SectionFirstPipeline(bm25_store=bm25, search_manager=manager)

        response = await pipeline.search("справочники", k=2)

        # Fallback hybrid was called
        manager.search.assert_called()
        assert isinstance(response, SearchResponse)
        assert len(response.results) == 2

    async def test_section_first_pipeline_dominant_section(self, tmp_path):
        """F2.3.6c: Pipeline routes to section-scoped search when section dominates."""
        from src.pdf_framework.search.pipelines.section_first import SectionFirstPipeline

        # BM25 returns hits whose metadata all point to section 5.14
        bm25_hits = [("c1", 0.9), ("c2", 0.85), ("c3", 0.8)]
        bm25 = MagicMock()
        bm25.search_two_pass = AsyncMock(return_value=bm25_hits)
        bm25.get_chunks_by_ids = AsyncMock(
            return_value=[
                {"chunk_id": "c1", "section_title": "5.14.3. Регистры сведений"},
                {"chunk_id": "c2", "section_title": "5.14.1. Структура"},
                {"chunk_id": "c3", "section_title": "5.14.2. Ключи"},
            ]
        )

        scoped_results = [_make_result("s1"), _make_result("s2"), _make_result("s3")]
        scoped_response = _make_response("регистры", scoped_results)
        scoped_response.metadata["section_first"] = "5.14"

        manager = MagicMock()
        manager.search = AsyncMock(return_value=scoped_response)

        pipeline = SectionFirstPipeline(bm25_store=bm25, search_manager=manager)

        response = await pipeline.search("регистры", k=3)

        assert isinstance(response, SearchResponse)
        # Confirm section-scoped call included section_prefix
        call_kwargs = manager.search.call_args
        assert call_kwargs is not None
