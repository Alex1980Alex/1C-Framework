"""Tests for StructureAwareSplitter (Phase 10.2).

Tests structure-aware chunking based on layout elements.
"""

import pytest

from src.pdf_framework.processing.splitters.structure_aware import StructureAwareSplitter
from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    DocumentMetadata,
    ProcessedDocument,
)


def _make_document(
    layout_elements: list[dict] | None = None,
    raw_text: str = "Default text content",
    doc_id: str = "doc_test123",
) -> ProcessedDocument:
    """Create a ProcessedDocument with layout elements in metadata.extra."""
    extra = {}
    if layout_elements is not None:
        extra["layout_elements"] = layout_elements
    return ProcessedDocument(
        id=doc_id,
        source_path="/test/doc.pdf",
        raw_text=raw_text,
        metadata=DocumentMetadata(
            source="/test/doc.pdf",
            title="Test Document",
            extra=extra,
        ),
    )


class TestStructureAwareSplitterInit:
    """Test initialization."""

    def test_default_init(self):
        s = StructureAwareSplitter()
        assert s._max_chunk_size == 1000
        assert s._chunk_overlap == 200
        assert s._min_chunk_size == 100
        assert s._text_splitter is not None

    def test_custom_init(self):
        s = StructureAwareSplitter(max_chunk_size=500, chunk_overlap=50, min_chunk_size=50)
        assert s._max_chunk_size == 500
        assert s._chunk_overlap == 50
        assert s._min_chunk_size == 50


class TestFallbackSplit:
    """Test fallback behavior when no layout elements."""

    def test_no_layout_elements_uses_fallback(self):
        s = StructureAwareSplitter()
        doc = _make_document(layout_elements=None, raw_text="Some text content here.")
        chunks = s.split(doc)
        # Fallback should split the raw_text
        assert len(chunks) >= 1
        assert chunks[0].document_id == "doc_test123"

    def test_empty_layout_elements_uses_fallback(self):
        s = StructureAwareSplitter()
        doc = _make_document(layout_elements=[], raw_text="Fallback text.")
        chunks = s.split(doc)
        assert len(chunks) >= 1

    def test_fallback_empty_text_returns_empty(self):
        s = StructureAwareSplitter()
        doc = _make_document(layout_elements=None, raw_text="   ")
        chunks = s.split(doc)
        assert chunks == []


