"""Source fusion: combine local docs + web + external sources (Phase 37).

Implements trust-based scoring and confidence-based fallback.
Priority: documentation > 1C data > corporate wiki > web.
"""

import logging
from typing import Any

from src.pdf_framework.schemas.documents import SearchResponse, SearchResult

logger = logging.getLogger(__name__)

# Trust multipliers for different source types
_TRUST_SCORES: dict[str, float] = {
    "documentation": 1.0,  # PDF docs — highest trust
    "1c_api": 0.8,  # 1C OData/API — high trust (live data)
    "wiki": 0.6,  # Corporate wiki — medium trust
    "web": 0.3,  # Web search — lowest trust
}


class SourceFusion:
    """Combine results from multiple sources with trust-based scoring.

    When local document search returns low-confidence results,
    automatically falls back to web search and fuses results.
    """

    def __init__(
        self,
        search_manager: Any,
        web_strategy: Any | None = None,
        confidence_threshold: float = 0.5,
    ):
        self._manager = search_manager
        self._web = web_strategy
        self._confidence_threshold = confidence_threshold

    async def search_with_fallback(
        self,
        query: str,
        strategy: str = "hybrid",
        k: int = 5,
        **kwargs: Any,
    ) -> SearchResponse:
        """Search local docs first, fall back to web if low confidence.

        Args:
            query: Search query.
            strategy: Primary local search strategy.
            k: Number of results.

        Returns:
            Fused SearchResponse with source metadata.
        """
        # Step 1: Search local documents
        local = await self._manager.search(
            query=query, strategy=strategy, k=k, **kwargs,
        )

        # Step 2: Check confidence
        avg_score = (
            sum(r.score for r in local.results) / len(local.results)
            if local.results
            else 0.0
        )

        # Tag local results with trust
        for r in local.results:
            r.chunk.metadata["trust"] = "documentation"
            r.chunk.metadata["trust_score"] = _TRUST_SCORES["documentation"]

        # Step 3: If confidence is high enough, return local results
        if avg_score >= self._confidence_threshold or self._web is None:
            local.metadata["source_fusion"] = {
                "local_count": len(local.results),
                "web_count": 0,
                "avg_local_score": round(avg_score, 3),
                "fallback_used": False,
            }
            return local

        # Step 4: Fall back to web search
        logger.info(
            "[FUSION] Local avg_score=%.3f < threshold=%.3f, adding web results",
            avg_score,
            self._confidence_threshold,
        )

        web_response = await self._web.search(query=query, k=k)

        # Step 5: Fuse results with trust scoring
        fused = self._fuse_results(
            local_results=local.results,
            web_results=web_response.results,
            k=k,
        )

        return SearchResponse(
            query=query,
            results=fused,
            total_found=len(fused),
            search_type=f"fused_{local.search_type}+{web_response.search_type}",
            elapsed_ms=local.elapsed_ms + web_response.elapsed_ms,
            metadata={
                "source_fusion": {
                    "local_count": len(local.results),
                    "web_count": len(web_response.results),
                    "avg_local_score": round(avg_score, 3),
                    "fallback_used": True,
                },
            },
        )

    def _fuse_results(
        self,
        local_results: list[SearchResult],
        web_results: list[SearchResult],
        k: int,
    ) -> list[SearchResult]:
        """Fuse local and web results with trust-based scoring."""
        all_results: list[SearchResult] = []

        for r in local_results:
            trust = _TRUST_SCORES.get(
                r.chunk.metadata.get("trust", "documentation"),
                1.0,
            )
            r.score *= trust
            all_results.append(r)

        for r in web_results:
            trust = _TRUST_SCORES.get(
                r.chunk.metadata.get("trust", "web"),
                0.3,
            )
            r.score *= trust
            all_results.append(r)

        # Sort by trust-adjusted score
        all_results.sort(key=lambda r: r.score, reverse=True)

        return all_results[:k]

    @staticmethod
    def get_trust_score(source_type: str) -> float:
        """Get trust multiplier for a source type."""
        return _TRUST_SCORES.get(source_type, 0.3)
