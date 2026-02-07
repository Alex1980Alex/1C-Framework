"""MMR (Maximal Marginal Relevance) search strategy.

Phase 2.1: Standalone strategy that balances relevance and diversity.
Uses vector_store.search_mmr() with configurable diversity lambda.
"""

import time
from typing import Any

from src.pdf_framework.config import SearchSettings
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.schemas.documents import SearchResponse
from src.pdf_framework.vector_store.base import BaseVectorStore


class MMRSearchStrategy:
    """Search with Maximal Marginal Relevance for diverse results.

    MMR = lambda * sim(query, doc) - (1 - lambda) * max(sim(doc, selected))

    Higher diversity_lambda → more relevance.
    Lower diversity_lambda → more diversity.
    """

    def __init__(
        self,
        embedding_engine: BaseEmbeddingEngine,
        vector_store: BaseVectorStore,
        search_settings: SearchSettings | None = None,
    ):
        self._embedding_engine = embedding_engine
        self._vector_store = vector_store
        settings = search_settings or SearchSettings()
        self._diversity_lambda = settings.mmr_diversity_lambda
        self._fetch_k = settings.mmr_fetch_k

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        diversity: float | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute MMR search.

        Args:
            query: Search query text.
            k: Number of final results.
            filter: Optional metadata filters.
            diversity: Override diversity lambda (0.0 = max diversity, 1.0 = pure relevance).
        """
        start = time.perf_counter()

        lambda_mult = diversity if diversity is not None else self._diversity_lambda
        query_embedding = await self._embedding_engine.embed_text(query)

        results = await self._vector_store.search_mmr(
            query_embedding=query_embedding,
            k=k,
            fetch_k=self._fetch_k,
            lambda_mult=lambda_mult,
            filter=filter,
        )

        elapsed = (time.perf_counter() - start) * 1000

        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            search_type="mmr",
            elapsed_ms=elapsed,
        )
