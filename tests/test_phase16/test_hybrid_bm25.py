"""Phase 16: Hybrid Search Strategy with BM25 integration tests.

Tests RRF merge with vector + graph + BM25 (three-way fusion).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.config import SearchSettings
from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)
from src.pdf_framework.search.strategies.hybrid_search import HybridSearchStrategy


def _make_result(chunk_id: str, score: float, source: str = "vector") -> SearchResult:
    return SearchResult(
        chunk=DocumentChunk(id=chunk_id, content=f"Content of {chunk_id}", document_id="d1"),
        score=score,
        source=source,
    )


def _make_response(results: list[SearchResult], search_type: str = "vector") -> SearchResponse:
    return SearchResponse(
        query="test", results=results, total_found=len(results), search_type=search_type,
    )


def _make_strategy(results: list[SearchResult]):
    s = AsyncMock()
    s.search = AsyncMock(return_value=_make_response(results))
    return s


class TestHybridWithBM25:
    @pytest.mark.asyncio
    async def test_three_way_merge(self):
        vector = _make_strategy([_make_result("v1", 0.9), _make_result("v2", 0.7)])
        graph = _make_strategy([_make_result("g1", 0.8), _make_result("v1", 0.6)])
        bm25 = _make_strategy([_make_result("b1", 1.0), _make_result("v1", 0.95)])

        settings = SearchSettings(
            hybrid_vector_weight=0.5,
            hybrid_graph_weight=0.2,
            bm25_weight=0.3,
            hybrid_rrf_k=60,
        )

        hybrid = HybridSearchStrategy(
            vector, graph, search_settings=settings, bm25_strategy=bm25,
        )

        response = await hybrid.search("test", k=5)

        assert response.search_type == "hybrid"
        ids = [r.chunk.id for r in response.results]
        # v1 appears in all three sources — should rank highest
        assert ids[0] == "v1"

    @pytest.mark.asyncio
    async def test_without_bm25(self):
        vector = _make_strategy([_make_result("v1", 0.9)])
        graph = _make_strategy([_make_result("g1", 0.8)])

        hybrid = HybridSearchStrategy(vector, graph, bm25_strategy=None)
        response = await hybrid.search("test", k=5)

        assert len(response.results) == 2

    @pytest.mark.asyncio
    async def test_bm25_failure_graceful(self):
        vector = _make_strategy([_make_result("v1", 0.9)])
        graph = _make_strategy([_make_result("g1", 0.8)])
        bm25 = AsyncMock()
        bm25.search = AsyncMock(side_effect=RuntimeError("BM25 error"))

        hybrid = HybridSearchStrategy(vector, graph, bm25_strategy=bm25)
        response = await hybrid.search("test", k=5)

        # Should still return vector + graph results
        assert len(response.results) >= 1

    @pytest.mark.asyncio
    async def test_rrf_scores_decrease_by_rank(self):
        vector = _make_strategy([
            _make_result("v1", 0.9),
            _make_result("v2", 0.7),
            _make_result("v3", 0.5),
        ])
        graph = _make_strategy([])
        hybrid = HybridSearchStrategy(vector, graph, bm25_strategy=None)

        response = await hybrid.search("test", k=5)

        scores = [r.score for r in response.results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_k_limits_output(self):
        results = [_make_result(f"v{i}", 1.0 - i * 0.1) for i in range(10)]
        vector = _make_strategy(results)
        graph = _make_strategy([])
        hybrid = HybridSearchStrategy(vector, graph)

        response = await hybrid.search("test", k=3)
        assert len(response.results) <= 3


class TestRRFMerge:
    def test_deduplication(self):
        """Same chunk from multiple sources should appear once."""
        vector = [_make_result("shared", 0.9, "vector")]
        graph = [_make_result("shared", 0.8, "graph")]
        bm25 = [_make_result("shared", 1.0, "bm25")]

        settings = SearchSettings(
            hybrid_vector_weight=0.5,
            hybrid_graph_weight=0.2,
            bm25_weight=0.3,
        )
        hybrid = HybridSearchStrategy(
            AsyncMock(), AsyncMock(), search_settings=settings,
        )
        merged = hybrid._rrf_merge(vector, graph, bm25, k=5)

        assert len(merged) == 1
        assert merged[0].chunk.id == "shared"
        assert merged[0].source == "hybrid"

    def test_empty_all_sources(self):
        hybrid = HybridSearchStrategy(AsyncMock(), AsyncMock())
        merged = hybrid._rrf_merge([], [], [], k=5)
        assert merged == []

    def test_weights_affect_ranking(self):
        """BM25-only result with high weight should beat vector-only with low weight."""
        vector = [_make_result("v_only", 0.9)]
        bm25 = [_make_result("b_only", 1.0)]

        settings = SearchSettings(
            hybrid_vector_weight=0.1,
            hybrid_graph_weight=0.0,
            bm25_weight=0.9,
        )
        hybrid = HybridSearchStrategy(
            AsyncMock(), AsyncMock(), search_settings=settings,
        )
        merged = hybrid._rrf_merge(vector, [], bm25, k=5)

        assert merged[0].chunk.id == "b_only"
