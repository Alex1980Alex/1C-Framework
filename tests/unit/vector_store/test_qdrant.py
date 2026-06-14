"""Unit tests for Qdrant Vector Store — current public API.

Covers:
- F2.7.1: _to_qdrant_id module-level function (determinism, uniqueness, UUID format)
- F2.7.2: QdrantVectorStore.search_mmr — MMR selection logic (mocked client)
- F2.7.3: QdrantVectorStore._point_to_search_result — payload → SearchResult mapping
- F2.7.4: QdrantVectorStore.supports_native_bm25 / hybrid_search fallback
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides):
    """Build a VectorStoreSettings without touching the real env / .env file."""
    from src.pdf_framework.config.vector_store import VectorStoreSettings

    defaults = dict(
        provider="qdrant",
        dimensions=4,  # tiny — fast numpy ops
        qdrant_url="http://localhost:6333",
        qdrant_api_key="",
        collection_name="test_collection",
        qdrant_bm25_enabled=False,
    )
    defaults.update(overrides)
    # pydantic-settings: pass values directly, bypass env
    return VectorStoreSettings.model_construct(**defaults)


def _make_store(**settings_overrides):
    """Return an uninitialised QdrantVectorStore with mocked settings."""
    from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

    settings = _make_settings(**settings_overrides)
    store = QdrantVectorStore(settings=settings)
    return store


def _make_scored_point(point_id: str, score: float, vector=None, payload=None):
    """Build a minimal mock ScoredPoint compatible with _point_to_search_result / search_mmr."""
    p = MagicMock()
    p.id = point_id
    p.score = score
    p.vector = vector  # None, list[float], or dict
    p.payload = payload or {
        "original_id": point_id,
        "content": f"content of {point_id}",
        "document_id": "doc1",
        "page_number": 1,
        "section": "intro",
        "chunk_index": 0,
    }
    return p


# ---------------------------------------------------------------------------
# F2.7.1 — _to_qdrant_id  (module-level function)
# ---------------------------------------------------------------------------


class TestQdrantIDMapping:
    """Test _to_qdrant_id determinism and format (F2.7.1)."""

    def test_to_qdrant_id_is_deterministic(self):
        """Same string should always produce the same UUID."""
        from src.pdf_framework.vector_store.providers.qdrant import _to_qdrant_id

        assert _to_qdrant_id("test_chunk_123") == _to_qdrant_id("test_chunk_123")

    def test_to_qdrant_id_unique_for_different_inputs(self):
        """100 distinct strings should produce 100 distinct UUIDs."""
        from src.pdf_framework.vector_store.providers.qdrant import _to_qdrant_id

        ids = [_to_qdrant_id(f"chunk_{i}") for i in range(100)]
        assert len(set(ids)) == 100

    def test_to_qdrant_id_returns_valid_uuid_format(self):
        """Result must be a valid UUID string (parseable by uuid.UUID)."""
        from src.pdf_framework.vector_store.providers.qdrant import _to_qdrant_id

        result = _to_qdrant_id("arbitrary_string_id")
        parsed = uuid.UUID(result)  # raises if invalid
        assert str(parsed) == result

    def test_to_qdrant_id_passthrough_valid_uuid(self):
        """If input is already a valid UUID string, it must be returned as-is."""
        from src.pdf_framework.vector_store.providers.qdrant import _to_qdrant_id

        valid_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert _to_qdrant_id(valid_uuid) == valid_uuid

    def test_to_qdrant_id_non_uuid_string_yields_deterministic_uuid5(self):
        """Non-UUID strings must be converted via UUID5 (deterministic namespace)."""
        from src.pdf_framework.vector_store.providers.qdrant import _QDRANT_NS, _to_qdrant_id

        string_id = "pdf_doc_page_42"
        expected = str(uuid.uuid5(_QDRANT_NS, string_id))
        assert _to_qdrant_id(string_id) == expected


# ---------------------------------------------------------------------------
# F2.7.2 — search_mmr  (async, mocked qdrant client)
# ---------------------------------------------------------------------------


class TestQdrantMMR:
    """Test MMR selection behaviour in search_mmr (F2.7.2)."""

    def _make_initialized_store(self, has_sparse: bool = False):
        store = _make_store()
        store._initialized = True
        store._has_sparse = has_sparse
        store._client = AsyncMock()
        return store

    @pytest.mark.asyncio
    async def test_mmr_returns_k_results_when_enough_candidates(self):
        """search_mmr must return exactly k results when fetch_k > k candidates exist."""
        import numpy as np

        store = self._make_initialized_store()

        # 6 candidate points, each with a 4-dim dense vector
        candidates = [
            _make_scored_point(f"p{i}", float(6 - i), vector=[1.0 - i * 0.1, 0.0, 0.0, 0.0])
            for i in range(6)
        ]
        # Normalize vectors to unit length manually for clean cosine sims
        for p in candidates:
            v = np.array(p.vector, dtype=float)
            nv = v / (np.linalg.norm(v) + 1e-10)
            p.vector = nv.tolist()

        mock_result = MagicMock()
        mock_result.points = candidates
        store._client.query_points = AsyncMock(return_value=mock_result)

        query = [1.0, 0.0, 0.0, 0.0]
        results = await store.search_mmr(query_embedding=query, k=3, fetch_k=6, lambda_mult=0.5)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_mmr_diversifies_by_selecting_orthogonal_vector(self):
        """With lambda=0, diversity wins — orthogonal vector should be selected."""
        store = self._make_initialized_store()

        # 3 candidates: two near-identical, one orthogonal
        near1 = [1.0, 0.0, 0.0, 0.0]
        near2 = [0.99, 0.14, 0.0, 0.0]
        orth = [0.0, 0.0, 1.0, 0.0]

        candidates = [
            _make_scored_point("near1", 0.99, vector=near1),
            _make_scored_point("near2", 0.98, vector=near2),
            _make_scored_point("orth", 0.50, vector=orth),
        ]

        mock_result = MagicMock()
        mock_result.points = candidates
        store._client.query_points = AsyncMock(return_value=mock_result)

        query = [1.0, 0.0, 0.0, 0.0]
        # lambda=0 → pure diversity after first pick
        results = await store.search_mmr(query_embedding=query, k=2, fetch_k=3, lambda_mult=0.0)

        ids = [r.chunk.id for r in results]
        # First pick is most-relevant (near1), second should be orthogonal
        assert ids[0] == "near1"
        assert ids[1] == "orth"

    @pytest.mark.asyncio
    async def test_mmr_returns_all_when_candidates_leq_k(self):
        """If candidates <= k, all are returned without MMR selection."""
        store = self._make_initialized_store()

        candidates = [
            _make_scored_point("a", 0.9, vector=[1.0, 0.0, 0.0, 0.0]),
            _make_scored_point("b", 0.8, vector=[0.0, 1.0, 0.0, 0.0]),
        ]

        mock_result = MagicMock()
        mock_result.points = candidates
        store._client.query_points = AsyncMock(return_value=mock_result)

        results = await store.search_mmr(query_embedding=[1.0, 0.0, 0.0, 0.0], k=5, fetch_k=10)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_mmr_handles_named_vectors_dict(self):
        """MMR must extract 'dense' key from named-vector dict (BM25 collection layout)."""
        store = self._make_initialized_store(has_sparse=True)

        dense_a = [1.0, 0.0, 0.0, 0.0]
        dense_b = [0.0, 1.0, 0.0, 0.0]
        dense_c = [0.0, 0.0, 1.0, 0.0]

        candidates = [
            _make_scored_point("a", 0.9, vector={"dense": dense_a, "bm25": {}}),
            _make_scored_point("b", 0.7, vector={"dense": dense_b, "bm25": {}}),
            _make_scored_point("c", 0.5, vector={"dense": dense_c, "bm25": {}}),
        ]

        mock_result = MagicMock()
        mock_result.points = candidates
        store._client.query_points = AsyncMock(return_value=mock_result)

        results = await store.search_mmr(query_embedding=dense_a, k=2, fetch_k=3, lambda_mult=0.5)

        assert len(results) == 2
        # Result objects should be valid SearchResults
        from src.pdf_framework.schemas.documents import SearchResult

        assert all(isinstance(r, SearchResult) for r in results)


# ---------------------------------------------------------------------------
# F2.7.3 — _point_to_search_result  (sync helper, no I/O)
# ---------------------------------------------------------------------------


class TestPointToSearchResult:
    """Test payload→SearchResult mapping (F2.7.3)."""

    def test_full_payload_maps_correctly(self):
        """All standard fields must be present in the returned SearchResult."""
        from src.pdf_framework.schemas.documents import SearchResult
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = _make_store()
        point = _make_scored_point(
            "chunk_42",
            score=0.87,
            payload={
                "original_id": "chunk_42",
                "content": "hello world",
                "document_id": "doc_001",
                "page_number": 3,
                "section": "abstract",
                "chunk_index": 7,
                "extra_meta": "foo",
            },
        )

        result = store._point_to_search_result(point)

        assert isinstance(result, SearchResult)
        assert result.score == pytest.approx(0.87)
        assert result.source == "qdrant"
        assert result.chunk.id == "chunk_42"
        assert result.chunk.content == "hello world"
        assert result.chunk.document_id == "doc_001"
        assert result.chunk.page_number == 3
        assert result.chunk.section == "abstract"
        assert result.chunk.chunk_index == 7
        # Extra fields land in metadata, not in standard fields
        assert result.chunk.metadata.get("extra_meta") == "foo"

    def test_missing_original_id_falls_back_to_point_id(self):
        """If payload has no original_id, point.id is used as chunk id."""
        store = _make_store()
        point = MagicMock()
        point.id = "qdrant-uuid-xyz"
        point.score = 0.5
        point.payload = {"content": "text", "document_id": "d"}

        result = store._point_to_search_result(point)

        assert result.chunk.id == "qdrant-uuid-xyz"

    def test_zero_page_number_becomes_none(self):
        """page_number=0 in payload should yield chunk.page_number=None."""
        store = _make_store()
        point = _make_scored_point(
            "x",
            0.5,
            payload={"original_id": "x", "content": "", "document_id": "", "page_number": 0},
        )

        result = store._point_to_search_result(point)

        assert result.chunk.page_number is None

    def test_standard_payload_fields_excluded_from_metadata(self):
        """Standard fields (content, document_id, etc.) must NOT appear in chunk.metadata."""
        from src.pdf_framework.vector_store.providers.qdrant import _STANDARD_PAYLOAD_FIELDS

        store = _make_store()
        payload = {
            "original_id": "id1",
            "content": "text",
            "document_id": "doc",
            "page_number": 1,
            "section": "s",
            "chunk_index": 0,
            "custom_tag": "keep_me",
        }
        point = _make_scored_point("id1", 0.6, payload=payload)

        result = store._point_to_search_result(point)

        for field in _STANDARD_PAYLOAD_FIELDS:
            assert field not in result.chunk.metadata
        assert result.chunk.metadata.get("custom_tag") == "keep_me"


# ---------------------------------------------------------------------------
# F2.7.4 — supports_native_bm25 + hybrid_search fallback
# ---------------------------------------------------------------------------


class TestQdrantBM25Support:
    """Test BM25 flag and hybrid fallback (F2.7.4)."""

    def test_supports_native_bm25_false_by_default(self):
        """Fresh (uninitialised) store has _has_sparse=False."""
        store = _make_store()
        assert store.supports_native_bm25() is False

    def test_supports_native_bm25_true_after_flag_set(self):
        """If _has_sparse is set to True, supports_native_bm25() must return True."""
        store = _make_store()
        store._has_sparse = True
        assert store.supports_native_bm25() is True

    @pytest.mark.asyncio
    async def test_hybrid_search_falls_back_to_dense_when_no_sparse(self):
        """hybrid_search must delegate to search() when _has_sparse is False."""
        store = _make_store()
        store._initialized = True
        store._has_sparse = False
        store._client = AsyncMock()

        dense_results = [_make_scored_point("a", 0.9)]
        mock_result = MagicMock()
        mock_result.points = dense_results
        store._client.query_points = AsyncMock(return_value=mock_result)

        results = await store.hybrid_search(
            query_embedding=[1.0, 0.0, 0.0, 0.0],
            query_text="hello",
            k=5,
        )

        # Should have called query_points (via search()) and returned results
        assert store._client.query_points.called
        assert len(results) == 1
        assert results[0].chunk.id == "a"
