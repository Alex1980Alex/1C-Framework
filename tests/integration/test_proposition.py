"""Integration tests for Proposition Chunking (Phase 58)."""

from unittest.mock import MagicMock

import pytest

from src.pdf_framework.processing.splitters.proposition import PropositionSplitter
from src.pdf_framework.schemas.documents import DocumentChunk


@pytest.fixture
def mock_llm():
    """Mock LLM for proposition extraction."""
    llm = MagicMock()

    # Simulate realistic proposition extraction
    llm.invoke.return_value = MagicMock(
        content="""1. Documents are primary objects for storing data in 1C:Enterprise.
2. Each document has a unique number and date.
3. Documents can be posted to update registers.
4. Catalogs are reference objects that store static data.
5. Catalogs have a hierarchical structure with groups and items."""
    )

    return llm


@pytest.fixture
def proposition_splitter(mock_llm):
    """Proposition splitter with mocked LLM."""
    return PropositionSplitter(llm=mock_llm, batch_size=2)


@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return DocumentChunk(
        id="doc_chunk_001",
        content="""Documents are primary objects for storing data in 1C:Enterprise.
Each document has a unique number and date. Documents can be posted to update registers.
Catalogs are reference objects that store static data with hierarchical structure.""",
        document_id="doc_001",
        page_number=1,
        section="introduction",
        metadata={"chapter": "Objects"},
    )


@pytest.mark.integration
class TestPropositionSplitterIntegration:
    """Integration tests for proposition splitter."""

    def test_split_single_document(self, proposition_splitter, sample_document):
        """Test splitting a single document chunk."""
        result = proposition_splitter.split_documents([sample_document])

        assert len(result) >= 3  # Should generate multiple propositions
        assert all(isinstance(c, DocumentChunk) for c in result)
        assert all(c.section == "proposition" for c in result)

    def test_split_multiple_documents(self, proposition_splitter):
        """Test splitting multiple document chunks."""
        chunks = [
            DocumentChunk(
                id=f"chunk_{i}",
                content=f"This is content for chunk {i}. It contains multiple facts.",
                document_id="doc_001",
                page_number=i,
            )
            for i in range(5)
        ]

        result = proposition_splitter.split_documents(chunks)

        # Should have more chunks than input (propositions > chunks)
        assert len(result) >= 5
        assert all(c.metadata.get("chunk_type") == "proposition" for c in result)

    def test_propositions_link_to_original(self, proposition_splitter, sample_document):
        """Test that propositions link back to original chunk."""
        result = proposition_splitter.split_documents([sample_document])

        for prop in result:
            assert prop.metadata.get("original_chunk_id") == sample_document.id
            assert prop.document_id == sample_document.document_id

    def test_propositions_have_sequential_indices(self, proposition_splitter, sample_document):
        """Test that propositions have sequential indices."""
        result = proposition_splitter.split_documents([sample_document])

        indices = [c.metadata.get("proposition_index") for c in result]
        assert indices == list(range(len(result)))

    def test_propositions_include_total_count(self, proposition_splitter, sample_document):
        """Test that each proposition includes total count."""
        result = proposition_splitter.split_documents([sample_document])

        for prop in result:
            assert prop.metadata.get("total_propositions") == len(result)

    def test_preserves_original_metadata(self, proposition_splitter, sample_document):
        """Test that original metadata is preserved."""
        result = proposition_splitter.split_documents([sample_document])

        assert result[0].metadata.get("chapter") == "Objects"

    def test_proposition_content_is_subset(self, proposition_splitter, sample_document):
        """Test that proposition content is from original text."""
        result = proposition_splitter.split_documents([sample_document])

        # Each proposition should be shorter than original
        for prop in result:
            assert len(prop.content) <= len(sample_document.content)


@pytest.mark.integration
class TestPropositionAsyncIntegration:
    """Integration tests for async proposition splitting."""

    @pytest.mark.asyncio
    async def test_async_split_documents(self, proposition_splitter):
        """Test async document splitting."""
        chunks = [
            DocumentChunk(
                id=f"chunk_{i}",
                content=f"Content {i} with facts A and B.",
                document_id="doc_001",
                page_number=i,
            )
            for i in range(6)
        ]

        result = await proposition_splitter.split_documents_async(chunks)

        assert len(result) >= 6
        assert all(isinstance(c, DocumentChunk) for c in result)

    @pytest.mark.asyncio
    async def test_async_batch_processing(self, proposition_splitter):
        """Test that batch processing works correctly."""
        # Create chunks that exceed batch size
        chunks = [
            DocumentChunk(
                id=f"chunk_{i}",
                content=f"Content {i}: Fact one, fact two, fact three.",
                document_id="doc_001",
                page_number=i,
            )
            for i in range(10)
        ]

        result = await proposition_splitter.split_documents_async(chunks)

        # All chunks should be processed
        assert len(result) >= 10


