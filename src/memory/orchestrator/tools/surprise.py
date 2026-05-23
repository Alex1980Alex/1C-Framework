"""Surprise Tool — unexpectedness score for new patterns.

Calculates how "surprising" (novel) a piece of content is compared to
existing memories. High surprise scores indicate genuinely new information
that the system hasn't seen before.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..unified_search import UnifiedSearchEngine

logger = logging.getLogger(__name__)


class SurpriseTool:
    """Calculate unexpectedness scores for new content.

    Compares incoming content against existing memory to determine novelty.
    Uses token-overlap and search-score inversion to estimate surprise.

    Higher score (closer to 1.0) = more surprising/novel.
    Lower score (closer to 0.0) = already well-known.

    Usage::

        tool = SurpriseTool(search_engine)
        result = await tool.score("New BSL pattern for batch processing")
    """

    def __init__(self, search_engine: UnifiedSearchEngine | None) -> None:
        self._search = search_engine

    async def score(
        self,
        content: str,
        context: str | None = None,
        top_k: int = 10,
        detail: bool = False,
    ) -> dict[str, Any]:
        """Calculate the surprise score for content.

        Args:
            content: The content to evaluate.
            context: Optional context hint (e.g., domain or topic).
            top_k: Number of similar items to compare against.
            detail: If True, include detailed comparison data.

        Returns:
            Dict with ``surprise_score`` (0-1), ``novelty_level``, and details.
        """
        if not content.strip():
            return {"surprise_score": 0.0, "novelty_level": "empty", "reason": "Empty content"}

        query = f"{context} {content}" if context else content

        # Search for similar existing content
        similar_items: list = []
        if self._search:
            try:
                search_result = await self._search.search(
                    query=query, limit=top_k, include_links=False
                )
                similar_items = search_result.results
            except Exception as e:
                logger.debug("Search failed during surprise scoring: %s", e)

        # Calculate surprise metrics
        if not similar_items:
            # Nothing similar found — maximally surprising
            return {
                "surprise_score": 1.0,
                "novelty_level": "high",
                "reason": "No similar content found in memory",
                "similar_count": 0,
            }

        # Metric 1: Best match score inversion
        best_score = max(item.raw_score for item in similar_items)
        score_surprise = 1.0 - min(best_score, 1.0)

        # Metric 2: Average similarity inversion
        avg_score = sum(item.raw_score for item in similar_items) / len(similar_items)
        avg_surprise = 1.0 - min(avg_score, 1.0)

        # Metric 3: Token novelty (how many content tokens are absent from top results)
        content_tokens = set(_tokenize(content))
        existing_tokens: set[str] = set()
        for item in similar_items:
            existing_tokens.update(_tokenize(item.content))
        novel_tokens = content_tokens - existing_tokens
        token_novelty = len(novel_tokens) / max(len(content_tokens), 1)

        # Combined surprise score (weighted)
        surprise = 0.4 * score_surprise + 0.3 * avg_surprise + 0.3 * token_novelty
        surprise = round(min(max(surprise, 0.0), 1.0), 4)

        # Classify novelty level
        if surprise >= 0.7:
            novelty_level = "high"
        elif surprise >= 0.4:
            novelty_level = "medium"
        else:
            novelty_level = "low"

        result: dict[str, Any] = {
            "surprise_score": surprise,
            "novelty_level": novelty_level,
            "similar_count": len(similar_items),
            "best_match_score": round(best_score, 4),
            "token_novelty": round(token_novelty, 4),
        }

        if detail:
            result["novel_tokens"] = sorted(novel_tokens)[:20]
            result["similar_items"] = [
                {
                    "unified_id": item.unified_id,
                    "score": round(item.raw_score, 4),
                    "content_preview": item.content[:100],
                }
                for item in similar_items[:5]
            ]
            result["metrics"] = {
                "score_surprise": round(score_surprise, 4),
                "avg_surprise": round(avg_surprise, 4),
                "token_novelty": round(token_novelty, 4),
            }

        return result

    async def batch_score(
        self,
        items: list[str],
        context: str | None = None,
    ) -> dict[str, Any]:
        """Score multiple items and return sorted by surprise.

        Args:
            items: List of content strings.
            context: Optional shared context.

        Returns:
            Dict with sorted scores and summary statistics.
        """
        scored_items = []
        for i, content in enumerate(items):
            result = await self.score(content, context=context)
            scored_items.append(
                {
                    "index": i,
                    "content_preview": content[:80],
                    **result,
                }
            )

        scored_items.sort(key=lambda x: x["surprise_score"], reverse=True)

        all_scores = [s["surprise_score"] for s in scored_items]
        return {
            "items": scored_items,
            "summary": {
                "total": len(scored_items),
                "avg_surprise": round(sum(all_scores) / max(len(all_scores), 1), 4),
                "max_surprise": round(max(all_scores), 4) if all_scores else 0.0,
                "min_surprise": round(min(all_scores), 4) if all_scores else 0.0,
                "high_novelty_count": sum(1 for s in all_scores if s >= 0.7),
            },
        }


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer with short-token filtering."""
    return [w.lower().strip(".,;:!?()[]{}\"'") for w in text.split() if len(w) > 2]


__all__ = ["SurpriseTool"]
