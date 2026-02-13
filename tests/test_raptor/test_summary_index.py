"""Tests for Document Summary Index (Phase 13.4)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.processing.summary_index import (
    DocumentSummary,
    DocumentSummaryIndex,
    get_summary_index,
)
from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult

# ChatAnthropic is imported lazily inside methods, patch at source
PATCH_CHAT = "langchain_anthropic.ChatAnthropic"
PATCH_CHROMA = "src.pdf_framework.vector_store.providers.chroma.ChromaVectorStore"


# ---------------------------------------------------------------------------
# DocumentSummary model
# ---------------------------------------------------------------------------

class TestDocumentSummary:
    def test_required_fields(self):
        ds = DocumentSummary(
            document_id="doc1",
            summary="A summary",
            title="Title",
            chunk_count=10,
            created_at="2024-01-01T00:00:00",
        )
        assert ds.document_id == "doc1"
        assert ds.summary == "A summary"
        assert ds.chunk_count == 10

    def test_defaults(self):
        ds = DocumentSummary(
            document_id="doc1",
            summary="s",
            title="t",
            chunk_count=0,
            created_at="2024-01-01",
        )
        assert ds.embedding is None
        assert ds.metadata == {}

    def test_with_embedding(self):
        ds = DocumentSummary(
            document_id="doc1",
            summary="s",
            title="t",
            chunk_count=5,
            created_at="2024-01-01",
            embedding=[0.1, 0.2, 0.3],
        )
        assert ds.embedding == [0.1, 0.2, 0.3]

    def test_with_metadata(self):
        ds = DocumentSummary(
            document_id="doc1",
            summary="s",
            title="t",
            chunk_count=5,
            created_at="2024-01-01",
            metadata={"key": "val"},
        )
        assert ds.metadata["key"] == "val"


# ---------------------------------------------------------------------------
# DocumentSummaryIndex
# ---------------------------------------------------------------------------

class TestDocumentSummaryIndex:
    def test_init_defaults(self):
        idx = DocumentSummaryIndex()
        assert idx._collection_name == "document_summaries"
        assert idx._summarization_model == "claude-haiku-4-5-20251001"
        assert idx._api_key == ""
        assert idx._initialized is False

    def test_init_custom(self):
        idx = DocumentSummaryIndex(
            collection_name="my_summaries",
            persist_dir="/tmp/test",
            summarization_model="custom-model",
            api_key="my-key",
        )
        assert idx._collection_name == "my_summaries"
        assert idx._api_key == "my-key"
        assert idx._summarization_model == "custom-model"

    @pytest.mark.asyncio
    async def test_ensure_initialized(self):
        idx = DocumentSummaryIndex(api_key="key")

        mock_store = AsyncMock()
        mock_store.initialize = AsyncMock()

        with patch(PATCH_CHROMA, return_value=mock_store):
            await idx._ensure_initialized()

        assert idx._initialized is True
        assert idx._vector_store is mock_store
        mock_store.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_initialized_only_once(self):
        idx = DocumentSummaryIndex(api_key="key")

        mock_store = AsyncMock()
        mock_store.initialize = AsyncMock()

        with patch(PATCH_CHROMA, return_value=mock_store):
            await idx._ensure_initialized()
            await idx._ensure_initialized()

        # Should only initialize once
        assert mock_store.initialize.await_count == 1

    @pytest.mark.asyncio
    async def test_embed_text_returns_384_floats(self):
        idx = DocumentSummaryIndex()
        emb = await idx._embed_text("test text")
        assert len(emb) == 384
        assert all(isinstance(v, float) for v in emb)

    @pytest.mark.asyncio
    async def test_embed_text_deterministic(self):
        idx = DocumentSummaryIndex()
        emb1 = await idx._embed_text("same text")
        emb2 = await idx._embed_text("same text")
        assert emb1 == emb2

    @pytest.mark.asyncio
    async def test_add_document(self):
        idx = DocumentSummaryIndex(api_key="key")

        # Pre-initialize with mock store
        mock_store = AsyncMock()
        mock_store.initialize = AsyncMock()
        mock_store.add_documents = AsyncMock(return_value=["summary_doc1"])
        idx._vector_store = mock_store
        idx._initialized = True

        # Mock summary generation
        mock_response = MagicMock()
        mock_response.content = "This is a document summary."

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            result = await idx.add_document(
                document_id="doc1",
                chunks=[{"content": "chunk text"}],
                title="Test Doc",
            )

        assert isinstance(result, DocumentSummary)
        assert result.document_id == "doc1"
        assert result.title == "Test Doc"
        assert result.summary == "This is a document summary."
        assert result.chunk_count == 1

        # Verify store was called
        mock_store.add_documents.assert_awaited_once()
        call_args = mock_store.add_documents.call_args[0]
        assert len(call_args[0]) == 1  # one chunk
        assert call_args[0][0].document_id == "doc1"

    @pytest.mark.asyncio
    async def test_add_document_created_at_is_utc(self):
        idx = DocumentSummaryIndex(api_key="key")

        mock_store = AsyncMock()
        mock_store.add_documents = AsyncMock(return_value=["id"])
        idx._vector_store = mock_store
        idx._initialized = True

        mock_response = MagicMock()
        mock_response.content = "Summary"

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            result = await idx.add_document("doc1", [{"content": "text"}])

        # created_at should be a valid ISO format datetime
        dt = datetime.fromisoformat(result.created_at)
        assert dt.tzinfo is not None  # Should have timezone

    @pytest.mark.asyncio
    async def test_add_document_handles_list_content(self):
        """Handle LangChain returning list[ContentBlock]."""
        idx = DocumentSummaryIndex(api_key="key")

        mock_store = AsyncMock()
        mock_store.add_documents = AsyncMock(return_value=["id"])
        idx._vector_store = mock_store
        idx._initialized = True

        mock_block = MagicMock()
        mock_block.text = "Summary from block"

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            result = await idx.add_document("doc1", [{"content": "text"}])

        assert result.summary == "Summary from block"

    @pytest.mark.asyncio
    async def test_search_returns_summaries(self):
        idx = DocumentSummaryIndex()

        # Pre-initialize
        mock_store = AsyncMock()
        mock_store.search = AsyncMock(return_value=[
            SearchResult(
                chunk=DocumentChunk(
                    id="summary_doc1",
                    content="Summary about AI",
                    document_id="doc1",
                    metadata={
                        "summary_id": "doc1",
                        "title": "AI Paper",
                        "chunk_count": 42,
                        "created_at": "2024-01-01",
                    },
                ),
                score=0.9,
                source="vector",
            ),
        ])
        idx._vector_store = mock_store
        idx._initialized = True

        results = await idx.search(
            query="artificial intelligence",
            query_embedding=[0.1] * 384,
            k=3,
        )

        assert len(results) == 1
        assert results[0].document_id == "doc1"
        assert results[0].title == "AI Paper"
        assert results[0].summary == "Summary about AI"
        assert results[0].embedding is None

    @pytest.mark.asyncio
    async def test_search_no_embedding_returns_empty(self):
        idx = DocumentSummaryIndex()
        idx._initialized = True
        idx._vector_store = AsyncMock()

        results = await idx.search(query="test", query_embedding=None)

        assert results == []

    @pytest.mark.asyncio
    async def test_rebuild(self):
        idx = DocumentSummaryIndex(api_key="key")

        mock_store = AsyncMock()
        mock_store.clear = AsyncMock()
        mock_store.add_documents = AsyncMock(return_value=["id"])
        idx._vector_store = mock_store
        idx._initialized = True

        mock_response = MagicMock()
        mock_response.content = "Summary"

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            await idx.rebuild([
                ("doc1", [{"content": "chunk1"}]),
                ("doc2", [{"content": "chunk2"}]),
            ])

        mock_store.clear.assert_awaited_once()
        assert mock_store.add_documents.await_count == 2

    @pytest.mark.asyncio
    async def test_rebuild_handles_errors(self):
        idx = DocumentSummaryIndex(api_key="key")

        mock_store = AsyncMock()
        mock_store.clear = AsyncMock()
        # First call succeeds, second fails
        mock_store.add_documents = AsyncMock(
            side_effect=[["id1"], Exception("fail")]
        )
        idx._vector_store = mock_store
        idx._initialized = True

        mock_response = MagicMock()
        mock_response.content = "Summary"

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            # Should not raise despite second document failing
            await idx.rebuild([
                ("doc1", [{"content": "c1"}]),
                ("doc2", [{"content": "c2"}]),
            ])

    @pytest.mark.asyncio
    async def test_generate_summary_error_fallback(self):
        idx = DocumentSummaryIndex(api_key="")

        with patch(PATCH_CHAT) as mock_cls:
            mock_cls.side_effect = Exception("API error")

            result = await idx._generate_summary([{"content": "text"}], "doc1")

        assert "Summary not available" in result


# ---------------------------------------------------------------------------
# get_summary_index singleton
# ---------------------------------------------------------------------------

class TestGetSummaryIndex:
    def test_returns_instance(self):
        import src.pdf_framework.processing.summary_index as mod
        mod._summary_index = None

        idx = get_summary_index()
        assert isinstance(idx, DocumentSummaryIndex)
        mod._summary_index = None

    def test_returns_same_instance(self):
        import src.pdf_framework.processing.summary_index as mod
        mod._summary_index = None

        i1 = get_summary_index()
        i2 = get_summary_index()
        assert i1 is i2
        mod._summary_index = None

    def test_accepts_kwargs(self):
        import src.pdf_framework.processing.summary_index as mod
        mod._summary_index = None

        idx = get_summary_index(api_key="my-key", collection_name="custom")
        assert idx._api_key == "my-key"
        assert idx._collection_name == "custom"
        mod._summary_index = None
