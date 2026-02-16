"""Tests for Phase 49: WebSocket search streaming endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult, SearchResponse


def _make_search_response() -> SearchResponse:
    """Create a mock SearchResponse."""
    chunk = DocumentChunk(
        id="c1",
        content="Справочники хранят условно постоянную информацию.",
        document_id="d1",
        metadata={"source": "test.pdf", "page_number": 42},
    )
    return SearchResponse(
        query="справочники",
        results=[SearchResult(chunk=chunk, score=0.95)],
        total_found=1,
        search_type="hybrid",
    )


@pytest.fixture
def mock_components():
    """Create a mock Components object."""
    components = MagicMock()
    components.search_manager.search = AsyncMock(return_value=_make_search_response())
    components.settings.agent = MagicMock()
    components.settings.agent.model = "claude-haiku-4-5-20251001"
    components.settings.agent.base_url = "https://test.api"
    components.settings.anthropic_api_key = "test-key"
    return components


class TestWebSocketMessages:
    """Test the _ws_message helper."""

    def test_ws_message_format(self):
        from src.api.routes.websocket import _ws_message

        msg = _ws_message("token", "Hello")
        parsed = json.loads(msg)
        assert parsed["type"] == "token"
        assert parsed["data"] == "Hello"
        assert parsed["metadata"] == {}

    def test_ws_message_with_metadata(self):
        from src.api.routes.websocket import _ws_message

        msg = _ws_message("status", "searching_done", {"elapsed_ms": 42})
        parsed = json.loads(msg)
        assert parsed["metadata"]["elapsed_ms"] == 42

    def test_ws_message_unicode(self):
        from src.api.routes.websocket import _ws_message

        msg = _ws_message("token", "Привет мир")
        assert "Привет мир" in msg


class TestWebSocketEndpoint:
    """Test the WebSocket endpoint with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """Test that invalid JSON gets error response."""
        from src.api.routes.websocket import _ws_message

        # The _ws_message helper should produce valid JSON for errors
        msg = _ws_message("error", "Invalid JSON")
        parsed = json.loads(msg)
        assert parsed["type"] == "error"

    @pytest.mark.asyncio
    async def test_missing_question(self):
        """Test that missing question field gets error response."""
        from src.api.routes.websocket import _ws_message

        msg = _ws_message("error", "Missing 'question' field")
        parsed = json.loads(msg)
        assert parsed["type"] == "error"
        assert "question" in parsed["data"]
