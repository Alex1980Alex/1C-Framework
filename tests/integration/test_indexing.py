"""Integration tests for Indexing Pipeline (F2.11.1).

Tests full indexing flow: PDF → chunks → Qdrant
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
class TestIndexingPipeline:
    """Test full indexing pipeline."""

    async def test_full_indexing_flow(self, tmp_path):
        """F2.11.1: PDF → chunks → Qdrant should work end-to-end."""
        from src.pdf_framework.indexing.pipeline import IndexingPipeline

        # Create test PDF
        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%test content")

        # Mock Qdrant client
        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient") as mock_qdrant:
            mock_qdrant.return_value.upsert = MagicMock()
            mock_qdrant.return_value.create_collection = MagicMock()

            pipeline = IndexingPipeline()

            result = await pipeline.index_pdf(
                file_path=str(test_pdf),
                collection_name="test_collection",
            )

            assert result.document_id is not None
            assert result.chunks_count > 0

    async def test_indexing_with_embeddings(self, tmp_path):
        """F2.11.1: Indexing should generate embeddings."""
        from src.pdf_framework.indexing.pipeline import IndexingPipeline

        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%test content")

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
            with patch("src.pdf_framework.embeddings.providers.local.LocalEmbeddingProvider") as mock_emb:
                mock_emb.return_value.embed_batch = AsyncMock(
                    return_value=[[0.1] * 1024 for _ in range(10)]
                )

                pipeline = IndexingPipeline()

                result = await pipeline.index_pdf(
                    file_path=str(test_pdf),
                    generate_embeddings=True,
                )

                assert result.embeddings_count > 0

    async def test_indexing_metadata_preservation(self, tmp_path):
        """F2.11.1: Should preserve document metadata."""
        from src.pdf_framework.indexing.pipeline import IndexingPipeline

        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%test content")

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
            pipeline = IndexingPipeline()

            metadata = {
                "title": "Test Document",
                "author": "Test Author",
                "tags": ["test", "integration"],
            }

            result = await pipeline.index_pdf(
                file_path=str(test_pdf),
                metadata=metadata,
            )

            assert result.metadata["title"] == "Test Document"

    async def test_indexing_resume_on_error(self, tmp_path):
        """F2.11.1: Should support resuming on partial failure."""
        from src.pdf_framework.indexing.pipeline import IndexingPipeline

        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%test content")

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
            pipeline = IndexingPipeline()

            # First attempt fails partway
            with patch.object(pipeline, "_process_chunks", side_effect=Exception("Partial failure")):
                try:
                    await pipeline.index_pdf(str(test_pdf))
                except Exception:
                    pass

            # Resume should process remaining
            result = await pipeline.index_pdf(str(test_pdf), resume=True)

            assert result is not None

    async def test_indexing_deduplication(self, tmp_path):
        """F2.11.1: Should skip already indexed documents."""
        from src.pdf_framework.indexing.pipeline import IndexingPipeline

        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%test content")

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient") as mock_qdrant:
            # Mock document exists
            mock_qdrant.return_value.retrieve.return_value.points = [
                MagicMock(payload={"document_id": "test_pdf_id"})
            ]

            pipeline = IndexingPipeline()

            result = await pipeline.index_pdf(
                file_path=str(test_pdf),
                skip_if_exists=True,
            )

            assert result.skipped is True

    async def test_indexing_progress_tracking(self, tmp_path):
        """F2.11.1: Should report indexing progress."""
        from src.pdf_framework.indexing.pipeline import IndexingPipeline

        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%test content")

        progress_updates = []

        async def progress_callback(progress):
            progress_updates.append(progress)

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
            pipeline = IndexingPipeline()

            await pipeline.index_pdf(
                file_path=str(test_pdf),
                progress_callback=progress_callback,
            )

            assert len(progress_updates) > 0
