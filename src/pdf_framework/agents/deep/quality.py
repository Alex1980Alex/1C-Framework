"""Research Quality Checker for Deep Research Agent (Phase 19).

Evaluates answer coverage, groundedness, and identifies gaps.

Author: Claude Code
Version: 1.0.0 - Phase 19: Deep Research Agent
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QualityResult(BaseModel):
    """Result of quality checking a research answer."""

    coverage_score: float = 0.0
    groundedness_score: float = 0.0
    needs_followup: bool = False
    gaps: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ResearchQualityChecker:
    """Check quality of deep research answers."""

    def __init__(self, llm: Any = None, api_key: str = "", base_url: str = ""):
        self._llm = llm

    async def check(
        self,
        question: str,
        plan: Any | None,
        answer: str,
        sub_results: list[Any] | None = None,
    ) -> QualityResult:
        """Check quality of a research answer.

        Args:
            question: Original question
            plan: Research plan (optional)
            answer: Generated answer
            sub_results: Sub-question results (optional)

        Returns:
            QualityResult with scores and gaps
        """
        if self._llm is not None:
            return await self._check_with_llm(question, answer, sub_results)
        return self._check_heuristic(question, answer, sub_results)

    def _check_heuristic(
        self,
        question: str,
        answer: str,
        sub_results: list[Any] | None,
    ) -> QualityResult:
        """Check quality using heuristics."""
        gaps: list[str] = []
        q_lower = question.lower()
        a_lower = answer.lower()

        # Coverage: check if answer addresses key terms from question
        q_words = set(q_lower.split())
        a_words = set(a_lower.split())
        overlap = len(q_words & a_words)
        coverage = min(1.0, overlap / max(len(q_words), 1) * 2)

        # Detect if answer is too short for a complex question
        if len(question.split()) > 10 and len(answer.split()) < 20:
            gaps.append("Answer is too brief for a complex question")
            coverage *= 0.5

        # Check for comparison completeness
        if any(kw in q_lower for kw in ["сравн", "отличи"]):
            if "отличи" not in a_lower and "различи" not in a_lower and "сравнен" not in a_lower:
                gaps.append("Comparison not explicitly stated")

        # Check for enumeration completeness
        if any(kw in q_lower for kw in ["все типы", "перечисл", "какие"]):
            if a_lower.count(",") < 2 and a_lower.count("\n") < 2:
                gaps.append("Enumeration may be incomplete")

        needs_followup = len(gaps) > 0 or coverage < 0.5
        groundedness = 0.8 if sub_results else 0.5

        return QualityResult(
            coverage_score=round(coverage, 2),
            groundedness_score=groundedness,
            needs_followup=needs_followup,
            gaps=gaps,
            suggestions=[f"Investigate: {g}" for g in gaps],
        )

    async def _check_with_llm(
        self, question: str, answer: str, sub_results: list[Any] | None,
    ) -> QualityResult:
        """Check quality using LLM."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            import json

            messages = [
                SystemMessage(content=(
                    "Evaluate the quality of this research answer. Return JSON: "
                    "{\"coverage_score\": 0.0-1.0, \"groundedness_score\": 0.0-1.0, "
                    "\"needs_followup\": bool, \"gaps\": [\"...\"]}"
                )),
                HumanMessage(content=f"Question: {question}\n\nAnswer: {answer}"),
            ]
            response = await self._llm.ainvoke(messages)
            text = response.content if isinstance(response.content, str) else response.content[0].text
            data = json.loads(text[text.find("{"):text.rfind("}") + 1])

            return QualityResult(
                coverage_score=float(data.get("coverage_score", 0.5)),
                groundedness_score=float(data.get("groundedness_score", 0.5)),
                needs_followup=bool(data.get("needs_followup", False)),
                gaps=data.get("gaps", []),
            )
        except Exception as e:
            logger.warning(f"[QUALITY] LLM check failed: {e}")
            return self._check_heuristic(question, answer, sub_results)
