"""OpenAI-Compatible API endpoints (Phase 14.3).

Provides /v1/chat/completions, /v1/embeddings, /v1/models endpoints
for integration with OpenAI SDK clients (Continue, Cursor, etc.).

Author: Claude Code
Version: 1.5.0 - Phase 14.3: OpenAI-Compatible API
"""

import logging
import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.dependencies.components import Components, get_components
from src.pdf_framework.agents.rag.agent import create_rag_agent
from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat"])


# OpenAI-compatible request/response models
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model: str = "pdf-rag"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]


class ChatChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[dict[str, Any]]


class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str = "local"


class EmbeddingData(BaseModel):
    embedding: list[float]
    index: int
    object: str = "embedding"


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingData]
    model: str


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int | None = None
    owned_by: str = "pdf-rag-framework"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


@router.post("/chat/completions", response_model=ChatResponse | None)
async def chat_completions(
    request: ChatRequest,
    components: Components = Depends(get_components),
    x_tenant_id: str = Header(default="default"),
) -> ChatResponse | StreamingResponse:
    """
    OpenAI-compatible chat completions endpoint.

    Converts OpenAI format requests to RAG pipeline and returns
    responses in OpenAI format.
    """
    settings = get_settings()

    if not settings.openai_compat.enabled:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="OpenAI-compatible API is disabled")

    # Extract the last user message as the query
    query = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            query = msg.content
            break

    if not query:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No user message found")

    # Generate unique ID for this completion
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(__import__("time").time())

    if request.stream:
        # Streaming response
        async def stream_generator():
            from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

            agent = create_rag_agent(
                search_manager=components.search_manager,
                settings=components.settings.agent,
                self_rag_settings=components.settings.self_rag,
                api_key=components.settings.anthropic_api_key,
            )
            runner = StreamingRAGRunner(agent, show_status=False)

            full_content = ""

            async for event in runner.stream(query, search_strategy="hybrid"):
                if event.type.value == "token":
                    token = event.data
                    full_content += token

                    chunk = ChatChunk(
                        id=completion_id,
                        created=created,
                        model=settings.openai_compat.model_name,
                        choices=[{
                            "index": 0,
                            "delta": {"content": token},
                            "finish_reason": None,
                        }],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

                elif event.type.value == "source":
                    # Sources are sent as a note after completion
                    pass

            # Final chunk with finish_reason
            final_chunk = ChatChunk(
                id=completion_id,
                created=created,
                model=settings.openai_compat.model_name,
                choices=[{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }],
            )
            yield f"data: {final_chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # Non-streaming response
    result = await _run_rag(query, components)

    response = ChatResponse(
        id=completion_id,
        created=created,
        model=settings.openai_compat.model_name,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content=result),
                finish_reason="stop",
            )
        ],
    )
    return response


async def _run_rag(query: str, components: Components) -> str:
    """Run RAG pipeline and return answer."""
    agent = create_rag_agent(
        search_manager=components.search_manager,
        settings=components.settings.agent,
        self_rag_settings=components.settings.self_rag,
        api_key=components.settings.anthropic_api_key,
    )

    result = await agent.ainvoke({
        "question": query,
        "search_strategy": "hybrid",
    })

    return result.get("answer", "No answer generated.")


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    components: Components = Depends(get_components),
) -> EmbeddingResponse:
    """
    OpenAI-compatible embeddings endpoint.

    Generates embeddings for the input text(s).
    """
    settings = get_settings()

    if not settings.openai_compat.enabled:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="OpenAI-compatible API is disabled")

    # Normalize input to list
    texts = request.input if isinstance(request.input, list) else [request.input]

    # Generate embeddings
    embeddings = []
    for i, text in enumerate(texts):
        emb = await components.embedding_engine.embed_text(text)
        embeddings.append(
            EmbeddingData(
                embedding=emb,
                index=i,
            )
        )

    return EmbeddingResponse(
        data=embeddings,
        model=request.model,
    )


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """
    OpenAI-compatible models endpoint.

    Returns available "models" (actually just our RAG model).
    """
    settings = get_settings()

    if not settings.openai_compat.enabled:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="OpenAI-compatible API is disabled")

    return ModelsResponse(
        data=[
            ModelInfo(
                id=settings.openai_compat.model_name,
                owned_by="pdf-rag-framework",
            )
        ],
    )
