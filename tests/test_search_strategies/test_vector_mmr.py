"""Unit tests for VectorSearchStrategy and MMRSearchStrategy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult
from src.pdf_framework.search.strategies.mmr_search import MMRSearchStrategy
from src.pdf_framework.search.strategies.vector_search import VectorSearchStrategy

pytestmark = pytest.mark.unit

_FAKE_EMBEDDING = [0.1] * 4096


def _make_chunk(chunk_id: str = "c1") -> DocumentChunk:
    return DocumentChunk(id=chunk_id, content="sample content", document_id="doc1")


def _make_result(chunk_id: str, score: float = 0.9) -> SearchResult:
    return SearchResult(chunk=_make_chunk(chunk_id), score=score)


def _make_engine(embedding: list[float] | None = None) -> AsyncMock:
    engine = AsyncMock()
    engine.embed_text.return_value = embedding or _FAKE_EMBEDDING
    return engine


def _make_store(results: list[SearchResult] | None = None) -> AsyncMock:
    store = AsyncMock()
    store.search.return_value = results or []
    store.search_mmr.return_value = results or []
    return store


# ---------------------------------------------------------------------------
# VectorSearchStrategy
# ---------------------------------------------------------------------------


class TestVectorSearchBasic:
    @pytest.mark.asyncio
    async def test_returns_search_response(self) -> None:
        strategy = VectorSearchStrategy(_make_engine(), _make_store())
        resp = await strategy.search("query")
        assert resp.query == "query"
        assert resp.search_type == "vector"

    @pytest.mark.asyncio
    async def test_results_forwarded(self) -> None:
        store = _make_store([_make_result("c1", 0.9), _make_result("c2", 0.7)])
        strategy = VectorSearchStrategy(_make_engine(), store)
        resp = await strategy.search("query")
        assert len(resp.results) == 2
        assert resp.total_found == 2

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        strategy = VectorSearchStrategy(_make_engine(), _make_store([]))
        resp = await strategy.search("query")
        assert resp.results == []
        assert resp.total_found == 0

    @pytest.mark.asyncio
    async def test_elapsed_ms_non_negative(self) -> None:
        strategy = VectorSearchStrategy(_make_engine(), _make_store())
        resp = await strategy.search("query")
        assert resp.elapsed_ms >= 0.0

    @pytest.mark.asyncio
    async def test_embed_text_called_with_query(self) -> None:
        engine = _make_engine()
        strategy = VectorSearchStrategy(engine, _make_store())
        await strategy.search("my query")
        engine.embed_text.assert_awaited_once_with("my query")

    @pytest.mark.asyncio
    async def test_store_search_receives_k(self) -> None:
        store = _make_store()
        strategy = VectorSearchStrategy(_make_engine(), store)
        await strategy.search("query", k=7)
        _, kwargs = store.search.call_args
        assert kwargs.get("k") == 7 or store.search.call_args[0][1] == 7

    @pytest.mark.asyncio
    async def test_store_search_receives_filter(self) -> None:
        store = _make_store()
        strategy = VectorSearchStrategy(_make_engine(), store)
        filt = {"source": "manual.pdf"}
        await strategy.search("query", filter=filt)
        call_kwargs = store.search.call_args[1]
        assert call_kwargs.get("filter") == filt


class TestVectorSearchMMRMode:
    @pytest.mark.asyncio
    async def test_use_mmr_calls_search_mmr(self) -> None:
        store = _make_store([_make_result("c1")])
        strategy = VectorSearchStrategy(_make_engine(), store)
        resp = await strategy.search("query", use_mmr=True)
        store.search_mmr.assert_awaited_once()
        store.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_default_no_mmr_calls_plain_search(self) -> None:
        store = _make_store([_make_result("c1")])
        strategy = VectorSearchStrategy(_make_engine(), store)
        await strategy.search("query")
        store.search.assert_awaited_once()
        store.search_mmr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_use_mmr_false_calls_plain_search(self) -> None:
        store = _make_store([_make_result("c1")])
        strategy = VectorSearchStrategy(_make_engine(), store)
        await strategy.search("query", use_mmr=False)
        store.search.assert_awaited_once()
        store.search_mmr.assert_not_awaited()


# ---------------------------------------------------------------------------
# MMRSearchStrategy
# ---------------------------------------------------------------------------


class TestMMRSearchBasic:
    @pytest.mark.asyncio
    async def test_returns_search_response(self) -> None:
        strategy = MMRSearchStrategy(_make_engine(), _make_store())
        resp = await strategy.search("query")
        assert resp.query == "query"
        assert resp.search_type == "mmr"

    @pytest.mark.asyncio
    async def test_results_forwarded(self) -> None:
        results = [_make_result("c1", 0.95), _make_result("c2", 0.8)]
        strategy = MMRSearchStrategy(_make_engine(), _make_store(results))
        resp = await strategy.search("query")
        assert len(resp.results) == 2
        assert resp.total_found == 2

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        strategy = MMRSearchStrategy(_make_engine(), _make_store([]))
        resp = await strategy.search("query")
        assert resp.results == []
        assert resp.total_found == 0

    @pytest.mark.asyncio
    async def test_elapsed_ms_non_negative(self) -> None:
        strategy = MMRSearchStrategy(_make_engine(), _make_store())
        resp = await strategy.search("query")
        assert resp.elapsed_ms >= 0.0

    @pytest.mark.asyncio
    async def test_always_calls_search_mmr(self) -> None:
        store = _make_store()
        strategy = MMRSearchStrategy(_make_engine(), store)
        await strategy.search("query")
        store.search_mmr.assert_awaited_once()
        store.search.assert_not_awaited()


class TestMMRSearchDiversity:
    @pytest.mark.asyncio
    async def test_diversity_override_passed_as_lambda_mult(self) -> None:
        store = _make_store()
        strategy = MMRSearchStrategy(_make_engine(), store)
        await strategy.search("query", diversity=0.3)
        call_kwargs = store.search_mmr.call_args[1]
        assert call_kwargs.get("lambda_mult") == pytest.approx(0.3)

    @pytest.mark.asyncio
    async def test_no_diversity_override_uses_default(self) -> None:
        from src.pdf_framework.config import SearchSettings

        settings = SearchSettings()
        store = _make_store()
        strategy = MMRSearchStrategy(_make_engine(), store, search_settings=settings)
        await strategy.search("query")
        call_kwargs = store.search_mmr.call_args[1]
        assert call_kwargs.get("lambda_mult") == pytest.approx(settings.mmr_diversity_lambda)

    @pytest.mark.asyncio
    async def test_diversity_1_passes_as_pure_relevance(self) -> None:
        store = _make_store()
        strategy = MMRSearchStrategy(_make_engine(), store)
        await strategy.search("query", diversity=1.0)
        call_kwargs = store.search_mmr.call_args[1]
        assert call_kwargs.get("lambda_mult") == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_diversity_0_passes_as_max_diversity(self) -> None:
        store = _make_store()
        strategy = MMRSearchStrategy(_make_engine(), store)
        await strategy.search("query", diversity=0.0)
        call_kwargs = store.search_mmr.call_args[1]
        assert call_kwargs.get("lambda_mult") == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_k_passed_to_search_mmr(self) -> None:
        store = _make_store()
        strategy = MMRSearchStrategy(_make_engine(), store)
        await strategy.search("query", k=3)
        call_kwargs = store.search_mmr.call_args[1]
        assert call_kwargs.get("k") == 3
