"""Tests for GraphRAG Global Search (Phase 6.4).

Tests utility functions without LLM calls.
"""

import time

import pytest

from src.pdf_framework.config import GraphRAGSettings
from src.pdf_framework.schemas.documents import DocumentChunk, SearchResponse, SearchResult


class TestExtractCommunityId:
    """Test _extract_community_id static parsing."""

    def _make_strategy(self):
        """Create strategy with mocked dependencies (no actual LLM calls)."""
        from unittest.mock import MagicMock

        from src.pdf_framework.search.strategies.graphrag_global import GraphRAGGlobalStrategy

        strategy = object.__new__(GraphRAGGlobalStrategy)
        strategy.settings = GraphRAGSettings()
        strategy._embedding_engine = MagicMock()
        strategy._vector_store = MagicMock()
        strategy._graph_store = MagicMock()
        strategy._map_llm = MagicMock()
        strategy._reduce_llm = MagicMock()
        strategy._parser = MagicMock()
        return strategy

    def test_extract_standard_format(self):
        s = self._make_strategy()
        result = s._extract_community_id("[Community 3 (level 0)] Summary text here...")
        assert result == "3"

    def test_extract_double_digit(self):
        s = self._make_strategy()
        result = s._extract_community_id("[Community 42 (level 1)] Some summary")
        assert result == "42"

    def test_extract_no_match(self):
        s = self._make_strategy()
        result = s._extract_community_id("No community marker here")
        assert result == "unknown"

    def test_extract_empty_string(self):
        s = self._make_strategy()
        result = s._extract_community_id("")
        assert result == "unknown"


class TestEmptyResponse:
    def _make_strategy(self):
        from unittest.mock import MagicMock

        from src.pdf_framework.search.strategies.graphrag_global import GraphRAGGlobalStrategy

        strategy = object.__new__(GraphRAGGlobalStrategy)
        strategy.settings = GraphRAGSettings()
        strategy._embedding_engine = MagicMock()
        strategy._vector_store = MagicMock()
        strategy._graph_store = MagicMock()
        strategy._map_llm = MagicMock()
        strategy._reduce_llm = MagicMock()
        strategy._parser = MagicMock()
        return strategy

    def test_empty_response_structure(self):
        s = self._make_strategy()
        start = time.perf_counter()
        resp = s._empty_response("test query", start)

        assert isinstance(resp, SearchResponse)
        assert resp.query == "test query"
        assert resp.results == []
        assert resp.total_found == 0
        assert resp.search_type == "graphrag_global"
        assert resp.elapsed_ms >= 0


class TestPrompts:
    def _make_strategy(self):
        from unittest.mock import MagicMock

        from src.pdf_framework.search.strategies.graphrag_global import GraphRAGGlobalStrategy

        strategy = object.__new__(GraphRAGGlobalStrategy)
        strategy.settings = GraphRAGSettings()
        strategy._embedding_engine = MagicMock()
        strategy._vector_store = MagicMock()
        strategy._graph_store = MagicMock()
        strategy._map_llm = MagicMock()
        strategy._reduce_llm = MagicMock()
        strategy._parser = MagicMock()
        return strategy

    def test_map_prompt_contains_instructions(self):
        s = self._make_strategy()
        prompt = s._get_map_prompt("What is 1C?")
        assert "community summary" in prompt.lower()
        assert "NOT_RELEVANT" in prompt

    def test_reduce_prompt_contains_query(self):
        s = self._make_strategy()
        prompt = s._get_reduce_prompt("What is 1C?", ["Answer 1", "Answer 2"])
        assert "What is 1C?" in prompt
        assert "Answer 1" in prompt
        assert "Answer 2" in prompt
        assert "Partial Answer 1" in prompt
        assert "Partial Answer 2" in prompt

    def test_reduce_prompt_with_empty_answers(self):
        s = self._make_strategy()
        prompt = s._get_reduce_prompt("query", [])
        assert "query" in prompt
