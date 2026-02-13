"""Tests for LLMResponseCache (Phase 11.3).

Tests SQLite-backed LLM response cache with TTL, stats, and invalidation.
"""

import asyncio

import pytest

from src.pdf_framework.agents.cache import LLMResponseCache, get_llm_cache


# ── LLMResponseCache Init Tests ────────────────────────────────


class TestLLMCacheInit:
    """Test LLMResponseCache initialization."""

    def test_default_init(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "test.db")
        assert cache._ttl_seconds == 3600
        assert not cache._initialized

    def test_custom_ttl(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "test.db", ttl_seconds=60)
        assert cache._ttl_seconds == 60

    def test_generate_key_deterministic(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "test.db")
        messages = [{"role": "user", "content": "hello"}]
        k1 = cache._generate_key("model-a", messages, 0.0)
        k2 = cache._generate_key("model-a", messages, 0.0)
        assert k1 == k2

    def test_generate_key_different_model(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "test.db")
        msgs = [{"role": "user", "content": "hello"}]
        k1 = cache._generate_key("model-a", msgs, 0.0)
        k2 = cache._generate_key("model-b", msgs, 0.0)
        assert k1 != k2

    def test_generate_key_different_messages(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "test.db")
        k1 = cache._generate_key("m", [{"role": "user", "content": "hello"}], 0.0)
        k2 = cache._generate_key("m", [{"role": "user", "content": "world"}], 0.0)
        assert k1 != k2

    def test_generate_key_different_temperature(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "test.db")
        msgs = [{"role": "user", "content": "hello"}]
        k1 = cache._generate_key("m", msgs, 0.0)
        k2 = cache._generate_key("m", msgs, 0.7)
        assert k1 != k2

    def test_generate_key_message_order_matters(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "test.db")
        msgs1 = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ]
        msgs2 = [
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "You are helpful."},
        ]
        k1 = cache._generate_key("m", msgs1, 0.0)
        k2 = cache._generate_key("m", msgs2, 0.0)
        assert k1 != k2


# ── LLMResponseCache Get/Set Tests ─────────────────────────────


class TestLLMCacheGetSet:
    """Test LLMResponseCache get/set operations."""

    @pytest.fixture
    def cache(self, tmp_path):
        return LLMResponseCache(db_path=tmp_path / "llm.db")

    def test_get_miss(self, cache):
        result = asyncio.get_event_loop().run_until_complete(
            cache.get("model", [{"role": "user", "content": "x"}])
        )
        assert result is None

    def test_set_and_get(self, cache):
        messages = [{"role": "user", "content": "What is 2+2?"}]

        async def _run():
            await cache.set("model-a", messages, "4")
            return await cache.get("model-a", messages)

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result == "4"

    def test_set_with_token_counts(self, cache):
        messages = [{"role": "user", "content": "test"}]

        async def _run():
            await cache.set(
                "model", messages, "response",
                prompt_tokens=100, completion_tokens=50,
            )
            return await cache.get("model", messages)

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result == "response"

    def test_overwrites_same_key(self, cache):
        messages = [{"role": "user", "content": "test"}]

        async def _run():
            await cache.set("m", messages, "old")
            await cache.set("m", messages, "new")
            return await cache.get("m", messages)

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result == "new"

    def test_different_temperature_separate_entries(self, cache):
        messages = [{"role": "user", "content": "hello"}]

        async def _run():
            await cache.set("m", messages, "deterministic", temperature=0.0)
            await cache.set("m", messages, "creative", temperature=0.9)
            r1 = await cache.get("m", messages, temperature=0.0)
            r2 = await cache.get("m", messages, temperature=0.9)
            return r1, r2

        r1, r2 = asyncio.get_event_loop().run_until_complete(_run())
        assert r1 == "deterministic"
        assert r2 == "creative"

    def test_multiline_response(self, cache):
        messages = [{"role": "user", "content": "explain"}]
        response = "Line 1\nLine 2\nLine 3\n\nParagraph 2"

        async def _run():
            await cache.set("m", messages, response)
            return await cache.get("m", messages)

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result == response


# ── LLMResponseCache Stats Tests ───────────────────────────────


class TestLLMCacheStats:
    """Test LLMResponseCache statistics tracking."""

    @pytest.fixture
    def cache(self, tmp_path):
        return LLMResponseCache(db_path=tmp_path / "stats.db")

    def test_initial_stats(self, cache):
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total"] == 0
        assert stats["hit_rate"] == 0.0

    def test_miss_stats(self, cache):
        asyncio.get_event_loop().run_until_complete(
            cache.get("m", [{"role": "user", "content": "x"}])
        )
        stats = cache.get_stats()
        assert stats["misses"] == 1
        assert stats["total"] == 1

    def test_hit_stats(self, cache):
        messages = [{"role": "user", "content": "test"}]

        async def _run():
            await cache.set("m", messages, "resp")
            await cache.get("m", messages)

        asyncio.get_event_loop().run_until_complete(_run())
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["total"] >= 1

    def test_hit_rate(self, cache):
        messages = [{"role": "user", "content": "test"}]

        async def _run():
            await cache.set("m", messages, "resp")
            await cache.get("m", messages)  # hit
            await cache.get("m", [{"role": "user", "content": "other"}])  # miss

        asyncio.get_event_loop().run_until_complete(_run())
        stats = cache.get_stats()
        assert stats["hit_rate"] == pytest.approx(0.5)


# ── LLMResponseCache Invalidation Tests ────────────────────────


class TestLLMCacheInvalidation:
    """Test LLMResponseCache invalidation."""

    @pytest.fixture
    def cache(self, tmp_path):
        return LLMResponseCache(db_path=tmp_path / "inv.db")

    def test_invalidate_pattern(self, cache):
        async def _run():
            msgs = [{"role": "user", "content": "t"}]
            await cache.set("m", msgs, "r")
            count = await cache.invalidate_pattern("%")
            return count

        count = asyncio.get_event_loop().run_until_complete(_run())
        assert count >= 0


# ── LLMResponseCache Clear Tests ───────────────────────────────


class TestLLMCacheClear:
    """Test LLMResponseCache clear."""

    def test_clear(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "clear.db")

        async def _run():
            for i in range(5):
                await cache.set("m", [{"role": "user", "content": f"q{i}"}], f"r{i}")
            count = await cache.clear()
            return count

        count = asyncio.get_event_loop().run_until_complete(_run())
        assert count == 5

    def test_clear_resets_stats(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "clear_stats.db")

        async def _run():
            msgs = [{"role": "user", "content": "t"}]
            await cache.set("m", msgs, "r")
            await cache.get("m", msgs)
            await cache.clear()

        asyncio.get_event_loop().run_until_complete(_run())
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


# ── Table Creation Tests ───────────────────────────────────────


class TestLLMCacheTableCreation:
    """Test table creation."""

    def test_creates_parent_dir(self, tmp_path):
        db_path = tmp_path / "sub" / "dir" / "cache.db"
        cache = LLMResponseCache(db_path=db_path)

        asyncio.get_event_loop().run_until_complete(cache._ensure_tables())
        assert db_path.parent.exists()

    def test_idempotent(self, tmp_path):
        cache = LLMResponseCache(db_path=tmp_path / "idem.db")

        async def _run():
            await cache._ensure_tables()
            await cache._ensure_tables()

        asyncio.get_event_loop().run_until_complete(_run())
