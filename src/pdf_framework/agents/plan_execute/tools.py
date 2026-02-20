"""Tools for Plan-Execute Agent (Phase 57).

Available tools:
- search: Vector/hybrid search
- graph_query: Knowledge graph queries
- calculate: Simple calculations
- web_search: External web search (optional)

Author: Claude Code
Version: 1.0.0 - Phase 57: Agentic RAG Plan-Execute
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def create_plan_execute_tools(search_manager: Any, graph_store: Any = None) -> dict[str, Any]:
    """Create tools dictionary for Plan-Execute agent.

    Args:
        search_manager: Search manager for queries
        graph_store: Optional graph store for entity queries

    Returns:
        Dictionary of tool functions
    """
    tools = {
        "search": SearchTool(search_manager),
    }

    if graph_store is not None:
        tools["graph_query"] = GraphQueryTool(graph_store)

    tools["calculate"] = CalculateTool()

    # web_search is optional, add only if explicitly enabled
    # tools["web_search"] = WebSearchTool()

    return tools


class SearchTool:
    """Tool for searching documents."""

    def __init__(self, search_manager: Any):
        self._search_manager = search_manager

    async def ainvoke(self, input: dict[str, Any]) -> dict[str, Any]:
        """Invoke search tool."""
        query = input.get("query", "")
        k = input.get("k", 5)

        response = await self._search_manager.search(
            query=query,
            strategy="hybrid",
            k=k,
        )

        return {
            "results": [
                {
                    "content": r.chunk.content,
                    "score": r.score,
                    "source": r.source,
                }
                for r in response.results
            ],
            "total": response.total_found,
        }


class GraphQueryTool:
    """Tool for querying knowledge graph."""

    def __init__(self, graph_store: Any):
        self._graph_store = graph_store

    async def ainvoke(self, input: dict[str, Any]) -> dict[str, Any]:
        """Invoke graph query tool."""
        query = input.get("query", "")

        # Simple entity extraction and lookup
        # In production, use NER for better entity detection
        results = await self._graph_store.search_entities(query, limit=10)

        return {
            "entities": [
                {
                    "name": e.get("name", ""),
                    "type": e.get("type", ""),
                    "properties": e.get("properties", {}),
                }
                for e in results
            ],
        }


class CalculateTool:
    """Tool for simple calculations."""

    async def ainvoke(self, input: dict[str, Any]) -> dict[str, Any]:
        """Invoke calculate tool."""
        expression = input.get("expression", "")

        try:
            # Safe eval with restricted globals
            result = eval(
                expression,
                {"__builtins__": {}},
                {"abs": abs, "min": min, "max": max, "sum": sum, "len": len}
            )
            return {"result": result, "expression": expression}
        except Exception as e:
            return {
                "result": f"Error: {str(e)}",
                "expression": expression,
                "error": True,
            }
