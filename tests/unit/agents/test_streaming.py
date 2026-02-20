"""Unit tests for StreamingRAGRunner event types (F2.9.3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestStreamingRAGRunner:
    """Test StreamingRAGRunner specific functionality."""

    def test_runner_initialization(self):
        """F2.9.3: Runner should initialize with configuration."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner(
            chunk_size=100,
            max_chunks=10,
        )

        assert runner.chunk_size == 100
        assert runner.max_chunks == 10

    async def test_stream_yields_events(self):
        """F2.9.3: stream() should be async generator."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner()

        events = []
        async def collect():
            async for event in runner.stream("test query"):
                events.append(event)

        await collect()

        assert len(events) > 0

    async def test_event_ordering(self):
        """F2.9.3: Events should be ordered correctly."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner, EventType

        runner = StreamingRAGRunner()

        event_order = []
        async def collect():
            async for event in runner.stream("test"):
                event_order.append(event.type)

        await collect()

        # Query start should come before end
        if EventType.QUERY_START in event_order and EventType.QUERY_END in event_order:
            start_idx = event_order.index(EventType.QUERY_START)
            end_idx = event_order.index(EventType.QUERY_END)
            assert start_idx < end_idx

    async def test_stream_cancellation(self):
        """F2.9.3: Should support stream cancellation."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner()

        consumed = []
        async def partial_consume():
            async for event in runner.stream("test"):
                consumed.append(event)
                if len(consumed) >= 2:  # Cancel early
                    break

        await partial_consume()

        assert len(consumed) == 2

    def test_event_metadata(self):
        """F2.9.3: Events should contain metadata."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner, Event

        event = Event(
            type="test_event",
            content="test content",
            metadata={"key": "value"},
        )

        assert event.metadata["key"] == "value"

    async def test_token_tracking(self):
        """F2.9.3: Should track tokens in streaming."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner()

        token_counts = []
        async def track_tokens():
            async for event in runner.stream("test"):
                if hasattr(event, "tokens"):
                    token_counts.append(event.tokens)

        await track_tokens()

        # Should track tokens
        assert sum(token_counts) > 0
