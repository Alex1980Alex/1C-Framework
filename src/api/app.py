"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat, documents, health, metrics, search
from src.pdf_framework.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup, cleanup on shutdown."""
    from src.api.dependencies.components import get_components
    from src.api.routes.chat import init_chat
    from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

    components = await get_components()

    # Phase 9: Initialize chat with streaming runner
    try:
        from src.pdf_framework.agents.rag.agent import create_rag_agent

        agent = create_rag_agent(
            search_manager=components.search_manager,
            settings=components.settings.agent,
            self_rag_settings=components.settings.self_rag,
            api_key=components.settings.anthropic_api_key,
        )
        runner = StreamingRAGRunner(agent)
        init_chat(memory=components.conversation_memory, runner=runner)
    except Exception:
        # Chat API will return 500 if not initialized
        pass

    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="PDF Vector & Graph Framework",
        version="1.0.0",
        description="Intelligent PDF processing with Vector and Graph databases",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(chat.router)  # Phase 9: Conversational RAG
    app.include_router(metrics.router)  # Phase 11.6: Metrics Dashboard

    return app


app = create_app()
