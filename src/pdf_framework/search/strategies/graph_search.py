"""Graph search strategy: search entities → retrieve related chunks."""

import time
from typing import Any

from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.schemas.documents import (
    SearchResponse,
    SearchResult,
)
from src.pdf_framework.vector_store.base import BaseVectorStore


class GraphSearchStrategy:
    """Search by finding entities in the graph and retrieving related document chunks."""

    def __init__(
        self,
        graph_store: BaseGraphStore,
        vector_store: BaseVectorStore,
    ):
        self._graph_store = graph_store
        self._vector_store = vector_store

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        depth: int = 1,
    ) -> SearchResponse:
        """Search entities by name, then retrieve their source chunks."""
        start = time.perf_counter()

        # Find matching entities
        entities = await self._graph_store.find_entities(name=query, limit=k)

        # Collect all source chunk IDs from matching entities and their neighbors
        chunk_ids: set[str] = set()
        for entity in entities:
            chunk_ids.update(entity.source_chunk_ids)
            if depth > 0:
                subgraph = await self._graph_store.get_neighbors(
                    entity.id, depth=depth
                )
                for neighbor in subgraph.entities:
                    chunk_ids.update(neighbor.source_chunk_ids)

        # Retrieve chunks from vector store
        results: list[SearchResult] = []
        if chunk_ids:
            chunks = await self._vector_store.get_by_ids(list(chunk_ids)[:k * 3])
            for chunk in chunks[:k]:
                results.append(
                    SearchResult(
                        chunk=chunk,
                        score=1.0,  # Graph results don't have a natural similarity score
                        source="graph",
                    )
                )

        elapsed = (time.perf_counter() - start) * 1000
        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            search_type="graph",
            elapsed_ms=elapsed,
        )
