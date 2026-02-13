"""Abstract base class for vector store implementations.

All vector store providers (Chroma, Qdrant, FAISS) must implement this interface.
This ensures consistent behavior and easy provider switching.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult


class BaseVectorStore(ABC):
    """Abstract interface for vector store operations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the vector store connection/collection."""

    @abstractmethod
    async def add_documents(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> list[str]:
        """Add document chunks with pre-computed embeddings.

        Returns list of stored IDs.
        """

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform similarity search.

        Args:
            query_embedding: Query vector.
            k: Number of results.
            filter: Metadata filter conditions.
        """

    @abstractmethod
    async def search_mmr(
        self,
        query_embedding: list[float],
        k: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Maximal Marginal Relevance search for diverse results."""

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """Delete documents by IDs."""

    @abstractmethod
    async def get_by_ids(self, ids: list[str]) -> list[DocumentChunk]:
        """Retrieve specific documents by their IDs."""

    @abstractmethod
    async def count(self) -> int:
        """Return total number of stored documents."""

    @abstractmethod
    async def scroll(
        self,
        filter: dict[str, Any] | None = None,
        limit: int = 10000,
        fields: list[str] | None = None,
    ) -> list[DocumentChunk]:
        """Get chunks by metadata filter without embedding query.

        Use for listing, dedup, and metadata-based retrieval.

        Args:
            filter: Metadata conditions (e.g. {"source": "file.pdf"}).
            limit: Max chunks to return.
            fields: Optional list of payload fields to return (optimization).
                    If None, returns all fields including content.
        """

    @abstractmethod
    async def delete_by_filter(self, filter: dict[str, Any]) -> int:
        """Delete all chunks matching a metadata filter.

        Returns the number of chunks deleted.
        """

    @abstractmethod
    async def clear(self) -> None:
        """Remove all documents from the store."""

    # ------------------------------------------------------------------
    # Optional: native BM25 hybrid search (override in providers that support it)
    # ------------------------------------------------------------------

    def supports_native_bm25(self) -> bool:
        """Whether this store supports native BM25 sparse vectors."""
        return False

    async def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Hybrid search (dense + BM25). Default: falls back to dense-only."""
        return await self.search(query_embedding, k, filter)
