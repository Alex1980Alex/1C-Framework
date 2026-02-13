"""RAPTOR Search Strategy (Phase 13.2).

Search across RAPTOR tree hierarchy with collapsed tree mode.

Author: Claude Code
Version: 1.4.0 - Phase 13.2: RAPTOR Search Strategy
"""

import time
import logging
from typing import Any

from pydantic import BaseModel

from src.pdf_framework.schemas.documents import SearchResult, SearchResponse

logger = logging.getLogger(__name__)


class RAPTORSearchConfig(BaseModel):
    """RAPTOR search configuration."""

    search_mode: str = "collapsed"  # collapsed or tree_traversal
    top_k_per_level: int = 5  # For collapsed mode
    max_depth: int = 4
    include_leaves: bool = True
    include_summaries: bool = True


class RAPTORSearchStrategy:
    """
    Search strategy for RAPTOR trees.

    Two modes:
    - collapsed: Search all levels simultaneously (simpler, effective)
    - tree_traversal: Top-down traversal through tree hierarchy
    """

    def __init__(
        self,
        vector_store,
        config: RAPTORSearchConfig | None = None,
    ):
        """
        Initialize RAPTOR search strategy.

        Args:
            vector_store: Vector store for embedding search
            config: RAPTOR search configuration
        """
        self._vector_store = vector_store
        self._config = config or RAPTORSearchConfig()

    async def search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs,
    ) -> SearchResponse:
        """
        Search RAPTOR tree for relevant nodes.

        Args:
            query: Search query
            query_embedding: Pre-computed query embedding
            k: Number of results to return
            filter: Metadata filter (will include raptor_level)
            **kwargs: Additional search parameters

        Returns:
            SearchResponse with mixed leaf and summary results
        """
        if self._config.search_mode == "collapsed":
            return await self._collapsed_tree_search(query, query_embedding, k, filter)
        else:
            return await self._tree_traversal_search(query, query_embedding, k, filter)

    async def _collapsed_tree_search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> SearchResponse:
        """
        Search all tree levels simultaneously (collapsed mode).

        This is simpler and often more effective than traversal.
        """
        start = time.perf_counter()

        if query_embedding is None:
            logger.warning("[RAPTOR] No query_embedding provided, cannot search")
            return SearchResponse(
                query=query,
                results=[],
                total_found=0,
                search_type="raptor_collapsed",
            )

        # Build filter for RAPTOR nodes
        raptor_filter = dict(filter) if filter else {}
        raptor_filter["raptor_node"] = True  # Filter for RAPTOR indexed nodes

        # Search in vector store (all levels in same collection)
        # BaseVectorStore.search(query_embedding, k, filter) -> list[SearchResult]
        results = await self._vector_store.search(
            query_embedding=query_embedding,
            k=k * 2,  # Fetch more to filter/reweight
            filter=raptor_filter,
        )

        # Apply level weighting
        search_results = []
        for result in results:
            # Extract raptor_level from metadata
            raptor_level = result.chunk.metadata.get("raptor_level", 0)

            # Create new SearchResult with weighted score
            search_result = SearchResult(
                chunk=result.chunk,
                score=result.score * self._level_weight(raptor_level),
                source=result.chunk.metadata.get("source", "raptor"),
            )
            search_results.append(search_result)

        # Sort by weighted score and take top-k
        search_results.sort(key=lambda r: r.score, reverse=True)
        search_results = search_results[:k]

        elapsed = (time.perf_counter() - start) * 1000

        # Build response
        response = SearchResponse(
            query=query,
            results=search_results,
            search_type="raptor_collapsed",
            total_found=len(search_results),
            elapsed_ms=elapsed,
        )

        logger.info(
            f"[RAPTOR] Collapsed search: {len(search_results)} results "
            f"(mix of summaries and leaves)"
        )

        return response

    async def _tree_traversal_search(
        self,
        query: str,
        query_embedding: list[float] | None,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> SearchResponse:
        """
        Top-down tree traversal search.

        Start from top-level summaries, drill down to leaves as needed.
        """
        # TODO: Implement tree traversal in future iteration
        # For now, fall back to collapsed mode
        logger.warning("[RAPTOR] Tree traversal not yet implemented, using collapsed mode")
        return await self._collapsed_tree_search(query, query_embedding, k, filter)

    def _level_weight(self, level: int) -> float:
        """
        Calculate weight for tree level.

        Higher levels (summaries) get higher weight for broad queries.
        Lower levels (leaves) get weight for specific queries.
        """
        # Simple linear weighting: level 0 = 1.0, level 1 = 1.1, etc.
        return 1.0 + (level * 0.1)


def create_raptor_search_strategy(
    vector_store,
    config: RAPTORSearchConfig | None = None,
) -> RAPTORSearchStrategy:
    """Factory function to create RAPTOR search strategy."""
    return RAPTORSearchStrategy(
        vector_store=vector_store,
        config=config,
    )
