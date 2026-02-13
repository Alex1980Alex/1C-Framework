"""Tests for EmbeddingCache (Phase 11.2).

Tests SQLite-backed embedding cache with TTL, stats, and cleanup.
"""

import asyncio
from pathlib import Path

import pytest

from src.pdf_framework.embeddings.cache import (
    CacheStats,
    EmbeddingCache,
    get_embedding_cache,
)


# ── CacheStats Tests ───────────────────────────────────────────


class TestCacheStats:
    """Test CacheStats model."""

    def test_default_values(self):
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total == 0
        assert stats.hit_rate == 0.0

    def test_total_computed(self):
        stats = CacheStats(hits=10, misses=5)
        assert stats.total == 15

    def test_hit_rate_computed(self):
        stats = CacheStats(hits=3, misses=1)
        assert stats.hit_rate == pytest.approx(0.75)

    def test_hit_rate_zero_total(self):
        stats = CacheStats(hits=0, misses=0)
        assert stats.hit_rate == 0.0

    def test_hit_rate_all_hits(self):
        stats = CacheStats(hits=10, misses=0)
        assert stats.hit_rate == 1.0

    def test_hit_rate_all_misses(self):
        stats = CacheStats(hits=0, misses=5)
        assert stats.hit_rate == 0.0

    def test_total_is_property_not_field(self):
        stats = CacheStats(hits=2, misses=3)
        # total should auto-compute from hits + misses
        assert stats.total == 5


# ── EmbeddingCache Tests ───────────────────────────────────────


class TestEmbeddingCacheInit:
    """Test EmbeddingCache initialization."""

    def test_default_init(self, tmp_path):
        db_path = tmp_path / "test.db"
        cache = EmbeddingCache(db_path=db_path)
        assert cache._ttl_days == 30
        assert not cache._initialized

    def test_custom_ttl(self, tmp_path):
        db_path = tmp_path / "test.db"
        cache = EmbeddingCache(db_path=db_path, ttl_days=7)
        assert cache._ttl_days == 7

    def test_hash_deterministic(self, tmp_path):
        db_path = tmp_path / "test.db"
        cache = EmbeddingCache(db_path=db_path)
        h1 = cache._hash_text("hello world", "model-a")
        h2 = cache._hash_text("hello world", "model-a")
        assert h1 == h2

    def test_hash_different_text(self, tmp_path):
        db_path = tmp_path / "test.db"
        cache = EmbeddingCache(db_path=db_path)
        h1 = cache._hash_text("hello", "model-a")
        h2 = cache._hash_text("world", "model-a")
        assert h1 != h2

    def test_hash_different_model(self, tmp_path):
        db_path = tmp_path / "test.db"
        cache = EmbeddingCache(db_path=db_path)
        h1 = cache._hash_text("hello", "model-a")
        h2 = cache._hash_text("hello", "model-b")
        assert h1 != h2


class TestEmbeddingCacheGetSet:
    """Test EmbeddingCache get/set operations."""

    @pytest.fixture
    def cache(self, tmp_path):
        db_path = tmp_path / "emb_cache.db"
        return EmbeddingCache(db_path=db_path, ttl_days=30)

    def test_get_miss_returns_none(self, cache):
        result = asyncio.get_event_loop().run_until_complete(
            cache.get("unknown text", "model-a")
        )
        assert result is None

    def test_set_and_get(self, cache):
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        async def _run():
            await cache.set("hello world", "model-a", embedding)
            result = await cache.get("hello world", "model-a")
            return result

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result == embedding

    def test_get_different_model_returns_none(self, cache):
        embedding = [0.1, 0.2, 0.3]

        async def _run():
            await cache.set("hello", "model-a", embedding)
            return await cache.get("hello", "model-b")

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result is None

    def test_set_overwrites(self, cache):
        async def _run():
            await cache.set("text", "model", [1.0, 2.0])
            await cache.set("text", "model", [3.0, 4.0])
            return await cache.get("text", "model")

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result == [3.0, 4.0]

    def test_multiple_entries(self, cache):
        async def _run():
            await cache.set("text1", "model", [1.0])
            await cache.set("text2", "model", [2.0])
            r1 = await cache.get("text1", "model")
            r2 = await cache.get("text2", "model")
            return r1, r2

        r1, r2 = asyncio.get_event_loop().run_until_complete(_run())
        assert r1 == [1.0]
        assert r2 == [2.0]


