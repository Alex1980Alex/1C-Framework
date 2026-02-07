"""LLM response cache for token savings (Phase 11).

Caches LLM responses for identical queries to save tokens and latency.

Author: Claude Code
Version: 1.2.0 - Phase 11.3: LLM Response Cache
"""

import aiosqlite
import hashlib
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LLMResponseCache:
    """
    Cache for LLM responses.

    Key: hash(model + system_prompt + user_prompt + temperature)
    Value: response text
    TTL: 1 hour (configurable)
    """

    def __init__(
        self,
        db_path: str | Path = "data/cache/llm_responses.db",
        ttl_seconds: int = 3600,
    ):
        """
        Initialize LLM response cache.

        Args:
            db_path: Path to SQLite database
            ttl_seconds: Time-to-live in seconds
        """
        self._db_path = Path(db_path)
        self._ttl_seconds = ttl_seconds
        self._initialized = False

        self._stats = {
            "hits": 0,
            "misses": 0,
            "total": 0,
        }

    async def _ensure_tables(self) -> None:
        """Create cache table if not exists."""
        if self._initialized:
            return

        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'utc')),
                    expires_at TIMESTAMP NOT NULL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER
                )
            """)

            # Index for TTL cleanup
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_cache_expires
                ON llm_cache(expires_at)
            """)

            await db.commit()

        self._initialized = True

    def _generate_key(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
    ) -> str:
        """Generate cache key from request parameters."""
        # Normalize messages for consistent hashing
        normalized_messages = json.dumps(messages, sort_keys=True)

        content = f"{model}:{temperature}:{normalized_messages}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
    ) -> str | None:
        """
        Get cached LLM response if available.

        Args:
            model: Model name
            messages: Message list (ChatAnthropic format)
            temperature: Temperature setting

        Returns:
            Cached response text or None
        """
        await self._ensure_tables()

        key = self._generate_key(model, messages, temperature)

        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row

                cursor = await db.execute("""
                    SELECT response, expires_at
                    FROM llm_cache
                    WHERE cache_key = ?
                    AND expires_at > datetime('now', 'utc')
                """, (key,))

                row = await cursor.fetchone()

                if row:
                    self._stats["hits"] += 1
                    self._stats["total"] += 1
                    logger.debug(f"[LLM_CACHE] Cache hit for key {key[:8]}...")
                    return row["response"]
                else:
                    self._stats["misses"] += 1
                    self._stats["total"] += 1
                    return None

        except Exception as e:
            logger.error(f"[LLM_CACHE] Error getting cache: {e}")
            self._stats["misses"] += 1
            self._stats["total"] += 1
            return None

    async def set(
        self,
        model: str,
        messages: list[dict],
        response: str,
        temperature: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """
        Store LLM response in cache.

        Args:
            model: Model name
            messages: Message list
            response: Response text
            temperature: Temperature setting
            prompt_tokens: Input token count
            completion_tokens: Output token count
        """
        await self._ensure_tables()

        key = self._generate_key(model, messages, temperature)

        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds)

        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO llm_cache
                    (cache_key, response, model, created_at, expires_at, prompt_tokens, completion_tokens)
                    VALUES (?, ?, ?, datetime('now', 'utc'), ?, ?, ?)
                """, (key, response, model, expires_at.isoformat(), prompt_tokens, completion_tokens))

                await db.commit()

                logger.debug(f"[LLM_CACHE] Cached response for key {key[:8]}...")

        except Exception as e:
            logger.error(f"[LLM_CACHE] Error setting cache: {e}")

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Args:
            pattern: SQL LIKE pattern for cache_key

        Returns:
            Number of entries deleted
        """
        await self._ensure_tables()

        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM llm_cache
                    WHERE cache_key LIKE ?
                """, (pattern,))

                await db.commit()

                count = cursor.rowcount
                logger.info(f"[LLM_CACHE] Invalidated {count} entries matching pattern '{pattern}'")
                return count

        except Exception as e:
            logger.error(f"[LLM_CACHE] Error invalidating pattern: {e}")
            return 0

    async def clear(self) -> int:
        """
        Clear all cached LLM responses.

        Returns:
            Number of entries deleted
        """
        await self._ensure_tables()

        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute("DELETE FROM llm_cache")
                await db.commit()

                count = cursor.rowcount
                self._stats = {"hits": 0, "misses": 0, "total": 0}

                logger.info(f"[LLM_CACHE] Cleared {count} entries")
                return count

        except Exception as e:
            logger.error(f"[LLM_CACHE] Error clearing cache: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "total": total,
            "hit_rate": hit_rate,
        }


# Global LLM cache instance
_llm_cache: LLMResponseCache | None = None


def get_llm_cache(**kwargs) -> LLMResponseCache:
    """Get or create global LLM cache instance."""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMResponseCache(**kwargs)
    return _llm_cache
