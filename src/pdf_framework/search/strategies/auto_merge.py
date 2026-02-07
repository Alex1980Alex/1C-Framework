"""Auto-Merging search strategy for parent-child retrieval.

Searches on child chunks but merges to parent chunks when multiple
children from the same parent are retrieved.

Author: Claude Code
Version: 0.8.0 - Phase 7.3: Auto-Merging Strategy
"""

import logging
import time
from collections import defaultdict
from typing import Any

from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.schemas.documents import SearchResponse, SearchResult
from src.pdf_framework.vector_store.base import BaseVectorStore
from src.pdf_framework.vector_store.parent_store import ParentDocumentStore

logger = logging.getLogger(__name__)


class AutoMergeStrategy:
    """
    Auto-merging search strategy for parent-child document retrieval.

    Strategy:
    1. Search child chunks (fetch more than k for merging)
    2. Group results by parent_id
    3. If group size >= threshold → return parent chunk
    4. Otherwise → return individual child chunks
    5. Sort by score and return top-k
    """

    def __init__(
        self,
        embedding_engine: BaseEmbeddingEngine,
        vector_store: BaseVectorStore,
        parent_store: ParentDocumentStore,
        merge_threshold: int = 3,
        fetch_multiplier: float = 3.0,
    ):
        """
        Initialize auto-merge strategy.

        Args:
            embedding_engine: For query embedding
            vector_store: For child chunk search (with embeddings)
            parent_store: For retrieving parent chunks
            merge_threshold: Minimum children from same parent to trigger merge
            fetch_multiplier: Multiplier for initial fetch (k * multiplier)
        """
        self._embedding = embedding_engine
        self._vector_store = vector_store
        self._parent_store = parent_store
        self._threshold = merge_threshold
        self._fetch_multiplier = fetch_multiplier

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs,
    ) -> SearchResponse:
        """
        Perform search with automatic parent-child merging.

        Args:
            query: Search query
            k: Number of final results to return
            filter: Optional metadata filters
            **kwargs: Additional parameters

        Returns:
            SearchResponse with merged results
        """
        start = time.perf_counter()

        # Step 1: Search child chunks (fetch more for merging)
        fetch_k = int(k * self._fetch_multiplier)

        query_embedding = await self._embedding.embed_text(query)
        child_results = await self._vector_store.search(
            query_embedding=query_embedding,
            k=fetch_k,
            filter=filter,
        )

        logger.info(
            f"[AUTO_MERGE] Fetched {len(child_results)} child chunks "
            f"(target k={k}, fetch_k={fetch_k})"
        )

        # Step 2: Group by parent_id
        groups = defaultdict(list)
        orphan_children = []

        for result in child_results:
            parent_id = result.chunk.metadata.get("parent_id")
            if parent_id:
                groups[parent_id].append(result)
            else:
                orphan_children.append(result)

        logger.info(
            f"[AUTO_MERGE] Grouped into {len(groups)} parent groups, "
            f"{len(orphan_children)} orphans"
        )

        # Step 3: Merge or keep children
        merged_results = []

        # Process each parent group
        for parent_id, children in groups.items():
            group_size = len(children)

            if group_size >= self._threshold:
                # Merge to parent chunk
                parent = await self._parent_store.get_parent(parent_id)

                if parent:
                    # Score = max of children scores
                    max_score = max(c.score for c in children)

                    merged_results.append(
                        SearchResult(
                            chunk=parent,
                            score=max_score,
                            source="auto_merge_parent",
                            highlights=[f"Merged from {group_size} children"],
                        )
                    )

                    logger.debug(
                        f"[AUTO_MERGE] Merged {group_size} children from {parent_id} "
                        f"(score={max_score:.3f})"
                    )
                else:
                    # Parent not found, keep children
                    merged_results.extend(children)
                    logger.warning(f"[AUTO_MERGE] Parent {parent_id} not found, keeping {group_size} children")
            else:
                # Below threshold, keep individual children
                merged_results.extend(children)

        # Add orphan children (no parent_id)
        merged_results.extend(orphan_children)

        # Step 4: Sort by score and trim to k
        merged_results.sort(key=lambda r: r.score, reverse=True)
        final_results = merged_results[:k]

        # Calculate statistics
        parent_count = sum(
            1 for r in final_results if r.chunk.metadata.get("chunk_type") == "parent"
        )
        child_count = len(final_results) - parent_count

        elapsed = (time.perf_counter() - start) * 1000

        logger.info(
            f"[AUTO_MERGE] Returning {parent_count} parents, {child_count} children "
            f"({elapsed:.0f}ms)"
        )

        return SearchResponse(
            query=query,
            results=final_results,
            total_found=len(final_results),
            search_type="auto_merge",
            elapsed_ms=elapsed,
        )

    async def get_merge_statistics(
        self,
        results: list[SearchResult],
    ) -> dict[str, Any]:
        """
        Get statistics about merge results.

        Args:
            results: Search results from auto_merge

        Returns:
            Statistics dictionary
        """
        parent_count = 0
        child_count = 0
        merged_children = 0
        parent_ids = set()

        for result in results:
            chunk_type = result.chunk.metadata.get("chunk_type", "")

            if chunk_type == "parent":
                parent_count += 1
                child_count_in_parent = result.chunk.metadata.get("child_count", 0)
                merged_children += child_count_in_parent
                parent_ids.add(result.chunk.id)
            else:
                child_count += 1
                parent_id = result.chunk.metadata.get("parent_id")
                if parent_id:
                    parent_ids.add(parent_id)

        return {
            "parent_chunks": parent_count,
            "child_chunks": child_count,
            "total_chunks": parent_count + child_count,
            "merged_into_parents": merged_children,
            "unique_parents": len(parent_ids),
            "merge_ratio": merged_children / len(results) if results else 0,
        }
