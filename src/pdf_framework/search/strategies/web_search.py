"""Web search fallback strategy (Phase 37).

When local document search yields low-confidence results,
falls back to web search via Tavily or SerpAPI.
"""

import asyncio
import logging
import time
from typing import Any

from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)

logger = logging.getLogger(__name__)


class WebSearchStrategy:
    """Search the web as fallback when local results are insufficient.

    Supports:
    - Tavily (preferred, optimized for RAG)
    - SerpAPI (fallback)
    - httpx+DuckDuckGo (no API key needed, basic)
    """

    def __init__(
        self,
        tavily_api_key: str = "",
        serpapi_key: str = "",
        max_results: int = 5,
        trust_score: float = 0.3,  # web results scored lower than docs
    ):
        self._tavily_key = tavily_api_key
        self._serpapi_key = serpapi_key
        self._max_results = max_results
        self._trust_score = trust_score
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        if self._tavily_key:
            try:
                import tavily  # noqa: F401

                return "tavily"
            except ImportError:
                logger.warning("[WEB] tavily-python not installed, trying serpapi")

        if self._serpapi_key:
            try:
                import serpapi  # noqa: F401

                return "serpapi"
            except ImportError:
                logger.warning("[WEB] serpapi not installed, using httpx fallback")

        return "httpx"

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute web search and return results as SearchResponse."""
        t0 = time.time()

        if self._backend == "tavily":
            results = await self._search_tavily(query, k)
        elif self._backend == "serpapi":
            results = await self._search_serpapi(query, k)
        else:
            results = await self._search_httpx(query, k)

        elapsed = (time.time() - t0) * 1000

        logger.info(
            "[WEB] %s search: %d results in %.0fms",
            self._backend,
            len(results),
            elapsed,
        )

        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            search_type=f"web_{self._backend}",
            elapsed_ms=elapsed,
            metadata={"source": "web", "backend": self._backend},
        )

    async def _search_tavily(self, query: str, k: int) -> list[SearchResult]:
        """Search via Tavily API (optimized for RAG)."""
        try:
            from tavily import AsyncTavilyClient

            client = AsyncTavilyClient(api_key=self._tavily_key)
            response = await client.search(
                query=query,
                max_results=min(k, self._max_results),
                search_depth="advanced",
                include_raw_content=False,
            )

            results = []
            for i, item in enumerate(response.get("results", [])):
                score = self._trust_score * (1.0 - i * 0.1)  # decay by rank
                chunk = DocumentChunk(
                    id=f"web_tavily_{i}",
                    document_id="web",
                    content=item.get("content", "")[:1000],
                    metadata={
                        "source": "web",
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "trust": "web",
                    },
                )
                results.append(SearchResult(chunk=chunk, score=score, source="web"))
            return results

        except Exception as e:
            logger.error("[WEB] Tavily search failed: %s", e)
            return []

    async def _search_serpapi(self, query: str, k: int) -> list[SearchResult]:
        """Search via SerpAPI."""
        try:
            import serpapi

            search = await asyncio.to_thread(
                serpapi.search,
                {"q": query, "num": min(k, self._max_results), "api_key": self._serpapi_key},
            )

            results = []
            for i, item in enumerate(search.get("organic_results", [])):
                score = self._trust_score * (1.0 - i * 0.1)
                chunk = DocumentChunk(
                    id=f"web_serp_{i}",
                    document_id="web",
                    content=item.get("snippet", "")[:1000],
                    metadata={
                        "source": "web",
                        "url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "trust": "web",
                    },
                )
                results.append(SearchResult(chunk=chunk, score=score, source="web"))
            return results

        except Exception as e:
            logger.error("[WEB] SerpAPI search failed: %s", e)
            return []

    async def _search_httpx(self, query: str, k: int) -> list[SearchResult]:
        """Basic web search via DuckDuckGo Lite (no API key)."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://lite.duckduckgo.com/lite/",
                    params={"q": query},
                    headers={"User-Agent": "PDF-Framework/1.0"},
                )
                # Parse basic HTML results
                text = resp.text
                results = []
                # Extract snippets from result links
                import re

                links = re.findall(
                    r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]+)</a>',
                    text,
                )
                for i, (url, title) in enumerate(links[:k]):
                    if "duckduckgo" in url:
                        continue
                    score = self._trust_score * (1.0 - i * 0.1)
                    chunk = DocumentChunk(
                        id=f"web_ddg_{i}",
                        document_id="web",
                        content=f"{title}\n{url}",
                        metadata={
                            "source": "web",
                            "url": url,
                            "title": title,
                            "trust": "web",
                        },
                    )
                    results.append(
                        SearchResult(chunk=chunk, score=score, source="web")
                    )
                return results[:k]

        except Exception as e:
            logger.warning("[WEB] httpx/DDG search failed: %s", e)
            return []
