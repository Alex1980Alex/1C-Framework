"""Vector store providers."""

from src.pdf_framework.config import VectorStoreSettings
from src.pdf_framework.vector_store.base import BaseVectorStore


def get_vector_store(settings: VectorStoreSettings | None = None) -> BaseVectorStore:
    """Factory: return a vector store based on settings."""
    settings = settings or VectorStoreSettings()
    if settings.provider == "chroma":
        from src.pdf_framework.vector_store.providers.chroma import ChromaVectorStore

        return ChromaVectorStore(settings)
    raise ValueError(f"Unsupported vector store provider: {settings.provider}")
