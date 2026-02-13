"""Phase 15: Image Understanding — ImageExtractor tests.

Tests for image extraction, Vision API description, caching,
and conversion to DocumentChunk objects for indexing.
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from src.pdf_framework.processing.image_extractor import (
    ImageDescription,
    ImageExtractor,
)
from src.pdf_framework.schemas.documents import DocumentChunk


# ---------------------------------------------------------------------------
# ImageDescription model
# ---------------------------------------------------------------------------

class TestImageDescription:
    def test_create_with_required_fields(self):
        desc = ImageDescription(
            image_bytes=b"\x89PNG",
            description="Скриншот формы документа",
            page_number=3,
            image_format="png",
            size=(800, 600),
            description_model="claude-sonnet-4-5-20250929",
        )
        assert desc.page_number == 3
        assert desc.size == (800, 600)
        assert desc.bbox is None

    def test_bbox_optional(self):
        desc = ImageDescription(
            image_bytes=b"x",
            description="d",
            page_number=1,
            bbox=(10.0, 20.0, 300.0, 400.0),
            image_format="png",
            size=(100, 100),
            description_model="m",
        )
        assert desc.bbox == (10.0, 20.0, 300.0, 400.0)

    def test_to_markdown_chunk_format(self):
        desc = ImageDescription(
            image_bytes=b"x",
            description="Диаграмма архитектуры системы",
            page_number=7,
            image_format="png",
            size=(1024, 768),
            description_model="m",
        )
        md = desc.to_markdown_chunk()
        assert "7" in md
        assert "Диаграмма архитектуры системы" in md

    def test_to_dict_excludes_image_bytes(self):
        desc = ImageDescription(
            image_bytes=b"large binary",
            description="Test",
            page_number=1,
            image_format="jpeg",
            size=(200, 200),
            description_model="m",
        )
        d = desc.to_dict()
        assert "image_bytes" not in d
        assert d["description"] == "Test"
        assert d["image_format"] == "jpeg"


# ---------------------------------------------------------------------------
# ImageExtractor init and has_vision_support
# ---------------------------------------------------------------------------

class TestImageExtractorInit:
    def test_default_init_no_api_key(self):
        ext = ImageExtractor()
        assert ext._api_key == ""
        assert ext._client is None
        assert ext.has_vision_support() is False

    def test_with_api_key_creates_client(self):
        with patch("src.pdf_framework.processing.image_extractor.Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            ext = ImageExtractor(api_key="sk-test-key")
        assert ext._api_key == "sk-test-key"
        assert ext._client is not None
        assert ext.has_vision_support() is True

    def test_with_base_url_passes_to_client(self):
        with patch("src.pdf_framework.processing.image_extractor.Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            ImageExtractor(api_key="sk-key", base_url="https://proxy.example.com")
            mock_cls.assert_called_once_with(api_key="sk-key", base_url="https://proxy.example.com")

    def test_custom_min_max_size(self):
        ext = ImageExtractor(min_size=200, max_size=2048, cache_enabled=False)
        assert ext._min_size == 200
        assert ext._max_size == 2048
        assert ext._cache_enabled is False


# ---------------------------------------------------------------------------
# Media type guessing
# ---------------------------------------------------------------------------

class TestGuessMediaType:
    def test_png(self):
        assert ImageExtractor()._guess_media_type(b"\x89PNG\r\n") == "image/png"

    def test_jpeg(self):
        assert ImageExtractor()._guess_media_type(b"\xff\xd8\xff\xe0") == "image/jpeg"

    def test_gif87a(self):
        assert ImageExtractor()._guess_media_type(b"GIF87a data") == "image/gif"

    def test_gif89a(self):
        assert ImageExtractor()._guess_media_type(b"GIF89a data") == "image/gif"

    def test_unknown_defaults_png(self):
        assert ImageExtractor()._guess_media_type(b"unknown") == "image/png"


# ---------------------------------------------------------------------------
# describe_image
# ---------------------------------------------------------------------------

class TestDescribeImage:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_fallback(self):
        ext = ImageExtractor()
        desc = await ext.describe_image(b"\x89PNG data")
        assert "недоступно" in desc or "not available" in desc.lower() or "нет API" in desc

    @pytest.mark.asyncio
    async def test_api_success(self):
        mock_client = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Скриншот окна настроек базы данных"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        ext = ImageExtractor(api_key="sk-test")
        ext._client = mock_client

        desc = await ext.describe_image(b"\x89PNG fake")
        assert "Скриншот" in desc or "настроек" in desc

    @pytest.mark.asyncio
    async def test_api_error_returns_error_message(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("timeout")

        ext = ImageExtractor(api_key="sk-test")
        ext._client = mock_client

        desc = await ext.describe_image(b"\x89PNG data")
        assert "Ошибка" in desc or "error" in desc.lower()

    @pytest.mark.asyncio
    async def test_caching_deduplicates_api_calls(self):
        mock_client = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Cached result"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        ext = ImageExtractor(api_key="sk-test", cache_enabled=True)
        ext._client = mock_client

        data = b"\x89PNG identical"
        d1 = await ext.describe_image(data)
        d2 = await ext.describe_image(data)

        assert d1 == d2
        assert mock_client.messages.create.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_key_is_md5(self):
        ext = ImageExtractor(api_key="sk-test")
        ext._client = MagicMock()
        ext._client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="desc")]
        )

        data = b"test bytes"
        await ext.describe_image(data)
        expected_key = hashlib.md5(data).hexdigest()
        assert expected_key in ext._description_cache

    @pytest.mark.asyncio
    async def test_different_images_cached_separately(self):
        mock_client = MagicMock()
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            block = MagicMock()
            block.text = f"Description {call_count}"
            return MagicMock(content=[block])

        mock_client.messages.create.side_effect = side_effect

        ext = ImageExtractor(api_key="sk-test", cache_enabled=True)
        ext._client = mock_client

        d1 = await ext.describe_image(b"image_A")
        d2 = await ext.describe_image(b"image_B")

        assert d1 != d2
        assert call_count == 2


# ---------------------------------------------------------------------------
# to_document_chunks
# ---------------------------------------------------------------------------

class TestToDocumentChunks:
    def test_converts_descriptions_to_chunks(self):
        ext = ImageExtractor()
        descriptions = [
            ImageDescription(
                image_bytes=b"img1",
                description="Форма документа Реализация",
                page_number=5,
                image_format="png",
                size=(800, 600),
                description_model="model-v1",
            ),
            ImageDescription(
                image_bytes=b"img2",
                description="Схема регистров накопления",
                page_number=12,
                image_format="jpeg",
                size=(1024, 768),
                description_model="model-v1",
            ),
        ]
        chunks = ext.to_document_chunks(descriptions, document_id="doc_42", source_path="test.pdf")

        assert len(chunks) == 2
        assert isinstance(chunks[0], DocumentChunk)
        assert chunks[0].document_id == "doc_42"
        assert chunks[0].section == "image"
        assert chunks[0].metadata["chunk_type"] == "image"
        assert chunks[0].metadata["source"] == "test.pdf"
        assert chunks[0].metadata["image_format"] == "png"
        assert "800x600" in chunks[0].metadata["image_size"]
        assert chunks[0].page_number == 5
        assert chunks[1].page_number == 12

    def test_chunk_index_starts_high(self):
        ext = ImageExtractor()
        descriptions = [
            ImageDescription(
                image_bytes=b"x", description="d", page_number=1,
                image_format="png", size=(100, 100), description_model="m",
            ),
        ]
        chunks = ext.to_document_chunks(descriptions, document_id="doc")
        assert chunks[0].chunk_index >= 9000

    def test_empty_descriptions_returns_empty(self):
        ext = ImageExtractor()
        chunks = ext.to_document_chunks([], document_id="doc")
        assert chunks == []

    def test_chunk_id_format(self):
        ext = ImageExtractor()
        descriptions = [
            ImageDescription(
                image_bytes=b"x", description="d", page_number=3,
                image_format="png", size=(100, 100), description_model="m",
            ),
        ]
        chunks = ext.to_document_chunks(descriptions, document_id="DOC_1")
        assert "DOC_1" in chunks[0].id
        assert "img" in chunks[0].id


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------

class TestClearCache:
    def test_clear_cache_empties_dict(self):
        ext = ImageExtractor()
        ext._description_cache["k1"] = "v1"
        ext._description_cache["k2"] = "v2"
        ext.clear_cache()
        assert len(ext._description_cache) == 0
