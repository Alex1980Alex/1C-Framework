"""Two-Stage Retrieval Pipeline.

Phase 3.3: Orchestrates a broad recall stage (bi-encoder) followed by
a precise selection stage (cross-encoder + MMR + FlashRank).

Architecture:
    Query
      ↓
    [Stage 1: Bi-Encoder — Fast, Broad]
      strategy.search(k=stage1_k)  → top 50
      ↓
    [Stage 2: Cross-Encoder — Precise]
      reranker.rerank(top stage2_rerank_k)  → top 20
      optional MMR diversity               → top 10
      optional FlashRank token selection    → top k
      ↓
    Final Results
"""

import time
from typing import Any

import numpy as np

from src.pdf_framework.config import TwoStageSettings
from src.pdf_framework.schemas.documents import SearchResponse, SearchResult
from src.pdf_framework.search.reranking.cross_encoder import CrossEncoderReranker
from src.pdf_framework.search.reranking.flashrank import FlashRankReranker


class TwoStagePipeline:
    """Two-stage retrieval: broad recall → precise selection."""

    def __init__(
        self,
        stage1_strategy: Any,
        reranker: Any,  # CrossEncoderReranker or LLMReranker (both have async rerank())
        flashrank: FlashRankReranker | None = None,
        settings: TwoStageSettings | None = None,
    ):
        self._stage1 = stage1_strategy
        self._reranker = reranker
        self._flashrank = flashrank
        self._settings = settings or TwoStageSettings()

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute two-stage retrieval pipeline."""
        start = time.perf_counter()

        # Stage 1: Broad recall via bi-encoder
        stage1_response = await self._stage1.search(
            query=query,
            k=self._settings.stage1_k,
            filter=filter,
            **kwargs,
        )

        if not stage1_response.results:
            elapsed = (time.perf_counter() - start) * 1000
            return SearchResponse(
                query=query,
                results=[],
                total_found=0,
                search_type="two_stage",
                elapsed_ms=elapsed,
            )

        # Stage 2: Cross-encoder reranking
        reranked = await self._reranker.rerank(
            query=query,
            results=stage1_response.results,
            top_k=self._settings.stage2_rerank_k,
        )

        # Optional: MMR diversity
        if self._settings.stage2_use_mmr and len(reranked) > k:
            reranked = self._apply_mmr(
                query, reranked, k=k * 2,  # Keep more for potential FlashRank
                lambda_mult=self._settings.stage2_mmr_lambda,
            )

        # Optional: FlashRank token-budget selection
        if self._settings.stage2_use_flashrank and self._flashrank:
            reranked = await self._flashrank.select(
                query=query,
                results=reranked,
            )

        # Final top-k
        final = reranked[:k]

        elapsed = (time.perf_counter() - start) * 1000

        return SearchResponse(
            query=query,
            results=final,
            total_found=len(final),
            search_type="two_stage",
            elapsed_ms=elapsed,
        )

    @staticmethod
    def _apply_mmr(
        query: str,
        results: list[SearchResult],
        k: int,
        lambda_mult: float = 0.5,
    ) -> list[SearchResult]:
        """Apply MMR diversity filtering on reranked results.

        Uses word-overlap similarity as a fast proxy (no extra embeddings needed
        since we're in the cross-encoder stage).
        """
        if len(results) <= k:
            return results

        # Build word sets for diversity calculation
        word_sets = [set(r.chunk.content.lower().split()) for r in results]
        scores = np.array([r.score for r in results])

        # Normalize scores to [0, 1]
        score_range = scores.max() - scores.min()
        if score_range > 0:
            norm_scores = (scores - scores.min()) / score_range
        else:
            norm_scores = np.ones_like(scores)

        selected: list[int] = []
        remaining = list(range(len(results)))

        for _ in range(min(k, len(results))):
            if not remaining:
                break

            if not selected:
                best = max(remaining, key=lambda i: norm_scores[i])
            else:
                best_mmr = -float("inf")
                best = remaining[0]
                for i in remaining:
                    # Max similarity to any selected result
                    max_sim = 0.0
                    for s in selected:
                        inter = len(word_sets[i] & word_sets[s])
                        union = len(word_sets[i] | word_sets[s])
                        sim = inter / union if union > 0 else 0.0
                        max_sim = max(max_sim, sim)

                    mmr = lambda_mult * norm_scores[i] - (1 - lambda_mult) * max_sim
                    if mmr > best_mmr:
                        best_mmr = mmr
                        best = i

            selected.append(best)
            remaining.remove(best)

        return [results[i] for i in selected]
