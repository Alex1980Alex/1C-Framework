"""Phase 17: Semantic Search Cache tests.

Tests SemanticSearchCache: init, get/set, similarity matching,
parameter matching, eviction, invalidation, stats.
"""

import numpy as np
import pytest

from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)
from src.pdf_framework.search.semantic_cache import SemanticSearchCache


def _make_embedding(dim: int = 64, seed: int = 0) -> list[float]:
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    vec /= np.linalg.norm(vec)  # normalize
    return vec.tolist()


def _make_response(query: str = "test", n_results: int = 2, doc_id: str = "d1") -> SearchResponse:
    results = [
        SearchResult(
            chunk=DocumentChunk(
                id=f"chunk_{i}", content=f"Content {i}", document_id=doc_id,
            ),
            score=1.0 - i * 0.1,
            source="vector",
        )
        for i in range(n_results)
    ]
    return SearchResponse(
        query=query, results=results, total_found=n_results, search_type="vector",
    )


@pytest.fixture
def cache(tmp_path):
    return SemanticSearchCache(
        db_path=tmp_path / "test_cache.db",
        similarity_threshold=0.95,
        ttl_seconds=3600,
        max_entries=100,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestSemanticCacheInit:
    @pytest.mark.asyncio
    async def test_initialize_creates_db(self, cache):
        await cache.initialize()
        stats = cache.get_stats()
        assert stats["entries"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_double_initialize_safe(self, cache):
        await cache.initialize()
        await cache.initialize()
        assert cache.get_stats()["entries"] == 0


# ---------------------------------------------------------------------------
# Set and Get
# ---------------------------------------------------------------------------

class TestSetAndGet:
    @pytest.mark.asyncio
    async def test_set_then_get_exact_match(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response("test query")

        await cache.set("test query", emb, "vector", 5, None, True, resp)

        # Exact same embedding → should hit
        cached = await cache.get(emb, "vector", 5, None, True)
        assert cached is not None
        assert cached.metadata.get("cache_hit") is True
        assert len(cached.results) == 2

    @pytest.mark.asyncio
    async def test_get_miss_on_empty_cache(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=1)
        cached = await cache.get(emb, "vector", 5, None, True)
        assert cached is None

    @pytest.mark.asyncio
    async def test_get_miss_below_threshold(self, cache):
        await cache.initialize()
        emb1 = _make_embedding(seed=1)
        emb2 = _make_embedding(seed=999)  # very different
        resp = _make_response()

        await cache.set("q1", emb1, "vector", 5, None, True, resp)
        cached = await cache.get(emb2, "vector", 5, None, True)
        assert cached is None

    @pytest.mark.asyncio
    async def test_similar_embedding_hits(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response()

        await cache.set("query", emb, "vector", 5, None, True, resp)

        # Slightly perturb the embedding (should still be > 0.95 similar)
        perturbed = np.array(emb, dtype=np.float32)
        perturbed += np.random.RandomState(0).randn(len(emb)).astype(np.float32) * 0.01
        perturbed /= np.linalg.norm(perturbed)

        sim = float(np.dot(np.array(emb), perturbed))
        if sim >= 0.95:
            cached = await cache.get(perturbed.tolist(), "vector", 5, None, True)
            assert cached is not None


# ---------------------------------------------------------------------------
# Parameter matching
# ---------------------------------------------------------------------------

class TestParameterMatching:
    @pytest.mark.asyncio
    async def test_strategy_mismatch(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response()

        await cache.set("q", emb, "vector", 5, None, True, resp)
        cached = await cache.get(emb, "hybrid", 5, None, True)
        assert cached is None  # strategy mismatch

    @pytest.mark.asyncio
    async def test_rerank_mismatch(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response()

        await cache.set("q", emb, "vector", 5, None, True, resp)
        cached = await cache.get(emb, "vector", 5, None, False)
        assert cached is None  # rerank mismatch

    @pytest.mark.asyncio
    async def test_filter_mismatch(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response()

        await cache.set("q", emb, "vector", 5, {"source": "a.pdf"}, True, resp)
        cached = await cache.get(emb, "vector", 5, {"source": "b.pdf"}, True)
        assert cached is None  # filter mismatch

    @pytest.mark.asyncio
    async def test_cached_k_greater_serves_smaller_k(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response(n_results=5)

        await cache.set("q", emb, "vector", 5, None, True, resp)
        # Request k=3 → should hit (cached k=5 >= 3) and trim
        cached = await cache.get(emb, "vector", 3, None, True)
        assert cached is not None
        assert len(cached.results) == 3

    @pytest.mark.asyncio
    async def test_cached_k_smaller_misses(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response(n_results=3)

        await cache.set("q", emb, "vector", 3, None, True, resp)
        # Request k=5 → should miss (cached k=3 < 5)
        cached = await cache.get(emb, "vector", 5, None, True)
        assert cached is None


# ---------------------------------------------------------------------------
# Filter hashing
# ---------------------------------------------------------------------------

class TestFilterHash:
    def test_none_filter(self):
        assert SemanticSearchCache._hash_filter(None) == "none"

    def test_empty_dict(self):
        assert SemanticSearchCache._hash_filter({}) == "none"

    def test_deterministic(self):
        h1 = SemanticSearchCache._hash_filter({"a": 1, "b": 2})
        h2 = SemanticSearchCache._hash_filter({"b": 2, "a": 1})
        assert h1 == h2  # sort_keys makes it deterministic

    def test_different_filters_different_hash(self):
        h1 = SemanticSearchCache._hash_filter({"a": 1})
        h2 = SemanticSearchCache._hash_filter({"a": 2})
        assert h1 != h2


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------

class TestEviction:
    @pytest.mark.asyncio
    async def test_eviction_when_over_max(self, tmp_path):
        cache = SemanticSearchCache(
            db_path=tmp_path / "evict.db",
            max_entries=3,
            ttl_seconds=3600,
        )
        await cache.initialize()

        for i in range(5):
            emb = _make_embedding(seed=i)
            resp = _make_response(query=f"q{i}", doc_id=f"d{i}")
            await cache.set(f"q{i}", emb, "vector", 5, None, True, resp)

        stats = cache.get_stats()
        assert stats["entries"] <= 3


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------

class TestInvalidation:
    @pytest.mark.asyncio
    async def test_invalidate_by_document(self, cache):
        await cache.initialize()

        emb1 = _make_embedding(seed=1)
        emb2 = _make_embedding(seed=2)
        resp1 = _make_response(doc_id="doc_A")
        resp2 = _make_response(doc_id="doc_B")

        await cache.set("q1", emb1, "vector", 5, None, True, resp1)
        await cache.set("q2", emb2, "vector", 5, None, True, resp2)

        assert cache.get_stats()["entries"] == 2

        removed = await cache.invalidate_by_document("doc_A")
        assert removed == 1
        assert cache.get_stats()["entries"] == 1

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_document(self, cache):
        await cache.initialize()
        removed = await cache.invalidate_by_document("nonexistent")
        assert removed == 0

    @pytest.mark.asyncio
    async def test_invalidate_all(self, cache):
        await cache.initialize()

        for i in range(3):
            emb = _make_embedding(seed=i)
            resp = _make_response(doc_id=f"d{i}")
            await cache.set(f"q{i}", emb, "vector", 5, None, True, resp)

        assert cache.get_stats()["entries"] == 3

        removed = await cache.invalidate_all()
        assert removed == 3
        assert cache.get_stats()["entries"] == 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    @pytest.mark.asyncio
    async def test_stats_tracking(self, cache):
        await cache.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response()

        await cache.set("q", emb, "vector", 5, None, True, resp)

        # Miss (different embedding)
        await cache.get(_make_embedding(seed=999), "vector", 5, None, True)

        # Hit (same embedding)
        await cache.get(emb, "vector", 5, None, True)

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(0.5)
        assert stats["entries"] == 1
        assert stats["threshold"] == 0.95

    @pytest.mark.asyncio
    async def test_stats_zero_division(self, cache):
        await cache.initialize()
        stats = cache.get_stats()
        assert stats["hit_rate"] == 0.0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    @pytest.mark.asyncio
    async def test_reload_from_sqlite(self, tmp_path):
        db_path = tmp_path / "persist.db"

        # Write
        cache1 = SemanticSearchCache(db_path=db_path, ttl_seconds=3600)
        await cache1.initialize()
        emb = _make_embedding(seed=42)
        resp = _make_response()
        await cache1.set("q", emb, "vector", 5, None, True, resp)
        assert cache1.get_stats()["entries"] == 1

        # Reload in new instance
        cache2 = SemanticSearchCache(db_path=db_path, ttl_seconds=3600)
        await cache2.initialize()
        assert cache2.get_stats()["entries"] == 1

        # Should hit
        cached = await cache2.get(emb, "vector", 5, None, True)
        assert cached is not None


# ---------------------------------------------------------------------------
# SearchManager integration with semantic cache
# ---------------------------------------------------------------------------

class TestSearchManagerCacheIntegration:
    @pytest.mark.asyncio
    async def test_cache_pre_check_and_post_write(self, cache):
        """Verify manager writes to cache on miss and reads on hit."""
        from unittest.mock import AsyncMock

        from src.pdf_framework.search.manager import SearchManager

        await cache.initialize()

        mock_embedding_engine = AsyncMock()
        mock_embedding_engine.embed_text = AsyncMock(return_value=_make_embedding(seed=42))

        manager = SearchManager(
            embedding_engine=mock_embedding_engine,
            semantic_cache=cache,
        )

        mock_strategy = AsyncMock()
        mock_strategy.search = AsyncMock(return_value=_make_response())
        manager.register_strategy("vector", mock_strategy)

        # First search → cache miss → calls strategy → writes cache
        r1 = await manager.search("test", strategy="vector", k=5, rerank=False)
        assert mock_strategy.search.call_count == 1

        # Second search → cache hit → does NOT call strategy
        r2 = await manager.search("test", strategy="vector", k=5, rerank=False)
        assert mock_strategy.search.call_count == 1  # still 1
        assert r2.metadata.get("cache_hit") is True
