"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat, documents, health, search
from src.pdf_framework.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="PDF Vector & Graph Framework",
        version="1.0.0",
        description="Intelligent PDF processing with Vector and Graph databases",
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

    return app


app = create_app()
