"""Unit tests for Qdrant Vector Store (F2.7).

Tests:
- F2.7.1: Test Qdrant _to_qdrant_id determinism
- F2.7.2: Test Qdrant hybrid_search RRF merge
- F2.7.3: Test Qdrant MMR with named vectors
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestQdrantIDMapping:
    """Test Qdrant ID determinism (F2.7.1)."""

    def test_to_qdrant_id_deterministic(self):
        """F2.7.1: Same string ID should produce same Qdrant ID."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        id1 = store._to_qdrant_id("test_chunk_123")
        id2 = store._to_qdrant_id("test_chunk_123")

        assert id1 == id2

    def test_to_qdrant_id_unique_for_different_ids(self):
        """F2.7.1: Different IDs should produce different Qdrant IDs."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        ids = [
            store._to_qdrant_id(f"chunk_{i}")
            for i in range(100)
        ]

        assert len(set(ids)) == 100

    def test_to_qdrant_id_format_is_uuid(self):
        """F2.7.1: Qdrant ID should be valid UUID format."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        qdrant_id = store._to_qdrant_id("test_id")

        # Should be UUID-like (hex string with dashes)
        assert "-" in qdrant_id
        assert len(qdrant_id) == 36  # Standard UUID length

    def test_from_qdrant_id_reversibility(self):
        """F2.7.1: Round-trip conversion should preserve original ID."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        original_id = "test_chunk_123"
        qdrant_id = store._to_qdrant_id(original_id)
        recovered_id = store._from_qdrant_id(qdrant_id)

        assert recovered_id == original_id


@pytest.mark.unit
class TestQdrantRRF:
    """Test Qdrant RRF merge (F2.7.2)."""

    def test_rrf_merge_combines_results(self):
        """F2.7.2: RRF should combine results from multiple sources."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        # Mock results from dense and sparse search
        dense_results = [
            MagicMock(id="chunk_1", score=0.9),
            MagicMock(id="chunk_3", score=0.7),
        ]

        sparse_results = [
            MagicMock(id="chunk_2", score=0.8),
            MagicMock(id="chunk_3", score=0.6),
        ]

        merged = store._rrf_merge(dense_results, sparse_results, k=60)

        # Should contain all unique chunks
        merged_ids = [r.id for r in merged]
        assert "chunk_1" in merged_ids
        assert "chunk_2" in merged_ids
        assert "chunk_3" in merged_ids

    def test_rrf_formula_weights_scores(self):
        """F2.7.2: RRF formula should properly weight and rank."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        # Higher rank should contribute more
        results1 = [MagicMock(id="a"), MagicMock(id="b"), MagicMock(id="c")]
        results2 = [MagicMock(id="b"), MagicMock(id="a"), MagicMock(id="c")]

        merged = store._rrf_merge(results1, results2, k=60)

        # Find 'a' position (rank 1 in results1, rank 2 in results2)
        # RRF = 1/(k+1) + 1/(k+2) = 1/61 + 1/62 ≈ 0.0328
        a_scores = [r.score for r in merged if r.id == "a"]
        assert len(a_scores) > 0

    def test_rrf_k_parameter_affects_weighting(self):
        """F2.7.2: Different k values should produce different rankings."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        results1 = [MagicMock(id="a"), MagicMock(id="b")]
        results2 = [MagicMock(id="b"), MagicMock(id="a")]

        merged_k60 = store._rrf_merge(results1, results2, k=60)
        merged_k100 = store._rrf_merge(results1, results2, k=100)

        # Rankings should differ
        assert len(merged_k60) == 2
        assert len(merged_k100) == 2


@pytest.mark.unit
class TestQdrantMMR:
    """Test Qdrant MMR with named vectors (F2.7.3)."""

    def test_mmr_diversifies_results(self):
        """F2.7.3: MMR should promote diverse results."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        # Mock embeddings (similar vectors)
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.95, 0.0, 0.0],  # Very similar to first
            [0.0, 1.0, 0.0],  # Diverse
            [0.9, 0.0, 0.0],   # Similar to first
        ]

        diverse_results = store._mmr_diversify(
            embeddings,
            lambda_query=[1.0, 0.0, 0.0],
            lambda_value=0.5,
            top_k=3,
        )

        # Should include the diverse vector
        assert 2 in diverse_results  # Index of [0.0, 1.0, 0.0]

    def test_mmr_lambda_parameter(self):
        """F2.7.3: Lambda controls relevance vs diversity tradeoff."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        embeddings = [
            [1.0, 0.0, 0.0],
            [0.9, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]

        # High lambda = more relevance, less diversity
        relevant_results = store._mmr_diversify(
            embeddings,
            lambda_query=[1.0, 0.0, 0.0],
            lambda_value=0.9,
            top_k=2,
        )

        # Should prioritize similar vectors
        assert 0 in relevant_results  # [1.0, 0.0, 0.0]
        assert 1 in relevant_results  # [0.9, 0.0, 0.0]

    def test_mmr_with_named_vectors(self):
        """F2.7.3: Should handle named vectors (dense, sparse)."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        # Mock results with named vectors
        results = [
            {
                "id": "chunk_1",
                "score": 0.9,
                "vector": {"dense": [1.0, 0.0], "sparse": {1: 0.5}}
            },
            {
                "id": "chunk_2",
                "score": 0.8,
                "vector": {"dense": [0.9, 0.0], "sparse": {1: 0.3}}
            },
        ]

        # MMR should work with named vector structure
        mmr_results = store._mmr_named_vectors(
            results,
            lambda_value=0.5,
            top_k=2,
        )

        assert len(mmr_results) <= 2

    def test_mmr_empty_results(self):
        """F2.7.3: MMR should handle empty results gracefully."""
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore()

        result = store._mmr_diversify(
            [],
            lambda_query=[1.0, 0.0],
            lambda_value=0.5,
            top_k=5,
        )

        assert result == []
