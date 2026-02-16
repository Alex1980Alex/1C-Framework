"""Tests for Phase 50: Contextual Retrieval (context_generator.py)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.config import AgentSettings, ContextualRetrievalSettings
from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    DocumentMetadata,
    ProcessedDocument,
)


def _make_chunk(content: str, chunk_id: str = "c1", doc_id: str = "d1") -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        content=content,
        document_id=doc_id,
        metadata={"source": "test.pdf"},
    )


def _make_document(raw_text: str = "Документ о справочниках 1С." * 50) -> ProcessedDocument:
    return ProcessedDocument(
        id="doc_test_001",
        raw_text=raw_text,
        source_path="test.pdf",
        metadata=DocumentMetadata(title="Глава 5"),
    )


@pytest.fixture
def ctx_settings(tmp_path: Path) -> ContextualRetrievalSettings:
    return ContextualRetrievalSettings(
        enabled=True,
        max_context_tokens=128,
        model="claude-haiku-4-5-20251001",
        batch_concurrency=2,
        min_chunk_tokens=10,
        cache_enabled=True,
        cache_db_path=tmp_path / "ctx_cache.db",
    )


@pytest.fixture
def agent_settings() -> AgentSettings:
    return AgentSettings(model="claude-haiku-4-5-20251001", base_url="https://test.api")


class TestContextCache:
    """Tests for _ContextCache SQLite store."""

    def test_cache_put_get(self, tmp_path: Path):
        from src.pdf_framework.processing.context_generator import _ContextCache

        cache = _ContextCache(tmp_path / "test.db")
        assert cache.get("c1") is None

        cache.put("c1", "d1", "This chunk discusses config.", "haiku")
        assert cache.get("c1") == "This chunk discusses config."
        cache.close()

    def test_cache_invalidate_document(self, tmp_path: Path):
        from src.pdf_framework.processing.context_generator import _ContextCache

        cache = _ContextCache(tmp_path / "test.db")
        cache.put("c1", "d1", "ctx1", "haiku")
        cache.put("c2", "d1", "ctx2", "haiku")
        cache.put("c3", "d2", "ctx3", "haiku")

        deleted = cache.invalidate_document("d1")
        assert deleted == 2
        assert cache.get("c1") is None
        assert cache.get("c3") == "ctx3"
        cache.close()

    def test_cache_upsert(self, tmp_path: Path):
        from src.pdf_framework.processing.context_generator import _ContextCache

        cache = _ContextCache(tmp_path / "test.db")
        cache.put("c1", "d1", "old context", "haiku")
        cache.put("c1", "d1", "new context", "haiku")
        assert cache.get("c1") == "new context"
        cache.close()


class TestContextGenerator:
    """Tests for ContextGenerator with mocked LLM."""

    @pytest.mark.asyncio
    async def test_generate_context(self, ctx_settings, agent_settings):
        from src.pdf_framework.processing.context_generator import ContextGenerator

        mock_response = MagicMock()
        mock_response.content = "Этот фрагмент описывает справочники в платформе 1С:Предприятие."

        with patch.object(
            ContextGenerator, "__init__", lambda self, **kw: None
        ):
            gen = ContextGenerator.__new__(ContextGenerator)
            gen._settings = agent_settings
            gen._ctx = ctx_settings
            gen._llm = AsyncMock()
            gen._llm.ainvoke = AsyncMock(return_value=mock_response)
            gen._semaphore = asyncio.Semaphore(2)
            gen._cache = None
            gen._model_name = "haiku"

            chunk = _make_chunk("Справочники используются для хранения условно постоянной информации.")
            doc = _make_document()
            context = await gen.generate_context(chunk, doc)

            assert len(context) > 15
            assert "справочник" in context.lower()

    @pytest.mark.asyncio
    async def test_skip_short_chunks(self, ctx_settings, agent_settings):
        from src.pdf_framework.processing.context_generator import ContextGenerator

        with patch.object(
            ContextGenerator, "__init__", lambda self, **kw: None
        ):
            gen = ContextGenerator.__new__(ContextGenerator)
            gen._settings = agent_settings
            gen._ctx = ctx_settings  # min_chunk_tokens=10
            gen._llm = AsyncMock()
            gen._semaphore = asyncio.Semaphore(2)
            gen._cache = None
            gen._model_name = "haiku"

            # Short chunk (< 10 words)
            chunk = _make_chunk("Короткий текст.")
            doc = _make_document()
            await gen._process_chunk(chunk, doc)

            assert chunk.metadata["context"] == ""
            assert chunk.metadata["contextual_content"] == "Короткий текст."
            # LLM should NOT have been called
            gen._llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, ctx_settings, agent_settings, tmp_path):
        from src.pdf_framework.processing.context_generator import ContextGenerator, _ContextCache

        cache = _ContextCache(tmp_path / "ctx.db")
        cache.put("c1", "d1", "Cached context about config.", "haiku")

        with patch.object(
            ContextGenerator, "__init__", lambda self, **kw: None
        ):
            gen = ContextGenerator.__new__(ContextGenerator)
            gen._settings = agent_settings
            gen._ctx = ctx_settings
            gen._llm = AsyncMock()
            gen._semaphore = asyncio.Semaphore(2)
            gen._cache = cache
            gen._model_name = "haiku"

            chunk = _make_chunk(
                "Достаточно длинный текст чтобы пройти проверку на минимальное количество слов.",
                chunk_id="c1",
            )
            doc = _make_document()
            await gen._process_chunk(chunk, doc)

            assert chunk.metadata["context"] == "Cached context about config."
            assert "Cached context about config." in chunk.metadata["contextual_content"]
            # LLM should NOT have been called — cache hit
            gen._llm.ainvoke.assert_not_called()

        cache.close()

    @pytest.mark.asyncio
    async def test_enrich_chunks_batch(self, ctx_settings, agent_settings):
        from src.pdf_framework.processing.context_generator import ContextGenerator

        mock_response = MagicMock()
        mock_response.content = "Контекст: этот фрагмент описывает объекты конфигурации."

        with patch.object(
            ContextGenerator, "__init__", lambda self, **kw: None
        ):
            gen = ContextGenerator.__new__(ContextGenerator)
            gen._settings = agent_settings
            gen._ctx = ctx_settings
            gen._llm = AsyncMock()
            gen._llm.ainvoke = AsyncMock(return_value=mock_response)
            gen._semaphore = asyncio.Semaphore(2)
            gen._cache = None
            gen._model_name = "haiku"

            chunks = [
                _make_chunk(
                    "Справочники хранят условно постоянную информацию о множестве объектов "
                    "конфигурации и используются для организации аналитического учёта в системе.",
                    f"c{i}",
                )
                for i in range(3)
            ]
            doc = _make_document()
            result = await gen.enrich_chunks(chunks, doc)

            assert len(result) == 3
            for c in result:
                assert c.metadata.get("context") != ""
                assert "contextual_content" in c.metadata

    @pytest.mark.asyncio
    async def test_ralph_wiggum_retry_on_short_context(self, ctx_settings, agent_settings):
        from src.pdf_framework.processing.context_generator import ContextGenerator

        # First response too short, second OK
        short_response = MagicMock()
        short_response.content = "OK"  # < 15 chars
        good_response = MagicMock()
        good_response.content = "Этот фрагмент описывает механизм проведения документов в 1С."

        with patch.object(
            ContextGenerator, "__init__", lambda self, **kw: None
        ):
            gen = ContextGenerator.__new__(ContextGenerator)
            gen._settings = agent_settings
            gen._ctx = ctx_settings
            gen._llm = AsyncMock()
            gen._llm.ainvoke = AsyncMock(side_effect=[short_response, good_response])
            gen._semaphore = asyncio.Semaphore(2)
            gen._cache = None
            gen._model_name = "haiku"

            chunk = _make_chunk("Проведение документов создаёт движения по регистрам.")
            doc = _make_document()
            context = await gen.generate_context(chunk, doc)

            assert len(context) > 15
            assert gen._llm.ainvoke.call_count == 2  # Retried once

    @pytest.mark.asyncio
    async def test_content_block_list_handling(self, ctx_settings, agent_settings):
        """Test that list[ContentBlock] response is properly extracted."""
        from src.pdf_framework.processing.context_generator import ContextGenerator

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Этот фрагмент описывает справочники и их реквизиты."
        mock_response.content = [mock_block]

        with patch.object(
            ContextGenerator, "__init__", lambda self, **kw: None
        ):
            gen = ContextGenerator.__new__(ContextGenerator)
            gen._settings = agent_settings
            gen._ctx = ctx_settings
            gen._llm = AsyncMock()
            gen._llm.ainvoke = AsyncMock(return_value=mock_response)
            gen._semaphore = asyncio.Semaphore(2)
            gen._cache = None
            gen._model_name = "haiku"

            chunk = _make_chunk("Справочники хранят условно постоянную информацию о множестве объектов.")
            doc = _make_document()
            context = await gen.generate_context(chunk, doc)

            assert "справочник" in context.lower()
