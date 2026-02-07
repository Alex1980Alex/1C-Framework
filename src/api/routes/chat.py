"""Chat API endpoints with SSE streaming support (Phase 9).

Provides REST API for multi-turn conversations with real-time streaming.

Author: Claude Code
Version: 1.0.0 - Phase 9.4: Chat API endpoints
"""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.pdf_framework.agents.memory.conversation import ConversationMemory, Message
from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Global conversation memory instance
_conversation_memory: ConversationMemory | None = None
_streaming_runner: StreamingRAGRunner | None = None


def init_chat(
    memory: ConversationMemory,
    runner: StreamingRAGRunner,
) -> None:
    """
    Initialize chat routes with dependencies.

    Args:
        memory: ConversationMemory instance
        runner: StreamingRAGRunner instance
    """
    global _conversation_memory, _streaming_runner
    _conversation_memory = memory
    _streaming_runner = runner


def _get_dependencies() -> tuple[ConversationMemory, StreamingRAGRunner]:
    """Get required dependencies, raising error if not initialized."""
    if _conversation_memory is None or _streaming_runner is None:
        raise HTTPException(
            status_code=500,
            detail="Chat not initialized. Call init_chat() first.",
        )
    return _conversation_memory, _streaming_runner


# ========== Request/Response Models ==========


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""

    message: str = Field(
        ...,
        description="User message to send",
        min_length=1,
    )
    thread_id: str | None = Field(
        None,
        description="Thread ID (auto-generated if not provided)",
    )
    strategy: str = Field(
        "adaptive",
        description="Search strategy to use",
    )
    stream: bool = Field(
        True,
        description="Use SSE streaming for response",
    )


class ChatHistoryResponse(BaseModel):
    """Response model for chat history."""

    thread_id: str
    messages: list[dict]
    message_count: int


class ThreadInfo(BaseModel):
    """Information about a conversation thread."""

    thread_id: str
    message_count: int
    last_updated: str


class ThreadsListResponse(BaseModel):
    """Response model for listing threads."""

    threads: list[ThreadInfo]
    total_count: int


# ========== API Endpoints ==========


@router.post("/message")
async def send_message(request: ChatMessageRequest):
    """
    Send a chat message and get streaming response.

    Returns SSE stream with events:
    - token: Individual response tokens
    - source: Source document references
    - status: Processing status updates
    - error: Error if occurred
    - done: Stream complete

    Args:
        request: Chat message request

    Returns:
        StreamingResponse with SSE events
    """
    memory, runner = _get_dependencies()

    # Generate thread_id if not provided
    thread_id = request.thread_id or str(uuid.uuid4())

    logger.info(f"[CHAT API] Message for thread {thread_id}: {request.message[:50]}...")

    # Store user message
    await memory.add_message(
        thread_id,
        role="user",
        content=request.message,
        metadata={"strategy": request.strategy},
    )

    # Get conversation history
    history = await memory.get_history(thread_id)
    # Exclude the just-added user message from history
    history = history[:-1] if len(history) > 1 else []

    async def event_generator():
        """Generate SSE events for the response."""
        try:
            assistant_response = []

            async for event in runner.stream(
                question=request.message,
                thread_id=thread_id,
                chat_history=history,
                search_strategy=request.strategy,
            ):
                # Yield SSE event
                yield event.to_sse()

                # Collect response for storage
                if event.type.value == "token":
                    assistant_response.append(event.data)

            # Store assistant response
            full_response = "".join(assistant_response)
            if full_response:
                await memory.add_message(
                    thread_id,
                    role="assistant",
                    content=full_response,
                    metadata={"strategy": request.strategy},
                )

        except Exception as e:
            logger.error(f"[CHAT API] Error processing message: {e}")
            from src.pdf_framework.agents.rag.streaming import StreamEvent, StreamEventType
            error_event = StreamEvent(
                type=StreamEventType.ERROR,
                data=str(e),
            )
            yield error_event.to_sse()

    if request.stream:
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming mode: collect and return
        from src.pdf_framework.agents.rag.streaming import collect_stream

        async def collect():
            async for event in runner.stream(
                question=request.message,
                thread_id=thread_id,
                chat_history=history,
                search_strategy=request.strategy,
            ):
                yield event

        result = await collect_stream(collect())

        # Store assistant response
        if result.get("answer"):
            await memory.add_message(
                thread_id,
                role="assistant",
                content=result["answer"],
                metadata={"strategy": request.strategy},
            )

        return {
            "thread_id": thread_id,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
        }


@router.get("/history/{thread_id}", response_model=ChatHistoryResponse)
async def get_history(thread_id: str):
    """
    Get conversation history for a thread.

    Args:
        thread_id: Thread identifier

    Returns:
        ChatHistoryResponse with messages
    """
    memory, _ = _get_dependencies()

    messages = await memory.get_history(thread_id)

    return ChatHistoryResponse(
        thread_id=thread_id,
        messages=[msg.to_dict() for msg in messages],
        message_count=len(messages),
    )


@router.delete("/history/{thread_id}")
async def clear_history(thread_id: str):
    """
    Clear conversation history for a thread.

    Args:
        thread_id: Thread identifier

    Returns:
        Success confirmation
    """
    memory, _ = _get_dependencies()

    await memory.clear_thread(thread_id)

    return {
        "status": "success",
        "thread_id": thread_id,
        "message": "Conversation history cleared",
    }


@router.get("/threads", response_model=ThreadsListResponse)
async def list_threads(limit: int = 100):
    """
    List all active conversation threads.

    Args:
        limit: Maximum threads to return

    Returns:
        ThreadsListResponse
    """
    memory, _ = _get_dependencies()

    threads = await memory.list_threads(limit)

    return ThreadsListResponse(
        threads=[
            ThreadInfo(
                thread_id=t["thread_id"],
                message_count=t["message_count"],
                last_updated=t["last_updated"],
            )
            for t in threads
        ],
        total_count=len(threads),
    )


@router.get("/stats/{thread_id}")
async def get_thread_stats(thread_id: str):
    """
    Get statistics for a conversation thread.

    Args:
        thread_id: Thread identifier

    Returns:
        Thread statistics
    """
    memory, _ = _get_dependencies()

    stats = await memory.get_thread_stats(thread_id)

    return {
        "thread_id": thread_id,
        **stats,
    }
