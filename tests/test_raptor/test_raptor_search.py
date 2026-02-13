"""Tests for RAPTOR Search Strategy (Phase 13.2)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.search.strategies.raptor_search import (
    RAPTORSearchConfig,
    RAPTORSearchStrategy,
    create_raptor_search_strategy,
)
from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResult,
    SearchResponse,
)


# ---------------------------------------------------------------------------
# RAPTORSearchConfig
# ---------------------------------------------------------------------------

class TestRAPTORSearchConfig:
    def test_defaults(self):
        config = RAPTORSearchConfig()
        assert config.search_mode == "collapsed"
        assert config.top_k_per_level == 5
        assert config.max_depth == 4
        assert config.include_leaves is True
        assert config.include_summaries is True

    def test_custom(self):
        config = RAPTORSearchConfig(
            search_mode="tree_traversal",
            top_k_per_level=10,
            max_depth=2,
        )
        assert config.search_mode == "tree_traversal"
        assert config.top_k_per_level == 10


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_search_result(chunk_id: str, score: float, raptor_level: int = 0):
    chunk = DocumentChunk(
        id=chunk_id,
        content=f"Content of {chunk_id}",
        document_id="doc1",
        metadata={
            "raptor_node": True,
            "raptor_level": raptor_level,
            "source": "raptor",
        },
    )
    return SearchResult(chunk=chunk, score=score, source="raptor")


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[
        _make_search_result("leaf_0", 0.9, raptor_level=0),
        _make_search_result("leaf_1", 0.8, raptor_level=0),
        _make_search_result("summary_0", 0.7, raptor_level=1),
        _make_search_result("summary_1", 0.6, raptor_level=2),
    ])
    return store


# ---------------------------------------------------------------------------
# RAPTORSearchStrategy
# ---------------------------------------------------------------------------

class TestRAPTORSearchStrategy:
    def test_init_defaults(self, mock_vector_store):
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        assert strategy._config.search_mode == "collapsed"

    def test_init_custom_config(self, mock_vector_store):
        config = RAPTORSearchConfig(search_mode="tree_traversal")
        strategy = RAPTORSearchStrategy(
            vector_store=mock_vector_store, config=config,
        )
        assert strategy._config.search_mode == "tree_traversal"

    @pytest.mark.asyncio
    async def test_search_collapsed_mode(self, mock_vector_store):
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        embedding = [0.1] * 384

        response = await strategy.search(
            query="test query",
            query_embedding=embedding,
            k=3,
        )

        assert isinstance(response, SearchResponse)
        assert response.search_type == "raptor_collapsed"
        assert len(response.results) <= 3
        mock_vector_store.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_with_filter(self, mock_vector_store):
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        embedding = [0.1] * 384

        await strategy.search(
            query="test",
            query_embedding=embedding,
            k=5,
            filter={"doc_type": "manual"},
        )

        call_kwargs = mock_vector_store.search.call_args[1]
        assert call_kwargs["filter"]["doc_type"] == "manual"
        assert call_kwargs["filter"]["raptor_node"] is True

    @pytest.mark.asyncio
    async def test_search_no_embedding_returns_empty(self, mock_vector_store):
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)

        response = await strategy.search(query="test", query_embedding=None, k=5)

        assert response.results == []
        assert response.total_found == 0
        mock_vector_store.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_level_weighting_applied(self, mock_vector_store):
        """Higher-level nodes get score boost."""
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        embedding = [0.1] * 384

        response = await strategy.search(
            query="test",
            query_embedding=embedding,
            k=10,
        )

        # summary_1 at level 2 with score 0.6 should get weight 1.2 → 0.72
        # leaf_0 at level 0 with score 0.9 should get weight 1.0 → 0.9
        scores = {r.chunk.id: r.score for r in response.results}
        assert scores["leaf_0"] == pytest.approx(0.9, abs=0.01)  # 0.9 * 1.0
        assert scores["summary_0"] == pytest.approx(0.77, abs=0.01)  # 0.7 * 1.1
        assert scores["summary_1"] == pytest.approx(0.72, abs=0.01)  # 0.6 * 1.2

    @pytest.mark.asyncio
    async def test_results_sorted_by_score(self, mock_vector_store):
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        embedding = [0.1] * 384

        response = await strategy.search(query="test", query_embedding=embedding, k=10)

        scores = [r.score for r in response.results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_results_limited_to_k(self, mock_vector_store):
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        embedding = [0.1] * 384

        response = await strategy.search(query="test", query_embedding=embedding, k=2)

        assert len(response.results) <= 2

    @pytest.mark.asyncio
    async def test_fetch_k_is_double(self, mock_vector_store):
        """Should fetch k*2 from vector store for reweighting."""
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        embedding = [0.1] * 384

        await strategy.search(query="test", query_embedding=embedding, k=3)

        call_kwargs = mock_vector_store.search.call_args[1]
        assert call_kwargs["k"] == 6  # 3 * 2

    @pytest.mark.asyncio
    async def test_tree_traversal_falls_back(self, mock_vector_store):
        """tree_traversal mode falls back to collapsed."""
        config = RAPTORSearchConfig(search_mode="tree_traversal")
        strategy = RAPTORSearchStrategy(
            vector_store=mock_vector_store, config=config,
        )
        embedding = [0.1] * 384

        response = await strategy.search(
            query="test", query_embedding=embedding, k=3,
        )

        assert isinstance(response, SearchResponse)
        mock_vector_store.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_elapsed_ms_tracked(self, mock_vector_store):
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        embedding = [0.1] * 384

        response = await strategy.search(query="test", query_embedding=embedding, k=3)

        assert response.elapsed_ms >= 0

    @pytest.mark.asyncio
    async def test_empty_store_results(self, mock_vector_store):
        mock_vector_store.search = AsyncMock(return_value=[])
        strategy = RAPTORSearchStrategy(vector_store=mock_vector_store)
        embedding = [0.1] * 384

        response = await strategy.search(query="test", query_embedding=embedding, k=5)

        assert response.results == []
        assert response.total_found == 0


# ---------------------------------------------------------------------------
# _level_weight
# ---------------------------------------------------------------------------

class TestLevelWeight:
    def test_level_0(self):
        strategy = RAPTORSearchStrategy(vector_store=MagicMock())
        assert strategy._level_weight(0) == 1.0

    def test_level_1(self):
        strategy = RAPTORSearchStrategy(vector_store=MagicMock())
        assert strategy._level_weight(1) == pytest.approx(1.1)

    def test_level_3(self):
        strategy = RAPTORSearchStrategy(vector_store=MagicMock())
        assert strategy._level_weight(3) == pytest.approx(1.3)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_create_raptor_search_strategy(self):
        store = MagicMock()
        strategy = create_raptor_search_strategy(vector_store=store)
        assert isinstance(strategy, RAPTORSearchStrategy)

    def test_create_with_config(self):
        store = MagicMock()
        config = RAPTORSearchConfig(search_mode="tree_traversal")
        strategy = create_raptor_search_strategy(vector_store=store, config=config)
        assert strategy._config.search_mode == "tree_traversal"
