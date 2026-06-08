"""Unit tests for Local Embedding Engine (F2.4.1-F2.4.2) and EmbeddingCache (F2.4.3)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.pdf_framework.config import EmbeddingSettings


def _local_settings(**overrides) -> EmbeddingSettings:
    defaults = {
        "provider": "local",
        "model": "intfloat/multilingual-e5-large",
        "dimensions": 1024,
        "device": "cpu",
        "batch_size": 2,
    }
    defaults.update(overrides)
    return EmbeddingSettings(**defaults)


@pytest.mark.unit
class TestLocalEmbeddingProvider:
    """Test LocalEmbeddingEngine initialization and settings."""

    def test_local_provider_init(self):
        """F2.4.1: LocalEmbeddingEngine initialises with EmbeddingSettings without loading weights."""
        from src.pdf_framework.embeddings.providers.local import LocalEmbeddingEngine

        settings = _local_settings()
        engine = LocalEmbeddingEngine(settings=settings)

        # Model is lazy-loaded; _model must be None until first embed call
        assert engine._model is None
        assert engine.get_model_name() == "intfloat/multilingual-e5-large"
        assert engine.get_dimensions() == 1024
        # E5 models need prefix handling — flag must be set
        assert engine._is_e5 is True

    @pytest.mark.skip(reason="Requires model download")
    def test_embed_batch_chunking(self):
        """F2.4.2: embed_batch should respect batch_size."""
        from src.pdf_framework.embeddings.providers.local import LocalEmbeddingEngine

        engine = LocalEmbeddingEngine(settings=_local_settings(batch_size=2))
        texts = [f"text {i}" for i in range(10)]
        embeddings = engine.embed_batch(texts)

        assert len(embeddings) == 10
        assert all(len(e) == 1024 for e in embeddings)


@pytest.mark.unit
class TestEmbeddingCache:
    """Test async SQLite embedding cache (F2.4.3)."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, tmp_path):
        """F2.4.3: EmbeddingCache.get returns the vector stored via set (cache hit)."""
        from src.pdf_framework.embeddings.cache.sqlite_cache import EmbeddingCache

        cache = EmbeddingCache(db_path=tmp_path / "cache.db")
        model = "intfloat/multilingual-e5-large"
        vector = [0.1] * 1024

        await cache.set("hello world", model, vector)
        result = await cache.get("hello world", model)

        assert result is not None
        assert len(result) == 1024
        assert result[0] == pytest.approx(0.1)
        assert cache.get_stats().hits == 1

    @pytest.mark.asyncio
    async def test_cache_miss(self, tmp_path):
        """Cache returns None for a key that was never stored."""
        from src.pdf_framework.embeddings.cache.sqlite_cache import EmbeddingCache

        cache = EmbeddingCache(db_path=tmp_path / "cache.db")
        result = await cache.get("nonexistent text", "some-model")

        assert result is None
        assert cache.get_stats().misses == 1
