"""LRU/TTL Cache for memory subsystem.

OrderedDict-based LRU with optional TTL per entry.
No Redis or external dependencies.

Version: 1.0 (2026-04-04) -- P2 migration
"""

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """A single cache entry with optional expiry."""

    value: T
    expires_at: float  # 0 = never expires
    access_count: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at


class LRUCache:
    """
    Thread-safe LRU cache with TTL support.

    Uses OrderedDict for O(1) get/put with LRU eviction.
    Entries move to the end on access (most recently used).

    Usage:
        cache = LRUCache(max_size=100, default_ttl=3600)
        cache.put("key", value)
        result = cache.get("key")
        stats = cache.stats()
    """

    def __init__(self, max_size: int = 256, default_ttl: float = 3600.0):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, CacheEntry[Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Any | None:
        """Get value by key. Returns None if missing or expired."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            del self._store[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._store.move_to_end(key)
        entry.access_count += 1
        self._hits += 1
        return entry.value

    def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Put value with optional TTL. Evicts LRU if at capacity."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.time() + effective_ttl if effective_ttl > 0 else 0.0

        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = CacheEntry(value=value, expires_at=expires_at)
        else:
            if len(self._store) >= self._max_size:
                self._evict_lru()
            self._store[key] = CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> bool:
        """Delete entry by key. Returns True if existed."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        """Clear all entries. Returns count of cleared entries."""
        count = len(self._store)
        self._store.clear()
        return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for key in expired_keys:
            del self._store[key]
        if expired_keys:
            logger.debug("Cleaned up %d expired cache entries", len(expired_keys))
        return len(expired_keys)

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
            "evictions": self._evictions,
        }

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if self._store:
            self._store.popitem(last=False)
            self._evictions += 1

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        entry = self._store.get(key)
        return entry is not None and not entry.is_expired

    def __repr__(self) -> str:
        return f"<LRUCache size={len(self._store)}/{self._max_size} hits={self._hits} misses={self._misses}>"


__all__ = ["LRUCache", "CacheEntry"]
