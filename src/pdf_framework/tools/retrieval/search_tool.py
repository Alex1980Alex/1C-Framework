"""LangChain tool wrapper for SearchManager."""

from langchain_core.tools import tool

from src.pdf_framework.search.manager import SearchManager


def create_search_tool(search_manager: SearchManager):
    """Create a LangChain tool for document search."""

    @tool
    async def search_documents(
        query: str,
        strategy: str = "vector",
        k: int = 5,
    ) -> str:
        """Search indexed documents by semantic similarity.

        Args:
            query: The search query text.
            strategy: Search strategy to use (vector, graph, hybrid).
            k: Number of results to return.
        """
        response = await search_manager.search(query=query, strategy=strategy, k=k)
        parts: list[str] = []
        for i, result in enumerate(response.results, 1):
            parts.append(
                f"[{i}] (score: {result.score:.3f}) {result.chunk.content[:300]}"
            )
        return "\n\n".join(parts) if parts else "No results found."

    return search_documents
