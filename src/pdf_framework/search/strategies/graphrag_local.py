"""GraphRAG Local Search: vector search + graph context enrichment.

Enhances vector search results with related entities and relationships
from the knowledge graph.

Author: Claude Code
Version: 0.7.0 - Phase 6.3: Local Search
"""

import logging
import re
import time
from typing import Any

from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.schemas.documents import SearchResponse, SearchResult
from src.pdf_framework.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class GraphRAGLocalStrategy:
    """
    Local Search strategy for GraphRAG.

    Combines vector similarity search with graph context enrichment:
    1. Vector search → top-k chunks
    2. Extract entities from chunks
    3. Get neighboring entities from graph
    4. Enrich results with graph context
    """

    def __init__(
        self,
        embedding_engine: BaseEmbeddingEngine,
        vector_store: BaseVectorStore,
        graph_store: BaseGraphStore,
        neighbor_depth: int = 1,
        include_community_summary: bool = True,
    ):
        """
        Initialize GraphRAG Local Search strategy.

        Args:
            embedding_engine: For query embedding
            vector_store: For vector similarity search
            graph_store: For graph context enrichment
            neighbor_depth: Depth for neighbor traversal (default: 1)
            include_community_summary: Include community summary in results
        """
        self._embedding_engine = embedding_engine
        self._vector_store = vector_store
        self._graph_store = graph_store
        self._neighbor_depth = neighbor_depth
        self._include_community_summary = include_community_summary

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs,
    ) -> SearchResponse:
        """
        Perform local search with graph context enrichment.

        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filters
            **kwargs: Additional parameters

        Returns:
            SearchResponse with graph-enriched results
        """
        start = time.perf_counter()

        # Step 1: Vector search
        query_embedding = await self._embedding_engine.embed_text(query)
        vector_results = await self._vector_store.search(
            query_embedding=query_embedding,
            k=k,
            filter=filter,
        )

        # Step 2: Extract entities from chunks
        entities_set = await self._extract_entities_from_chunks(vector_results)

        logger.info(f"[LOCAL_SEARCH] Extracted {len(entities_set)} unique entities from chunks")

        # Step 3: Get graph context for each entity
        graph_contexts = await self._get_graph_contexts(entities_set)

        # Step 4: Enrich results with graph context
        enriched_results = []
        for result in vector_results:
            enriched = await self._enrich_result(result, graph_contexts)
            enriched_results.append(enriched)

        elapsed = (time.perf_counter() - start) * 1000

        logger.info(
            f"[LOCAL_SEARCH] Found {len(enriched_results)} results "
            f"with graph context ({elapsed:.0f}ms)"
        )

        return SearchResponse(
            query=query,
            results=enriched_results,
            total_found=len(enriched_results),
            search_type="graphrag_local",
            elapsed_ms=elapsed,
        )

    async def _extract_entities_from_chunks(
        self,
        results: list[SearchResult],
    ) -> set[str]:
        """
        Extract unique entity names from chunk content.

        Uses graph-aware matching: checks known entity names from the graph
        against chunk content, supporting any language (Cyrillic, Latin, etc.).
        Falls back to regex for capitalized phrases if no graph entities found.

        Args:
            results: Search results with chunk content

        Returns:
            Set of unique entity names
        """
        entities = set()

        # Get known entity names from the graph for matching
        known_names = await self._get_known_entity_names()

        for result in results:
            content = result.chunk.content
            content_lower = content.lower()

            # Graph-aware: find known entity names that appear in chunk
            for name in known_names:
                if len(name) >= 3 and name.lower() in content_lower:
                    entities.add(name)

            # Regex fallback for Latin capitalized phrases and acronyms
            patterns = [
                r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b',
                r'\b[A-Z]{2,}\b',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if match.lower() not in {
                        "the", "and", "this", "that", "with", "from",
                        "but", "not", "are", "was", "were", "been",
                    }:
                        entities.add(match)

        return entities

    async def _get_known_entity_names(self) -> set[str]:
        """Get all entity names from the graph store for matching."""
        names = set()
        graph = getattr(self._graph_store, "_graph", None)
        if graph is None:
            return names
        for _, data in graph.nodes(data=True):
            name = data.get("name", "")
            if name and data.get("node_type") != "COMMUNITY":
                names.add(name)
        return names

    async def _get_graph_contexts(
        self,
        entity_names: set[str],
    ) -> dict[str, dict[str, Any]]:
        """
        Get graph context for each entity.

        Args:
            entity_names: Set of entity names to look up

        Returns:
            Dictionary mapping entity_name -> graph context
        """
        contexts = {}

        for name in entity_names:
            # Find entities by name
            entities = await self._graph_store.find_entities(name=name, limit=3)

            if not entities:
                continue

            # Get neighbors for first matching entity
            entity = entities[0]
            subgraph = await self._graph_store.get_neighbors(
                entity.id,
                depth=self._neighbor_depth,
            )

            if subgraph.entities:
                contexts[name] = {
                    "entity": entity,
                    "neighbors": subgraph.entities[1:],  # Exclude center entity
                    "relations": subgraph.relations,
                    "community_id": entity.properties.get("community_id"),
                }

        return contexts

    async def _enrich_result(
        self,
        result: SearchResult,
        graph_contexts: dict[str, dict[str, Any]],
    ) -> SearchResult:
        """
        Enrich a single search result with graph context.

        Args:
            result: Original search result
            graph_contexts: Graph contexts for entities

        Returns:
            Enriched search result
        """
        # Extract entities from this chunk
        entities_in_chunk = await self._extract_entities_from_chunks([result])

        # Build graph context text
        context_parts = []

        for entity_name in entities_in_chunk:
            if entity_name in graph_contexts:
                ctx = graph_contexts[entity_name]
                context_text = self._format_graph_context(ctx)
                if context_text:
                    context_parts.append(context_text)

        # Add to metadata
        enriched_metadata = dict(result.chunk.metadata)
        if context_parts:
            enriched_metadata["graph_context"] = "\n".join(context_parts)
            enriched_metadata["related_entities"] = list(entities_in_chunk)

        return SearchResult(
            chunk=result.chunk.model_copy(update={"metadata": enriched_metadata}),
            score=result.score,
        )

    def _format_graph_context(self, context: dict[str, Any]) -> str:
        """
        Format graph context as readable text.

        Args:
            context: Graph context dictionary

        Returns:
            Formatted context string
        """
        parts = []

        entity = context.get("entity")
        if entity:
            parts.append(f"Related to: {entity.name} ({entity.entity_type})")

        neighbors = context.get("neighbors", [])
        if neighbors:
            neighbor_names = [n.name for n in neighbors[:5]]
            parts.append(f"Connected to: {', '.join(neighbor_names)}")

        relations = context.get("relations", [])
        if relations:
            rel_texts = [
                f"{r.source_entity_id} --[{r.relation_type}]--> {r.target_entity_id}"
                for r in relations[:3]
            ]
            parts.append(f"Relations: {'; '.join(rel_texts)}")

        return " | ".join(parts) if parts else ""
