"""Unit tests for Self-RAG parser functions.

Tests _parse_relevance (grader) and _parse_hallucination_result (hallucination_checker).
These are pure functions — no LLM needed.
"""

import pytest

from src.pdf_framework.agents.rag.nodes.grader import _parse_relevance
from src.pdf_framework.agents.rag.nodes.hallucination_checker import (
    _parse_hallucination_result,
)


# ============================================================
# _parse_relevance
# ============================================================


class TestParseRelevance:
    """Tests for binary relevance parsing from LLM responses."""

    # --- Positive (relevant) ---

    @pytest.mark.parametrize(
        "response",
        [
            "yes",
            "Yes",
            "YES",
            "yes - contains definition of конфигуратор",
            "yes, this document discusses the topic",
            "relevant",
            "Relevant - directly answers the question",
            "да",
            "Да, документ релевантен",
        ],
    )
    def test_relevant_responses(self, response: str):
        assert _parse_relevance(response) is True

    # --- Negative (not relevant) ---

    @pytest.mark.parametrize(
        "response",
        [
            "no",
            "No",
            "NO",
            "no - unrelated topic",
            "no, this document is about something else",
            "not relevant",
            "Not relevant - discusses different subject",
            "нет",
            "Нет, документ не по теме",
            "unrelated",
        ],
    )
    def test_not_relevant_responses(self, response: str):
        assert _parse_relevance(response) is False

    # --- Edge cases ---

    def test_empty_string_assumes_relevant(self):
        """Empty response should fallback to relevant (safe default)."""
        assert _parse_relevance("") is True

    def test_whitespace_only_assumes_relevant(self):
        assert _parse_relevance("   ") is True

    def test_ambiguous_response_assumes_relevant(self):
        """Ambiguous responses fallback to relevant to avoid false negatives."""
        assert _parse_relevance("maybe") is True
        assert _parse_relevance("partially relevant") is True

    def test_response_with_leading_whitespace(self):
        assert _parse_relevance("  yes - relevant") is True
        assert _parse_relevance("  no - not relevant") is False

    def test_response_with_newlines(self):
        assert _parse_relevance("yes\nBecause it mentions...") is True
        assert _parse_relevance("no\nUnrelated topic") is False


# ============================================================
# _parse_hallucination_result
# ============================================================


class TestParseHallucinationResult:
    """Tests for hallucination check result parsing.

    Returns True if hallucinated, False if grounded.
    """

    # --- Grounded (not hallucinated → False) ---

    @pytest.mark.parametrize(
        "response",
        [
            "grounded",
            "Grounded",
            "GROUNDED",
            "grounded - all claims supported",
            "supported",
            "yes",
            "верно",
            "подтверждено",
        ],
    )
    def test_grounded_responses(self, response: str):
        assert _parse_hallucination_result(response) is False

    # --- Hallucinated (→ True) ---

    @pytest.mark.parametrize(
        "response",
        [
            "not_grounded",
            "not_grounded: answer mentions 2024 but context only discusses 2023",
            "Not grounded",
            "not grounded - introduces new facts",
            "hallucinated",
            "Hallucinated: the date is wrong",
            "not supported",
            "unsupported",
            "not supported: claims not in context",
        ],
    )
    def test_hallucinated_responses(self, response: str):
        assert _parse_hallucination_result(response) is True

    # --- Edge cases ---

    def test_empty_string_assumes_grounded(self):
        """Empty response should fallback to grounded (safe default)."""
        assert _parse_hallucination_result("") is False

    def test_ambiguous_response_assumes_grounded(self):
        """Ambiguous responses fallback to grounded to avoid false positives."""
        assert _parse_hallucination_result("unclear") is False
        assert _parse_hallucination_result("partially") is False

    def test_not_grounded_with_colon_explanation(self):
        result = _parse_hallucination_result(
            "not_grounded: the answer claims the system was released in 2020, "
            "but the context says 2019"
        )
        assert result is True

    def test_grounded_with_explanation(self):
        result = _parse_hallucination_result(
            "grounded - all factual claims are directly supported by the provided context"
        )
        assert result is False

    def test_response_with_leading_whitespace(self):
        assert _parse_hallucination_result("  grounded") is False
        assert _parse_hallucination_result("  not_grounded: wrong date") is True
