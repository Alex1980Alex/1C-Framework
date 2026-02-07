"""Vector search strategy: embed query → search vector store."""

import time
from typing import Any

from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.schemas.documents import SearchResponse
from src.pdf_framework.vector_store.base import BaseVectorStore


class VectorSearchStrategy:
    """Search by embedding the query and querying the vector store."""

    def __init__(
        self,
        embedding_engine: BaseEmbeddingEngine,
        vector_store: BaseVectorStore,
    ):
        self._embedding_engine = embedding_engine
        self._vector_store = vector_store

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        use_mmr: bool = False,
    ) -> SearchResponse:
        """Embed query and perform similarity search."""
        start = time.perf_counter()

        query_embedding = await self._embedding_engine.embed_text(query)

        if use_mmr:
            results = await self._vector_store.search_mmr(
                query_embedding=query_embedding,
                k=k,
                filter=filter,
            )
        else:
            results = await self._vector_store.search(
                query_embedding=query_embedding,
                k=k,
                filter=filter,
            )

        elapsed = (time.perf_counter() - start) * 1000

        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            search_type="vector",
            elapsed_ms=elapsed,
        )
