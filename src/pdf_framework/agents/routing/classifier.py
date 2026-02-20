"""Query Complexity Classifier for Model Routing (Phase 54.1).

Classifies queries into complexity levels and maps them to appropriate LLM models.
Simple → Haiku, Moderate → Sonnet, Complex → Opus.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class ClassificationResult:
    level: ComplexityLevel
    model: str
    features: dict
    reason: str


# Default model map
DEFAULT_MODEL_MAP: dict[ComplexityLevel, str] = {
    ComplexityLevel.SIMPLE: "claude-haiku-3-5",
    ComplexityLevel.MODERATE: "claude-sonnet-4-5-20250929",
    ComplexityLevel.COMPLEX: "claude-opus-4-6",
}

# Keywords that signal higher complexity
_COMPLEX_KEYWORDS = {
    "сравни", "сравнение", "проанализируй", "анализ", "объясни подробно",
    "различия между", "преимущества и недостатки", "плюсы и минусы",
    "как устроен", "архитектура", "в чём разница",
    "compare", "analyze", "explain in detail", "differences between",
    "pros and cons", "architecture", "how does it work internally",
    "step by step", "пошагово", "все варианты", "все способы",
}

_MODERATE_KEYWORDS = {
    "как", "почему", "зачем", "когда использовать", "пример",
    "how to", "why", "when to use", "example", "tutorial",
    "покажи", "опиши", "расскажи", "объясни",
    "show", "describe", "explain",
}


class ModelRoutingClassifier:
    """Classify query complexity and select appropriate model.

    Rules:
        simple   — factual, <20 words, single-concept → Haiku
        moderate — how-to, explanations, examples → Sonnet
        complex  — analysis, comparison, multi-step reasoning → Opus
    """

    def __init__(
        self,
        model_map: dict[ComplexityLevel, str] | None = None,
    ):
        self.model_map = model_map or DEFAULT_MODEL_MAP.copy()

    def classify(self, query: str) -> ClassificationResult:
        """Classify query and return recommended model."""
        features = self._extract_features(query)

        # Rule-based classification
        level = self._apply_rules(features)

        model = self.model_map[level]
        reason = self._explain(level, features)

        return ClassificationResult(
            level=level,
            model=model,
            features=features,
            reason=reason,
        )

    def _extract_features(self, query: str) -> dict:
        """Extract classification features from query."""
        words = query.split()
        word_count = len(words)
        query_lower = query.lower()

        # Count question marks
        question_marks = query.count("?")

        # Check for complex keywords
        complex_hits = sum(1 for kw in _COMPLEX_KEYWORDS if kw in query_lower)
        moderate_hits = sum(1 for kw in _MODERATE_KEYWORDS if kw in query_lower)

        # Check for sub-questions (multiple sentences ending with ?)
        sub_questions = len(re.findall(r'[?？]', query))

        # Check for enumeration requests
        has_enumeration = bool(re.search(
            r'(?:перечисли|список|все\s+(?:виды|типы|варианты)|list\s+all|enumerate)',
            query_lower,
        ))

        # Check for code requests
        has_code_request = bool(re.search(
            r'(?:код|пример кода|code|snippet|покажи как написать|напиши)',
            query_lower,
        ))

        return {
            "word_count": word_count,
            "question_marks": question_marks,
            "complex_hits": complex_hits,
            "moderate_hits": moderate_hits,
            "sub_questions": sub_questions,
            "has_enumeration": has_enumeration,
            "has_code_request": has_code_request,
        }

    def _apply_rules(self, features: dict) -> ComplexityLevel:
        """Apply classification rules based on features."""
        # Complex: multi-part questions, analytical keywords, long queries
        if (
            features["complex_hits"] >= 1
            or features["sub_questions"] >= 2
            or (features["word_count"] > 40 and features["moderate_hits"] >= 1)
        ):
            return ComplexityLevel.COMPLEX

        # Moderate: how-to, explanations, code examples
        if (
            features["moderate_hits"] >= 1
            or features["has_code_request"]
            or features["has_enumeration"]
            or features["word_count"] > 20
        ):
            return ComplexityLevel.MODERATE

        # Simple: short factual queries
        return ComplexityLevel.SIMPLE

    @staticmethod
    def _explain(level: ComplexityLevel, features: dict) -> str:
        """Human-readable reason for classification."""
        if level == ComplexityLevel.COMPLEX:
            reasons = []
            if features["complex_hits"]:
                reasons.append(f"{features['complex_hits']} analytical keywords")
            if features["sub_questions"] >= 2:
                reasons.append(f"{features['sub_questions']} sub-questions")
            if features["word_count"] > 40:
                reasons.append(f"{features['word_count']} words")
            return f"complex: {', '.join(reasons)}"

        if level == ComplexityLevel.MODERATE:
            reasons = []
            if features["moderate_hits"]:
                reasons.append("how-to/explanation keywords")
            if features["has_code_request"]:
                reasons.append("code request")
            if features["has_enumeration"]:
                reasons.append("enumeration request")
            return f"moderate: {', '.join(reasons)}"

        return f"simple: {features['word_count']} words, factual query"
