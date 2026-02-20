"""Unit tests for Processing pipeline (F2.6.3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestPipeline:
    """Test ProcessingPipeline operations."""

    def test_pipeline_initialization(self):
        """F2.6.3: Pipeline should initialize with correct config."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline(
            chunk_size=1000,
            overlap=100,
        )

        assert pipeline.config.chunk_size == 1000
        assert pipeline.config.overlap == 100

    async def test_pipeline_process_document(self):
        """F2.6.3: Should process document and return chunks."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline
        from src.pdf_framework.schemas.documents import ProcessedDocument

        pipeline = ProcessingPipeline()

        mock_loader = AsyncMock()
        mock_loader.load.return_value = ProcessedDocument(
            id="test",
            source_path="/test.pdf",
            metadata=MagicMock(page_count=1),
            raw_text="Test content",
            chunks=[],
        )

        result = await pipeline.process(mock_loader, "/test.pdf")

        assert result.id == "test"

    def test_pipeline_assign_chunk_indices(self):
        """F2.6.3: Chunk indices should be sequential."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline()

        chunks = [
            MagicMock(chunk_index=None),
            MagicMock(chunk_index=None),
            MagicMock(chunk_index=None),
        ]

        result = pipeline._assign_chunk_indices(chunks)

        assert result[0].chunk_index == 0
        assert result[1].chunk_index == 1
        assert result[2].chunk_index == 2

    def test_pipeline_preserve_metadata(self):
        """F2.6.3: Should preserve document metadata through pipeline."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline()

        metadata = {
            "title": "Test Doc",
            "author": "Test Author",
            "page_count": 5,
        }

        result = pipeline._process_metadata(metadata)

        assert result["title"] == "Test Doc"
        assert result["author"] == "Test Author"
        assert result["page_count"] == 5
