"""LangChain tool wrapper for SearchManager."""

import time

from langchain_core.tools import tool

from src.pdf_framework.observability.langfuse_setup import emit_observation
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
        t0 = time.monotonic()
        span_input = {"query_len": len(query or ""), "strategy": strategy, "k": k}
        try:
            response = await search_manager.search(query=query, strategy=strategy, k=k)
        except Exception as e:
            try:
                emit_observation(
                    name="tool.search_documents",
                    input=span_input,
                    output={
                        "status": "error",
                        "error_type": type(e).__name__,
                        "duration_ms": round((time.monotonic() - t0) * 1000, 1),
                    },
                    flush=False,
                )
            except Exception:
                pass
            raise

        parts: list[str] = []
        for i, result in enumerate(response.results, 1):
            parts.append(f"[{i}] (score: {result.score:.3f}) {result.chunk.content[:300]}")

        try:
            emit_observation(
                name="tool.search_documents",
                input=span_input,
                output={
                    "status": "ok",
                    "results": len(response.results),
                    "duration_ms": round((time.monotonic() - t0) * 1000, 1),
                },
                flush=False,
            )
        except Exception:
            pass

        return "\n\n".join(parts) if parts else "No results found."

    return search_documents