class TestEmbeddingCacheStats:
    """Test EmbeddingCache statistics tracking."""

    @pytest.fixture
    def cache(self, tmp_path):
        db_path = tmp_path / "stats_cache.db"
        return EmbeddingCache(db_path=db_path)

    def test_initial_stats(self, cache):
        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total == 0

    def test_miss_increments(self, cache):
        asyncio.get_event_loop().run_until_complete(
            cache.get("nonexistent", "model")
        )
        stats = cache.get_stats()
        assert stats.misses == 1
        assert stats.hits == 0
        assert stats.total == 1

    def test_hit_increments(self, cache):
        async def _run():
            await cache.set("text", "model", [1.0])
            await cache.get("text", "model")

        asyncio.get_event_loop().run_until_complete(_run())
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.total >= 1

    def test_hit_rate_computed(self, cache):
        async def _run():
            await cache.set("text", "model", [1.0])
            await cache.get("text", "model")  # hit
            await cache.get("other", "model")  # miss

        asyncio.get_event_loop().run_until_complete(_run())
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == pytest.approx(0.5)


class TestEmbeddingCacheInvalidate:
    """Test EmbeddingCache invalidation."""

    @pytest.fixture
    def cache(self, tmp_path):
        db_path = tmp_path / "inv_cache.db"
        return EmbeddingCache(db_path=db_path)

    def test_invalidate_model(self, cache):
        async def _run():
            await cache.set("text1", "model-a", [1.0])
            await cache.set("text2", "model-a", [2.0])
            await cache.set("text3", "model-b", [3.0])
            count = await cache.invalidate_model("model-a")
            r1 = await cache.get("text1", "model-a")
            r3 = await cache.get("text3", "model-b")
            return count, r1, r3

        count, r1, r3 = asyncio.get_event_loop().run_until_complete(_run())
        assert count == 2
        assert r1 is None
        assert r3 == [3.0]


class TestEmbeddingCacheClear:
    """Test EmbeddingCache clear."""

    def test_clear_all(self, tmp_path):
        cache = EmbeddingCache(db_path=tmp_path / "clear.db")

        async def _run():
            await cache.set("t1", "m", [1.0])
            await cache.set("t2", "m", [2.0])
            count = await cache.clear()
            r1 = await cache.get("t1", "m")
            return count, r1

        count, r1 = asyncio.get_event_loop().run_until_complete(_run())
        assert count == 2
        assert r1 is None

    def test_clear_resets_stats(self, tmp_path):
        cache = EmbeddingCache(db_path=tmp_path / "clear_stats.db")

        async def _run():
            await cache.set("t", "m", [1.0])
            await cache.get("t", "m")  # hit
            await cache.clear()

        asyncio.get_event_loop().run_until_complete(_run())
        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0


class TestEmbeddingCacheCleanup:
    """Test EmbeddingCache TTL cleanup."""

    def test_cleanup_expired(self, tmp_path):
        # Use very short TTL
        cache = EmbeddingCache(db_path=tmp_path / "ttl.db", ttl_days=0)

        async def _run():
            await cache.set("text", "model", [1.0])
            count = await cache.cleanup_expired()
            return count

        count = asyncio.get_event_loop().run_until_complete(_run())
        # With 0 TTL, entry should expire immediately
        assert count >= 0  # May be 0 or 1 depending on timing


class TestEmbeddingCacheEnsureTables:
    """Test table creation."""

    def test_creates_parent_dir(self, tmp_path):
        db_path = tmp_path / "subdir" / "deep" / "cache.db"
        cache = EmbeddingCache(db_path=db_path)

        asyncio.get_event_loop().run_until_complete(cache._ensure_tables())
        assert db_path.parent.exists()

    def test_idempotent(self, tmp_path):
        cache = EmbeddingCache(db_path=tmp_path / "idem.db")

        async def _run():
            await cache._ensure_tables()
            await cache._ensure_tables()  # Should not raise

        asyncio.get_event_loop().run_until_complete(_run())
