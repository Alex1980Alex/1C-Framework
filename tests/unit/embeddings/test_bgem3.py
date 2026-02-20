"""Unit tests for BGE-M3 Unified Embedding Provider (Phase 56)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from src.pdf_framework.embeddings.providers.bgem3 import (
    BGEM3Output,
    BGEM3Provider,
    create_bgem3_provider,
    get_cached_bgem3_provider,
)


@pytest.fixture
def mock_bgem3_model():
    """Mock BGE-M3 FlagModel."""
    model = MagicMock()

    # Mock encode method
    def mock_encode(
        texts,
        batch_size=256,
        return_dense=False,
        return_sparse=False,
        return_colbert_vecs=False,
    ):
        n = len(texts)
        result = {}

        if return_dense:
            result["dense_vecs"] = torch.randn(n, 1024)
        if return_sparse:
            # Mock sparse: dict with token_id -> weight
            result["lexical_weights"] = [
                {i: 0.1 + (i * 0.01) for i in range(10)} for _ in range(n)
            ]
        if return_colbert_vecs:
            # Mock ColBERT: variable token count per text
            result["colbert_vecs"] = [
                torch.randn(len(text.split()) + 2, 1024) for text in texts
            ]

        return result

    model.encode = mock_encode
    return model


@pytest.fixture
def bgem3_provider(mock_bgem3_model):
    """BGE-M3 provider with mocked model."""
    provider = BGEM3Provider()
    provider._model = mock_bgem3_model
    return provider


@pytest.mark.unit
class TestBGEM3Provider:
    """Tests for BGEM3Provider."""

    def test_init_auto_detect_device_cpu(self):
        """Should auto-detect CPU when CUDA unavailable."""
        with patch("torch.cuda.is_available", return_value=False):
            provider = BGEM3Provider()
            assert provider._device == "cpu"

    def test_init_with_device_override(self):
        """Should use device override when provided."""
        provider = BGEM3Provider(device="cuda")
        assert provider._device == "cuda"

    def test_dimensions_property(self):
        """BGE-M3 dense dimension is 1024."""
        provider = BGEM3Provider()
        assert provider.dimensions == 1024

    def test_get_dimensions(self):
        """get_dimensions returns 1024."""
        provider = BGEM3Provider()
        assert provider.get_dimensions() == 1024

    def test_embed_dense_single_text(self, bgem3_provider):
        """Should generate dense embedding for single text."""
        result = bgem3_provider.embed_dense("test text")

        assert isinstance(result, list)
        assert len(result) == 1024

    def test_embed_dense_batch(self, bgem3_provider):
        """Should generate dense embeddings for batch."""
        texts = ["text1", "text2", "text3"]
        result = bgem3_provider.embed_dense(texts)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(len(vec) == 1024 for vec in result)

    def test_embed_dense_empty_batch(self, bgem3_provider):
        """Should handle empty batch."""
        result = bgem3_provider.embed_dense([])
        assert result == []

    def test_embed_sparse_single_text(self, bgem3_provider):
        """Should generate sparse embedding for single text."""
        result = bgem3_provider.embed_sparse("machine learning")

        assert isinstance(result, dict)
        assert len(result) > 0
        # Check that values are floats
        assert all(isinstance(v, (int, float)) for v in result.values())

    def test_embed_sparse_batch(self, bgem3_provider):
        """Should generate sparse embeddings for batch."""
        texts = ["text1", "text2"]
        result = bgem3_provider.embed_sparse(texts)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(r, dict) for r in result)

    def test_embed_colbert_single_text(self, bgem3_provider):
        """Should generate ColBERT embeddings for single text."""
        result = bgem3_provider.embed_colbert("short text")

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(len(vec) == 1024 for vec in result)

    def test_embed_colbert_batch(self, bgem3_provider):
        """Should generate ColBERT embeddings for batch."""
        texts = ["first text", "second longer text here"]
        result = bgem3_provider.embed_colbert(texts)

        assert isinstance(result, list)
        assert len(result) == 2
        # Each text has variable token count
        assert all(isinstance(vec, list) for vec in result)

    def test_embed_multi_single_text(self, bgem3_provider):
        """Should generate all three embedding types for single text."""
        result = bgem3_provider.embed_multi("comprehensive test")

        assert isinstance(result, BGEM3Output)
        assert result.dense is not None
        assert result.sparse is not None
        assert result.colbert is not None

        assert len(result.dense) == 1024
        assert isinstance(result.sparse, dict)
        assert len(result.colbert) > 0

    def test_embed_multi_batch(self, bgem3_provider):
        """Should generate all three embedding types for batch."""
        texts = ["text1", "text2"]
        result = bgem3_provider.embed_multi(texts)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(r, BGEM3Output) for r in result)

        # Check first result
        assert result[0].dense is not None
        assert result[0].sparse is not None
        assert result[0].colbert is not None

    @pytest.mark.asyncio
    async def test_embed_text_async(self, bgem3_provider):
        """Async compatibility: embed_text."""
        result = await bgem3_provider.embed_text("async test")

        assert isinstance(result, list)
        assert len(result) == 1024

    @pytest.mark.asyncio
    async def test_embed_batch_async(self, bgem3_provider):
        """Async compatibility: embed_batch."""
        texts = ["a", "b", "c"]
        result = await bgem3_provider.embed_batch(texts)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(len(vec) == 1024 for vec in result)

    def test_model_lazy_loading(self):
        """Model should be lazy-loaded on first access."""
        provider = BGEM3Provider()

        with patch.object(provider, "_load_model") as mock_load:
            # Access model property
            _ = provider.model
            mock_load.assert_called_once()

    def test_tokenizer_lazy_loading(self):
        """Tokenizer should be lazy-loaded on first access."""
        provider = BGEM3Provider()

        with patch.object(provider, "_load_model") as mock_load:
            # Access tokenizer property
            _ = provider.tokenizer
            mock_load.assert_called_once()

    def test_get_model_name(self):
        """Should return configured model name."""
        provider = BGEM3Provider(model_name="custom/bge-model")
        assert provider.get_model_name() == "custom/bge-model"


@pytest.mark.unit
class TestBGEM3Output:
    """Tests for BGEM3Output dataclass."""

    def test_create_empty_output(self):
        """Can create output with None values."""
        output = BGEM3Output()
        assert output.dense is None
        assert output.sparse is None
        assert output.colbert is None

    def test_create_full_output(self):
        """Can create output with all embeddings."""
        output = BGEM3Output(
            dense=[0.1] * 1024,
            sparse={1: 0.5, 2: 0.3},
            colbert=[[0.2] * 1024, [0.3] * 1024],
        )
        assert len(output.dense) == 1024
        assert len(output.sparse) == 2
        assert len(output.colbert) == 2


@pytest.mark.unit
class TestBGE3Factory:
    """Tests for factory functions."""

    def test_create_bgem3_provider(self):
        """Factory should create configured provider."""
        provider = create_bgem3_provider(model_name="BAAI/bge-m3")

        assert isinstance(provider, BGEM3Provider)
        assert provider._model_name == "BAAI/bge-m3"

    def test_create_with_device(self):
        """Factory should pass device override."""
        provider = create_bgem3_provider(device="cpu")

        assert provider._device == "cpu"

    def test_get_cached_provider_same_instance(self):
        """Cached provider should return same instance."""
        provider1 = get_cached_bgem3_provider()
        provider2 = get_cached_bgem3_provider()

        assert provider1 is provider2

    def test_get_cached_with_different_model(self):
        """Different model names create different cached instances."""
        # Clear cache first
        get_cached_bgem3_provider.cache_clear()

        p1 = get_cached_bgem3_provider("BAAI/bge-m3")
        p2 = get_cached_bgem3_provider("custom/model")

        # Should be different instances due to different args
        assert p1 is not p2


@pytest.mark.unit
class TestBGEM3Errors:
    """Tests for error handling."""

    def test_import_error_without_flagembedding(self):
        """Should raise ImportError if FlagEmbedding not installed."""
        provider = BGEM3Provider()

        with patch("builtins.__import__", side_effect=ImportError):
            with pytest.raises(ImportError, match="FlagEmbedding"):
                _ = provider.model

    def test_model_load_failure_propagates(self):
        """Model load failures should propagate."""
        provider = BGEM3Provider()

        with patch("src.pdf_framework.embeddings.providers.bgem3.BGEM3FlagModel") as mock_class:
            mock_class.side_effect = RuntimeError("CUDA OOM")

            with pytest.raises(RuntimeError, match="CUDA OOM"):
                _ = provider.model
