"""Tests for ImageExtractor and ImageDescription (Phase 10.4).

Tests image extraction model and Vision API interaction with mocks.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.pdf_framework.processing.image_extractor import (
    ImageDescription,
    ImageExtractor,
)


class TestImageDescription:
    """Test ImageDescription model."""

    def test_basic_creation(self):
        desc = ImageDescription(
            image_bytes=b"\x89PNG test",
            description="A chart showing revenue growth",
            page_number=5,
            image_format="png",
            size=(800, 600),
            description_model="claude-sonnet-4-5-20250929",
        )
        assert desc.description == "A chart showing revenue growth"
        assert desc.page_number == 5
        assert desc.image_format == "png"
        assert desc.size == (800, 600)
        assert desc.bbox is None

    def test_with_bbox(self):
        desc = ImageDescription(
            image_bytes=b"data",
            description="Diagram",
            page_number=1,
            bbox=(10.0, 20.0, 300.0, 400.0),
            image_format="jpeg",
            size=(400, 300),
            description_model="test-model",
        )
        assert desc.bbox == (10.0, 20.0, 300.0, 400.0)

    def test_to_markdown_chunk(self):
        desc = ImageDescription(
            image_bytes=b"data",
            description="Architecture diagram of the system",
            page_number=3,
            image_format="png",
            size=(1024, 768),
            description_model="model",
        )
        md = desc.to_markdown_chunk()
        assert "3" in md  # page number present
        assert "Architecture diagram" in md

    def test_to_dict_excludes_bytes(self):
        desc = ImageDescription(
            image_bytes=b"large binary data",
            description="Test",
            page_number=1,
            image_format="png",
            size=(100, 100),
            description_model="model",
        )
        d = desc.to_dict()
        assert "image_bytes" not in d
        assert d["description"] == "Test"
        assert d["page_number"] == 1
        assert d["image_format"] == "png"
        assert d["size"] == (100, 100)


class TestImageExtractorInit:
    """Test ImageExtractor initialization."""

    def test_default_init(self):
        ext = ImageExtractor()
        assert ext._api_key == ""
        assert ext._model == "claude-sonnet-4-5-20250929"
        assert ext._min_size == 100
        assert ext._max_size == 4096
        assert ext._cache_enabled is True
        assert ext._client is None

    def test_with_api_key(self):
        with patch("src.pdf_framework.processing.image_extractor.Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            ext = ImageExtractor(api_key="sk-test-123")
        assert ext._api_key == "sk-test-123"
        assert ext._client is not None

    def test_custom_params(self):
        ext = ImageExtractor(
            min_size=100,
            max_size=2048,
            cache_enabled=False,
        )
        assert ext._min_size == 100
        assert ext._max_size == 2048
        assert ext._cache_enabled is False


class TestVisionSupport:
    """Test has_vision_support method."""

    def test_no_api_key(self):
        ext = ImageExtractor()
        assert ext.has_vision_support() is False

    def test_with_api_key(self):
        with patch("src.pdf_framework.processing.image_extractor.Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            ext = ImageExtractor(api_key="sk-test")
        assert ext.has_vision_support() is True


class TestMediaTypeGuessing:
    """Test _guess_media_type method."""

    def test_png(self):
        ext = ImageExtractor()
        assert ext._guess_media_type(b"\x89PNG\r\n") == "image/png"

    def test_jpeg(self):
        ext = ImageExtractor()
        assert ext._guess_media_type(b"\xff\xd8\xff\xe0") == "image/jpeg"

    def test_gif87a(self):
        ext = ImageExtractor()
        assert ext._guess_media_type(b"GIF87a...") == "image/gif"

    def test_gif89a(self):
        ext = ImageExtractor()
        assert ext._guess_media_type(b"GIF89a...") == "image/gif"

    def test_unknown_defaults_to_png(self):
        ext = ImageExtractor()
        assert ext._guess_media_type(b"unknown binary") == "image/png"


class TestDescribeImage:
    """Test describe_image method."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_fallback(self):
        ext = ImageExtractor()
        desc = await ext.describe_image(b"image data")
        assert "недоступно" in desc.lower() or "not available" in desc.lower()

    @pytest.mark.asyncio
    async def test_api_call_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "A technical diagram showing database connections."
        mock_response.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_response

        ext = ImageExtractor(api_key="sk-test")
        ext._client = mock_client

        desc = await ext.describe_image(b"\x89PNG fake image data")
        assert "technical diagram" in desc

    @pytest.mark.asyncio
    async def test_api_error_returns_failure_message(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")

        ext = ImageExtractor(api_key="sk-test")
        ext._client = mock_client

        desc = await ext.describe_image(b"\x89PNG data")
        assert "ошибка" in desc.lower() or "failed" in desc.lower()

    @pytest.mark.asyncio
    async def test_caching(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "Cached description"
        mock_response.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_response

        ext = ImageExtractor(api_key="sk-test", cache_enabled=True)
        ext._client = mock_client

        image_data = b"\x89PNG test image"

        desc1 = await ext.describe_image(image_data)
        desc2 = await ext.describe_image(image_data)

        # Should only call API once (cached)
        assert mock_client.messages.create.call_count == 1
        assert desc1 == desc2

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "Description"
        mock_response.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_response

        ext = ImageExtractor(api_key="sk-test", cache_enabled=False)
        ext._client = mock_client

        image_data = b"\x89PNG test image"

        await ext.describe_image(image_data)
        await ext.describe_image(image_data)

        # Should call API twice (no cache)
        assert mock_client.messages.create.call_count == 2


class TestClearCache:
    """Test cache clearing."""

    def test_clear_cache(self):
        ext = ImageExtractor()
        ext._description_cache["key1"] = "value1"
        ext._description_cache["key2"] = "value2"
        ext.clear_cache()
        assert len(ext._description_cache) == 0


class TestDescriptionsToChunks:
    """Test conversion to embedding chunks."""

    def test_descriptions_to_chunks(self):
        ext = ImageExtractor()
        descriptions = [
            ImageDescription(
                image_bytes=b"data1",
                description="Chart showing growth",
                page_number=5,
                image_format="png",
                size=(800, 600),
                description_model="model",
            ),
            ImageDescription(
                image_bytes=b"data2",
                description="Architecture diagram",
                page_number=10,
                image_format="jpeg",
                size=(1024, 768),
                description_model="model",
            ),
        ]
        chunks = ext.to_document_chunks(descriptions, document_id="doc123")
        assert len(chunks) == 2
        assert "Chart showing growth" in chunks[0].content
        assert chunks[0].metadata["element_type"] == "image"
        assert chunks[0].metadata["document_id"] == "doc123"
        assert chunks[0].metadata["page_number"] == "5"
