"""Embedding cache for faster repeated embeddings (Phase 11).

Provides:
- FileEmbeddingCache: disk-based JSON file cache (legacy)
- EmbeddingCache: SQLite-based async cache with TTL (Phase 11.2)
- CacheStats: Pydantic model for cache statistics
"""

from src.pdf_framework.embeddings.cache.file_cache import FileEmbeddingCache
from src.pdf_framework.embeddings.cache.sqlite_cache import (
    CacheStats,
    EmbeddingCache,
    get_embedding_cache,
)

__all__ = [
    "CacheStats",
    "EmbeddingCache",
    "FileEmbeddingCache",
    "get_embedding_cache",
]
