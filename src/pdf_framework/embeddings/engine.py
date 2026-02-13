"""Abstract embedding engine interface.

Provides a unified interface for generating embeddings across different providers.
Supports batch processing and caching.
"""

from abc import ABC, abstractmethod


class BaseEmbeddingEngine(ABC):
    """Abstract interface for embedding generation."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""

    @abstractmethod
    def get_dimensions(self) -> int:
        """Return the dimensionality of the embedding model."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the name of the embedding model."""
