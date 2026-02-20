"""Unit tests for Local Embedding Provider (F2.4.1-F2.4.2)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestLocalEmbeddingProvider:
    """Test LocalEmbeddingProvider initialization and batching."""

    def test_local_provider_init(self):
        """F2.4.1: LocalEmbeddingProvider should initialize with model."""
        from src.pdf_framework.embeddings.providers.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(
            model="intfloat/multilingual-e5-large",
            device="cpu",
        )

        assert provider.model_name == "intfloat/multilingual-e5-large"
        assert provider.device == "cpu"

    @pytest.mark.skip(reason="Requires model download")
    def test_embed_batch_chunking(self):
        """F2.4.2: embed_batch should respect batch_size."""
        from src.pdf_framework.embeddings.providers.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(batch_size=2)

        texts = [f"text {i}" for i in range(10)]
        embeddings = provider.embed_batch(texts)

        assert len(embeddings) == 10
        assert all(len(e) == 1024 for e in embeddings)


@pytest.mark.unit
class TestEmbeddingCache:
    """Test SQLite embedding cache (F2.4.3)."""

    def test_cache_hit(self, tmp_path):
        """F2.4.3: SQLite cache should return cached embeddings."""
        from src.pdf_framework.embeddings.cache.sqlite_cache import SQLiteEmbeddingCache

        cache = SQLiteEmbeddingCache(db_path=tmp_path / "cache.db")

        # Cache an embedding
        cache.put("test_key", [0.1] * 1024)

        # Retrieve it
        cached = cache.get("test_key")

        assert cached is not None
        assert len(cached) == 1024
        assert cached[0] == 0.1

    def test_cache_miss(self, tmp_path):
        """Cache should return None for missing keys."""
        from src.pdf_framework.embeddings.cache.sqlite_cache import SQLiteEmbeddingCache

        cache = SQLiteEmbeddingCache(db_path=tmp_path / "cache.db")

        cached = cache.get("nonexistent_key")

        assert cached is None
