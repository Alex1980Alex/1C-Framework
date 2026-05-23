"""Warmup Tool — preload frequently used data into LRU cache.

Analyzes access patterns and preloads high-value entities into the
in-memory LRU cache to reduce cold-start latency.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ...infrastructure.cache import LRUCache

if TYPE_CHECKING:
    from ...infrastructure.event_store import EventStore
    from ...orchestrator.unified_search import UnifiedSearchEngine

logger = logging.getLogger(__name__)


class WarmupTool:
    """Preload frequently or recently used data into LRU cache.

    Strategies:
      - **frequent**: Load entities with highest access counts.
      - **recent**: Load most recently created/updated entities.
      - **important**: Load entities with highest importance scores.
      - **pattern**: Load entities matching a specific pattern/query.

    Usage::

        tool = WarmupTool(cache, search_engine, event_store)
        result = await tool.warmup(strategy="frequent", limit=50)
    """

    def __init__(
        self,
        cache: LRUCache,
        search_engine: UnifiedSearchEngine | None = None,
        event_store: EventStore | None = None,
    ) -> None:
        self._cache = cache
        self._search = search_engine
        self._event_store = event_store

    async def warmup(
        self,
        strategy: str = "frequent",
        limit: int = 50,
        query: str | None = None,
        ttl: float | None = None,
    ) -> dict[str, Any]:
        """Execute cache warmup with the specified strategy.

        Args:
            strategy: Warmup strategy (``frequent``, ``recent``,
                ``important``, ``pattern``).
            limit: Maximum entities to preload.
            query: Query for ``pattern`` strategy.
            ttl: Optional TTL override for cached entries.

        Returns:
            Warmup result with stats.
        """
        cache_before = self._cache.stats()

        if strategy == "frequent":
            loaded = await self._warmup_frequent(limit, ttl)
        elif strategy == "recent":
            loaded = await self._warmup_recent(limit, ttl)
        elif strategy == "important":
            loaded = await self._warmup_important(limit, ttl)
        elif strategy == "pattern":
            loaded = await self._warmup_pattern(query or "", limit, ttl)
        else:
            return {"error": f"Unknown strategy: {strategy}"}

        cache_after = self._cache.stats()

        return {
            "strategy": strategy,
            "entities_loaded": loaded,
            "cache_before": cache_before,
            "cache_after": cache_after,
            "cache_delta": cache_after["size"] - cache_before["size"],
        }

    async def _warmup_frequent(self, limit: int, ttl: float | None) -> int:
        """Warmup using event history to find frequently accessed entities."""
        if not self._event_store:
            return 0

        events = await self._event_store.query(event_type="memory.search", limit=limit * 5)
        # Count entity mentions in search results
        entity_counts: dict[str, int] = {}
        for event in events:
            for entity_id in event.data.get("result_ids", []):
                entity_counts[entity_id] = entity_counts.get(entity_id, 0) + 1

        # Sort by frequency, load top entities
        top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        loaded = 0
        for entity_id, count in top_entities:
            if entity_id not in self._cache:
                self._cache.put(
                    f"warmup:{entity_id}",
                    {"entity_id": entity_id, "access_count": count, "warmed": True},
                    ttl=ttl,
                )
                loaded += 1
        return loaded

    async def _warmup_recent(self, limit: int, ttl: float | None) -> int:
        """Warmup using most recent events."""
        if not self._event_store:
            return 0

        events = await self._event_store.query(limit=limit)
        loaded = 0
        for event in events:
            cache_key = f"warmup:event:{event.event_id}"
            if cache_key not in self._cache:
                self._cache.put(
                    cache_key,
                    {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "data": event.data,
                        "warmed": True,
                    },
                    ttl=ttl,
                )
                loaded += 1
        return loaded

    async def _warmup_important(self, limit: int, ttl: float | None) -> int:
        """Warmup using search for high-importance items."""
        if not self._search:
            return 0

        try:
            result = await self._search.search(
                query="important",
                limit=limit,
                min_score=0.5,
                include_links=False,
            )
            loaded = 0
            for item in result.results:
                cache_key = f"warmup:{item.unified_id}"
                if cache_key not in self._cache:
                    self._cache.put(
                        cache_key,
                        {
                            "unified_id": item.unified_id,
                            "content": item.content[:500],
                            "score": item.raw_score,
                            "warmed": True,
                        },
                        ttl=ttl,
                    )
                    loaded += 1
            return loaded
        except Exception as e:
            logger.debug("Important warmup failed: %s", e)
            return 0

    async def _warmup_pattern(self, query: str, limit: int, ttl: float | None) -> int:
        """Warmup using a specific search pattern."""
        if not self._search or not query:
            return 0

        try:
            result = await self._search.search(query=query, limit=limit, include_links=False)
            loaded = 0
            for item in result.results:
                cache_key = f"warmup:{item.unified_id}"
                if cache_key not in self._cache:
                    self._cache.put(
                        cache_key,
                        {
                            "unified_id": item.unified_id,
                            "content": item.content[:500],
                            "score": item.raw_score,
                            "warmed": True,
                        },
                        ttl=ttl,
                    )
                    loaded += 1
            return loaded
        except Exception as e:
            logger.debug("Pattern warmup failed: %s", e)
            return 0

    async def get_warmup_stats(self) -> dict[str, Any]:
        """Return current cache warmup statistics."""
        stats = self._cache.stats()
        # Count warmed entries
        warmed = 0
        for key in list(self._cache._store.keys()):
            if key.startswith("warmup:"):
                warmed += 1
        stats["warmed_entries"] = warmed
        return stats


__all__ = ["WarmupTool"]
