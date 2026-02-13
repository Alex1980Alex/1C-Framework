"""Tests for Streaming Pipeline (Phase 9.3).

Tests StreamEvent, StreamingRAGRunner, and collect_stream.
"""

import json

import pytest

from src.pdf_framework.agents.rag.streaming import (
    StreamEvent,
    StreamEventType,
    _format_sources,
    collect_stream,
)


class TestStreamEventType:
    """Test StreamEventType enum."""

    def test_values(self):
        assert StreamEventType.TOKEN.value == "token"
        assert StreamEventType.SOURCE.value == "source"
        assert StreamEventType.STATUS.value == "status"
        assert StreamEventType.ERROR.value == "error"
        assert StreamEventType.DONE.value == "done"


class TestStreamEvent:
    """Test StreamEvent class."""

    def test_creates_from_enum(self):
        event = StreamEvent(type=StreamEventType.TOKEN, data="Hello")
        assert event.type == StreamEventType.TOKEN
        assert event.data == "Hello"

    def test_creates_from_string(self):
        event = StreamEvent(type="token", data="Hello")
        assert event.type == StreamEventType.TOKEN

    def test_metadata_default_empty(self):
        event = StreamEvent(type=StreamEventType.TOKEN, data="test")
        assert event.metadata == {}

    def test_metadata_custom(self):
        event = StreamEvent(
            type=StreamEventType.STATUS,
            data="searching",
            metadata={"stage": "retrieval"},
        )
        assert event.metadata["stage"] == "retrieval"

    def test_to_sse_format(self):
        event = StreamEvent(type=StreamEventType.TOKEN, data="Hello")
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")

        # Parse the JSON payload
        payload = json.loads(sse[len("data: "):-2])
        assert payload["type"] == "token"
        assert payload["data"] == "Hello"

    def test_to_sse_unicode(self):
        event = StreamEvent(type=StreamEventType.TOKEN, data="Привет мир")
        sse = event.to_sse()
        assert "Привет мир" in sse  # ensure_ascii=False

    def test_to_dict(self):
        event = StreamEvent(type=StreamEventType.SOURCE, data=[{"id": "doc1"}])
        d = event.to_dict()
        assert d["type"] == "source"
        assert isinstance(d["data"], list)
        assert d["data"][0]["id"] == "doc1"

    def test_to_sse_with_dict_data(self):
        event = StreamEvent(
            type=StreamEventType.SOURCE,
            data=[{"id": "doc1", "score": 0.9}],
        )
        sse = event.to_sse()
        payload = json.loads(sse[len("data: "):-2])
        assert payload["type"] == "source"
        assert payload["data"][0]["score"] == 0.9

    def test_done_event(self):
        event = StreamEvent(
            type=StreamEventType.DONE,
            data="",
            metadata={"answer_length": 100},
        )
        assert event.type == StreamEventType.DONE
        assert event.metadata["answer_length"] == 100

    def test_error_event(self):
        event = StreamEvent(type=StreamEventType.ERROR, data="Connection failed")
        d = event.to_dict()
        assert d["type"] == "error"
        assert d["data"] == "Connection failed"


class TestCollectStream:
    """Test collect_stream utility."""

    @pytest.mark.asyncio
    async def test_collects_tokens(self):
        async def gen():
            yield StreamEvent(type=StreamEventType.TOKEN, data="Hello ")
            yield StreamEvent(type=StreamEventType.TOKEN, data="World")
            yield StreamEvent(type=StreamEventType.DONE, data="")

        result = await collect_stream(gen())
        assert result["answer"] == "Hello World"

    @pytest.mark.asyncio
    async def test_collects_sources(self):
        async def gen():
            yield StreamEvent(type=StreamEventType.TOKEN, data="Answer")
            yield StreamEvent(type=StreamEventType.SOURCE, data=[{"id": "doc1"}])
            yield StreamEvent(type=StreamEventType.DONE, data="")

        result = await collect_stream(gen())
        assert len(result["sources"]) == 1
        assert result["sources"][0]["id"] == "doc1"

    @pytest.mark.asyncio
    async def test_collects_status_events(self):
        async def gen():
            yield StreamEvent(type=StreamEventType.STATUS, data="searching")
            yield StreamEvent(type=StreamEventType.STATUS, data="generating")
            yield StreamEvent(type=StreamEventType.DONE, data="")

        result = await collect_stream(gen())
        assert result["status_events"] == ["searching", "generating"]

    @pytest.mark.asyncio
    async def test_error_stops_collection(self):
        async def gen():
            yield StreamEvent(type=StreamEventType.TOKEN, data="Partial ")
            yield StreamEvent(type=StreamEventType.ERROR, data="LLM timeout")

        result = await collect_stream(gen())
        assert result["answer"] == "Partial "
        assert result["error"] == "LLM timeout"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        async def gen():
            yield StreamEvent(type=StreamEventType.DONE, data="")

        result = await collect_stream(gen())
        assert result["answer"] == ""
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_source_as_single_dict(self):
        """Source data can be a single dict instead of list."""
        async def gen():
            yield StreamEvent(type=StreamEventType.SOURCE, data={"id": "doc1"})
            yield StreamEvent(type=StreamEventType.DONE, data="")

        result = await collect_stream(gen())
        assert len(result["sources"]) == 1


class TestFormatSources:
    """Test _format_sources helper (E7-1 fix)."""

    def test_string_sources(self):
        """RAGState.sources is list[str] — should not crash."""
        result = _format_sources(["file1.pdf", "file2.pdf"])
        assert len(result) == 2
        assert result[0] == {"id": "file1.pdf", "score": 0.0, "metadata": {}}
        assert result[1] == {"id": "file2.pdf", "score": 0.0, "metadata": {}}

    def test_dict_sources(self):
        """Dict sources should pass through."""
        result = _format_sources([{"id": "doc1", "score": 0.9, "metadata": {"page": 1}}])
        assert result[0]["id"] == "doc1"
        assert result[0]["score"] == 0.9
        assert result[0]["metadata"] == {"page": 1}

    def test_mixed_sources(self):
        """Mix of strings and dicts."""
        result = _format_sources(["path.pdf", {"id": "doc2", "score": 0.5}])
        assert result[0]["id"] == "path.pdf"
        assert result[1]["id"] == "doc2"

    def test_empty_sources(self):
        assert _format_sources([]) == []
