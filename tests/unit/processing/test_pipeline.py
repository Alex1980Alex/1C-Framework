"""Unit tests for Processing pipeline (F2.6.3)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestPipeline:
    """Test ProcessingPipeline operations."""

    def test_pipeline_initialization(self):
        """F2.6.3: Pipeline should initialize with PDFSettings config."""
        from src.pdf_framework.config import PDFSettings
        from src.pdf_framework.processing.pipeline import ProcessingPipeline

        settings = PDFSettings(chunk_size=1000, chunk_overlap=100)
        pipeline = ProcessingPipeline(settings=settings)

        assert pipeline._settings.chunk_size == 1000
        assert pipeline._settings.chunk_overlap == 100

    def test_pipeline_process_document(self):
        """F2.6.3: Should process document synchronously and return chunks."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline
        from src.pdf_framework.schemas.documents import (
            DocumentChunk,
            DocumentMetadata,
            ProcessedDocument,
        )

        pipeline = ProcessingPipeline(enable_metadata_enrichment=False)

        doc = ProcessedDocument(
            id="doc-1",
            source_path="/test.pdf",
            metadata=DocumentMetadata(title="Test Doc", page_count=2),
            raw_text="Hello world chunk one. Hello world chunk two.",
        )
        fake_chunks = [
            DocumentChunk(
                id="c-0",
                content="Hello world chunk one.",
                document_id="doc-1",
                chunk_index=0,
            ),
            DocumentChunk(
                id="c-1",
                content="Hello world chunk two.",
                document_id="doc-1",
                chunk_index=1,
            ),
        ]

        with patch.object(pipeline._splitter, "split", return_value=fake_chunks):
            result = pipeline.process(doc)

        assert len(result) == 2
        assert result[0].content == "Hello world chunk one."
        assert result[1].content == "Hello world chunk two."
        # process() must also set document.chunks
        assert doc.chunks == result

    def test_pipeline_assign_chunk_indices(self):
        """F2.6.3: _assign_page_numbers maps chunks to pages via page_offsets."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline
        from src.pdf_framework.schemas.documents import (
            DocumentChunk,
            DocumentMetadata,
            ProcessedDocument,
        )

        pipeline = ProcessingPipeline()

        raw = "Page one text here. Page two text here."
        # page_offsets: page 1 starts at offset 0, page 2 starts at offset 20
        doc = ProcessedDocument(
            id="doc-pages",
            source_path="/pages.pdf",
            metadata=DocumentMetadata(
                page_count=2,
                extra={"page_offsets": [(0, 1), (20, 2)]},
            ),
            raw_text=raw,
        )

        chunks = [
            DocumentChunk(
                id="c-0",
                content="Page one text here.",
                document_id="doc-pages",
            ),
            DocumentChunk(
                id="c-1",
                content="Page two text here.",
                document_id="doc-pages",
            ),
        ]

        result = ProcessingPipeline._assign_page_numbers(chunks, doc)

        assert result[0].page_number == 1
        assert result[1].page_number == 2

    def test_pipeline_preserve_metadata(self):
        """F2.6.3: Document metadata fields are preserved after process()."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline
        from src.pdf_framework.schemas.documents import (
            DocumentChunk,
            DocumentMetadata,
            ProcessedDocument,
        )

        pipeline = ProcessingPipeline(enable_metadata_enrichment=False)

        doc = ProcessedDocument(
            id="doc-meta",
            source_path="/meta.pdf",
            metadata=DocumentMetadata(
                title="Test Doc",
                author="Test Author",
                page_count=5,
            ),
            raw_text="Some content.",
        )

        fake_chunk = DocumentChunk(
            id="c-0",
            content="Some content.",
            document_id="doc-meta",
        )

        with patch.object(pipeline._splitter, "split", return_value=[fake_chunk]):
            pipeline.process(doc)

        # Metadata must be unchanged after pipeline processing
        assert doc.metadata.title == "Test Doc"
        assert doc.metadata.author == "Test Author"
        assert doc.metadata.page_count == 5
