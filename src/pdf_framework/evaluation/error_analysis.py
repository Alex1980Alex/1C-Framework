"""Error Analyzer — classify RAG error types (Phase 21).

Author: Claude Code
Version: 1.0.0 - Phase 21: RAGAS Evaluation
"""

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Types of RAG errors."""

    RETRIEVAL_MISS = "retrieval_miss"
    WRONG_CONTEXT = "wrong_context"
    HALLUCINATION = "hallucination"
    INCOMPLETE = "incomplete"
    OFF_TOPIC = "off_topic"


class ErrorReport(BaseModel):
    """Report from error analysis."""

    by_type: dict[str, int] = Field(default_factory=dict)
    total_errors: int = 0
    recommendations: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)


class ErrorAnalyzer:
    """Classify and analyze RAG errors."""

    def __init__(self, threshold: float = 0.5):
        self._threshold = threshold

    async def analyze(
        self, report: Any = None,
    ) -> ErrorReport:
        """Analyze evaluation report and classify errors.

        Without a real report, returns empty analysis.
        """
        if report is None:
            return ErrorReport(
                by_type={},
                total_errors=0,
                recommendations=self._default_recommendations(),
            )

        # Analyze real report
        by_type: dict[str, int] = {}
        examples: list[dict[str, Any]] = []

        items = getattr(report, "items", None) or []
        for item in items:
            error_type = self._classify_error(item)
            if error_type:
                by_type[error_type] = by_type.get(error_type, 0) + 1
                examples.append({"error_type": error_type, "item": str(item)[:200]})

        recommendations = self._generate_recommendations(by_type)

        return ErrorReport(
            by_type=by_type,
            total_errors=sum(by_type.values()),
            recommendations=recommendations,
            examples=examples[:10],
        )

    def _classify_error(self, item: Any) -> str | None:
        """Classify a single error."""
        score = getattr(item, "score", 0.5)
        if score < 0.2:
            return ErrorType.RETRIEVAL_MISS
        elif score < 0.4:
            return ErrorType.WRONG_CONTEXT
        return None

    def _default_recommendations(self) -> list[str]:
        return [
            "Increase retrieval k for better recall",
            "Enable reranking to improve precision",
            "Consider hybrid search for diverse queries",
        ]

    def _generate_recommendations(self, by_type: dict[str, int]) -> list[str]:
        recs: list[str] = []
        if by_type.get(ErrorType.RETRIEVAL_MISS, 0) > 0:
            recs.append("Increase k or enable query expansion to reduce retrieval misses")
        if by_type.get(ErrorType.HALLUCINATION, 0) > 0:
            recs.append("Enable hallucination checking in Self-RAG")
        if by_type.get(ErrorType.INCOMPLETE, 0) > 0:
            recs.append("Consider deep research agent for complex queries")
        if not recs:
            recs = self._default_recommendations()
        return recs
