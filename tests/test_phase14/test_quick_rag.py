"""Tests for QuickRAG High-Level API (Phase 14.4)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.pdf_framework.quick import (
    IndexResult,
    QuickRAG,
    get_quick_rag,
)


# ---------------------------------------------------------------------------
# IndexResult
# ---------------------------------------------------------------------------

class TestIndexResult:
    def test_create(self):
        r = IndexResult(
            document_id="doc-1",
            chunks_stored=42,
            embeddings_computed=42,
            source_path="/tmp/test.pdf",
        )
        assert r.document_id == "doc-1"
        assert r.chunks_stored == 42
        assert r.embeddings_computed == 42
        assert r.source_path == "/tmp/test.pdf"

    def test_str_with_path(self):
        r = IndexResult(
            document_id="doc-1",
            chunks_stored=10,
            embeddings_computed=10,
            source_path="test.pdf",
        )
        assert "10 chunks" in str(r)
        assert "test.pdf" in str(r)

    def test_str_without_path(self):
        r = IndexResult(
            document_id="doc-1",
            chunks_stored=5,
            embeddings_computed=5,
        )
        assert "doc-1" in str(r)

    def test_optional_source_path(self):
        r = IndexResult(
            document_id="doc-1",
            chunks_stored=1,
            embeddings_computed=1,
        )
        assert r.source_path is None


# ---------------------------------------------------------------------------
# QuickRAG — Init
# ---------------------------------------------------------------------------

class TestQuickRAGInit:
    def test_default_state(self):
        rag = QuickRAG()
        assert rag._initialized is False
        assert rag._components is None
        assert rag._kwargs == {}

    def test_kwargs_stored(self):
        rag = QuickRAG(strategy="vector", api_key="key123")
        assert rag._kwargs["strategy"] == "vector"
        assert rag._kwargs["api_key"] == "key123"

    @patch("src.pdf_framework.quick.asyncio")
    @patch("src.pdf_framework.config.get_settings")
    @patch("src.api.dependencies.components.Components")
    def test_ensure_initialized(self, mock_comp_cls, mock_settings, mock_asyncio):
        mock_settings.return_value = MagicMock()
        mock_comp = MagicMock()
        mock_comp_cls.return_value = mock_comp
        mock_loop = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_loop.run_until_complete.return_value = None

        rag = QuickRAG()
        rag._ensure_initialized()

        assert rag._initialized is True
        assert rag._components is mock_comp
        mock_asyncio.new_event_loop.assert_called_once()
        mock_asyncio.set_event_loop.assert_called_once_with(mock_loop)
        mock_loop.run_until_complete.assert_called_once()

    @patch("src.pdf_framework.quick.asyncio")
    @patch("src.pdf_framework.config.get_settings")
    @patch("src.api.dependencies.components.Components")
    def test_ensure_initialized_idempotent(self, mock_comp_cls, mock_settings, mock_asyncio):
        mock_settings.return_value = MagicMock()
        mock_comp_cls.return_value = MagicMock()
        mock_loop = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_loop.run_until_complete.return_value = None

        rag = QuickRAG()
        rag._ensure_initialized()
        rag._ensure_initialized()  # Second call should be no-op

        mock_asyncio.new_event_loop.assert_called_once()

    @patch("src.pdf_framework.quick.asyncio")
    @patch("src.pdf_framework.config.get_settings")
    @patch("src.api.dependencies.components.Components")
    def test_settings_overrides(self, mock_comp_cls, mock_settings, mock_asyncio):
        mock_s = MagicMock()
        mock_s.strategy = "default"
        mock_settings.return_value = mock_s
        mock_comp_cls.return_value = MagicMock()
        mock_loop = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_loop.run_until_complete.return_value = None

        rag = QuickRAG(strategy="vector")
        rag._ensure_initialized()

        assert mock_s.strategy == "vector"


# ---------------------------------------------------------------------------
# QuickRAG — Sync methods (with mocked components)
# ---------------------------------------------------------------------------

class TestQuickRAGSync:
    def _make_initialized_rag(self):
        """Create a QuickRAG with mocked components."""
        rag = QuickRAG()
        rag._initialized = True
        rag._loop = MagicMock()
        rag._components = MagicMock()
        return rag

    def test_add_calls_loop(self):
        rag = self._make_initialized_rag()
        rag._loop.run_until_complete.return_value = IndexResult(
            document_id="d1", chunks_stored=5, embeddings_computed=5,
        )

        result = rag.add("test.pdf")
        assert result.document_id == "d1"
        rag._loop.run_until_complete.assert_called_once()

    def test_search_calls_loop(self):
        rag = self._make_initialized_rag()
        rag._loop.run_until_complete.return_value = [
            {"score": 0.9, "content": "test", "source": "s1", "metadata": {}}
        ]

        result = rag.search("query")
        assert len(result) == 1
        assert result[0]["score"] == 0.9

    def test_ask_calls_loop(self):
        rag = self._make_initialized_rag()
        rag._loop.run_until_complete.return_value = "The answer is 42."

        result = rag.ask("What is the meaning?")
        assert result == "The answer is 42."

    def test_stats_calls_loop(self):
        rag = self._make_initialized_rag()
        rag._loop.run_until_complete.return_value = {
            "chunks": 100, "entities": 50, "relations": 25,
        }

        result = rag.stats()
        assert result["chunks"] == 100
        assert result["entities"] == 50


# ---------------------------------------------------------------------------
# QuickRAG — Async methods
# ---------------------------------------------------------------------------

class TestQuickRAGAsync:
    def _make_initialized_rag(self):
        rag = QuickRAG()
        rag._initialized = True
        rag._loop = MagicMock()
        rag._components = MagicMock()
        return rag

    @pytest.mark.asyncio
    async def test_aadd(self):
        rag = self._make_initialized_rag()
        mock_loader = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.source_path = "test.pdf"
        mock_loader.load.return_value = mock_doc
        rag._components.loader = mock_loader

        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = ["chunk1", "chunk2"]
        rag._components.pipeline = mock_pipeline

        index_result = IndexResult(
            document_id="doc-1", chunks_stored=2, embeddings_computed=2,
        )
        rag._components.indexer = AsyncMock()
        rag._components.indexer.index_chunks.return_value = index_result

        result = await rag.aadd("test.pdf")
        assert result.document_id == "doc-1"
        assert result.chunks_stored == 2

    @pytest.mark.asyncio
    async def test_asearch(self):
        rag = self._make_initialized_rag()

        mock_result = MagicMock()
        mock_result.score = 0.95
        mock_result.chunk.content = "Test content"
        mock_result.source = "source1"
        mock_result.chunk.metadata = {"page": 1}

        mock_response = MagicMock()
        mock_response.results = [mock_result]

        rag._components.search_manager = AsyncMock()
        rag._components.search_manager.search.return_value = mock_response

        result = await rag.asearch("query", k=3)
        assert len(result) == 1
        assert result[0]["score"] == 0.95
        assert result[0]["content"] == "Test content"

    @pytest.mark.asyncio
    async def test_aask(self):
        rag = self._make_initialized_rag()
        rag._components.settings = MagicMock()
        rag._components.settings.anthropic_api_key = "key"

        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {"answer": "42"}

        with patch("src.pdf_framework.agents.rag.agent.create_rag_agent", return_value=mock_agent):
            result = await rag.aask("What?")

        assert result == "42"

    @pytest.mark.asyncio
    async def test_aask_no_answer(self):
        rag = self._make_initialized_rag()
        rag._components.settings = MagicMock()
        rag._components.settings.anthropic_api_key = "key"

        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {}  # No "answer" key

        with patch("src.pdf_framework.agents.rag.agent.create_rag_agent", return_value=mock_agent):
            result = await rag.aask("What?")

        assert result == "No answer generated."

    @pytest.mark.asyncio
    async def test_astats(self):
        rag = self._make_initialized_rag()
        rag._components.vector_store = AsyncMock()
        rag._components.vector_store.count.return_value = 100
        rag._components.graph_store = AsyncMock()
        rag._components.graph_store.get_statistics.return_value = {
            "entity_count": 50,
            "relation_count": 25,
        }

        result = await rag.astats()
        assert result["chunks"] == 100
        assert result["entities"] == 50
        assert result["relations"] == 25


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestQuickRAGSingleton:
    def test_get_quick_rag(self):
        import src.pdf_framework.quick as mod
        mod._quick_rag = None

        r1 = get_quick_rag(strategy="vector")
        r2 = get_quick_rag(strategy="hybrid")  # Ignored — singleton
        assert r1 is r2
        assert r1._kwargs["strategy"] == "vector"

        mod._quick_rag = None  # Cleanup
