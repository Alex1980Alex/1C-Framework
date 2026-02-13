"""Streaming RAG runner for real-time response delivery (Phase 9).

Provides SSE-compatible streaming events for token-by-token response
delivery using LangGraph's astream_events.

Author: Claude Code
Version: 1.0.1 - Phase 9.3: Streaming Pipeline (E7-1 fix)
"""

import json
import logging
from enum import Enum
from typing import Any, AsyncIterator

from src.pdf_framework.agents.rag.state import RAGState

logger = logging.getLogger(__name__)


class StreamEventType(str, Enum):
    """Types of streaming events."""

    TOKEN = "token"          # Single token from LLM
    SOURCE = "source"        # Source document reference
    STATUS = "status"        # Status update (searching, generating, etc.)
    ERROR = "error"          # Error occurred
    DONE = "done"            # Stream complete


class StreamEvent:
    """Single streaming event for SSE delivery."""

    def __init__(
        self,
        type: StreamEventType | str,
        data: str | dict | list,
        metadata: dict | None = None,
    ):
        """
        Initialize stream event.

        Args:
            type: Event type (token, source, status, error, done)
            data: Event data (string for tokens, dict/list for structured data)
            metadata: Optional additional metadata
        """
        self.type = StreamEventType(type) if isinstance(type, str) else type
        self.data = data
        self.metadata = metadata or {}

    def to_sse(self) -> str:
        """
        Convert to Server-Sent Events format.

        Returns:
            SSE-formatted string (data: {json}\n\n)
        """
        payload = {
            "type": self.type.value,
            "data": self.data,
            "metadata": self.metadata,
        }

        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def to_dict(self) -> dict:
        """Convert to dictionary for non-SSE delivery."""
        return {
            "type": self.type.value,
            "data": self.data,
            "metadata": self.metadata,
        }


def _format_sources(sources: list) -> list[dict]:
    """Format source items (strings or dicts) into uniform dicts."""
    formatted = []
    for s in sources:
        if isinstance(s, dict):
            formatted.append({
                "id": s.get("id", ""),
                "score": s.get("score", 0.0),
                "metadata": s.get("metadata", {}),
            })
        else:
            # RAGState.sources is list[str] (file paths)
            formatted.append({"id": str(s), "score": 0.0, "metadata": {}})
    return formatted


class StreamingRAGRunner:
    """
    Runs RAG agent with streaming event generation.

    Uses LangGraph's astream_events to capture:
    - Individual tokens as they're generated
    - Source documents after retrieval
    - Status updates for pipeline stages
    - Errors if they occur
    """

    def __init__(
        self,
        graph,
        show_status: bool = True,
        show_sources: bool = True,
    ):
        """
        Initialize streaming runner.

        Args:
            graph: LangGraph compiled agent
            show_status: Whether to emit status events
            show_sources: Whether to emit source events
        """
        self._graph = graph
        self._show_status = show_status
        self._show_sources = show_sources

    async def stream(
        self,
        question: str,
        thread_id: str | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream RAG execution with real-time events.

        Args:
            question: User question
            thread_id: Optional thread ID for conversation memory
            **kwargs: Additional state parameters

        Yields:
            StreamEvent objects with token/source/status/done events
        """
        # Build input state
        input_state: RAGState = {
            "question": question,
            "thread_id": thread_id,
            **kwargs,
        }

        logger.info(f"[STREAM] Starting stream for thread {thread_id}")

        try:
            # Emit searching status
            if self._show_status:
                yield StreamEvent(
                    type=StreamEventType.STATUS,
                    data="searching",
                    metadata={"stage": "retrieval"},
                )

            # Stream events from graph
            answer_parts = []
            sources = []

            async for event in self._graph.astream_events(
                input_state,
                version="v2",
            ):
                # Guard: astream_events can yield non-dict objects
                # in LangGraph 1.0.x (strings, metadata markers)
                if not isinstance(event, dict):
                    continue

                event_type = event.get("event", "")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                if not isinstance(event_data, dict):
                    continue

                # Handle token streaming from LLM
                if event_type == "on_chat_model_stream":
                    # Only capture tokens from answer generation nodes,
                    # not from analyze/grade/rewrite/hallucination nodes
                    node = event.get("metadata", {}).get("langgraph_node", "")
                    if node not in ("generate", "regenerate"):
                        continue

                    chunk = event_data.get("chunk")
                    if hasattr(chunk, "content"):
                        content = chunk.content
                        # content can be str or list[ContentBlock]
                        if isinstance(content, list):
                            content = "".join(
                                getattr(block, "text", "")
                                for block in content
                            )
                        if content:
                            answer_parts.append(content)
                            yield StreamEvent(
                                type=StreamEventType.TOKEN,
                                data=content,
                            )

                # Handle chain end (capture sources)
                elif event_type == "on_chain_end":
                    output = event_data.get("output")

                    # Only process dict outputs with sources
                    if isinstance(output, dict) and output.get("sources"):
                        sources = output["sources"]
                        if self._show_sources:
                            yield StreamEvent(
                                type=StreamEventType.SOURCE,
                                data=_format_sources(sources),
                            )

                    # Detect stage changes: "search" node = retrieval done
                    if event_name in ("search", "execute_search"):
                        if self._show_status:
                            yield StreamEvent(
                                type=StreamEventType.STATUS,
                                data="generating",
                                metadata={"stage": "answer_generation"},
                            )

            # Emit done event
            yield StreamEvent(
                type=StreamEventType.DONE,
                data="",
                metadata={
                    "answer_length": sum(len(p) for p in answer_parts),
                    "sources_count": len(sources),
                },
            )

            logger.info(f"[STREAM] Stream complete: {len(answer_parts)} tokens, {len(sources)} sources")

        except Exception as e:
            logger.error(f"[STREAM] Error during streaming: {e}")
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data=str(e),
            )

    async def stream_to_sse(
        self,
        question: str,
        thread_id: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream RAG execution as SSE-formatted strings.

        Args:
            question: User question
            thread_id: Optional thread ID
            **kwargs: Additional state parameters

        Yields:
            SSE-formatted strings (data: {json}\n\n)
        """
        async for event in self.stream(question, thread_id, **kwargs):
            yield event.to_sse()


async def collect_stream(stream: AsyncIterator[StreamEvent]) -> dict:
    """
    Collect all events from a stream into a structured result.

    Useful for non-streaming clients or testing.

    Args:
        stream: Stream of StreamEvent objects

    Returns:
        Dict with answer (concatenated tokens), sources, and metadata
    """
    answer_parts = []
    sources = []
    status_events = []

    async for event in stream:
        if event.type == StreamEventType.TOKEN:
            answer_parts.append(event.data)
        elif event.type == StreamEventType.SOURCE:
            sources.extend(event.data if isinstance(event.data, list) else [event.data])
        elif event.type == StreamEventType.STATUS:
            status_events.append(event.data)
        elif event.type == StreamEventType.ERROR:
            return {
                "answer": "".join(answer_parts),
                "sources": sources,
                "status_events": status_events,
                "error": event.data,
            }

    return {
        "answer": "".join(answer_parts),
        "sources": sources,
        "status_events": status_events,
    }
