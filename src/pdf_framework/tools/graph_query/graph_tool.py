"""LangChain tool for graph queries."""

from langchain_core.tools import tool

from src.pdf_framework.graph_store.base import BaseGraphStore


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
        entities = await graph_store.find_entities(
            name=query,
            entity_type=entity_type or None,
            limit=10,
        )

        if not entities:
            return f"No entities found matching '{query}'."

        parts: list[str] = []
        for entity in entities:
            subgraph = await graph_store.get_neighbors(entity.id, depth=depth)
            relations_str = ", ".join(
                f"{r.relation_type} → {r.target_entity_id}"
                for r in subgraph.relations[:5]
            )
            parts.append(
                f"• {entity.name} ({entity.entity_type})"
                + (f" — Relations: {relations_str}" if relations_str else "")
            )

        return "\n".join(parts)

    return query_knowledge_graph
