"""LangChain tool for graph queries."""

import time

from langchain_core.tools import tool

from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.observability.langfuse_setup import emit_observation


def create_graph_query_tool(graph_store: BaseGraphStore):
    """Create a LangChain tool for querying the knowledge graph."""

    @tool
    async def query_knowledge_graph(
        query: str,
        entity_type: str = "",
        depth: int = 1,
    ) -> str:
        """Query the knowledge graph for entities and their relations.

        Args:
            query: Entity name or search term.
            entity_type: Filter by entity type (PERSON, ORG, LOCATION, etc.).
            depth: How many hops to traverse from found entities.
        """
        t0 = time.monotonic()
        span_input = {
            "query_len": len(query or ""),
            "entity_type": entity_type or None,
            "depth": depth,
        }

        def _emit(status: str, **extra: object) -> None:
            try:
                emit_observation(
                    name="tool.query_knowledge_graph",
                    input=span_input,
                    output={
                        "status": status,
                        "duration_ms": round((time.monotonic() - t0) * 1000, 1),
                        **extra,
                    },
                    flush=False,
                )
            except Exception:
                pass

        try:
            entities = await graph_store.find_entities(
                name=query,
                entity_type=entity_type or None,
                limit=10,
            )
        except Exception as e:
            _emit("error", error_type=type(e).__name__)
            raise

        if not entities:
            _emit("no-results", entities=0)
            return f"No entities found matching '{query}'."

        parts: list[str] = []
        total_relations = 0
        for entity in entities:
            subgraph = await graph_store.get_neighbors(entity.id, depth=depth)
            total_relations += len(subgraph.relations)
            relations_str = ", ".join(
                f"{r.relation_type} → {r.target_entity_id}" for r in subgraph.relations[:5]
            )
            parts.append(
                f"• {entity.name} ({entity.entity_type})"
                + (f" — Relations: {relations_str}" if relations_str else "")
            )

        _emit("ok", entities=len(entities), relations=total_relations)
        return "\n".join(parts)

    return query_knowledge_graph
