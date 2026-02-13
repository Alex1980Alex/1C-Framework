"""Embedding engines with caching (Phase 11)."""

from src.pdf_framework.config import EmbeddingSettings
from src.pdf_framework.embeddings.cache import (
    CacheStats,
    EmbeddingCache,
    get_embedding_cache,
)
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine


def get_embedding_engine(settings: EmbeddingSettings | None = None) -> BaseEmbeddingEngine:
    """Factory: return an embedding engine based on settings."""
    settings = settings or EmbeddingSettings()
    if settings.provider == "local":
        from src.pdf_framework.embeddings.providers.local import LocalEmbeddingEngine

        return LocalEmbeddingEngine(settings)
    if settings.provider == "giga":
        from src.pdf_framework.embeddings.providers.giga import GigaEmbeddingEngine

        return GigaEmbeddingEngine(settings)
    raise ValueError(f"Unsupported embedding provider: {settings.provider}")


__all__ = [
    "BaseEmbeddingEngine",
    "EmbeddingSettings",
    "EmbeddingCache",
    "CacheStats",
    "get_embedding_cache",
    "get_embedding_engine",
]
