"""Tests for LayoutElement and LayoutAwareLoader (Phase 10.1).

Tests layout element model and loader behavior with mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.pdf_framework.loaders.providers.layout_parser import (
    LayoutAwareLoader,
    LayoutElement,
)
from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument


class TestLayoutElement:
    """Test LayoutElement model."""

    def test_basic_creation(self):
        el = LayoutElement(
            type="paragraph",
            content="Hello world",
            page_number=1,
        )
        assert el.type == "paragraph"
        assert el.content == "Hello world"
        assert el.page_number == 1
        assert el.bbox is None
        assert el.element_id is None
        assert el.metadata == {}

    def test_with_bbox(self):
        el = LayoutElement(
            type="table",
            content="Table content",
            page_number=3,
            bbox=(10.0, 20.0, 300.0, 400.0),
        )
        assert el.bbox == (10.0, 20.0, 300.0, 400.0)

    def test_with_element_id(self):
        el = LayoutElement(
            type="title",
            content="My Title",
            page_number=1,
            element_id="title_1_abc123",
        )
        assert el.element_id == "title_1_abc123"

    def test_with_metadata(self):
        el = LayoutElement(
            type="image",
            content="Image description",
            page_number=5,
            metadata={"unstructured_category": "Image"},
        )
        assert el.metadata["unstructured_category"] == "Image"

    def test_to_dict(self):
        el = LayoutElement(
            type="list",
            content="- item 1\n- item 2",
            page_number=2,
            bbox=(0.0, 0.0, 100.0, 50.0),
            element_id="list_2_xyz",
            metadata={"key": "value"},
        )
        d = el.to_dict()
        assert d["type"] == "list"
        assert d["content"] == "- item 1\n- item 2"
        assert d["page_number"] == 2
        assert d["bbox"] == (0.0, 0.0, 100.0, 50.0)
        assert d["element_id"] == "list_2_xyz"
        assert d["metadata"] == {"key": "value"}

    def test_all_element_types(self):
        valid_types = [
            "title", "paragraph", "table", "image", "list",
            "header", "footer", "page_number", "section_header",
        ]
        for t in valid_types:
            el = LayoutElement(type=t, content="x", page_number=1)
            assert el.type == t

    def test_to_dict_roundtrip(self):
        el = LayoutElement(
            type="paragraph",
            content="Some text",
            page_number=1,
        )
        d = el.to_dict()
        el2 = LayoutElement(**d)
        assert el2.type == el.type
        assert el2.content == el.content
        assert el2.page_number == el.page_number


class TestLayoutAwareLoaderInit:
    """Test LayoutAwareLoader initialization."""

    def test_default_init(self):
        loader = LayoutAwareLoader()
        # hi_res auto-downgrades to fast if Tesseract is not installed
        assert loader._strategy in ("hi_res", "fast")
        assert loader._infer_table_structure is True
        assert loader._extract_images is False
        assert loader._skip_headers_and_footers is True
        assert loader._min_image_size == 50

    def test_custom_init(self):
        loader = LayoutAwareLoader(
            strategy="fast",
            infer_table_structure=False,
            extract_images=True,
            skip_headers_and_footers=False,
            min_image_size=100,
        )
        assert loader._strategy == "fast"
        assert loader._infer_table_structure is False
        assert loader._extract_images is True
        assert loader._skip_headers_and_footers is False
        assert loader._min_image_size == 100

    def test_supported_extensions(self):
        loader = LayoutAwareLoader()
        assert loader.supported_extensions() == [".pdf"]


class TestLayoutAwareLoaderHelpers:
    """Test helper methods."""

    def test_generate_element_id(self):
        loader = LayoutAwareLoader()
        eid = loader._generate_element_id("title", "Some title", 1)
        assert eid.startswith("title_1_")
        assert len(eid) > 8

    def test_generate_element_id_deterministic(self):
        loader = LayoutAwareLoader()
        eid1 = loader._generate_element_id("paragraph", "Same content", 3)
        eid2 = loader._generate_element_id("paragraph", "Same content", 3)
        assert eid1 == eid2

    def test_generate_element_id_different_content(self):
        loader = LayoutAwareLoader()
        eid1 = loader._generate_element_id("paragraph", "Content A", 1)
        eid2 = loader._generate_element_id("paragraph", "Content B", 1)
        assert eid1 != eid2

    def test_generate_doc_id(self):
        loader = LayoutAwareLoader()
        doc_id = loader._generate_doc_id(Path("test.pdf"))
        assert doc_id.startswith("doc_")
        assert len(doc_id) == 16  # "doc_" + 12 hex chars

    def test_generate_doc_id_deterministic(self):
        loader = LayoutAwareLoader()
        id1 = loader._generate_doc_id(Path("test.pdf"))
        id2 = loader._generate_doc_id(Path("test.pdf"))
        assert id1 == id2

    def test_count_element_types(self):
        loader = LayoutAwareLoader()
        elements = [
            LayoutElement(type="title", content="T", page_number=1),
            LayoutElement(type="paragraph", content="P1", page_number=1),
            LayoutElement(type="paragraph", content="P2", page_number=1),
            LayoutElement(type="table", content="Tab", page_number=2),
        ]
        counts = loader._count_element_types(elements)
        assert counts == {"title": 1, "paragraph": 2, "table": 1}

    def test_count_element_types_empty(self):
        loader = LayoutAwareLoader()
        assert loader._count_element_types([]) == {}


class TestLayoutAwareLoaderLoad:
    """Test load method with PyMuPDF fallback."""

    @pytest.mark.asyncio
    async def test_load_file_not_found(self):
        loader = LayoutAwareLoader()
        with pytest.raises(FileNotFoundError):
            await loader.load("nonexistent.pdf")

    @pytest.mark.asyncio
    async def test_pymupdf_fallback_creates_proper_document(self, tmp_path):
        """Test that PyMuPDF fallback creates proper ProcessedDocument."""
        loader = LayoutAwareLoader()
        loader._unstructured_available = False

        # Create a mock fitz module
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page 1 content here"

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        # Create a temp PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test content")

        with patch("fitz.open", return_value=mock_doc):
            doc = await loader._load_with_pymupdf(pdf_file)

        assert isinstance(doc, ProcessedDocument)
        assert isinstance(doc.metadata, DocumentMetadata)
        assert doc.raw_text == "Page 1 content here"
        assert doc.metadata.source == str(pdf_file)
        assert doc.metadata.title == "test"
        assert doc.metadata.page_count == 1

        # Layout elements stored in metadata.extra
        layout_elements = doc.metadata.extra["layout_elements"]
        assert len(layout_elements) == 1
        assert layout_elements[0]["type"] == "paragraph"
        assert layout_elements[0]["content"] == "Page 1 content here"
        assert doc.metadata.extra["layout_detection_method"] == "pymupdf_fallback"

    @pytest.mark.asyncio
    async def test_pymupdf_fallback_multi_page(self, tmp_path):
        """Test multi-page PyMuPDF fallback."""
        loader = LayoutAwareLoader()
        loader._unstructured_available = False

        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1"
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Page 2"

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.__getitem__ = MagicMock(side_effect=[mock_page1, mock_page2])

        pdf_file = tmp_path / "multi.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test")

        with patch("fitz.open", return_value=mock_doc):
            doc = await loader._load_with_pymupdf(pdf_file)

        assert "Page 1" in doc.raw_text
        assert "Page 2" in doc.raw_text
        layout_elements = doc.metadata.extra["layout_elements"]
        assert len(layout_elements) == 2
        assert layout_elements[0]["page_number"] == 1
        assert layout_elements[1]["page_number"] == 2

    @pytest.mark.asyncio
    async def test_pymupdf_fallback_skips_empty_pages(self, tmp_path):
        """Test that empty pages are skipped."""
        loader = LayoutAwareLoader()
        loader._unstructured_available = False

        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Content"
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "   "  # empty

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.__getitem__ = MagicMock(side_effect=[mock_page1, mock_page2])

        pdf_file = tmp_path / "sparse.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test")

        with patch("fitz.open", return_value=mock_doc):
            doc = await loader._load_with_pymupdf(pdf_file)

        layout_elements = doc.metadata.extra["layout_elements"]
        assert len(layout_elements) == 1

    @pytest.mark.asyncio
    async def test_load_batch(self, tmp_path):
        """Test batch loading."""
        loader = LayoutAwareLoader()
        loader._unstructured_available = False

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Content"

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        pdf1 = tmp_path / "a.pdf"
        pdf2 = tmp_path / "b.pdf"
        pdf1.write_bytes(b"%PDF-1.4 test")
        pdf2.write_bytes(b"%PDF-1.4 test")

        with patch("fitz.open", return_value=mock_doc):
            docs = await loader.load_batch([pdf1, pdf2])

        assert len(docs) == 2
        assert all(isinstance(d, ProcessedDocument) for d in docs)
