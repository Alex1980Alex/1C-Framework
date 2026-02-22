"""Hybrid search strategy: merge vector + graph + BM25 results via Reciprocal Rank Fusion."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TYPE_CHECKING

from src.pdf_framework.config import SearchSettings
from src.pdf_framework.schemas.documents import SearchResponse, SearchResult
from src.pdf_framework.search.strategies.graph_search import GraphSearchStrategy
from src.pdf_framework.search.strategies.vector_search import VectorSearchStrategy

if TYPE_CHECKING:
    from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
    from src.pdf_framework.search.strategies.bm25_search import BM25SearchStrategy
    from src.pdf_framework.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class HybridSearchStrategy:
    """Combine vector, graph, and BM25 search results using RRF.

    Phase 1.2: Supports configurable weights via SearchSettings.
    Phase 16: Adds BM25 lexical search as third source.
    Phase 24: Qdrant native BM25 — server-side dense+sparse RRF.
    """

    def __init__(
        self,
        vector_strategy: VectorSearchStrategy,
        graph_strategy: GraphSearchStrategy,
        search_settings: SearchSettings | None = None,
        vector_weight: float | None = None,
        graph_weight: float | None = None,
        rrf_k: int | None = None,
        bm25_strategy: BM25SearchStrategy | None = None,
        bm25_weight: float | None = None,
        vector_store: BaseVectorStore | None = None,
        embedding_engine: BaseEmbeddingEngine | None = None,
    ):
        self._vector = vector_strategy
        self._graph = graph_strategy
        self._bm25 = bm25_strategy

        # Direct references for native BM25 path
        self._vector_store = vector_store
        self._embedding_engine = embedding_engine

        # Use settings from config if provided, otherwise use defaults
        self._settings = search_settings or SearchSettings()
        self._vector_weight = vector_weight if vector_weight is not None else self._settings.hybrid_vector_weight
        self._graph_weight = graph_weight if graph_weight is not None else self._settings.hybrid_graph_weight
        self._rrf_k = rrf_k if rrf_k is not None else self._settings.hybrid_rrf_k
        self._bm25_weight = bm25_weight if bm25_weight is not None else self._settings.bm25_weight

    def _use_native_bm25(self) -> bool:
        """Check if we should use Qdrant native BM25 (dense+sparse RRF)."""
        backend = getattr(self._settings, "bm25_backend", "fts5")
        if backend not in ("qdrant", "both"):
            return False
        if self._vector_store is None or self._embedding_engine is None:
            return False
        return self._vector_store.supports_native_bm25()

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute search — native Qdrant BM25 path or classic parallel path."""
        _ = kwargs  # reserved for future strategy-specific params
        start = time.perf_counter()

        if self._use_native_bm25():
            merged = await self._search_native_bm25(query, k, filter)
        else:
            merged = await self._search_classic(query, k, filter)

        elapsed = (time.perf_counter() - start) * 1000
        return SearchResponse(
            query=query,
            results=merged,
            total_found=len(merged),
            search_type="hybrid",
            elapsed_ms=elapsed,
        )

    async def _search_native_bm25(
        self,
        query: str,
        k: int,
        filter: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Qdrant server-side dense+BM25 RRF, plus graph results merged client-side."""
        assert self._embedding_engine is not None, "embedding_engine required for native BM25"
        assert self._vector_store is not None, "vector_store required for native BM25"

        # Embed query for Qdrant hybrid
        query_embedding = await self._embedding_engine.embed_text(query)

        # Run Qdrant hybrid (dense+BM25) + graph in parallel
        tasks = [
            self._vector_store.hybrid_search(
                query_embedding=query_embedding,
                query_text=query,
                k=k * 2,
                filter=filter,
            ),
            self._graph.search(query=query, k=k, filter=filter),
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        raw_qdrant = responses[0]
        raw_graph = responses[1]

        if isinstance(raw_qdrant, BaseException):
            logger.warning("[HYBRID] Qdrant native BM25 failed: %s", raw_qdrant)
            qdrant_results: list[SearchResult] = []
        else:
            qdrant_results = raw_qdrant

        if isinstance(raw_graph, BaseException):
            logger.warning("[HYBRID] Graph search failed: %s", raw_graph)
            graph_results: list[SearchResult] = []
        else:
            graph_results = raw_graph.results

        # Merge Qdrant hybrid + graph via client-side RRF
        # Qdrant hybrid results already have dense+BM25 fused, so treat as one source
        qdrant_bm25_weight = self._vector_weight + self._bm25_weight

        scores: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}

        for rank, result in enumerate(qdrant_results):
            chunk_id = result.chunk.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + qdrant_bm25_weight / (
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
            SearchResult(chunk=result_map[cid].chunk, score=scores[cid], source="hybrid")
            for cid in sorted_ids
        ]

    async def _search_classic(
        self,
        query: str,
        k: int,
        filter: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Classic parallel vector + BM25 (FTS5) + graph with client-side RRF."""
        tasks = [
            self._vector.search(query=query, k=k, filter=filter),
            self._graph.search(query=query, k=k, filter=filter),
        ]
        if self._bm25 is not None:
            tasks.append(self._bm25.search(query=query, k=k, filter=filter))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        vector_results = responses[0].results if not isinstance(responses[0], Exception) else []
        graph_results = responses[1].results if not isinstance(responses[1], Exception) else []
        bm25_results = []
        if self._bm25 is not None and len(responses) > 2:
            if not isinstance(responses[2], Exception):
                bm25_results = responses[2].results
            else:
                logger.warning("[HYBRID] BM25 search failed: %s", responses[2])

        return self._rrf_merge(
            vector_results=vector_results,
            graph_results=graph_results,
            bm25_results=bm25_results,
            k=k,
        )

    def _rrf_merge(
        self,
        vector_results: list[SearchResult],
        graph_results: list[SearchResult],
        bm25_results: list[SearchResult] | None = None,
        k: int = 5,
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion merge across all sources."""
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

        # Phase 16: BM25 contribution
        if bm25_results:
            for rank, result in enumerate(bm25_results):
                chunk_id = result.chunk.id
                scores[chunk_id] = scores.get(chunk_id, 0.0) + self._bm25_weight / (
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
