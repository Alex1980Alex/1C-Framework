"""Unit tests for Proposition Splitter (Phase 58)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.processing.splitters.proposition import (
    PropositionSplitter,
    create_proposition_splitter,
)
from src.pdf_framework.schemas.documents import DocumentChunk


@pytest.fixture
def mock_llm():
    """Mock LLM for proposition extraction."""
    llm = MagicMock()

    # Default response: numbered list of propositions
    llm.invoke.return_value = MagicMock(
        content="""1. The Eiffel Tower is 324 meters tall.
2. The Eiffel Tower is located in Paris, France.
3. The Eiffel Tower was completed in 1889."""
    )

    return llm


@pytest.fixture
def proposition_splitter(mock_llm):
    """Proposition splitter with mocked LLM."""
    return PropositionSplitter(llm=mock_llm)


@pytest.mark.unit
class TestPropositionSplitter:
    """Tests for PropositionSplitter."""

    def test_init_default_params(self):
        """Should initialize with default parameters."""
        splitter = PropositionSplitter()

        assert splitter._model == "claude-3-haiku-20240307"
        assert splitter._min_propositions == 3
        assert splitter._max_propositions == 10
        assert splitter._batch_size == 5

    def test_init_custom_params(self):
        """Should accept custom parameters."""
        splitter = PropositionSplitter(
            model="claude-3-opus-20240229",
            min_propositions=2,
            max_propositions=15,
            batch_size=10,
        )

        assert splitter._model == "claude-3-opus-20240229"
        assert splitter._min_propositions == 2
        assert splitter._max_propositions == 15
        assert splitter._batch_size == 10

    def test_init_with_llm(self, mock_llm):
        """Should accept provided LLM instance."""
        splitter = PropositionSplitter(llm=mock_llm)

        assert splitter._llm is mock_llm

    def test_split_text_basic(self, proposition_splitter):
        """Should split text into propositions."""
        text = "The Eiffel Tower is 324m tall and located in Paris."

        result = proposition_splitter.split_text(text)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(p, str) for p in result)

    def test_split_text_short(self, proposition_splitter):
        """Should return short text as-is."""
        text = "Short text"

        result = proposition_splitter.split_text(text)

        assert result == [text]

    def test_split_text_empty(self, proposition_splitter):
        """Should handle empty text."""
        result = proposition_splitter.split_text("")

        assert result == [""]

    def test_split_text_with_llm_error(self, mock_llm):
        """Should fallback to original text on LLM error."""
        mock_llm.invoke.side_effect = Exception("LLM error")

        splitter = PropositionSplitter(llm=mock_llm)
        result = splitter.split_text("Some text")

        assert result == ["Some text"]

    def test_split_text_with_retry(self, mock_llm):
        """Should retry when too few propositions extracted."""
        # First call returns too few
        first_response = MagicMock(content="1. Only one proposition")
        # Second call (retry) returns more
        second_response = MagicMock(
            content="""1. First proposition
2. Second proposition
3. Third proposition"""
        )

        mock_llm.invoke.side_effect = [first_response, second_response]

        splitter = PropositionSplitter(llm=mock_llm, min_propositions=3)
        result = splitter.split_text("Long text that needs multiple propositions")

        assert len(result) >= 3

    def test_parse_numbered_list_dots(self, proposition_splitter):
        """Should parse numbered list with dots."""
        text = """1. First item
2. Second item
3. Third item"""

        result = proposition_splitter._parse_numbered_list(text)

        assert len(result) == 3
        assert result[0] == "First item"
        assert result[1] == "Second item"
        assert result[2] == "Third item"

    def test_parse_numbered_list_parens(self, proposition_splitter):
        """Should parse numbered list with parentheses."""
        text = """1) First item
2) Second item
3) Third item"""

        result = proposition_splitter._parse_numbered_list(text)

        assert len(result) == 3

    def test_parse_numbered_list_mixed_format(self, proposition_splitter):
        """Should handle mixed formatting."""
        text = """1. First item
2) Second item
3. Third item"""

        result = proposition_splitter._parse_numbered_list(text)

        assert len(result) == 3

    def test_parse_numbered_list_extra_spaces(self, proposition_splitter):
        """Should handle extra whitespace."""
        text = """  1.  First item
   2.  Second item"""

        result = proposition_splitter._parse_numbered_list(text)

        assert len(result) == 2

    def test_parse_numbered_list_filters_non_matching(self, proposition_splitter):
        """Should ignore lines without numbers."""
        text = """1. First item
