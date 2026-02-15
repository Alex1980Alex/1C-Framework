"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import analytics, auth, cache, chat, collections, documents, feedback, graph, health, metrics, optimization, search, toc
from src.api.routes import openai_compat  # Phase 14: OpenAI-compatible API
from src.pdf_framework.config import get_settings

# Configure module-level logging so [LOADER], [PIPELINE], [INDEXER], etc. are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


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

    openapi_tags = [
        {"name": "health", "description": "Health checks, readiness/liveness probes for Kubernetes"},
        {"name": "auth", "description": "JWT authentication, token management, RBAC roles"},
        {"name": "documents", "description": "PDF upload, indexing (sync/stream/batch/delta), document listing, BM25/sparse rebuild"},
        {"name": "search", "description": "Vector, BM25, hybrid, section-aware search. RAG QA with LLM reranking"},
        {"name": "chat", "description": "Conversational RAG with message history and streaming"},
        {"name": "graph", "description": "Knowledge graph: entities, relations, neighbors, communities, LightRAG"},
        {"name": "cache", "description": "Semantic search cache management"},
        {"name": "metrics", "description": "Prometheus metrics, evaluation results dashboard"},
        {"name": "openai_compat", "description": "OpenAI-compatible /v1/chat/completions endpoint"},
        {"name": "feedback", "description": "User feedback collection for self-learning retrieval"},
        {"name": "toc", "description": "Table of contents navigation, section summaries"},
        {"name": "collections", "description": "Multi-document knowledge bases: collections, scoped search"},
        {"name": "optimization", "description": "DSPy prompt optimization, A/B experiments"},
        {"name": "analytics", "description": "Enterprise analytics: query tracking, cost analysis, audit logs"},
    ]

    app = FastAPI(
        title="PDF Vector & Graph Framework",
        version="1.5.0",
        description=(
            "Intelligent PDF processing with Vector and Graph databases.\n\n"
            "**Features**: 12 search strategies, LLM reranking, hybrid BM25+vector search, "
            "knowledge graphs, conversational RAG, multi-document collections, "
            "DSPy optimization, enterprise analytics.\n\n"
            "**Stack**: Qdrant, E5 multilingual embeddings, Claude (Anthropic), LangGraph agents."
        ),
        lifespan=lifespan,
        openapi_tags=openapi_tags,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)  # Phase 12: Authentication
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(chat.router)  # Phase 9: Conversational RAG
    app.include_router(graph.router)  # Knowledge graph API
    app.include_router(cache.router)  # Cache management API
    app.include_router(metrics.router)  # Phase 11.6: Metrics Dashboard
    app.include_router(openai_compat.router)  # Phase 14.3: OpenAI-compatible API
    app.include_router(feedback.router)  # Phase 22: Self-Learning Feedback
    app.include_router(toc.router)  # Phase 30: ToC Navigation API
    app.include_router(collections.router)  # Phase 32: Collection Management
    app.include_router(optimization.router)  # Phase 34: DSPy Optimization
    app.include_router(analytics.router)  # Phase 40: Enterprise Analytics

    return app


app = create_app()