class TestHeaderFooterSkip:
    """Test that header/footer/page_number elements are skipped."""

    def test_header_skipped(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "header", "content": "Page Header", "page_number": 1},
            {"type": "paragraph", "content": "Body text.", "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        contents = [c.content for c in chunks]
        assert not any("Page Header" in c for c in contents)
        assert any("Body text" in c for c in contents)

    def test_footer_skipped(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "paragraph", "content": "Body.", "page_number": 1},
            {"type": "footer", "content": "Copyright 2024", "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        contents = [c.content for c in chunks]
        assert not any("Copyright" in c for c in contents)

    def test_page_number_skipped(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "page_number", "content": "42", "page_number": 42},
            {"type": "paragraph", "content": "Text.", "page_number": 42},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        # Only the paragraph should produce a chunk
        assert len(chunks) == 1
        assert "42" not in chunks[0].content or "Text" in chunks[0].content


class TestTableChunking:
    """Test that tables produce separate, unsplit chunks."""

    def test_table_separate_chunk(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "paragraph", "content": "Before table.", "page_number": 1},
            {"type": "table", "content": "| A | B |\n|---|---|\n| 1 | 2 |", "page_number": 1},
            {"type": "paragraph", "content": "After table.", "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)

        table_chunks = [c for c in chunks if c.metadata.get("element_type") == "table"]
        assert len(table_chunks) == 1
        assert "| A | B |" in table_chunks[0].content

    def test_table_never_split(self):
        """Even large tables should be a single chunk."""
        s = StructureAwareSplitter(max_chunk_size=50, chunk_overlap=10)
        big_table = "| " + " | ".join(["Col"] * 20) + " |\n" + ("| " + " | ".join(["x"] * 20) + " |\n") * 50
        elements = [
            {"type": "table", "content": big_table, "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)

        table_chunks = [c for c in chunks if c.metadata.get("element_type") == "table"]
        assert len(table_chunks) == 1

    def test_table_preserves_bbox(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "table", "content": "Table", "page_number": 2, "bbox": (10, 20, 300, 400)},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        assert chunks[0].metadata["bbox"] == (10, 20, 300, 400)

    def test_table_flushes_previous_section(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "paragraph", "content": "Section content.", "page_number": 1},
            {"type": "table", "content": "Table data", "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        # Should produce 2 chunks: section + table
        assert len(chunks) == 2
        assert chunks[0].metadata["element_type"] == "section"
        assert chunks[1].metadata["element_type"] == "table"


class TestImageChunking:
    """Test image element handling."""

    def test_image_separate_chunk(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "image", "content": "A diagram showing X", "page_number": 3},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        assert len(chunks) == 1
        assert chunks[0].metadata["element_type"] == "image"
        assert "diagram" in chunks[0].content


class TestTitleSectionGrouping:
    """Test title + content grouping into sections."""

    def test_title_groups_with_following_paragraphs(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "title", "content": "Introduction", "page_number": 1},
            {"type": "paragraph", "content": "First paragraph of intro.", "page_number": 1},
            {"type": "paragraph", "content": "Second paragraph of intro.", "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        # Should be a single section chunk
        assert len(chunks) == 1
        assert "First paragraph" in chunks[0].content
        assert "Second paragraph" in chunks[0].content
        assert chunks[0].metadata["section_title"] == "Introduction"

    def test_section_header_groups_content(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "section_header", "content": "Methods", "page_number": 2},
            {"type": "paragraph", "content": "We used method A.", "page_number": 2},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        assert len(chunks) == 1
        assert chunks[0].metadata["section_title"] == "Methods"

    def test_multiple_sections(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "title", "content": "Section A", "page_number": 1},
            {"type": "paragraph", "content": "Content A.", "page_number": 1},
            {"type": "title", "content": "Section B", "page_number": 2},
            {"type": "paragraph", "content": "Content B.", "page_number": 2},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        assert len(chunks) == 2
        assert chunks[0].metadata["section_title"] == "Section A"
        assert chunks[1].metadata["section_title"] == "Section B"


class TestLargeSectionSplit:
    """Test splitting of oversized sections."""

    def test_large_section_gets_split(self):
        s = StructureAwareSplitter(max_chunk_size=100, chunk_overlap=20)
        elements = [
            {"type": "title", "content": "Big Section", "page_number": 1},
            {"type": "paragraph", "content": "word " * 200, "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        # Should split into multiple chunks
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata["section_title"] == "Big Section"
            assert "chunk_index" in chunk.metadata
            assert "total_chunks" in chunk.metadata


class TestDocumentId:
    """Test that document_id is properly set."""

    def test_document_id_propagated(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "paragraph", "content": "Text.", "page_number": 1},
            {"type": "table", "content": "Table.", "page_number": 1},
            {"type": "image", "content": "Image.", "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements, doc_id="my_doc_42")
        chunks = s.split(doc)
        for chunk in chunks:
            assert chunk.document_id == "my_doc_42"


class TestListHandling:
    """Test list element handling."""

    def test_list_grouped_with_section(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "title", "content": "Steps", "page_number": 1},
            {"type": "list", "content": "1. Step one\n2. Step two", "page_number": 1},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        assert len(chunks) == 1
        assert "Step one" in chunks[0].content
        assert chunks[0].metadata["section_title"] == "Steps"


class TestPageNumber:
    """Test page number metadata."""

    def test_page_number_in_metadata(self):
        s = StructureAwareSplitter()
        elements = [
            {"type": "paragraph", "content": "Page 5 text.", "page_number": 5},
        ]
        doc = _make_document(layout_elements=elements)
        chunks = s.split(doc)
        assert chunks[0].page_number == 5
        assert chunks[0].metadata["page_number"] == 5
