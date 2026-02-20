"""Unit tests for Processing splitters and pipeline (F2.6).

Tests:
- F2.6.1: RecursiveSplitter chunk sizes
- F2.6.2: SemanticSplitter boundary detection
- F2.6.3: Pipeline._assign_page_numbers
- F2.6.4: deterministic ID generation
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestRecursiveSplitter:
    """Test RecursiveSplitter chunk size control."""

    def test_chunk_size_respects_max(self):
        """F2.6.1: RecursiveSplitter should respect max chunk size."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveSplitter

        splitter = RecursiveSplitter(max_chunk_size=1000, overlap=100)

        long_text = "word " * 500  # ~2500 chars

        chunks = splitter.split_text(long_text)

        # All chunks should be <= max_chunk_size + overlap
        for chunk in chunks:
            assert len(chunk) <= 1100  # max + overlap

    def test_overlap_between_chunks(self):
        """F2.6.1: Overlap should be preserved between chunks."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveSplitter

        splitter = RecursiveSplitter(max_chunk_size=500, overlap=50)

        text = "word " * 200  # ~1000 chars
        chunks = splitter.split_text(text)

        if len(chunks) > 1:
            # Check overlap exists
            assert chunks[0][-50:] in chunks[1][:100]

    def test_empty_text_returns_empty_list(self):
        """F2.6.1: Empty text should return empty list."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveSplitter

        splitter = RecursiveSplitter()
        chunks = splitter.split_text("")

        assert chunks == []

    def test_single_chunk_for_short_text(self):
        """F2.6.1: Short text should return single chunk."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveSplitter

        splitter = RecursiveSplitter(max_chunk_size=1000)
        chunks = splitter.split_text("Short text")

        assert len(chunks) == 1
        assert chunks[0] == "Short text"


@pytest.mark.unit
class TestSemanticSplitter:
    """Test SemanticSplitter boundary detection."""

    def test_boundary_detection_sentences(self):
        """F2.6.2: SemanticSplitter should detect sentence boundaries."""
        from src.pdf_framework.processing.splitters.semantic import SemanticSplitter

        splitter = SemanticSplitter()

        text = "First sentence. Second sentence. Third sentence."

        boundaries = splitter._find_boundaries(text)

        # Should find sentence boundaries
        assert len(boundaries) >= 2

    def test_boundary_detection_paragraphs(self):
        """F2.6.2: Should detect paragraph boundaries."""
        from src.pdf_framework.processing.splitters.semantic import SemanticSplitter

        splitter = SemanticSplitter()

        text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"

        boundaries = splitter._find_boundaries(text)

        # Should find paragraph boundaries
        assert len(boundaries) >= 2

    def test_semantic_similarity_threshold(self):
        """F2.6.2: Should only split at low similarity points."""
        from src.pdf_framework.processing.splitters.semantic import SemanticSplitter

        splitter = SemanticSplitter(similarity_threshold=0.3)

        # Mock similarity scores
        similarities = [0.9, 0.2, 0.8, 0.1, 0.95]
        boundary_indices = splitter._select_boundaries_by_similarity(similarities)

        # Should select indices where similarity < threshold
        expected = [1, 3]  # 0.2 and 0.1
        assert boundary_indices == expected

    def test_no_boundaries_for_short_text(self):
        """F2.6.2: Short text should have no boundaries."""
        from src.pdf_framework.processing.splitters.semantic import SemanticSplitter

        splitter = SemanticSplitter()
        boundaries = splitter._find_boundaries("Short")

        assert len(boundaries) == 0


@pytest.mark.unit
class TestPipeline:
    """Test Pipeline page number assignment."""

    def test_assign_page_numbers_sequential(self):
        """F2.6.3: Page numbers should be assigned sequentially."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline()

        chunks = [
            {"content": f"chunk {i}"}
            for i in range(10)
        ]

        result = pipeline._assign_page_numbers(chunks, start_page=1)

        assert result[0]["page_number"] == 1
        assert result[-1]["page_number"] == 1  # All on same page by default

    def test_assign_page_numbers_with_page_breaks(self):
        """F2.6.3: Should respect page break markers."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline()

        chunks = [
            {"content": "page1", "page_break": True},
            {"content": "page2", "page_break": True},
            {"content": "page3"},
        ]

        result = pipeline._assign_page_numbers(chunks, start_page=1)

        assert result[0]["page_number"] == 1
        assert result[1]["page_number"] == 2
        assert result[2]["page_number"] == 3

    def test_assign_page_numbers_preserves_metadata(self):
        """F2.6.3: Page assignment should preserve other metadata."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline()

        chunks = [
            {"content": "test", "metadata": {"key": "value"}}
        ]

        result = pipeline._assign_page_numbers(chunks, start_page=1)

        assert result[0]["metadata"] == {"key": "value"}
        assert "page_number" in result[0]


@pytest.mark.unit
class TestIDGeneration:
    """Test deterministic ID generation (F2.6.4)."""

    def test_id_generation_deterministic(self):
        """F2.6.4: Same input should produce same ID."""
        from src.pdf_framework.utils.id_generator import generate_id

        id1 = generate_id("document.pdf", 0, 0)
        id2 = generate_id("document.pdf", 0, 0)

        assert id1 == id2

    def test_id_generation_unique_for_different_chunks(self):
        """F2.6.4: Different chunks should have unique IDs."""
        from src.pdf_framework.utils.id_generator import generate_id

        ids = [
            generate_id("doc.pdf", 0, i)
            for i in range(100)
        ]

        assert len(set(ids)) == 100  # All unique

    def test_id_generation_includes_context(self):
        """F2.6.4: ID should include document and page info."""
        from src.pdf_framework.utils.id_generator import generate_id

        id1 = generate_id("doc1.pdf", 1, 0)
        id2 = generate_id("doc2.pdf", 1, 0)
        id3 = generate_id("doc1.pdf", 2, 0)

        assert id1 != id2  # Different documents
        assert id1 != id3  # Different pages

    def test_id_format_consistent(self):
        """F2.6.4: ID format should be consistent."""
        from src.pdf_framework.utils.id_generator import generate_id

        id_value = generate_id("test.pdf", 0, 0)

        # Should be string with consistent format
        assert isinstance(id_value, str)
        assert len(id_value) > 0
