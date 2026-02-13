"""Content Booster — boost scores for positive chunks (Phase 22).

Author: Claude Code
Version: 1.0.0 - Phase 22: Self-Learning Feedback
"""

import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ContentBooster:
    """Boost search result scores based on accumulated positive feedback."""

    def __init__(
        self,
        feedback_store: Any = None,
        max_boost: float = 1.3,
        min_positive_count: int = 3,
    ):
        self._store = feedback_store
        self._max_boost = max_boost
        self._min_count = min_positive_count
        self._boost_map: dict[str, float] = {}
        self._built = False

    async def _build_boost_map(self) -> None:
        """Build chunk_id → boost factor from positive feedback."""
        if not self._store or self._built:
            return

        try:
            positive = await self._store.get_positive(limit=500)
            chunk_counts: dict[str, int] = {}

            for entry in positive:
                for cid in entry.chunk_ids:
                    chunk_counts[cid] = chunk_counts.get(cid, 0) + 1

            for cid, count in chunk_counts.items():
                if count >= self._min_count:
                    # Linear boost: more positive mentions → higher boost
                    factor = min(self._max_boost, 1.0 + (count / 10.0) * 0.3)
                    self._boost_map[cid] = factor

            self._built = True
            logger.info(f"[BOOST] Built boost map: {len(self._boost_map)} boosted chunks")

        except Exception as e:
            logger.warning(f"[BOOST] Failed to build map: {e}")

    async def get_boost(self, chunk_id: str) -> float:
        """Get boost factor for a chunk (1.0 = no boost)."""
        if not self._built:
            await self._build_boost_map()
        return self._boost_map.get(chunk_id, 1.0)

    async def apply_boost(self, results: list[Any]) -> list[Any]:
        """Apply boost to search results and re-sort."""
        if not self._built:
            await self._build_boost_map()

        boosted = []
        for r in results:
            chunk_id = r.chunk.id if hasattr(r, "chunk") else ""
            factor = self._boost_map.get(chunk_id, 1.0)
            # Create a copy-like structure with boosted score
            boosted.append({"result": r, "original_score": r.score, "boosted_score": r.score * factor})

        boosted.sort(key=lambda x: x["boosted_score"], reverse=True)

        # Update scores and return original objects
        reordered = []
        for item in boosted:
            r = item["result"]
            r.score = item["boosted_score"]
            reordered.append(r)

        return reordered
