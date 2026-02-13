"""RAGAS Adapter — convert framework data to RAGAS-compatible format (Phase 21).

Author: Claude Code
Version: 1.0.0 - Phase 21: RAGAS Evaluation
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RAGASDataset:
    """Minimal RAGAS-compatible dataset wrapper."""

    def __init__(self, data: list[dict[str, Any]]):
        self._data = data

    @property
    def column_names(self) -> list[str]:
        if not self._data:
            return []
        return list(self._data[0].keys())

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self._data[index]


class RAGASAdapter:
    """Convert framework format to RAGAS-compatible datasets."""

    def to_ragas_dataset(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: list[str] | None = None,
    ) -> RAGASDataset:
        """Convert lists to RAGAS dataset."""
        data = []
        for i in range(len(questions)):
            row = {
                "question": questions[i],
                "answer": answers[i] if i < len(answers) else "",
                "contexts": contexts[i] if i < len(contexts) else [],
            }
            if ground_truths and i < len(ground_truths):
                row["ground_truth"] = ground_truths[i]
            data.append(row)
        return RAGASDataset(data)

    async def evaluate(
        self,
        dataset: RAGASDataset,
        metrics: list[str] | None = None,
    ) -> dict[str, float]:
        """Evaluate dataset using specified metrics.

        Returns dict of metric_name → score.
        Without RAGAS library, uses heuristic scoring.
        """
        metrics = metrics or ["faithfulness", "answer_relevancy", "context_precision"]
        results: dict[str, float] = {}

        for metric in metrics:
            scores = []
            for row in dataset:
                score = self._score_heuristic(row, metric)
                scores.append(score)
            results[metric] = sum(scores) / len(scores) if scores else 0.0

        return results

    def _score_heuristic(self, row: dict[str, Any], metric: str) -> float:
        """Simple heuristic scoring when RAGAS library is not available."""
        question = row.get("question", "")
        answer = row.get("answer", "")
        contexts = row.get("contexts", [])

        if metric == "faithfulness":
            # Check answer overlap with contexts
            if not contexts or not answer:
                return 0.0
            context_text = " ".join(contexts).lower()
            answer_words = set(answer.lower().split())
            context_words = set(context_text.split())
            overlap = len(answer_words & context_words)
            return min(1.0, overlap / max(len(answer_words), 1))

        elif metric == "answer_relevancy":
            # Check answer overlap with question
            if not answer:
                return 0.0
            q_words = set(question.lower().split())
            a_words = set(answer.lower().split())
            overlap = len(q_words & a_words)
            return min(1.0, overlap / max(len(q_words), 1) * 2)

        elif metric == "context_precision":
            # Check context relevance to question
            if not contexts:
                return 0.0
            context_text = " ".join(contexts).lower()
            q_words = set(question.lower().split())
            c_words = set(context_text.split())
            overlap = len(q_words & c_words)
            return min(1.0, overlap / max(len(q_words), 1) * 2)

        return 0.5
