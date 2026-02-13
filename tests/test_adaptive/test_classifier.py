"""Tests for Query Complexity Classifier (Phase 8.1).

Tests parsing logic and caching without LLM calls.
"""

import pytest

from src.pdf_framework.search.routing.classifier import QueryClassifier, QueryClassification


def _make_classifier():
    """Create classifier with mocked LLM (no real API calls)."""
    classifier = object.__new__(QueryClassifier)
    classifier._llm = None
    classifier._parser = None
    classifier._cache_enabled = True
    classifier._cache = {}
    return classifier


class TestParseClassification:
    """Test _parse_classification method."""

    def test_parses_valid_three_part_response(self):
        c = _make_classifier()
        result = c._parse_classification("simple factual 0.95")
        assert result.complexity == "simple"
        assert result.query_type == "factual"
        assert result.confidence == 0.95

    def test_parses_moderate_analytical(self):
        c = _make_classifier()
        result = c._parse_classification("moderate analytical 0.88")
        assert result.complexity == "moderate"
        assert result.query_type == "analytical"
        assert result.confidence == 0.88

    def test_parses_complex_comparative(self):
        c = _make_classifier()
        result = c._parse_classification("complex comparative 0.82")
        assert result.complexity == "complex"
        assert result.query_type == "comparative"
        assert result.confidence == 0.82

    def test_parses_thematic(self):
        c = _make_classifier()
        result = c._parse_classification("thematic thematic 0.90")
        assert result.complexity == "thematic"
        assert result.query_type == "thematic"
        assert result.confidence == 0.90

    def test_unknown_complexity_falls_back_to_moderate(self):
        c = _make_classifier()
        result = c._parse_classification("weird analytical 0.5")
        assert result.complexity == "moderate"

    def test_unknown_query_type_falls_back_to_analytical(self):
        c = _make_classifier()
        result = c._parse_classification("simple weird 0.5")
        assert result.query_type == "analytical"

    def test_missing_confidence_defaults_to_05(self):
        c = _make_classifier()
        result = c._parse_classification("simple factual")
        assert result.complexity == "simple"
        assert result.query_type == "factual"
        assert result.confidence == 0.5

    def test_single_word_response_falls_back(self):
        c = _make_classifier()
        result = c._parse_classification("simple")
        assert result.complexity == "moderate"
        assert result.query_type == "unknown"
        assert result.confidence == 0.0

    def test_empty_response_falls_back(self):
        c = _make_classifier()
        result = c._parse_classification("")
        assert result.complexity == "moderate"
        assert result.confidence == 0.0

    def test_confidence_clamped_to_max_1(self):
        c = _make_classifier()
        result = c._parse_classification("simple factual 1.5")
        assert result.confidence == 1.0

    def test_confidence_clamped_to_min_0(self):
        c = _make_classifier()
        result = c._parse_classification("simple factual -0.3")
        assert result.confidence == 0.0

    def test_invalid_confidence_falls_back(self):
        c = _make_classifier()
        result = c._parse_classification("simple factual abc")
        assert result.confidence == 0.5

    def test_extra_whitespace_handled(self):
        c = _make_classifier()
        result = c._parse_classification("  complex  comparative  0.77  ")
        assert result.complexity == "complex"
        assert result.query_type == "comparative"
        assert result.confidence == 0.77


class TestClassifierCache:
    """Test caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_object(self):
        c = _make_classifier()
        cached = QueryClassification(
            complexity="simple", query_type="factual", confidence=0.9
        )
        c._cache["test query"] = cached

        result = await c.classify("test query")
        assert result is cached

    @pytest.mark.asyncio
    async def test_empty_query_returns_moderate(self):
        c = _make_classifier()
        result = await c.classify("")
        assert result.complexity == "moderate"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_query_returns_moderate(self):
        c = _make_classifier()
        result = await c.classify("   ")
        assert result.complexity == "moderate"
        assert result.confidence == 0.0

    def test_clear_cache(self):
        c = _make_classifier()
        c._cache["q1"] = QueryClassification(
            complexity="simple", query_type="factual", confidence=0.9
        )
        c.clear_cache()
        assert len(c._cache) == 0

    def test_get_cached_classification(self):
        c = _make_classifier()
        cached = QueryClassification(
            complexity="complex", query_type="comparative", confidence=0.8
        )
        c._cache["compare A and B"] = cached
        result = c.get_cached_classification("compare A and B")
        assert result is cached

    def test_get_cached_classification_miss(self):
        c = _make_classifier()
        result = c.get_cached_classification("nonexistent")
        assert result is None
