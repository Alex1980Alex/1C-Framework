"""Few-Shot Provider — find similar positive examples (Phase 22).

Author: Claude Code
Version: 1.0.0 - Phase 22: Self-Learning Feedback
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FewShotExample(BaseModel):
    """A few-shot example with similarity score."""

    question: str
    answer: str
    similarity: float = 0.0


class FewShotProvider:
    """Provide few-shot examples from positive feedback."""

    def __init__(
        self,
        feedback_store: Any = None,
        embedding_engine: Any = None,
        max_examples: int = 3,
        similarity_threshold: float = 0.7,
    ):
        self._store = feedback_store
        self._engine = embedding_engine
        self._max_examples = max_examples
        self._threshold = similarity_threshold

    async def get_examples(self, question: str) -> list[FewShotExample]:
        """Find similar positive Q&A pairs for few-shot prompting."""
        if not self._store:
            return []

        positive = await self._store.get_positive(limit=50)

        if not positive or not self._engine:
            # Without embedding engine, return top N by recency
            return [
                FewShotExample(
                    question=p.question,
                    answer=p.answer,
                    similarity=0.5,
                )
                for p in positive[:self._max_examples]
            ]

        # Compute similarities
        try:
            query_emb = await self._engine.embed_text(question)
            examples_with_sim: list[tuple[float, FewShotExample]] = []

            for p in positive:
                p_emb = await self._engine.embed_text(p.question)
                # Dot product (assuming normalized)
                sim = sum(a * b for a, b in zip(query_emb, p_emb))

                if sim >= self._threshold:
                    examples_with_sim.append((sim, FewShotExample(
                        question=p.question,
                        answer=p.answer,
                        similarity=sim,
                    )))

            examples_with_sim.sort(key=lambda x: x[0], reverse=True)
            return [ex for _, ex in examples_with_sim[:self._max_examples]]

        except Exception as e:
            logger.warning(f"[FEW_SHOT] Embedding failed: {e}")
            return []

    def format_for_prompt(self, examples: list[FewShotExample]) -> str:
        """Format examples for inclusion in a prompt."""
        if not examples:
            return ""

        parts = ["Here are similar previous Q&A pairs:"]
        for i, ex in enumerate(examples, 1):
            parts.append(f"\nExample {i}:")
            parts.append(f"Q: {ex.question}")
            parts.append(f"A: {ex.answer}")

        return "\n".join(parts)
