"""OpenAI-Compatible API Endpoints (Phase 23.4).

Provides standard OpenAI API compatibility for integration with
existing tools and ecosystems.

Author: Claude Code
Version: 1.0.0 - Phase 23: Production Hardening
"""

import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.dependencies.components import Components, get_components

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat"])


# OpenAI-compatible request/response models
class ChatMessage(BaseModel):
    """Chat message in OpenAI format."""

    role: str  # "system", "user", "assistant"
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    # RAG-specific parameters (non-standard but useful)
    rag_enabled: bool = True
    search_k: int = 5
    strategy: str = "hybrid"


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int]


class ChatCompletionChunk(BaseModel):
    """Streaming response chunk."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[dict[str, Any]]


@router.post("/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    components: Components = Depends(get_components),
):
    """Create chat completion (OpenAI-compatible).

    Supports both streaming and non-streaming modes.
    Integrates with RAG pipeline when enabled.
    """
    import time
    import uuid

    if request.stream:
        return StreamingResponse(
            _stream_completion(request, components),
            media_type="text/event-stream",
        )

    # Non-streaming mode
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    # Extract user message
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    # Get RAG response
    if request.rag_enabled:
        try:
            rag_response = await components.search_manager.search_and_answer(
                query=user_message,
                strategy=request.strategy,
                k=request.search_k,
            )
            answer = rag_response.get("answer", "Unable to process request.")
        except Exception as e:
            logger.error(f"[OPENAI_COMPAT] RAG failed: {e}")
            answer = f"Error: {str(e)}"
    else:
        # Direct LLM call without RAG
        try:
            response = components.agent.model.invoke(user_message)
            answer = response.content
        except Exception as e:
            logger.error(f"[OPENAI_COMPAT] LLM failed: {e}")
            answer = f"Error: {str(e)}"

    # Format OpenAI-compatible response
    response = ChatCompletionResponse(
        id=completion_id,
        created=created,
        model=request.model,
        choices=[
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": answer,
                },
                "finish_reason": "stop",
            }
        ],
        usage={
            "prompt_tokens": len(user_message.split()),
            "completion_tokens": len(answer.split()),
            "total_tokens": len(user_message.split()) + len(answer.split()),
        },
    )

    return response


async def _stream_completion(
    request: ChatCompletionRequest,
    components: Components,
) -> AsyncGenerator[str, None]:
    """Generate streaming chat completion.

    Args:
        request: Chat completion request
        components: Application components

    Yields:
        Server-sent events chunks
    """
    import time
    import uuid
    import json

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    # Extract user message
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        error_chunk = {
            "error": {
                "message": "No user message found",
                "type": "invalid_request_error",
                "code": None,
            }
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Get response (streaming)
    try:
        if request.rag_enabled:
            # For RAG, we'll simulate streaming by splitting the answer
            rag_response = await components.search_manager.search_and_answer(
                query=user_message,
                strategy=request.strategy,
                k=request.search_k,
            )
            full_answer = rag_response.get("answer", "Unable to process request.")
        else:
            response = components.agent.model.invoke(user_message)
            full_answer = response.content

        # Stream answer word by word
        words = full_answer.split()

        for i, word in enumerate(words):
            chunk = ChatCompletionChunk(
                id=completion_id,
                created=created,
                model=request.model,
                choices=[
                    {
                        "index": 0,
                        "delta": {
                            "content": word + " " if i < len(words) - 1 else word,
                        },
                        "finish_reason": None,
                    }
                ],
            )

            yield f"data: {chunk.model_dump_json()}\n\n"

        # Final chunk
        final_chunk = ChatCompletionChunk(
            id=completion_id,
            created=created,
            model=request.model,
            choices=[
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        )

        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"[OPENAI_COMPAT] Streaming failed: {e}")
        error_chunk = {
            "error": {
                "message": str(e),
                "type": "server_error",
                "code": None,
            }
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


@router.get("/models")
async def list_models():
    """List available models (OpenAI-compatible)."""

    return {
        "object": "list",
        "data": [
            {
                "id": "pdf-rag-v1",
                "object": "model",
                "created": 1677610602,
                "owned_by": "pdf-rag-framework",
            },
            {
                "id": "claude-opus-4-6",
                "object": "model",
                "created": 1677610602,
                "owned_by": "anthropic",
            },
            {
                "id": "claude-sonnet-4-5",
                "object": "model",
                "created": 1677610602,
                "owned_by": "anthropic",
            },
        ],
    }


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """Get model info (OpenAI-compatible)."""

    models = {
        "pdf-rag-v1": {
            "id": "pdf-rag-v1",
            "object": "model",
            "created": 1677610602,
            "owned_by": "pdf-rag-framework",
        },
        "claude-opus-4-6": {
            "id": "claude-opus-4-6",
            "object": "model",
            "created": 1677610602,
            "owned_by": "anthropic",
        },
    }

    if model_id not in models:
        raise HTTPException(status_code=404, detail="Model not found")

    return models[model_id]


@router.post("/embeddings")
async def create_embedding(
    text: str,
    model: str = "multilingual-e5-large",
    components: Components = Depends(get_components),
):
    """Create embedding (OpenAI-compatible).

    Args:
        text: Text to embed
        model: Embedding model name
        components: Application components

    Returns:
        OpenAI-compatible embedding response
    """
    import time
    import uuid

    embedding_id = f"embedding-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    try:
        # Generate embedding
        embedding = await components.embedding_engine.embed_text(text)

        return {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "embedding": embedding,
                    "index": 0,
                }
            ],
            "model": model,
            "usage": {
                "prompt_tokens": len(text.split()),
                "total_tokens": len(text.split()),
            },
        }

    except Exception as e:
        logger.error(f"[OPENAI_COMPAT] Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
