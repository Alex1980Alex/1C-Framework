"""Vector store providers."""

from src.pdf_framework.config import VectorStoreSettings
from src.pdf_framework.vector_store.base import BaseVectorStore


def get_vector_store(settings: VectorStoreSettings | None = None) -> BaseVectorStore:
    """Factory: return a vector store based on settings."""
    settings = settings or VectorStoreSettings()
    if settings.provider == "chroma":
        from src.pdf_framework.vector_store.providers.chroma import ChromaVectorStore

        return ChromaVectorStore(settings)
    elif settings.provider == "qdrant":
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        return QdrantVectorStore(settings)
    elif settings.provider == "pgvector":
        from src.pdf_framework.vector_store.providers.pgvector import PgVectorStore

        return PgVectorStore(settings)
    raise ValueError(f"Unsupported vector store provider: {settings.provider}")
