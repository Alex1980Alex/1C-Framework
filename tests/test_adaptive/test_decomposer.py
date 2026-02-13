"""Tests for Sub-Question Decomposer (Phase 8.3).

Tests parsing logic and should_decompose without LLM calls.
"""

import pytest

from src.pdf_framework.search.routing.classifier import QueryClassification
from src.pdf_framework.search.routing.decomposer import SubQuestionDecomposer


def _make_decomposer(max_sub_questions: int = 4):
    """Create decomposer with mocked LLM (no real API calls)."""
    decomposer = object.__new__(SubQuestionDecomposer)
    decomposer._llm = None
    decomposer._parser = None
    decomposer._max_sub_questions = max_sub_questions
    return decomposer


class TestParseSubQuestions:
    """Test _parse_sub_questions method."""

    def test_parses_numbered_list(self):
        d = _make_decomposer()
        text = "1. What are the features of PostgreSQL?\n2. What are the features of MySQL?\n3. How do they differ?"
        result = d._parse_sub_questions(text)
        assert len(result) == 3
        assert "What are the features of PostgreSQL?" in result[0]
        assert "What are the features of MySQL?" in result[1]
        assert "How do they differ?" in result[2]

    def test_parses_dot_numbered(self):
        d = _make_decomposer()
        text = "1. First question\n2. Second question"
        result = d._parse_sub_questions(text)
        assert len(result) == 2

    def test_parses_dash_prefixed(self):
        d = _make_decomposer()
        text = "- First question\n- Second question\n- Third question"
        result = d._parse_sub_questions(text)
        assert len(result) == 3

    def test_parses_bullet_prefixed(self):
        d = _make_decomposer()
        text = "• First question\n• Second question"
        result = d._parse_sub_questions(text)
        assert len(result) == 2

    def test_skips_empty_lines(self):
        d = _make_decomposer()
        text = "1. First\n\n2. Second\n\n3. Third"
        result = d._parse_sub_questions(text)
        assert len(result) == 3

    def test_respects_max_sub_questions(self):
        d = _make_decomposer(max_sub_questions=2)
        text = "1. First\n2. Second\n3. Third\n4. Fourth"
        result = d._parse_sub_questions(text)
        assert len(result) == 2

    def test_empty_text_returns_empty(self):
        d = _make_decomposer()
        result = d._parse_sub_questions("")
        assert result == []

    def test_whitespace_only_returns_empty(self):
        d = _make_decomposer()
        result = d._parse_sub_questions("   \n  \n  ")
        assert result == []

    def test_removes_parenthesis_numbering(self):
        d = _make_decomposer()
        text = "1) First question\n2) Second question"
        result = d._parse_sub_questions(text)
        assert len(result) == 2
        assert "First question" in result[0]


class TestShouldDecompose:
    """Test should_decompose method."""

    def test_complex_high_confidence_decomposes(self):
        d = _make_decomposer()
        classification = QueryClassification(
            complexity="complex", query_type="comparative", confidence=0.85
        )
        assert d.should_decompose(classification) is True

    def test_complex_low_confidence_does_not_decompose(self):
        d = _make_decomposer()
        classification = QueryClassification(
            complexity="complex", query_type="comparative", confidence=0.5
        )
        assert d.should_decompose(classification) is False

    def test_complex_boundary_confidence_does_not_decompose(self):
        d = _make_decomposer()
        classification = QueryClassification(
            complexity="complex", query_type="comparative", confidence=0.7
        )
        # 0.7 is not > 0.7, so should not decompose
        assert d.should_decompose(classification) is False

    def test_simple_does_not_decompose(self):
        d = _make_decomposer()
        classification = QueryClassification(
            complexity="simple", query_type="factual", confidence=0.95
        )
        assert d.should_decompose(classification) is False

    def test_moderate_does_not_decompose(self):
        d = _make_decomposer()
        classification = QueryClassification(
            complexity="moderate", query_type="analytical", confidence=0.9
        )
        assert d.should_decompose(classification) is False

    def test_thematic_does_not_decompose(self):
        d = _make_decomposer()
        classification = QueryClassification(
            complexity="thematic", query_type="thematic", confidence=0.9
        )
        assert d.should_decompose(classification) is False


class TestSynthesizeFallback:
    """Test synthesize fallback behaviors (no LLM)."""

    @pytest.mark.asyncio
    async def test_empty_sub_answers(self):
        d = _make_decomposer()
        result = await d.synthesize("test query", [])
        assert "Unable to answer" in result

    @pytest.mark.asyncio
    async def test_single_sub_answer_returned_as_is(self):
        d = _make_decomposer()
        result = await d.synthesize("test query", ["This is the answer."])
        assert result == "This is the answer."


class TestDecomposeFallback:
    """Test decompose error handling."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        d = _make_decomposer()
        result = await d.decompose("")
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_query_returns_empty(self):
        d = _make_decomposer()
        result = await d.decompose("   ")
        assert result == []
