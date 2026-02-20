"""Visual Search Strategy for ColPali Retrieval (Phase 55).

Search strategy using visual embeddings for table/chart/diagram queries.
Combines ColPali visual similarity with Qdrant vector store.

Author: Claude Code
Version: 1.0.0 - Phase 55: ColPali Visual Retrieval
"""

import logging
import time
from typing import Any

from src.pdf_framework.embeddings.providers.colpali import ColPaliProvider
from src.pdf_framework.schemas.documents import SearchResponse
from src.pdf_framework.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class VisualSearchStrategy:
    """Search strategy using visual embeddings.

    Workflow:
        1. Embed query using ColPali (text → multi-vector)
        2. Mean pool to single 128-dim vector
        3. Search visual_pages collection in Qdrant
        4. Return page image references with scores

    Example:
        >>> strategy = VisualSearchStrategy(colpali, vector_store)
        >>> response = await strategy.search("table with quarterly revenue")
        >>> for result in response.results:
        ...     print(f"Page {result.chunk.page_number}: {result.score}")
    """

    def __init__(
        self,
        colpali_provider: ColPaliProvider,
        vector_store: BaseVectorStore,
        visual_collection: str = "visual_pages",
    ):
        """Initialize visual search strategy.

        Args:
            colpali_provider: ColPali provider for query embedding
            vector_store: Qdrant vector store with visual collection
            visual_collection: Name of visual collection
        """
        self._colpali = colpali_provider
        self._vector_store = vector_store
        self._visual_collection = visual_collection

        logger.info(
            f"[VISUAL_SEARCH] Initialized with collection={visual_collection}"
        )

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        document_id: str | None = None,
    ) -> SearchResponse:
        """Search visual pages by query.

        Args:
            query: Text query (e.g., "table showing revenue")
            k: Number of results to return
            filter: Optional metadata filter
            document_id: Optional filter by document ID

        Returns:
            SearchResponse with visual page results
        """
        start = time.perf_counter()

        # Embed query using ColPali
        query_vectors = self._colpali.embed_query(query)

        # Mean pool multi-vector to single 128-dim vector
        import torch
        query_vector = query_vectors.mean(dim=0).cpu().tolist()

        # Build filter if document_id specified
        search_filter = filter or {}
        if document_id:
            search_filter["document_id"] = document_id

        # Search visual collection
        # Note: We use the visual_search method if available, otherwise fallback
        if hasattr(self._vector_store, "visual_search"):
            results = await self._vector_store.visual_search(
                query_embedding=query_vector,
                collection_name=self._visual_collection,
                k=k,
                filter=search_filter if search_filter else None,
            )
        else:
            # Fallback to regular search on visual collection
            results = await self._vector_store.search(
                query_embedding=query_vector,
                k=k,
                filter=search_filter if search_filter else None,
            )

        elapsed = (time.perf_counter() - start) * 1000

        logger.info(
            f"[VISUAL_SEARCH] Query: '{query[:50]}...' "
            f"Found {len(results)} results in {elapsed:.0f}ms"
        )

        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            search_type="visual",
            elapsed_ms=elapsed,
            metadata={
                "visual_collection": self._visual_collection,
                "query_type": "visual",
            },
        )

    async def hybrid_visual_text_search(
        self,
        query: str,
        text_embedding: list[float],
        k: int = 5,
        visual_weight: float = 0.5,
        text_weight: float = 0.5,
        document_id: str | None = None,
    ) -> SearchResponse:
        """Hybrid search combining visual and text results.

        Uses Reciprocal Rank Fusion (RRF) to combine results.

        Args:
            query: Text query
            text_embedding: Pre-computed text query embedding
            k: Number of results per strategy
            visual_weight: Weight for visual results (0-1)
            text_weight: Weight for text results (0-1)
            document_id: Optional document filter

        Returns:
            SearchResponse with fused results
        """
        start = time.perf_counter()

        # Get visual results
        visual_response = await self.search(
            query=query,
            k=k,
            document_id=document_id,
        )

        # Get text results
        text_results = await self._vector_store.search(
            query_embedding=text_embedding,
            k=k,
            filter={"document_id": document_id} if document_id else None,
        )

        # RRF fusion
        fused_results = self._rrf_fusion(
            visual_results=visual_response.results,
            text_results=text_results,
            visual_weight=visual_weight,
            text_weight=text_weight,
        )

        elapsed = (time.perf_counter() - start) * 1000

        return SearchResponse(
            query=query,
            results=fused_results[:k],
            total_found=len(fused_results),
            search_type="hybrid_visual_text",
            elapsed_ms=elapsed,
            metadata={
                "visual_count": len(visual_response.results),
                "text_count": len(text_results),
                "visual_weight": visual_weight,
                "text_weight": text_weight,
            },
        )

    def _rrf_fusion(
        self,
        visual_results: list[Any],
        text_results: list[Any],
        visual_weight: float = 0.5,
        text_weight: float = 0.5,
        k: int = 60,
    ) -> list[Any]:
        """Reciprocal Rank Fusion for combining result sets.

        RRF score = weight / (k + rank)

        Args:
            visual_results: Results from visual search
            text_results: Results from text search
            visual_weight: Weight for visual results
            text_weight: Weight for text results
            k: RRF constant (default 60)

        Returns:
            Fused and sorted results
        """
        from src.pdf_framework.schemas.documents import SearchResult

        scores: dict[str, float] = {}

        # Score visual results
        for rank, result in enumerate(visual_results, 1):
            chunk_id = result.chunk.id
            rrf_score = visual_weight / (k + rank)
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score

        # Score text results
        for rank, result in enumerate(text_results, 1):
            chunk_id = result.chunk.id
            rrf_score = text_weight / (k + rank)
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score

        # Create mapping of chunk_id to result objects
        result_map: dict[str, Any] = {}
        for result in visual_results + text_results:
            chunk_id = result.chunk.id
            if chunk_id not in result_map:
                result_map[chunk_id] = result

        # Sort by RRF score descending
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        # Build fused results
        fused = []
        for chunk_id in sorted_ids:
            result = result_map[chunk_id]
            # Update score with RRF score
            fused.append(SearchResult(
                chunk=result.chunk,
                score=scores[chunk_id],
                source=f"{result.source}_rrf",
            ))

        return fused


def create_visual_search_strategy(
    colpali_provider: ColPaliProvider,
    vector_store: BaseVectorStore,
    visual_collection: str = "visual_pages",
) -> VisualSearchStrategy:
    """Factory function to create visual search strategy.

    Args:
        colpali_provider: ColPali provider
        vector_store: Qdrant vector store
        visual_collection: Visual collection name

    Returns:
        Configured VisualSearchStrategy instance
    """
    return VisualSearchStrategy(
        colpali_provider=colpali_provider,
        vector_store=vector_store,
        visual_collection=visual_collection,
    )
