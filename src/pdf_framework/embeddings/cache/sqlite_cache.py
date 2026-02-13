"""Embedding cache for faster repeated embeddings (Phase 11).

Caches embedding results by text hash + model to avoid recomputation.

Author: Claude Code
Version: 1.2.0 - Phase 11.2: Embedding Cache
"""

import aiosqlite
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CacheStats(BaseModel):
    """Cache statistics."""

    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        """Total requests (hits + misses)."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        return self.hits / self.total if self.total > 0 else 0.0


class EmbeddingCache:
    """
    Cache for embedding results using SQLite backend.

    Key: SHA-256(text + model_name)
    Value: embedding vector (JSON array)
    TTL: 30 days (configurable)
    """

    def __init__(
        self,
        db_path: str | Path = "data/cache/embeddings.db",
        ttl_days: int = 30,
    ):
        """
        Initialize embedding cache.

        Args:
            db_path: Path to SQLite database
            ttl_days: Time-to-live in days
        """
        self._db_path = Path(db_path)
        self._ttl_days = ttl_days
        self._initialized = False

        self._stats = CacheStats()

    async def _ensure_tables(self) -> None:
        """Create cache table if not exists."""
        if self._initialized:
            return

        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    text_hash TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'utc')),
                    expires_at TIMESTAMP NOT NULL
                )
            """)

            # Index for TTL cleanup
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_embedding_cache_expires
                ON embedding_cache(expires_at)
            """)

            await db.commit()

        self._initialized = True

    def _hash_text(self, text: str, model: str) -> str:
        """Generate cache key from text and model."""
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(
        self,
        text: str,
        model: str,
    ) -> list[float] | None:
        """
        Get cached embedding if available.

        Args:
            text: Input text
            model: Model name

        Returns:
            Cached embedding vector or None
        """
        await self._ensure_tables()

        key = self._hash_text(text, model)

        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row

                cursor = await db.execute("""
                    SELECT embedding, expires_at
                    FROM embedding_cache
                    WHERE text_hash = ? AND model = ?
                    AND expires_at > datetime('now', 'utc')
                """, (key, model))

                row = await cursor.fetchone()

                if row:
                    self._stats.hits += 1
                    embedding = json.loads(row["embedding"])
                    logger.debug(f"[EMB_CACHE] Cache hit for key {key[:8]}...")
                    return embedding
                else:
                    self._stats.misses += 1
                    return None

        except Exception as e:
            logger.error(f"[EMB_CACHE] Error getting cache: {e}")
            self._stats.misses += 1
            return None

    async def set(
        self,
        text: str,
        model: str,
        embedding: list[float],
    ) -> None:
        """
        Store embedding in cache.

        Args:
            text: Input text
            model: Model name
            embedding: Embedding vector
        """
        await self._ensure_tables()

        key = self._hash_text(text, model)
        embedding_json = json.dumps(embedding)

        # Calculate expiration (TTL)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._ttl_days)

        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO embedding_cache
                    (text_hash, model, embedding, created_at, expires_at)
                    VALUES (?, ?, ?, datetime('now', 'utc'), ?)
                """, (key, model, embedding_json, expires_at.isoformat()))

                await db.commit()

                logger.debug(f"[EMB_CACHE] Cached embedding for key {key[:8]}...")

        except Exception as e:
            logger.error(f"[EMB_CACHE] Error setting cache: {e}")

    async def invalidate_model(self, model: str) -> int:
        """
        Invalidate all embeddings for a specific model.

        Args:
            model: Model name to invalidate

        Returns:
            Number of entries deleted
        """
        await self._ensure_tables()

        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM embedding_cache
                    WHERE model = ?
                """, (model,))

                await db.commit()
                count = cursor.rowcount

                logger.info(f"[EMB_CACHE] Invalidated {count} entries for model {model}")
                return count

        except Exception as e:
            logger.error(f"[EMB_CACHE] Error invalidating model: {e}")
            return 0

    async def clear(self) -> int:
        """
        Clear all cached embeddings.

        Returns:
            Number of entries deleted
        """
        await self._ensure_tables()

        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute("DELETE FROM embedding_cache")
                await db.commit()

                count = cursor.rowcount
                self._stats = CacheStats()  # Reset stats

                logger.info(f"[EMB_CACHE] Cleared {count} entries")
                return count

        except Exception as e:
            logger.error(f"[EMB_CACHE] Error clearing cache: {e}")
            return 0

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        await self._ensure_tables()

        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM embedding_cache
                    WHERE expires_at < datetime('now', 'utc')
                """)
                await db.commit()

                count = cursor.rowcount
                if count > 0:
                    logger.info(f"[EMB_CACHE] Cleaned up {count} expired entries")

                return count

        except Exception as e:
            logger.error(f"[EMB_CACHE] Error cleaning up: {e}")
            return 0

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats


# Global cache instance
_embedding_cache: EmbeddingCache | None = None


def get_embedding_cache(**kwargs) -> EmbeddingCache:
    """Get or create global embedding cache instance."""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache(**kwargs)
    return _embedding_cache
