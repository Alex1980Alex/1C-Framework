"""ColBERT late-interaction reranker (Phase 35).

Token-level MaxSim scoring for precise reranking of technical terms.
Uses Jina ColBERT v2 (jinaai/jina-colbert-v2) or RAGatouille wrapper.

ColBERT computes per-token similarities between query and document tokens,
then takes the maximum similarity for each query token (MaxSim).
This is especially effective for technical terms like CamelCase identifiers
in 1C documentation (e.g., "РегистрНакопления", "ДокументОбъект").

Requires: ragatouille (pip install ragatouille) or colbert-ai.
"""

import asyncio
import logging
from typing import Any

from src.pdf_framework.schemas.documents import SearchResult

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "jinaai/jina-colbert-v2"


class ColBERTReranker:
    """Rerank search results using ColBERT late interaction.

    Lazy-loads the model on first use. Supports:
    - RAGatouille wrapper (preferred, simpler API)
    - Direct colbert-ai (fallback)
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        device: str = "auto",
        max_length: int = 512,
    ):
        self._model_name = model_name
        self._device = device
        self._max_length = max_length
        self._model: Any = None
        self._backend: str = "none"

    def _load_model(self) -> None:
        """Lazy-load ColBERT model."""
        if self._model is not None:
            return

        # Try RAGatouille first
        try:
            from ragatouille import RAGPretrainedModel

            self._model = RAGPretrainedModel.from_pretrained(self._model_name)
            self._backend = "ragatouille"
            logger.info("[COLBERT] Loaded via RAGatouille: %s", self._model_name)
            return
        except ImportError:
            logger.info("[COLBERT] ragatouille not available, trying sentence-transformers")
        except Exception as e:
            logger.warning("[COLBERT] RAGatouille load failed: %s", e)

        # Try sentence-transformers ColBERT
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self._model_name,
                trust_remote_code=True,
                device=self._device if self._device != "auto" else None,
            )
            self._backend = "sentence_transformers"
            logger.info(
                "[COLBERT] Loaded via sentence-transformers: %s", self._model_name
            )
            return
        except ImportError:
            logger.warning("[COLBERT] sentence-transformers not available")
        except Exception as e:
            logger.warning("[COLBERT] sentence-transformers load failed: %s", e)

        raise RuntimeError(
            f"Cannot load ColBERT model {self._model_name}. "
            "Install: pip install ragatouille OR pip install sentence-transformers"
        )

    def _score_ragatouille(
        self, query: str, documents: list[str]
    ) -> list[float]:
        """Score using RAGatouille API."""
        results = self._model.rerank(query=query, documents=documents, k=len(documents))
        # RAGatouille returns sorted results with scores
        score_map: dict[int, float] = {}
        for r in results:
            idx = r.get("result_index", 0)
            score = r.get("score", 0.0)
            score_map[idx] = score
        return [score_map.get(i, 0.0) for i in range(len(documents))]

    def _score_sentence_transformers(
        self, query: str, documents: list[str]
    ) -> list[float]:
        """Score using sentence-transformers MaxSim."""
        # Encode query and documents
        q_emb = self._model.encode(query, convert_to_tensor=True)
        d_embs = self._model.encode(documents, convert_to_tensor=True)

        # MaxSim: for each query token, take max similarity with any doc token
        # Then average over query tokens
        import torch

        if q_emb.dim() == 1:
            # Dense embedding fallback (not true ColBERT)
            similarities = torch.nn.functional.cosine_similarity(
                q_emb.unsqueeze(0), d_embs
            )
            return similarities.tolist()

        # True ColBERT: q_emb is (q_tokens, dim), d_embs is (n_docs, d_tokens, dim)
        scores = []
        for d_emb in d_embs:
            if d_emb.dim() == 1:
                d_emb = d_emb.unsqueeze(0)
            # (q_tokens, dim) @ (dim, d_tokens) => (q_tokens, d_tokens)
            sim_matrix = torch.matmul(q_emb, d_emb.T)
            # MaxSim: max over d_tokens for each q_token, then average
            max_sim = sim_matrix.max(dim=1).values
            scores.append(max_sim.mean().item())

        return scores

    def _rerank_sync(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        """Synchronous reranking."""
        self._load_model()

        documents = [r.chunk.content for r in results]

        if self._backend == "ragatouille":
            scores = self._score_ragatouille(query, documents)
        else:
            scores = self._score_sentence_transformers(query, documents)

        # Combine with original scores (weighted)
        scored = []
        for result, colbert_score in zip(results, scores):
            # Blend: 70% ColBERT + 30% original
            blended = 0.7 * float(colbert_score) + 0.3 * result.score
            scored.append((result, blended, float(colbert_score)))

        scored.sort(key=lambda x: x[1], reverse=True)

        reranked: list[SearchResult] = []
        for result, blended_score, colbert_score in scored[:top_k]:
            new_result = SearchResult(
                chunk=result.chunk,
                score=blended_score,
                source=result.source,
                highlights=result.highlights,
            )
            # Store ColBERT score in metadata for debugging
            new_result.chunk.metadata["colbert_score"] = round(colbert_score, 4)
            reranked.append(new_result)

        return reranked

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        """Rerank results using ColBERT late interaction scores.

        Args:
            query: Search query.
            results: Search results to rerank.
            top_k: Number of results to return.

        Returns:
            Reranked results sorted by ColBERT-blended score.
        """
        if not results:
            return []

        return await asyncio.to_thread(self._rerank_sync, query, results, top_k)

    @property
    def backend(self) -> str:
        """Which backend is being used."""
        return self._backend

    @property
    def model_name(self) -> str:
        return self._model_name
