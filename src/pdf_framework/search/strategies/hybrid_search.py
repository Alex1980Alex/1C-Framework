"""Hybrid search strategy: merge vector + graph results via Reciprocal Rank Fusion."""

import time
from typing import Any

from src.pdf_framework.config import SearchSettings
from src.pdf_framework.schemas.documents import SearchResponse, SearchResult
from src.pdf_framework.search.strategies.graph_search import GraphSearchStrategy
from src.pdf_framework.search.strategies.vector_search import VectorSearchStrategy


class HybridSearchStrategy:
    """Combine vector and graph search results using RRF.

    Phase 1.2: Supports configurable weights via SearchSettings.
    """

    def __init__(
        self,
        vector_strategy: VectorSearchStrategy,
        graph_strategy: GraphSearchStrategy,
        search_settings: SearchSettings | None = None,
        vector_weight: float | None = None,
        graph_weight: float | None = None,
        rrf_k: int | None = None,
    ):
        self._vector = vector_strategy
        self._graph = graph_strategy

        # Use settings from config if provided, otherwise use defaults (Phase 1.2)
        settings = search_settings or SearchSettings()
        self._vector_weight = vector_weight if vector_weight is not None else settings.hybrid_vector_weight
        self._graph_weight = graph_weight if graph_weight is not None else settings.hybrid_graph_weight
        self._rrf_k = rrf_k if rrf_k is not None else settings.hybrid_rrf_k

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute both strategies and merge with RRF."""
        start = time.perf_counter()

        vector_response = await self._vector.search(query=query, k=k, filter=filter)
        graph_response = await self._graph.search(query=query, k=k, filter=filter)

        merged = self._rrf_merge(
            vector_results=vector_response.results,
            graph_results=graph_response.results,
            k=k,
        )

        elapsed = (time.perf_counter() - start) * 1000
        return SearchResponse(
            query=query,
            results=merged,
            total_found=len(merged),
            search_type="hybrid",
            elapsed_ms=elapsed,
        )

    def _rrf_merge(
        self,
        vector_results: list[SearchResult],
        graph_results: list[SearchResult],
        k: int,
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion merge."""
        scores: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}

        for rank, result in enumerate(vector_results):
            chunk_id = result.chunk.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + self._vector_weight / (
                self._rrf_k + rank + 1
            )
            result_map[chunk_id] = result

        for rank, result in enumerate(graph_results):
            chunk_id = result.chunk.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + self._graph_weight / (
                self._rrf_k + rank + 1
            )
            if chunk_id not in result_map:
                result_map[chunk_id] = result

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:k]

        return [
            SearchResult(
                chunk=result_map[cid].chunk,
                score=scores[cid],
                source="hybrid",
            )
            for cid in sorted_ids
        ]
