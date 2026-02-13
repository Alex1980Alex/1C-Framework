"""FlashRank: Token-budget-aware reranking with marginal utility.

Phase 3.2: Selects documents that maximize information coverage within
a token budget. Unlike standard reranking (which just sorts by score),
FlashRank greedily picks the highest-utility document that still fits
the remaining budget, reducing redundancy and token waste.

Algorithm:
    1. Score all results via cross-encoder relevance
    2. Compute pairwise similarity between candidates
    3. Iteratively select highest marginal-utility result within budget
    4. Marginal utility = relevance - max_similarity_to_already_selected
"""

import asyncio
import logging

import numpy as np
from sentence_transformers import CrossEncoder

from src.pdf_framework.schemas.documents import SearchResult

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for mixed RU/EN text."""
    return max(1, len(text) // 4)


class FlashRankReranker:
    """Select documents by marginal utility within a token budget."""

    def __init__(
        self,
        token_budget: int = 4096,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ):
        self._token_budget = token_budget
        self._model_name = model_name
        self._model: CrossEncoder | None = None

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self._model_name)
        return self._model

    def _select_sync(
        self,
        query: str,
        results: list[SearchResult],
        token_budget: int | None = None,
    ) -> list[SearchResult]:
        """Synchronous FlashRank selection."""
        if not results:
            return []

        budget = token_budget or self._token_budget
        model = self._get_model()

        # 1. Score all results by relevance
        pairs = [(query, r.chunk.content) for r in results]
        relevance_scores = model.predict(pairs).astype(float)

        # 2. Compute content embeddings for diversity (use relevance proxy via content similarity)
        contents = [r.chunk.content for r in results]
        content_tokens = [_estimate_tokens(c) for c in contents]

        # Simple TF overlap as similarity proxy (fast, no extra model needed)
        n = len(results)
        similarity_matrix = self._compute_similarity_matrix(contents)

        # 3. Greedy selection by marginal utility within budget
        selected_indices: list[int] = []
        remaining = set(range(n))
        used_tokens = 0

        while remaining:
            best_idx = -1
            best_utility = -float("inf")

            for idx in remaining:
                # Skip if doesn't fit budget
                if used_tokens + content_tokens[idx] > budget:
                    continue

                # Marginal utility = relevance - max_similarity_to_selected
                if selected_indices:
                    max_sim = max(
                        similarity_matrix[idx][s] for s in selected_indices
                    )
                    utility = float(relevance_scores[idx]) - max_sim
                else:
                    utility = float(relevance_scores[idx])

                if utility > best_utility:
                    best_utility = utility
                    best_idx = idx

            if best_idx < 0:
                break  # Nothing more fits

            selected_indices.append(best_idx)
            remaining.remove(best_idx)
            used_tokens += content_tokens[best_idx]

        logger.debug(
            "FlashRank: selected %d/%d results, %d/%d tokens used",
            len(selected_indices), n, used_tokens, budget,
        )

        # Build results preserving relevance score
        return [
            SearchResult(
                chunk=results[i].chunk,
                score=float(relevance_scores[i]),
                source=results[i].source,
                highlights=results[i].highlights,
            )
            for i in selected_indices
        ]

    @staticmethod
    def _compute_similarity_matrix(contents: list[str]) -> np.ndarray:
        """Compute word-overlap similarity between all content pairs.

        Uses Jaccard similarity on word sets as a fast proxy
        for content similarity (no extra model needed).
        """
        n = len(contents)
        word_sets = [set(c.lower().split()) for c in contents]
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                intersection = len(word_sets[i] & word_sets[j])
                union = len(word_sets[i] | word_sets[j])
                sim = intersection / union if union > 0 else 0.0
                matrix[i][j] = sim
                matrix[j][i] = sim

        return matrix

    async def select(
        self,
        query: str,
        results: list[SearchResult],
        token_budget: int | None = None,
    ) -> list[SearchResult]:
        """Select results by marginal utility within token budget."""
        if not results:
            return []
        return await asyncio.to_thread(
            self._select_sync, query, results, token_budget,
        )