@pytest.mark.integration
class TestPropositionComparison:
    """Compare proposition chunking vs traditional chunking."""

    def test_propositions_increase_chunk_count(self, proposition_splitter):
        """Proposition splitting should increase chunk count."""
        # A single chunk with multiple facts
        chunk = DocumentChunk(
            id="orig_1",
            content="""1C:Enterprise has several object types. Documents store operational data.
Catalogs store reference data. Registers store aggregated data. Each type serves different purposes.""",
            document_id="doc_001",
            page_number=1,
        )

        result = proposition_splitter.split_documents([chunk])

        # Should split into more than 1 chunk
        assert len(result) > 1

    def test_propositions_are_more_focused(self, proposition_splitter):
        """Each proposition should be more focused than original."""
        chunk = DocumentChunk(
            id="orig_1",
            content="""Documents have numbers and dates. Documents can be posted.
Documents have tabular sections. Documents form the basis of accounting.""",
            document_id="doc_001",
            page_number=1,
        )

        result = proposition_splitter.split_documents([chunk])

        # Each proposition should be shorter
        for prop in result:
            assert len(prop.content) < len(chunk.content)

    def test_propositions_preserve_information(self, proposition_splitter, mock_llm):
        """Propositions should preserve key information."""
        # Mock LLM to return comprehensive propositions
        mock_llm.invoke.return_value = MagicMock(
            content="""1. The Eiffel Tower is 324 meters tall.
2. The Eiffel Tower is located in Paris.
3. The Eiffel Tower was completed in 1889.
4. The Eiffel Tower receives 7 million visitors annually."""
        )

        chunk = DocumentChunk(
            id="eiffel",
            content="""The Eiffel Tower is 324 meters tall and located in Paris.
It was completed in 1889 and receives 7 million visitors annually.""",
            document_id="doc_001",
            page_number=1,
        )

        result = proposition_splitter.split_documents([chunk])

        # Key facts should be preserved
        combined = " ".join(c.content for c in result)
        assert "324" in combined
        assert "Paris" in combined
        assert "1889" in combined


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_proposition_workflow(proposition_splitter):
    """End-to-end test: full proposition splitting workflow."""
    # Simulate documents from PDF processing
    documents = [
        DocumentChunk(
            id=f"page_{i}",
            content=f"""Page {i} content about 1C:Enterprise.
Documents are used for operational data. Catalogs store reference data.
Registers accumulate data from documents. Information registers store time-dependent data.
Accumulation registers store numeric totals.""",
            document_id="guide_001",
            page_number=i,
            section=f"chapter_{i}",
        )
        for i in range(1, 4)  # 3 pages
    ]

    # Split into propositions
    propositions = await proposition_splitter.split_documents_async(documents)

    # Verify results
    assert len(propositions) >= 9  # At least 3 per page

    # All should be proposition type
    assert all(c.section == "proposition" for c in propositions)

    # All should have proper metadata
    for prop in propositions:
        assert prop.metadata.get("chunk_type") == "proposition"
        assert prop.metadata.get("original_chunk_id") is not None
        assert prop.metadata.get("proposition_index") is not None


@pytest.mark.integration
class TestPropositionEdgeCases:
    """Integration tests for edge cases."""

    def test_split_empty_document(self, proposition_splitter):
        """Test splitting empty document."""
        chunk = DocumentChunk(
            id="empty",
            content="",
            document_id="doc_001",
            page_number=1,
        )

        result = proposition_splitter.split_documents([chunk])

        # Should handle gracefully
        assert isinstance(result, list)

    def test_split_very_short_document(self, proposition_splitter):
        """Test splitting very short document (< 50 chars)."""
        chunk = DocumentChunk(
            id="short",
            content="Short text",
            document_id="doc_001",
            page_number=1,
        )

        result = proposition_splitter.split_documents([chunk])

        # Short text should be returned as-is
        assert len(result) >= 1

    def test_split_mixed_language_document(self, proposition_splitter, mock_llm):
        """Test splitting document with mixed languages."""
        mock_llm.invoke.return_value = MagicMock(
            content="""1. Справочник — объект для хранения нормативно-справочной информации.
2. Documents are used for operational data.
3. Каждый элемент справочника имеет уникальный код."""
        )

        chunk = DocumentChunk(
            id="mixed",
            content="Справочник — объект хранения. Documents are for data.",
            document_id="doc_001",
            page_number=1,
        )

        result = proposition_splitter.split_documents([chunk])

        # Should handle mixed language
        assert len(result) >= 1

    def test_split_image_chunk(self, proposition_splitter):
        """Test that image chunks are skipped."""
        chunk = DocumentChunk(
            id="image_1",
            content="[Image: Diagram showing document flow]",
            document_id="doc_001",
            page_number=1,
            section="image",
            metadata={"type": "image"},
        )

        result = proposition_splitter.split_documents([chunk])

        # Image chunks should still be processed (actual filtering happens in pipeline)
        assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
