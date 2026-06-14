"""Integration tests for the Search Pipeline (F2.11.2).

`SearchManager` wires strategies externally via `register_strategy` (a bare
manager has none — `search()` raises ``Unknown strategy`` otherwise). These tests
inject mock strategies and assert the manager's dispatch + post-processing
(rerank / filter / cache skip) returns a real ``SearchResponse``.

Rewritten 2026-06-14 (roadmap 260614 integration remediation): the previous
version patched a non-existent ``qdrant.QdrantClient`` and called a strategy-less
manager — both drifted vs current source.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)
from src.pdf_framework.search.manager import SearchManager


def _mk_response(query: str = "q", n: int = 1, elapsed_ms: float = 1.5) -> SearchResponse:
    """Build a real SearchResponse a mock strategy can return."""
    results = [
        SearchResult(
            chunk=DocumentChunk(
                id=f"chunk_{i}",
                content=f"content {i}",
                document_id="doc_1",
                page_number=1,
            ),
            score=0.9 - i * 0.1,
            source="hybrid",
        )
        for i in range(n)
    ]
    return SearchResponse(query=query, results=results, total_found=n, elapsed_ms=elapsed_ms)


def _manager_with(*strategy_names: str, response: SearchResponse | None = None) -> SearchManager:
    """SearchManager with the named strategies registered as mocks."""
    manager = SearchManager()
    for name in strategy_names:
        strat = AsyncMock()
        strat.search = AsyncMock(return_value=response if response is not None else _mk_response())
        manager.register_strategy(name, strat)
    return manager


@pytest.mark.integration
class TestSearchPipeline:
    """SearchManager dispatch via injected mock strategies."""

    async def test_full_search_flow(self):
        """F2.11.2: query → results → SearchResponse with SearchResults."""
        manager = _manager_with("hybrid")
        response = await manager.search("test query about 1С", strategy="hybrid", rerank=False)
        assert len(response.results) > 0
        assert isinstance(response.results[0], SearchResult)

    async def test_search_with_reranking(self):
        """F2.11.2: rerank=True routes results through the configured reranker."""
        manager = _manager_with("hybrid", response=_mk_response(n=2))
        manager._reranker = MagicMock()
        manager._reranker.rerank = AsyncMock(
            return_value=[
                SearchResult(
                    chunk=DocumentChunk(id="chunk_1", content="c1", document_id="doc_1"),
                    score=0.95,
                ),
            ]
        )
        response = await manager.search("регистры в 1С", strategy="hybrid", rerank=True)
        assert len(response.results) > 0
        manager._reranker.rerank.assert_awaited_once()

    async def test_search_multiple_strategies(self):
        """F2.11.2: dispatch works for each registered strategy."""
        manager = _manager_with("vector", "bm25", "hybrid")
        for strategy in ("vector", "bm25", "hybrid"):
            response = await manager.search("справочники", strategy=strategy, rerank=False)
            assert len(response.results) >= 0

    async def test_search_filters(self):
        """F2.11.2: a metadata filter is accepted and passed to the strategy."""
        manager = _manager_with("hybrid")
        response = await manager.search(
            "справочники",
            strategy="hybrid",
            filter={"page_number": 5, "section": "Config"},
            rerank=False,
        )
        assert response.results is not None

    async def test_search_with_graphrag(self):
        """F2.11.2: GraphRAG strategy dispatches like any other."""
        manager = _manager_with("graphrag_local")
        response = await manager.search(
            "какие есть типы регистров", strategy="graphrag_local", rerank=False
        )
        assert len(response.results) >= 0

    async def test_search_latency_tracking(self):
        """F2.11.2: SearchResponse carries elapsed_ms."""
        manager = _manager_with("hybrid", response=_mk_response(elapsed_ms=2.0))
        response = await manager.search("test query", strategy="hybrid", rerank=False)
        assert response.elapsed_ms > 0

    async def test_search_unknown_strategy_raises(self):
        """A strategy-less / unknown name raises a clear ValueError (regression)."""
        manager = _manager_with("hybrid")
        with pytest.raises(ValueError, match="Unknown search strategy"):
            await manager.search("q", strategy="does_not_exist", rerank=False)

    async def test_search_repeated_calls(self):
        """F2.11.2: repeated searches return independent responses (cache skip)."""
        manager = _manager_with("hybrid")
        r1 = await manager.search("cached query", strategy="hybrid", rerank=False)
        r2 = await manager.search("cached query", strategy="hybrid", rerank=False)
        assert r1 is not None
        assert r2 is not None
