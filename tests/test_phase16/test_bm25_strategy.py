"""Phase 16: BM25 Search Strategy tests.

Tests BM25SearchStrategy: search, score normalization, metadata filtering.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.schemas.documents import DocumentChunk, SearchResponse
from src.pdf_framework.search.strategies.bm25_search import BM25SearchStrategy


def _make_mock_bm25(results: list[tuple[str, float]]):
    store = AsyncMock()
    store.search = AsyncMock(return_value=results)
    return store


def _make_mock_vector_store(chunks: dict[str, DocumentChunk]):
    store = MagicMock()
    collection = MagicMock()

    def mock_get(ids, include=None):
        found_ids = [cid for cid in ids if cid in chunks]
        return {
            "ids": found_ids,
            "documents": [chunks[cid].content for cid in found_ids],
            "metadatas": [
                {
                    "document_id": chunks[cid].document_id,
                    "page_number": str(chunks[cid].page_number or 0),
                    "section": chunks[cid].section,
                    "chunk_index": str(chunks[cid].chunk_index),
                    **chunks[cid].metadata,
                }
                for cid in found_ids
            ],
        }

    collection.get = mock_get
    store.collection = collection
    return store


@pytest.fixture
def sample_chunks():
    return {
        "c1": DocumentChunk(
            id="c1", content="Регистр накопления", document_id="d1",
            page_number=1, chunk_index=0, metadata={"source": "a.pdf"},
        ),
        "c2": DocumentChunk(
            id="c2", content="Справочник номенклатуры", document_id="d1",
            page_number=2, chunk_index=1, metadata={"source": "a.pdf"},
        ),
        "c3": DocumentChunk(
            id="c3", content="Регистр сведений", document_id="d2",
            page_number=1, chunk_index=0, metadata={"source": "b.pdf"},
        ),
    }


class TestBM25SearchStrategy:
    @pytest.mark.asyncio
    async def test_basic_search_returns_results(self, sample_chunks):
        bm25 = _make_mock_bm25([("c1", -10.0), ("c3", -5.0)])
        vs = _make_mock_vector_store(sample_chunks)
        strategy = BM25SearchStrategy(bm25, vs)

        response = await strategy.search("регистр", k=5)

        assert isinstance(response, SearchResponse)
        assert response.search_type == "bm25"
        assert len(response.results) == 2
        assert response.results[0].chunk.id == "c1"

    @pytest.mark.asyncio
    async def test_score_normalization(self, sample_chunks):
        bm25 = _make_mock_bm25([("c1", -10.0), ("c2", -5.0)])
        vs = _make_mock_vector_store(sample_chunks)
        strategy = BM25SearchStrategy(bm25, vs)

        response = await strategy.search("test", k=5)

        # Best score should be 1.0 (normalized)
        assert response.results[0].score == 1.0
        # Second should be 0.5 (5/10)
        assert response.results[1].score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_empty_query(self, sample_chunks):
        bm25 = _make_mock_bm25([])
        vs = _make_mock_vector_store(sample_chunks)
        strategy = BM25SearchStrategy(bm25, vs)

        response = await strategy.search("", k=5)
        assert len(response.results) == 0
        assert response.total_found == 0

    @pytest.mark.asyncio
    async def test_respects_k_limit(self, sample_chunks):
        bm25 = _make_mock_bm25([("c1", -10.0), ("c2", -8.0), ("c3", -5.0)])
        vs = _make_mock_vector_store(sample_chunks)
        strategy = BM25SearchStrategy(bm25, vs)

        response = await strategy.search("test", k=2)
        assert len(response.results) <= 2

    @pytest.mark.asyncio
    async def test_metadata_filter(self, sample_chunks):
        bm25 = _make_mock_bm25([("c1", -10.0), ("c2", -8.0), ("c3", -5.0)])
        vs = _make_mock_vector_store(sample_chunks)
        strategy = BM25SearchStrategy(bm25, vs)

        response = await strategy.search("test", k=5, filter={"source": "b.pdf"})
        assert len(response.results) == 1
        assert response.results[0].chunk.id == "c3"

    @pytest.mark.asyncio
    async def test_missing_chunk_in_vector_store(self):
        bm25 = _make_mock_bm25([("c1", -10.0), ("missing", -5.0)])
        chunks = {
            "c1": DocumentChunk(
                id="c1", content="Текст", document_id="d1",
                metadata={"source": "s"},
            ),
        }
        vs = _make_mock_vector_store(chunks)
        strategy = BM25SearchStrategy(bm25, vs)

        response = await strategy.search("test", k=5)
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_elapsed_ms_set(self, sample_chunks):
        bm25 = _make_mock_bm25([("c1", -10.0)])
        vs = _make_mock_vector_store(sample_chunks)
        strategy = BM25SearchStrategy(bm25, vs)

        response = await strategy.search("test", k=5)
        assert response.elapsed_ms > 0


class TestMatchesFilter:
    def test_matching_filter(self):
        chunk = DocumentChunk(
            id="c1", content="x", document_id="d1",
            metadata={"source": "a.pdf", "type": "text"},
        )
        assert BM25SearchStrategy._matches_filter(chunk, {"source": "a.pdf"})

    def test_non_matching_filter(self):
        chunk = DocumentChunk(
            id="c1", content="x", document_id="d1",
            metadata={"source": "a.pdf"},
        )
        assert not BM25SearchStrategy._matches_filter(chunk, {"source": "b.pdf"})

    def test_empty_filter_matches_all(self):
        chunk = DocumentChunk(id="c1", content="x", document_id="d1")
        assert BM25SearchStrategy._matches_filter(chunk, {})


class TestSafeInt:
    def test_normal_int(self):
        assert BM25SearchStrategy._safe_int(42) == 42

    def test_string_int(self):
        assert BM25SearchStrategy._safe_int("5") == 5

    def test_none_returns_default(self):
        assert BM25SearchStrategy._safe_int(None) == 0

    def test_none_string_returns_default(self):
        assert BM25SearchStrategy._safe_int("None") == 0

    def test_empty_string_returns_default(self):
        assert BM25SearchStrategy._safe_int("") == 0

    def test_invalid_string_returns_default(self):
        assert BM25SearchStrategy._safe_int("abc") == 0
