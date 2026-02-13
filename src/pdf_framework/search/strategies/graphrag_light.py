"""LightRAG Search Strategy (Phase 38).

Economical alternative to Full GraphRAG Global:
- Vector search over entity/relation embeddings (~100 tokens/query)
- vs. LLM map-reduce over community summaries (~5000 tokens/query)
- 50x cheaper, <500ms latency

Two-level retrieval:
- Low-level: entity matches → specific facts, direct relations
- High-level: relation matches → topic connections, conceptual links
"""

import logging
import time
from typing import Any

from src.pdf_framework.config import LightRAGSettings
from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)

logger = logging.getLogger(__name__)


class LightRAGStrategy:
    """LightRAG search: vector retrieval over graph entity/relation embeddings.

    Instead of expensive LLM calls (map-reduce), uses pre-computed
    entity/relation embeddings for fast graph-aware retrieval.
    """

    def __init__(
        self,
        embedding_engine: Any,
        vector_store: Any,
        graph_store: Any,
        entity_embeddings: Any,
        settings: LightRAGSettings | None = None,
    ):
        self._embedding_engine = embedding_engine
        self._vector_store = vector_store
        self._graph_store = graph_store
        self._entity_embeddings = entity_embeddings
        self._settings = settings or LightRAGSettings()

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Perform LightRAG search.

        1. Embed query
        2. Search entity embeddings → relevant entities
        3. Search relation embeddings → relevant relations
        4. Collect source chunk IDs from entities and relations
        5. Fetch and score those chunks
        6. Return top-k results

        Args:
            query: Search query.
            k: Number of results to return.
            filter: Optional metadata filters.

        Returns:
            SearchResponse with graph-enriched results.
        """
        start = time.perf_counter()

        # Step 1: Embed query
        query_embedding = await self._embedding_engine.embed_text(query)

        # Step 2+3: Search entities and relations in parallel
        import asyncio

        entity_task = self._entity_embeddings.search_entities(
            query_embedding=query_embedding,
            k=self._settings.entity_top_k,
            type_filter="entity",
        )
        relation_task = self._entity_embeddings.search_entities(
            query_embedding=query_embedding,
            k=self._settings.relation_top_k,
            type_filter="relation",
        )

        entity_hits, relation_hits = await asyncio.gather(entity_task, relation_task)

        logger.info(
            "[LIGHTRAG] Found %d entity hits + %d relation hits",
            len(entity_hits), len(relation_hits),
        )

        # Step 4: Collect source chunk IDs with scores
        chunk_scores: dict[str, float] = {}  # chunk_id -> best entity/relation score
        entity_names: set[str] = set()
        graph_context_parts: list[str] = []

        for hit in entity_hits:
            src_chunks = hit.get("source_chunk_ids", [])
            hit_score = hit.get("score", 0.0)
            if isinstance(src_chunks, list):
                for cid in src_chunks:
                    chunk_scores[cid] = max(chunk_scores.get(cid, 0.0), hit_score)
            entity_names.add(hit.get("name", ""))

            graph_context_parts.append(
                f"Entity: {hit.get('name', '?')} ({hit.get('entity_type', '?')}) "
                f"[score={hit_score:.3f}]"
            )

        for hit in relation_hits:
            src_chunk = hit.get("source_chunk_id", "")
            hit_score = hit.get("score", 0.0)
            if src_chunk:
                chunk_scores[src_chunk] = max(chunk_scores.get(src_chunk, 0.0), hit_score)

            graph_context_parts.append(
                f"Relation: {hit.get('source_name', '?')} "
                f"-[{hit.get('relation_type', '?')}]-> "
                f"{hit.get('target_name', '?')} "
                f"[score={hit_score:.3f}]"
            )

        # Step 5: Expand entity neighbors (optional depth)
        if entity_hits and self._settings.neighbor_depth > 0:
            neighbor_chunks = await self._get_neighbor_chunks(entity_hits)
            for cid in neighbor_chunks:
                if cid not in chunk_scores:
                    chunk_scores[cid] = 0.5  # Lower score for neighbor chunks

        logger.info(
            "[LIGHTRAG] Collected %d unique chunk IDs from %d entities + %d relations",
            len(chunk_scores), len(entity_names), len(relation_hits),
        )

        # Step 6: Fetch chunks from vector store (no re-embedding needed)
        results: list[SearchResult] = []

        if chunk_scores:
            # Sort chunk IDs by score, take top candidates
            sorted_ids = sorted(chunk_scores.keys(), key=lambda x: chunk_scores[x], reverse=True)
            top_ids = sorted_ids[:self._settings.max_chunks * 2]

            chunks = await self._vector_store.get_by_ids(top_ids)

            if chunks:
                # Use entity/relation scores directly (no costly re-embedding)
                for chunk in chunks:
                    score = chunk_scores.get(chunk.id, 0.0)
                    chunk.metadata["graph_context"] = "\n".join(graph_context_parts[:5])
                    chunk.metadata["lightrag_entities"] = list(entity_names)[:10]
                    results.append(SearchResult(
                        chunk=chunk,
                        score=score,
                        source="lightrag",
                    ))

                # Sort by score and limit
                results.sort(key=lambda r: r.score, reverse=True)
                results = results[:k]

        # Fallback: if no chunks from graph, use vector search
        if not results:
            logger.info("[LIGHTRAG] No chunks from graph refs -- falling back to vector search")
            results = await self._fallback_search(
                query, query_embedding, entity_names, k, filter,
            )

        elapsed = (time.perf_counter() - start) * 1000

        logger.info(
            "[LIGHTRAG] Completed in %.0fms: %d results from %d entities + %d relations",
            elapsed, len(results), len(entity_names), len(relation_hits),
        )

        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            search_type="graphrag_light",
            elapsed_ms=elapsed,
            metadata={
                "entity_hits": len(entity_hits),
                "relation_hits": len(relation_hits),
                "chunk_ids_found": len(chunk_scores),
                "entity_names": list(entity_names)[:10],
            },
        )

    async def _get_neighbor_chunks(self, entity_hits: list[dict]) -> set[str]:
        """Get chunk IDs from entity neighbors in the graph."""
        chunk_ids: set[str] = set()
        graph = getattr(self._graph_store, "_graph", None)
        if graph is None:
            return chunk_ids

        for hit in entity_hits[:5]:  # Limit to top-5 entities
            graph_id = hit.get("graph_id", "")
            if not graph_id or graph_id not in graph:
                continue

            # Get immediate neighbors
            for neighbor_id in graph.neighbors(graph_id):
                neighbor_data = graph.nodes.get(neighbor_id, {})
                if neighbor_data.get("node_type") == "COMMUNITY":
                    continue
                src_chunks = neighbor_data.get("source_chunk_ids", [])
                if isinstance(src_chunks, list):
                    chunk_ids.update(src_chunks)

        return chunk_ids

    async def _fallback_search(
        self,
        query: str,
        query_embedding: list[float],
        entity_names: set[str],
        k: int,
        filter: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Fallback: regular vector search, enriched with entity context."""
        results = await self._vector_store.search(
            query_embedding=query_embedding,
            k=k,
            filter=filter,
        )

        # Enrich results with found entity names
        for r in results:
            r.chunk.metadata["lightrag_entities"] = list(entity_names)[:10]
            r.source = "lightrag_fallback"

        return results
