"""Custom evaluation metrics for DSPy optimization (Phase 34).

Metrics for measuring quality of LLM outputs:
- CompletenessMetric: Does the answer cover all aspects of the question?
- AccuracyMetric: Is the answer factually correct per ground truth?
- TablePresenceMetric: For comparative questions, is there a comparison table?
- GroundednessMetric: Are claims backed by retrieved chunks?
- CompositeMetric: Weighted combination of all metrics.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class CompletenessMetric:
    """Checks if the answer covers all expected aspects.

    Simple keyword overlap approach — checks if key terms
    from the ground truth appear in the answer.
    """

    def __call__(
        self,
        example: dict[str, Any],
        prediction: Any,
        trace: Any = None,
    ) -> float:
        """Score 0-1 based on term coverage."""
        answer = _get_answer(prediction)
        ground_truth = example.get("answer", "")

        if not ground_truth or not answer:
            return 0.0

        # Extract key terms from ground truth (words > 4 chars)
        gt_terms = {
            w.lower()
            for w in re.findall(r"\w+", ground_truth)
            if len(w) > 4
        }
        if not gt_terms:
            return 1.0

        answer_lower = answer.lower()
        covered = sum(1 for t in gt_terms if t in answer_lower)
        return covered / len(gt_terms)


class AccuracyMetric:
    """Simple string overlap accuracy between prediction and ground truth."""

    def __call__(
        self,
        example: dict[str, Any],
        prediction: Any,
        trace: Any = None,
    ) -> float:
        answer = _get_answer(prediction)
        ground_truth = example.get("answer", "")

        if not ground_truth or not answer:
            return 0.0

        # Jaccard similarity on word level
        pred_words = set(re.findall(r"\w+", answer.lower()))
        gt_words = set(re.findall(r"\w+", ground_truth.lower()))

        if not gt_words:
            return 1.0

        intersection = pred_words & gt_words
        union = pred_words | gt_words

        return len(intersection) / len(union) if union else 0.0


class TablePresenceMetric:
    """Checks if a markdown comparison table is present in the answer.

    Returns 1.0 if table with | separators found, 0.0 otherwise.
    For non-comparative questions, always returns 1.0.
    """

    def __call__(
        self,
        example: dict[str, Any],
        prediction: Any,
        trace: Any = None,
    ) -> float:
        q_type = example.get("question_type", "factual")

        # Only check for comparative questions
        if q_type != "comparative":
            return 1.0

        answer = _get_answer(prediction)

        # Check for markdown table pattern: | ... | ... |
        table_lines = [
            line for line in answer.split("\n")
            if line.strip().startswith("|") and line.strip().endswith("|")
            and line.count("|") >= 3
        ]

        return 1.0 if len(table_lines) >= 3 else 0.0


class GroundednessMetric:
    """Checks if the answer references source material.

    Looks for citation patterns like [1], [2] etc.
    """

    def __call__(
        self,
        example: dict[str, Any],
        prediction: Any,
        trace: Any = None,
    ) -> float:
        answer = _get_answer(prediction)

        if not answer:
            return 0.0

        # Count citation references
        citations = re.findall(r"\[\d+\]", answer)
        if not citations:
            return 0.0

        # More citations = higher groundedness (cap at 1.0)
        return min(len(citations) / 3, 1.0)


class CompositeMetric:
    """Weighted combination of all metrics.

    Default weights:
    - completeness: 0.35
    - accuracy: 0.30
    - table_presence: 0.15
    - groundedness: 0.20
    """

    def __init__(
        self,
        completeness_weight: float = 0.35,
        accuracy_weight: float = 0.30,
        table_weight: float = 0.15,
        groundedness_weight: float = 0.20,
    ):
        self._weights = {
            "completeness": completeness_weight,
            "accuracy": accuracy_weight,
            "table_presence": table_weight,
            "groundedness": groundedness_weight,
        }
        self._metrics = {
            "completeness": CompletenessMetric(),
            "accuracy": AccuracyMetric(),
            "table_presence": TablePresenceMetric(),
            "groundedness": GroundednessMetric(),
        }

    def __call__(
        self,
        example: dict[str, Any],
        prediction: Any,
        trace: Any = None,
    ) -> float:
        total = 0.0
        for name, metric in self._metrics.items():
            score = metric(example, prediction, trace)
            weight = self._weights.get(name, 0.25)
            total += score * weight
        return total

    def detailed(
        self,
        example: dict[str, Any],
        prediction: Any,
    ) -> dict[str, float]:
        """Get per-metric scores."""
        return {
            name: metric(example, prediction)
            for name, metric in self._metrics.items()
        }


def _get_answer(prediction: Any) -> str:
    """Extract answer text from a DSPy prediction or dict."""
    if isinstance(prediction, dict):
        return prediction.get("answer", prediction.get("conclusion", ""))
    if hasattr(prediction, "answer"):
        return prediction.answer
    if hasattr(prediction, "conclusion"):
        return prediction.conclusion
    return str(prediction)
