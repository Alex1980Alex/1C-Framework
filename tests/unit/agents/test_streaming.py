"""Unit tests for StreamingRAGRunner lifecycle behavior (F2.9.3).

Focuses on runner construction, event ordering guarantees, metadata
payloads, token-count tracking, and async-generator cancellation.
All LLM / graph I/O is mocked — no network required.
"""

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner(graph_events, show_status=True, show_sources=True):
    """Return a StreamingRAGRunner backed by a deterministic fake graph."""
    from unittest.mock import MagicMock

    from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

    graph = MagicMock()

    async def fake_astream_events(state, version="v2"):
        for ev in graph_events:
            yield ev

    graph.astream_events = fake_astream_events
    return StreamingRAGRunner(graph=graph, show_status=show_status, show_sources=show_sources)


def _token_event(text: str, node: str = "generate") -> dict:
    """Build a fake on_chat_model_stream event dict."""
    from unittest.mock import MagicMock

    chunk = MagicMock()
    chunk.content = text
    return {
        "event": "on_chat_model_stream",
        "name": node,
        "metadata": {"langgraph_node": node},
        "data": {"chunk": chunk},
    }


# ---------------------------------------------------------------------------
# TestStreamingRAGRunner
# ---------------------------------------------------------------------------


class TestStreamingRAGRunner:
    """Runner lifecycle, event ordering, metadata, token tracking, cancellation."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_runner_stores_graph_and_flags(self):
        """Runner exposes the injected graph and boolean flags."""
        from unittest.mock import MagicMock

        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        graph = MagicMock()
        runner = StreamingRAGRunner(graph=graph, show_status=False, show_sources=False)

        assert runner._graph is graph
        assert runner._show_status is False
        assert runner._show_sources is False

    def test_runner_defaults_show_status_and_sources_true(self):
        """Defaults for show_status / show_sources are both True."""
        from unittest.mock import MagicMock

        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner(graph=MagicMock())
        assert runner._show_status is True
        assert runner._show_sources is True

    # ------------------------------------------------------------------
    # stream() yields events
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stream_yields_at_least_one_event(self):
        """stream() is an async generator that always yields at least DONE."""
        runner = _make_runner([])
        events = [ev async for ev in runner.stream("hello")]
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_stream_always_ends_with_done(self):
        """The last event emitted is always StreamEventType.DONE."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        runner = _make_runner([_token_event("word1"), _token_event("word2")])
        events = [ev async for ev in runner.stream("q")]
        assert events[-1].type == StreamEventType.DONE

    # ------------------------------------------------------------------
    # Event ordering
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_status_searching_emitted_before_tokens(self):
        """STATUS 'searching' is emitted before any TOKEN events."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        runner = _make_runner([_token_event("tok")])
        events = [ev async for ev in runner.stream("q")]

        types = [ev.type for ev in events]
        # At least one STATUS event must precede the first TOKEN
        first_token_idx = next((i for i, t in enumerate(types) if t == StreamEventType.TOKEN), None)
        first_status_idx = next(
            (i for i, t in enumerate(types) if t == StreamEventType.STATUS), None
        )
        assert first_status_idx is not None
        if first_token_idx is not None:
            assert first_status_idx < first_token_idx

    @pytest.mark.asyncio
    async def test_done_emitted_after_all_tokens(self):
        """DONE event index is always greater than every TOKEN event index."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        token_texts = ["A", "B", "C"]
        runner = _make_runner([_token_event(t) for t in token_texts])
        events = [ev async for ev in runner.stream("q")]

        types = [ev.type for ev in events]
        done_idx = types.index(StreamEventType.DONE)
        token_indices = [i for i, t in enumerate(types) if t == StreamEventType.TOKEN]
        assert all(idx < done_idx for idx in token_indices)

    # ------------------------------------------------------------------
    # Event metadata payloads
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stream_event_has_type_data_metadata_attributes(self):
        """Every StreamEvent exposes .type, .data, and .metadata."""
        runner = _make_runner([])
        events = [ev async for ev in runner.stream("q")]
        for ev in events:
            assert hasattr(ev, "type")
            assert hasattr(ev, "data")
            assert hasattr(ev, "metadata")

    @pytest.mark.asyncio
    async def test_done_metadata_contains_answer_length_and_sources_count(self):
        """DONE event metadata keys: answer_length (int >= 0), sources_count (int >= 0)."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        runner = _make_runner([_token_event("hello "), _token_event("world")])
        events = [ev async for ev in runner.stream("q")]

        done = next(ev for ev in events if ev.type == StreamEventType.DONE)
        assert isinstance(done.metadata.get("answer_length"), int)
        assert done.metadata["answer_length"] >= 0
        assert isinstance(done.metadata.get("sources_count"), int)
        assert done.metadata["sources_count"] >= 0

    @pytest.mark.asyncio
    async def test_token_event_data_is_the_token_text(self):
        """TOKEN event .data carries the exact token string from the LLM chunk."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        runner = _make_runner([_token_event("exact-token")])
        events = [ev async for ev in runner.stream("q")]

        token_events = [ev for ev in events if ev.type == StreamEventType.TOKEN]
        assert len(token_events) == 1
        assert token_events[0].data == "exact-token"

    # ------------------------------------------------------------------
    # Token-count tracking via DONE metadata
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_answer_length_reflects_all_tokens(self):
        """answer_length in DONE metadata equals the total chars of all TOKEN data."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        tokens = ["Hello", " ", "world", "!"]
        runner = _make_runner([_token_event(t) for t in tokens])
        events = [ev async for ev in runner.stream("q")]

        collected_tokens = [ev.data for ev in events if ev.type == StreamEventType.TOKEN]
        done = next(ev for ev in events if ev.type == StreamEventType.DONE)

        expected_len = sum(len(t) for t in collected_tokens)
        assert done.metadata["answer_length"] == expected_len

    @pytest.mark.asyncio
    async def test_answer_length_zero_when_no_tokens(self):
        """answer_length is 0 when the graph emits no token events."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        runner = _make_runner([])
        events = [ev async for ev in runner.stream("q")]
        done = next(ev for ev in events if ev.type == StreamEventType.DONE)
        assert done.metadata["answer_length"] == 0

    # ------------------------------------------------------------------
    # Stream cancellation (early break)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stream_supports_early_break(self):
        """Breaking out of the async-for loop after N events does not raise."""
        runner = _make_runner([_token_event(f"t{i}") for i in range(20)])

        consumed = []
        async for ev in runner.stream("q"):
            consumed.append(ev)
            if len(consumed) >= 3:
                break

        # Exactly 3 events consumed without exception
        assert len(consumed) == 3

    @pytest.mark.asyncio
    async def test_stream_to_sse_produces_data_prefix_strings(self):
        """stream_to_sse() wraps every event as 'data: {...}\\n\\n' SSE format."""
        import json

        from src.pdf_framework.agents.rag.streaming import StreamEventType

        runner = _make_runner([_token_event("hi")])
        lines = [line async for line in runner.stream_to_sse("q")]

        assert len(lines) > 0
        for line in lines:
            assert line.startswith("data: ")
            assert line.endswith("\n\n")
            payload = json.loads(line[len("data: ") :].strip())
            assert "type" in payload
            assert "data" in payload

        # The last SSE line should be the DONE event
        last_payload = json.loads(lines[-1][len("data: ") :].strip())
        assert last_payload["type"] == StreamEventType.DONE.value
