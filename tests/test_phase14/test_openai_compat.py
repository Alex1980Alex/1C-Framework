"""Tests for OpenAI-Compatible API models and endpoints (Phase 14.3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.openai_compat import (
    ChatChoice,
    ChatChunk,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelInfo,
    ModelsResponse,
    _run_rag,
)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class TestChatMessage:
    def test_create(self):
        m = ChatMessage(role="user", content="Hello")
        assert m.role == "user"
        assert m.content == "Hello"

    def test_roles(self):
        for role in ("system", "user", "assistant"):
            m = ChatMessage(role=role, content="test")
            assert m.role == role

    def test_invalid_role(self):
        with pytest.raises(Exception):
            ChatMessage(role="admin", content="test")


class TestChatRequest:
    def test_defaults(self):
        r = ChatRequest(messages=[ChatMessage(role="user", content="Hi")])
        assert r.model == "pdf-rag"
        assert r.stream is False
        assert r.temperature is None
        assert r.max_tokens is None

    def test_custom(self):
        r = ChatRequest(
            model="custom",
            messages=[ChatMessage(role="user", content="test")],
            stream=True,
            temperature=0.7,
            max_tokens=100,
        )
        assert r.model == "custom"
        assert r.stream is True
        assert r.temperature == 0.7


class TestChatChoice:
    def test_create(self):
        c = ChatChoice(
            index=0,
            message=ChatMessage(role="assistant", content="response"),
        )
        assert c.index == 0
        assert c.finish_reason == "stop"


class TestChatResponse:
    def test_create(self):
        resp = ChatResponse(
            id="chatcmpl-test123",
            created=1700000000,
            model="pdf-rag",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hi!"),
                )
            ],
        )
        assert resp.id == "chatcmpl-test123"
        assert resp.object == "chat.completion"
        assert len(resp.choices) == 1


class TestChatChunk:
    def test_create(self):
        chunk = ChatChunk(
            id="chatcmpl-test",
            created=1700000000,
            model="pdf-rag",
            choices=[{"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}],
        )
        assert chunk.object == "chat.completion.chunk"
        assert len(chunk.choices) == 1


class TestEmbeddingRequest:
    def test_string_input(self):
        r = EmbeddingRequest(input="hello")
        assert r.input == "hello"
        assert r.model == "local"

    def test_list_input(self):
        r = EmbeddingRequest(input=["hello", "world"])
        assert isinstance(r.input, list)
        assert len(r.input) == 2


class TestEmbeddingData:
    def test_create(self):
        d = EmbeddingData(embedding=[0.1, 0.2, 0.3], index=0)
        assert d.object == "embedding"
        assert len(d.embedding) == 3


class TestEmbeddingResponse:
    def test_create(self):
        resp = EmbeddingResponse(
            data=[EmbeddingData(embedding=[0.1], index=0)],
            model="local",
        )
        assert resp.object == "list"
        assert len(resp.data) == 1


class TestModelInfo:
    def test_defaults(self):
        m = ModelInfo(id="pdf-rag")
        assert m.object == "model"
        assert m.owned_by == "pdf-rag-framework"
        assert m.created is None


class TestModelsResponse:
    def test_create(self):
        resp = ModelsResponse(data=[ModelInfo(id="pdf-rag")])
        assert resp.object == "list"
        assert len(resp.data) == 1


# ---------------------------------------------------------------------------
# _run_rag
# ---------------------------------------------------------------------------

class TestRunRag:
    @pytest.mark.asyncio
    async def test_returns_answer(self):
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {"answer": "Test answer"}

        mock_components = MagicMock()
        mock_components.settings.anthropic_api_key = "key"

        with patch(
            "src.api.routes.openai_compat.create_rag_agent",
            return_value=mock_agent,
        ):
            result = await _run_rag("test query", mock_components)

        assert result == "Test answer"

    @pytest.mark.asyncio
    async def test_returns_default_on_missing_answer(self):
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {}

        mock_components = MagicMock()
        mock_components.settings.anthropic_api_key = "key"

        with patch(
            "src.api.routes.openai_compat.create_rag_agent",
            return_value=mock_agent,
        ):
            result = await _run_rag("test query", mock_components)

        assert result == "No answer generated."

    @pytest.mark.asyncio
    async def test_passes_correct_query(self):
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {"answer": "ok"}

        mock_components = MagicMock()
        mock_components.settings.anthropic_api_key = "key"

        with patch(
            "src.api.routes.openai_compat.create_rag_agent",
            return_value=mock_agent,
        ):
            await _run_rag("my specific question", mock_components)

        call_args = mock_agent.ainvoke.call_args[0][0]
        assert call_args["question"] == "my specific question"
        assert call_args["search_strategy"] == "hybrid"
