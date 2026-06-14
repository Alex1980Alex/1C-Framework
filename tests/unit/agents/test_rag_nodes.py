"""Unit tests for RAG Agent nodes (F2.9).

Tests:
- F2.9.1: Test RAG agent node: grader (grade_documents)
- F2.9.1b: Test RAG agent node: hallucination checker (check_hallucination)
- F2.9.2: Test RAG agent node: rewriter (rewrite_query)
- F2.9.3: Test StreamingRAGRunner event types
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers: build minimal RAGState-compatible dicts and schema objects
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str, content: str) -> Any:
    from src.pdf_framework.schemas.documents import DocumentChunk

    return DocumentChunk(id=chunk_id, content=content, document_id="doc1")


def _make_search_result(chunk_id: str, content: str, score: float) -> Any:
    from src.pdf_framework.schemas.documents import SearchResult

    return SearchResult(chunk=_make_chunk(chunk_id, content), score=score)


def _make_search_response(results: list) -> Any:
    from src.pdf_framework.schemas.documents import SearchResponse

    return SearchResponse(query="test", results=results)


def _make_settings(**overrides):
    from src.pdf_framework.config import SelfRAGSettings

    return SelfRAGSettings(**overrides)


def _make_llm(response_text: str) -> MagicMock:
    """Return a mock ChatAnthropic whose ainvoke returns an AIMessage with given text.

    Uses a real AIMessage so that StrOutputParser.invoke() receives a proper
    string-typed .content attribute and does not raise a Pydantic validation error.
    """
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=response_text))
    return llm


# ---------------------------------------------------------------------------
# TestGradeDocuments
# ---------------------------------------------------------------------------


class TestGradeDocuments:
    """F2.9.1: grade_documents node behavior."""

    @pytest.mark.asyncio
    async def test_returns_relevant_flag_for_yes_response(self):
        """LLM returning 'yes' marks document as relevant."""
        from src.pdf_framework.agents.rag.nodes.grader import grade_documents

        llm = _make_llm("yes - contains definition of 1С")
        settings = _make_settings(score_prefilter_threshold=0.0)
        state: dict = {
            "question": "What is 1С?",
            "search_response": _make_search_response(
                [_make_search_result("doc1", "1С is a platform", 0.9)]
            ),
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.grader.is_cheap_llm_enabled", return_value=False
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.grader.is_dspy_available", return_value=False
            ),
        ):
            result = await grade_documents(state, llm, settings)

        assert "graded_documents" in result
        assert len(result["graded_documents"]) == 1
        assert result["graded_documents"][0]["is_relevant"] is True

    @pytest.mark.asyncio
    async def test_returns_not_relevant_for_no_response(self):
        """LLM returning 'no' marks document as not relevant."""
        from src.pdf_framework.agents.rag.nodes.grader import grade_documents

        llm = _make_llm("no - unrelated topic")
        settings = _make_settings(score_prefilter_threshold=0.0)
        state: dict = {
            "question": "What is 1С?",
            "search_response": _make_search_response(
                [_make_search_result("doc2", "Recipe for cake", 0.9)]
            ),
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.grader.is_cheap_llm_enabled", return_value=False
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.grader.is_dspy_available", return_value=False
            ),
        ):
            result = await grade_documents(state, llm, settings)

        assert result["graded_documents"][0]["is_relevant"] is False

    @pytest.mark.asyncio
    async def test_prefilter_auto_rejects_low_score_docs(self):
        """Documents below score_prefilter_threshold are auto-rejected without LLM call."""
        from src.pdf_framework.agents.rag.nodes.grader import grade_documents

        llm = _make_llm("yes")
        settings = _make_settings(score_prefilter_threshold=0.5)
        state: dict = {
            "question": "What is 1С?",
            "search_response": _make_search_response(
                [
                    _make_search_result("high", "1С is a platform", 0.9),
                    _make_search_result("low", "Unrelated content", 0.1),
                ]
            ),
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.grader.is_cheap_llm_enabled", return_value=False
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.grader.is_dspy_available", return_value=False
            ),
        ):
            result = await grade_documents(state, llm, settings)

        graded = result["graded_documents"]
        assert len(graded) == 2
        # Low-score doc is auto-rejected (no LLM call), high-score doc graded via LLM
        low_doc = next(g for g in graded if g["chunk_id"] == "low")
        high_doc = next(g for g in graded if g["chunk_id"] == "high")
        assert low_doc["is_relevant"] is False
        assert high_doc["is_relevant"] is True
        # LLM should only be called once (for the high-score doc)
        assert llm.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_relevance_ratio_calculated(self):
        """relevance_ratio reflects fraction of relevant documents."""
        from src.pdf_framework.agents.rag.nodes.grader import grade_documents

        # Two docs above threshold, LLM says yes/no alternately
        call_count = 0

        async def side_effect(messages):
            nonlocal call_count
            call_count += 1
            return AIMessage(content="yes" if call_count == 1 else "no - irrelevant")

        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=side_effect)
        settings = _make_settings(score_prefilter_threshold=0.0)
        state: dict = {
            "question": "test",
            "search_response": _make_search_response(
                [
                    _make_search_result("a", "relevant doc", 0.8),
                    _make_search_result("b", "irrelevant doc", 0.7),
                ]
            ),
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.grader.is_cheap_llm_enabled", return_value=False
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.grader.is_dspy_available", return_value=False
            ),
        ):
            result = await grade_documents(state, llm, settings)

        assert result["relevance_ratio"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_empty_search_response(self):
        """Empty search results return empty graded_documents and ratio 0."""
        from src.pdf_framework.agents.rag.nodes.grader import grade_documents

        llm = _make_llm("yes")
        settings = _make_settings()
        state: dict = {
            "question": "test",
            "search_response": _make_search_response([]),
        }

        result = await grade_documents(state, llm, settings)

        assert result["graded_documents"] == []
        assert result["relevance_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_missing_search_response_in_state(self):
        """No search_response key in state returns safe defaults."""
        from src.pdf_framework.agents.rag.nodes.grader import grade_documents

        llm = _make_llm("yes")
        settings = _make_settings()
        state: dict = {"question": "test"}

        result = await grade_documents(state, llm, settings)

        assert result["graded_documents"] == []
        assert result["relevance_ratio"] == 0.0


# ---------------------------------------------------------------------------
# TestCheckHallucination
# ---------------------------------------------------------------------------


class TestCheckHallucination:
    """F2.9.1b: check_hallucination node behavior."""

    @pytest.mark.asyncio
    async def test_detects_hallucination_when_not_grounded(self):
        """LLM returning 'not_grounded' sets is_hallucinated=True."""
        from src.pdf_framework.agents.rag.nodes.hallucination_checker import check_hallucination

        llm = _make_llm("not_grounded: answer mentions 2050 but context says 1991")
        settings = _make_settings(hallucination_check_enabled=True)
        state: dict = {
            "answer": "1С was created in 2050",
            "context": "1С was created in 1991",
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.hallucination_checker.is_cheap_llm_enabled",
                return_value=False,
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.hallucination_checker.is_dspy_available",
                return_value=False,
            ),
        ):
            result = await check_hallucination(state, llm, settings)

        assert result["is_hallucinated"] is True
        assert "hallucination_reason" in result

    @pytest.mark.asyncio
    async def test_grounded_answer_not_hallucinated(self):
        """LLM returning 'grounded' sets is_hallucinated=False."""
        from src.pdf_framework.agents.rag.nodes.hallucination_checker import check_hallucination

        llm = _make_llm("grounded")
        settings = _make_settings(hallucination_check_enabled=True)
        state: dict = {
            "answer": "1С was created in 1991",
            "context": "1С (1C) was founded in 1991 by Boris Nuraliev.",
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.hallucination_checker.is_cheap_llm_enabled",
                return_value=False,
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.hallucination_checker.is_dspy_available",
                return_value=False,
            ),
        ):
            result = await check_hallucination(state, llm, settings)

        assert result["is_hallucinated"] is False

    @pytest.mark.asyncio
    async def test_disabled_check_skips_llm(self):
        """When hallucination_check_enabled=False, LLM is never called."""
        from src.pdf_framework.agents.rag.nodes.hallucination_checker import check_hallucination

        llm = _make_llm("should not be called")
        settings = _make_settings(hallucination_check_enabled=False)
        state: dict = {
            "answer": "some answer",
            "context": "some context",
        }

        result = await check_hallucination(state, llm, settings)

        assert result["is_hallucinated"] is False
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_context_means_potential_hallucination(self):
        """Without context, result is is_hallucinated=True (cannot verify)."""
        from src.pdf_framework.agents.rag.nodes.hallucination_checker import check_hallucination

        llm = _make_llm("grounded")
        settings = _make_settings(hallucination_check_enabled=True)
        state: dict = {
            "answer": "some answer",
            "context": "",
        }

        result = await check_hallucination(state, llm, settings)

        assert result["is_hallucinated"] is True

    @pytest.mark.asyncio
    async def test_no_answer_returns_not_hallucinated(self):
        """Without an answer to verify, returns is_hallucinated=False."""
        from src.pdf_framework.agents.rag.nodes.hallucination_checker import check_hallucination

        llm = _make_llm("grounded")
        settings = _make_settings(hallucination_check_enabled=True)
        state: dict = {
            "answer": "",
            "context": "some context",
        }

        result = await check_hallucination(state, llm, settings)

        assert result["is_hallucinated"] is False


# ---------------------------------------------------------------------------
# TestRewriteQuery
# ---------------------------------------------------------------------------


class TestRewriteQuery:
    """F2.9.2: rewrite_query node behavior."""

    @pytest.mark.asyncio
    async def test_rewrites_query_via_llm(self):
        """LLM produces a rewritten question different from original."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        rewritten_text = "справочники в 1С: типы, структура и использование"
        llm = _make_llm(rewritten_text)
        settings = _make_settings()
        state: dict = {
            "question": "справочники",
            "retry_count": 0,
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_cheap_llm_enabled",
                return_value=False,
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_dspy_available", return_value=False
            ),
        ):
            result = await rewrite_query(state, llm, settings)

        assert result["question"] == rewritten_text
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_increments_retry_count(self):
        """retry_count is incremented on each rewrite call."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        llm = _make_llm("регистры накопления в 1С Предприятие")
        settings = _make_settings()
        state: dict = {
            "question": "регистры",
            "retry_count": 1,
            "original_question": "регистры",
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_cheap_llm_enabled",
                return_value=False,
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_dspy_available", return_value=False
            ),
        ):
            result = await rewrite_query(state, llm, settings)

        assert result["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_returns_search_strategy_key(self):
        """Result always contains search_strategy key."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        llm = _make_llm("регистры накопления")
        settings = _make_settings()
        state: dict = {
            "question": "регистры",
            "retry_count": 0,
            "search_strategy": "vector",
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_cheap_llm_enabled",
                return_value=False,
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_dspy_available", return_value=False
            ),
        ):
            result = await rewrite_query(state, llm, settings)

        assert "search_strategy" in result

    @pytest.mark.asyncio
    async def test_strategy_escalation_on_second_retry(self):
        """Strategy escalates from 'vector' to 'hybrid' on second retry."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        llm = _make_llm("more specific query about registers")
        settings = _make_settings(strategy_escalation_enabled=True)
        state: dict = {
            "question": "регистры",
            "retry_count": 1,  # next call makes retry_count=2 -> escalation
            "original_question": "регистры",
            "search_strategy": "vector",
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_cheap_llm_enabled",
                return_value=False,
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_dspy_available", return_value=False
            ),
        ):
            result = await rewrite_query(state, llm, settings)

        # retry_count will become 2 -> strategy should escalate from vector to hybrid
        assert result["search_strategy"] == "hybrid"

    @pytest.mark.asyncio
    async def test_no_strategy_escalation_on_first_retry(self):
        """Strategy stays the same on the first retry (retry_count=0 -> 1)."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        llm = _make_llm("справочники 1С: типы объектов метаданных")
        settings = _make_settings(strategy_escalation_enabled=True)
        state: dict = {
            "question": "справочники",
            "retry_count": 0,
            "search_strategy": "vector",
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_cheap_llm_enabled",
                return_value=False,
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_dspy_available", return_value=False
            ),
        ):
            result = await rewrite_query(state, llm, settings)

        # retry_count=1, escalation only triggers at >=2
        assert result["search_strategy"] == "vector"

    @pytest.mark.asyncio
    async def test_fallback_to_original_when_llm_returns_empty(self):
        """When LLM returns empty/identical response, original question is used."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        # Return identical text (the rewriter validates and falls back)
        llm = _make_llm("справочники")
        settings = _make_settings()
        state: dict = {
            "question": "справочники",
            "retry_count": 0,
            "original_question": "справочники",
        }

        with (
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_cheap_llm_enabled",
                return_value=False,
            ),
            patch(
                "src.pdf_framework.agents.rag.nodes.rewriter.is_dspy_available", return_value=False
            ),
        ):
            result = await rewrite_query(state, llm, settings)

        # Falls back to original_question when all rewrites are identical
        assert result["question"] == "справочники"
        assert result["retry_count"] == 1


# ---------------------------------------------------------------------------
# TestStreamingRAGRunner
# ---------------------------------------------------------------------------


async def _make_async_events(*events):
    """Async generator that yields the given event dicts."""
    for ev in events:
        yield ev


class TestStreamingRAGRunner:
    """F2.9.3: StreamingRAGRunner event types."""

    def _make_runner(self, graph_events: list) -> Any:
        """Build a StreamingRAGRunner with a mocked graph."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        graph = MagicMock()

        async def fake_astream_events(state, version="v2"):
            for ev in graph_events:
                yield ev

        graph.astream_events = fake_astream_events
        return StreamingRAGRunner(graph=graph, show_status=True, show_sources=True)

    @pytest.mark.asyncio
    async def test_emits_status_and_done_events(self):
        """Runner always emits STATUS (searching) and DONE even with no graph output."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        runner = self._make_runner([])  # graph yields nothing

        events = []
        async for ev in runner.stream("test query"):
            events.append(ev)

        types = [ev.type for ev in events]
        assert StreamEventType.STATUS in types
        assert StreamEventType.DONE in types

    @pytest.mark.asyncio
    async def test_emits_token_events_from_generate_node(self):
        """on_chat_model_stream from 'generate' node yields TOKEN events."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        chunk = MagicMock()
        chunk.content = "Hello"
        graph_events = [
            {
                "event": "on_chat_model_stream",
                "name": "generate",
                "metadata": {"langgraph_node": "generate"},
                "data": {"chunk": chunk},
            }
        ]
        runner = self._make_runner(graph_events)

        events = []
        async for ev in runner.stream("test"):
            events.append(ev)

        token_events = [ev for ev in events if ev.type == StreamEventType.TOKEN]
        assert len(token_events) == 1
        assert token_events[0].data == "Hello"

    @pytest.mark.asyncio
    async def test_non_generate_nodes_not_yielded_as_tokens(self):
        """Tokens from grader/rewriter nodes are filtered out."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        chunk = MagicMock()
        chunk.content = "grading..."
        graph_events = [
            {
                "event": "on_chat_model_stream",
                "name": "grader",
                "metadata": {"langgraph_node": "grader"},
                "data": {"chunk": chunk},
            }
        ]
        runner = self._make_runner(graph_events)

        events = []
        async for ev in runner.stream("test"):
            events.append(ev)

        token_events = [ev for ev in events if ev.type == StreamEventType.TOKEN]
        assert len(token_events) == 0

    @pytest.mark.asyncio
    async def test_emits_source_events_when_chain_end_has_sources(self):
        """on_chain_end with sources key yields SOURCE events."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        graph_events = [
            {
                "event": "on_chain_end",
                "name": "search",
                "data": {"output": {"sources": ["doc_a.pdf", "doc_b.pdf"]}},
            }
        ]
        runner = self._make_runner(graph_events)

        events = []
        async for ev in runner.stream("test"):
            events.append(ev)

        source_events = [ev for ev in events if ev.type == StreamEventType.SOURCE]
        assert len(source_events) == 1
        # source data is a list of formatted dicts
        assert isinstance(source_events[0].data, list)
        assert len(source_events[0].data) == 2

    @pytest.mark.asyncio
    async def test_emits_generating_status_after_search_node(self):
        """After a 'search' chain_end event, a STATUS 'generating' event is emitted."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        graph_events = [
            {
                "event": "on_chain_end",
                "name": "search",
                "data": {"output": {}},
            }
        ]
        runner = self._make_runner(graph_events)

        events = []
        async for ev in runner.stream("test"):
            events.append(ev)

        status_events = [ev for ev in events if ev.type == StreamEventType.STATUS]
        status_data = [ev.data for ev in status_events]
        assert "generating" in status_data

    @pytest.mark.asyncio
    async def test_done_event_has_answer_length_metadata(self):
        """DONE event metadata contains answer_length and sources_count."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        chunk = MagicMock()
        chunk.content = "The answer is 42."
        graph_events = [
            {
                "event": "on_chat_model_stream",
                "name": "generate",
                "metadata": {"langgraph_node": "generate"},
                "data": {"chunk": chunk},
            }
        ]
        runner = self._make_runner(graph_events)

        done_events = []
        async for ev in runner.stream("test"):
            if ev.type == StreamEventType.DONE:
                done_events.append(ev)

        assert len(done_events) == 1
        meta = done_events[0].metadata
        assert "answer_length" in meta
        assert meta["answer_length"] == len("The answer is 42.")
        assert "sources_count" in meta

    @pytest.mark.asyncio
    async def test_error_event_emitted_on_graph_exception(self):
        """If graph raises, an ERROR event is yielded instead of propagating."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        graph = MagicMock()

        async def failing_astream_events(state, version="v2"):
            raise RuntimeError("Graph failed")
            yield  # make it a generator

        graph.astream_events = failing_astream_events

        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner(graph=graph)

        events = []
        async for ev in runner.stream("test"):
            events.append(ev)

        error_events = [ev for ev in events if ev.type == StreamEventType.ERROR]
        assert len(error_events) == 1
        assert "Graph failed" in str(error_events[0].data)

    @pytest.mark.asyncio
    async def test_to_sse_produces_valid_sse_format(self):
        """stream_to_sse yields strings in SSE 'data: {...}\\n\\n' format."""
        runner = self._make_runner([])

        lines = []
        async for line in runner.stream_to_sse("test"):
            lines.append(line)

        assert len(lines) > 0
        for line in lines:
            assert line.startswith("data: ")
            assert line.endswith("\n\n")

    @pytest.mark.asyncio
    async def test_stream_event_to_dict(self):
        """StreamEvent.to_dict() returns proper keys."""
        from src.pdf_framework.agents.rag.streaming import StreamEvent, StreamEventType

        ev = StreamEvent(type=StreamEventType.TOKEN, data="hello", metadata={"k": "v"})
        d = ev.to_dict()

        assert d["type"] == "token"
        assert d["data"] == "hello"
        assert d["metadata"] == {"k": "v"}

    @pytest.mark.asyncio
    async def test_non_dict_graph_events_are_ignored(self):
        """Non-dict objects yielded by graph (LangGraph 1.0.x markers) are skipped."""
        from src.pdf_framework.agents.rag.streaming import StreamEventType

        # Mix non-dict markers with a real event
        chunk = MagicMock()
        chunk.content = "ok"
        graph_events = [
            "some_string_marker",
            None,
            {
                "event": "on_chat_model_stream",
                "name": "generate",
                "metadata": {"langgraph_node": "generate"},
                "data": {"chunk": chunk},
            },
        ]
        runner = self._make_runner(graph_events)

        events = []
        async for ev in runner.stream("test"):
            events.append(ev)

        token_events = [ev for ev in events if ev.type == StreamEventType.TOKEN]
        assert len(token_events) == 1
