"""Cross-encoder reranker for search result refinement."""

import asyncio

from sentence_transformers import CrossEncoder

from src.pdf_framework.schemas.documents import SearchResult


class CrossEncoderReranker:
    """Rerank search results using a cross-encoder model."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model_name = model_name
        self._model: CrossEncoder | None = None

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self._model_name)
        return self._model

    def _rerank_sync(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        model = self._get_model()
        pairs = [(query, r.chunk.content) for r in results]
        scores = model.predict(pairs)

        scored = list(zip(results, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        reranked: list[SearchResult] = []
        for result, score in scored[:top_k]:
            reranked.append(
                SearchResult(
                    chunk=result.chunk,
                    score=float(score),
                    source=result.source,
                    highlights=result.highlights,
                )
            )
        return reranked

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        """Rerank results using cross-encoder scores."""
        if not results:
            return []
        return await asyncio.to_thread(self._rerank_sync, query, results, top_k)