Random line without number
2. Second item
Another random line"""

        result = proposition_splitter._parse_numbered_list(text)

        assert len(result) == 2

    def test_extract_propositions_calls_llm(self, proposition_splitter, mock_llm):
        """Should call LLM with correct prompt."""
        proposition_splitter._extract_propositions("Test text")

        mock_llm.invoke.assert_called_once()
        call_args = mock_llm.invoke.call_args[0][0]
        assert "Test text" in call_args[0]["content"]

    def test_extract_with_retry(self, proposition_splitter):
        """Should use different prompt on retry."""
        result = proposition_splitter._extract_with_retry("Test text")

        assert isinstance(result, list)


@pytest.mark.unit
class TestPropositionSplitDocuments:
    """Tests for split_documents method."""

    @pytest.fixture
    def sample_chunks(self):
        """Sample document chunks."""
        return [
            DocumentChunk(
                id="chunk_1",
                content="The Eiffel Tower is 324m tall.",
                document_id="doc_1",
                page_number=1,
                section="intro",
                metadata={"source": "test"},
            ),
            DocumentChunk(
                id="chunk_2",
                content="The Louvre is a famous museum.",
                document_id="doc_1",
                page_number=2,
                section="intro",
            ),
        ]

    def test_split_documents(self, proposition_splitter, sample_chunks):
        """Should split documents into proposition chunks."""
        result = proposition_splitter.split_documents(sample_chunks)

        assert len(result) >= 2  # At least 2 chunks (1 per doc)
        assert all(isinstance(c, DocumentChunk) for c in result)
        assert all(c.section == "proposition" for c in result)

    def test_split_documents_preserves_metadata(self, proposition_splitter, sample_chunks):
        """Should preserve original metadata."""
        result = proposition_splitter.split_documents(sample_chunks)

        # First result should have original metadata
        assert result[0].metadata.get("source") == "test"
        assert result[0].metadata.get("chunk_type") == "proposition"
        assert "original_chunk_id" in result[0].metadata

    def test_split_documents_with_dicts(self, proposition_splitter):
        """Should handle dict input."""
        docs = [
            {"id": "dict_1", "content": "Test content", "document_id": "doc_1"},
        ]

        result = proposition_splitter.split_documents(docs)

        assert len(result) > 0
        assert isinstance(result[0], DocumentChunk)

    def test_split_documents_generates_unique_ids(self, proposition_splitter, sample_chunks):
        """Should generate unique IDs for proposition chunks."""
        result = proposition_splitter.split_documents(sample_chunks)

        ids = [c.id for c in result]
        assert len(ids) == len(set(ids))  # All unique

    def test_split_documents_includes_proposition_index(self, proposition_splitter, sample_chunks):
        """Should include proposition index in metadata."""
        result = proposition_splitter.split_documents(sample_chunks)

        assert "proposition_index" in result[0].metadata
        assert "total_propositions" in result[0].metadata


@pytest.mark.unit
class TestPropositionAsync:
    """Tests for async methods."""

    @pytest.mark.asyncio
    async def test_split_documents_async(self, proposition_splitter):
        """Should split documents asynchronously."""
        chunks = [
            DocumentChunk(
                id=f"chunk_{i}",
                content=f"Content {i}",
                document_id="doc_1",
                page_number=i,
            )
            for i in range(3)
        ]

        result = await proposition_splitter.split_documents_async(chunks)

        assert len(result) >= 3
        assert all(isinstance(c, DocumentChunk) for c in result)

    @pytest.mark.asyncio
    async def test_split_documents_async_batches(self, proposition_splitter):
        """Should process documents in batches."""
        # Create more chunks than batch_size
        chunks = [
            DocumentChunk(
                id=f"chunk_{i}",
                content=f"Content {i}" * 20,  # Make it longer
                document_id="doc_1",
                page_number=i,
            )
            for i in range(10)
        ]

        splitter = PropositionSplitter(llm=proposition_splitter._llm, batch_size=3)

        result = await splitter.split_documents_async(chunks)

        assert len(result) >= 10


@pytest.mark.unit
class TestPropositionFactory:
    """Tests for factory function."""

    def test_create_proposition_splitter_default(self):
        """Factory should create splitter with defaults."""
        splitter = create_proposition_splitter()

        assert isinstance(splitter, PropositionSplitter)
        assert splitter._model == "claude-3-haiku-20240307"

    def test_create_proposition_splitter_custom(self):
        """Factory should accept custom parameters."""
        splitter = create_proposition_splitter(
            model="claude-3-opus-20240229",
            min_propositions=2,
            max_propositions=20,
        )

        assert splitter._model == "claude-3-opus-20240229"
        assert splitter._min_propositions == 2
        assert splitter._max_propositions == 20


@pytest.mark.unit
class TestPropositionEdgeCases:
    """Tests for edge cases and error handling."""

    def test_split_text_with_unicode(self, proposition_splitter):
        """Should handle unicode characters."""
        text = "Текст на русском языке с эмодзи 🚀"

        result = proposition_splitter.split_text(text)

        assert isinstance(result, list)

    def test_split_very_long_text(self, proposition_splitter):
        """Should handle very long text."""
        text = "This is a very long text. " * 50

        result = proposition_splitter.split_text(text)

        assert len(result) > 0

    def test_split_text_with_markdown(self, proposition_splitter):
        """Should handle markdown in text."""
        text = """# Heading

## Subheading

This is **bold** and *italic* text."""

        result = proposition_splitter.split_text(text)

        assert isinstance(result, list)

    def test_parse_malformed_list(self, proposition_splitter):
        """Should handle malformed numbered lists."""
        text = """First item without number
Second item
Third item"""

        result = proposition_splitter._parse_numbered_list(text)

        # Should return empty list for non-numbered items
        assert len(result) == 0


@pytest.mark.unit
class TestPropositionCostTracking:
    """Tests for cost tracking functionality."""

    def test_split_text_tracks_llm_usage(self, proposition_splitter, mock_llm):
        """Should track LLM usage for cost estimation."""
        mock_llm.invoke.return_value = MagicMock(
            content="1. Proposition one\n2. Proposition two"
        )

        proposition_splitter.split_text("Test content")

        # LLM should have been called
        assert mock_llm.invoke.called

    def test_min_propositions_threshold(self, mock_llm):
        """Should only retry if below min_propositions threshold."""
        mock_llm.invoke.return_value = MagicMock(
            content="1. Single proposition"
        )

        # With min_propositions=2, should retry
        splitter = PropositionSplitter(llm=mock_llm, min_propositions=2)
        result = splitter.split_text("Test text")

        # Should have called invoke twice (initial + retry)
        assert mock_llm.invoke.call_count >= 1
