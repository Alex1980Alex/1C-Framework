"""Unit tests for Jina Embeddings v3 provider (Phase 47)."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.config import EmbeddingSettings


def _make_jina_settings(**overrides) -> EmbeddingSettings:
    defaults = {
        "provider": "jina",
        "model": "jina-embeddings-v3",
        "jina_api_key": "jina_test_key_12345",
        "jina_task": "retrieval.passage",
        "dimensions": 1024,
        "batch_size": 32,
    }
    defaults.update(overrides)
    return EmbeddingSettings(**defaults)


def _mock_api_response(n: int, dims: int = 1024) -> dict:
    """Create a mock Jina API JSON response."""
    return {
        "data": [
            {"index": i, "embedding": [0.1 * (i + 1)] * dims}
            for i in range(n)
        ],
        "usage": {"total_tokens": n * 10},
    }


@pytest.mark.unit
class TestJinaEmbeddingEngine:
    """Tests for JinaEmbeddingEngine."""

    def test_init_requires_api_key(self):
        """Should raise ValueError without API key."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = EmbeddingSettings(provider="jina", jina_api_key="")
        with pytest.raises(ValueError, match="Jina API key required"):
            JinaEmbeddingEngine(settings)

    def test_init_with_valid_key(self):
        """Should initialize with valid API key."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = JinaEmbeddingEngine(settings)
        assert engine.get_model_name() == "jina-embeddings-v3"
        assert engine.get_dimensions() == 1024

    def test_get_dimensions_with_truncation(self):
        """Should return truncated dimensions when jina_truncate_dim is set."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings(jina_truncate_dim=256)
        engine = JinaEmbeddingEngine(settings)
        assert engine.get_dimensions() == 256

    @pytest.mark.asyncio
    async def test_embed_text(self):
        """Should embed a single text using retrieval.query task."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = JinaEmbeddingEngine(settings)

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_api_response(1)
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await engine.embed_text("test query")

        assert len(result) == 1024
        assert result[0] == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_embed_text_uses_query_task(self):
        """embed_text should use 'retrieval.query' task type."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = JinaEmbeddingEngine(settings)

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_api_response(1)
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            await engine.embed_text("test query")

        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs["json"]
        assert body["task"] == "retrieval.query"

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """Should embed a batch of texts."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings(batch_size=32)
        engine = JinaEmbeddingEngine(settings)

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_api_response(3)
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await engine.embed_batch(["text1", "text2", "text3"])

        assert len(result) == 3
        assert all(len(e) == 1024 for e in result)

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self):
        """Should return empty list for empty input."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = JinaEmbeddingEngine(settings)
        result = await engine.embed_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_batch_sub_batching(self):
        """Should split large inputs into sub-batches."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings(batch_size=2)
        engine = JinaEmbeddingEngine(settings)

        # 5 texts with batch_size=2 → 3 API calls (2+2+1)
        call_count = 0

        async def mock_post(url, json=None):
            nonlocal call_count
            call_count += 1
            n = len(json["input"])
            resp = MagicMock()
            resp.json.return_value = _mock_api_response(n)
            resp.raise_for_status = MagicMock()
            return resp

        with patch.object(engine._client, "post", side_effect=mock_post):
            result = await engine.embed_batch([f"text{i}" for i in range(5)])

        assert len(result) == 5
        assert call_count == 3  # ceil(5/2)

    @pytest.mark.asyncio
    async def test_embed_batch_uses_passage_task(self):
        """embed_batch should use configured task type (default: retrieval.passage)."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = JinaEmbeddingEngine(settings)

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_api_response(1)
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            await engine.embed_batch(["indexing text"])

        body = mock_post.call_args.kwargs["json"]
        assert body["task"] == "retrieval.passage"

    @pytest.mark.asyncio
    async def test_matryoshka_truncation(self):
        """Should include dimensions in API request when truncation is set."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings(jina_truncate_dim=512)
        engine = JinaEmbeddingEngine(settings)

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_api_response(1, dims=512)
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            await engine.embed_text("test")

        body = mock_post.call_args.kwargs["json"]
        assert body["dimensions"] == 512

    @pytest.mark.asyncio
    async def test_no_truncation_by_default(self):
        """Should NOT include dimensions when truncation is None."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = JinaEmbeddingEngine(settings)

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_api_response(1)
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            await engine.embed_text("test")

        body = mock_post.call_args.kwargs["json"]
        assert "dimensions" not in body

    @pytest.mark.asyncio
    async def test_close(self):
        """Should close the HTTP client."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = JinaEmbeddingEngine(settings)

        with patch.object(engine._client, "aclose", new_callable=AsyncMock) as mock_close:
            await engine.close()

        mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_sorted_by_index(self):
        """Should handle out-of-order API response (sort by index)."""
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = JinaEmbeddingEngine(settings)

        # Return embeddings in reversed order
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"index": 2, "embedding": [0.3] * 1024},
                {"index": 0, "embedding": [0.1] * 1024},
                {"index": 1, "embedding": [0.2] * 1024},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await engine.embed_batch(["a", "b", "c"])

        # Should be sorted: index 0 first, then 1, then 2
        assert result[0][0] == pytest.approx(0.1)
        assert result[1][0] == pytest.approx(0.2)
        assert result[2][0] == pytest.approx(0.3)


@pytest.mark.unit
class TestJinaFactory:
    """Test factory integration."""

    def test_factory_returns_jina(self):
        """get_embedding_engine should return JinaEmbeddingEngine for provider='jina'."""
        from src.pdf_framework.embeddings import get_embedding_engine
        from src.pdf_framework.embeddings.providers.jina import JinaEmbeddingEngine

        settings = _make_jina_settings()
        engine = get_embedding_engine(settings)
        assert isinstance(engine, JinaEmbeddingEngine)
