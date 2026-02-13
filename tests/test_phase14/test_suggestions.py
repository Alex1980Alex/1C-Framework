"""Tests for Query Suggestions (Phase 14.5)."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.search.suggestions import (
    QuerySuggester,
    SuggestionConfig,
    get_query_suggester,
)

# ChatAnthropic is imported lazily inside methods, patch at source
PATCH_CHAT = "langchain_anthropic.ChatAnthropic"


# ---------------------------------------------------------------------------
# SuggestionConfig
# ---------------------------------------------------------------------------

class TestSuggestionConfig:
    def test_defaults(self):
        config = SuggestionConfig()
        assert config.method == "entity"
        assert config.max_suggestions == 5
        assert config.cache_ttl == 3600
        assert config.llm_model == "claude-haiku-4-5-20251001"

    def test_custom(self):
        config = SuggestionConfig(method="llm", max_suggestions=10, cache_ttl=60)
        assert config.method == "llm"
        assert config.max_suggestions == 10
        assert config.cache_ttl == 60

    def test_method_validation(self):
        for method in ("entity", "frequency", "llm", "related"):
            config = SuggestionConfig(method=method)
            assert config.method == method

    def test_invalid_method(self):
        with pytest.raises(Exception):
            SuggestionConfig(method="invalid")


# ---------------------------------------------------------------------------
# QuerySuggester — Init
# ---------------------------------------------------------------------------

class TestQuerySuggesterInit:
    def test_defaults(self):
        s = QuerySuggester()
        assert s._api_key == ""
        assert isinstance(s._config, SuggestionConfig)
        assert s._cache == {}
        assert s._query_counts == {}

    def test_custom_api_key(self):
        s = QuerySuggester(api_key="test-key-123")
        assert s._api_key == "test-key-123"

    def test_custom_config(self):
        config = SuggestionConfig(method="frequency", max_suggestions=3)
        s = QuerySuggester(config=config)
        assert s._config.method == "frequency"
        assert s._config.max_suggestions == 3


# ---------------------------------------------------------------------------
# QuerySuggester — Entity suggestions
# ---------------------------------------------------------------------------

class TestEntitySuggestions:
    @pytest.mark.asyncio
    async def test_no_graph_store_returns_empty(self):
        s = QuerySuggester()
        result = await s._entity_suggestions(None, 5)
        assert result == []

    @pytest.mark.asyncio
    async def test_with_graph_store(self):
        graph = AsyncMock()
        graph.get_statistics.return_value = {"entity_count": 10}

        s = QuerySuggester()
        result = await s._entity_suggestions(graph, 3)
        assert len(result) == 3
        assert all(isinstance(r, str) for r in result)

    @pytest.mark.asyncio
    async def test_with_graph_store_error(self):
        graph = AsyncMock()
        graph.get_statistics.side_effect = RuntimeError("connection failed")

        s = QuerySuggester()
        result = await s._entity_suggestions(graph, 5)
        assert result == []


# ---------------------------------------------------------------------------
# QuerySuggester — Frequency suggestions
# ---------------------------------------------------------------------------

class TestFrequencySuggestions:
    def test_empty_log(self):
        s = QuerySuggester(config=SuggestionConfig(method="frequency"))
        result = s._frequency_suggestions(5)
        assert result == []

    def test_with_queries(self):
        s = QuerySuggester(config=SuggestionConfig(method="frequency"))
        s.log_query("what is RAG")
        s.log_query("what is RAG")
        s.log_query("explain graphs")
        s.log_query("what is RAG")
        s.log_query("explain graphs")
        s.log_query("hello")

        result = s._frequency_suggestions(2)
        assert len(result) == 2
        assert result[0] == "what is RAG"  # most frequent
        assert result[1] == "explain graphs"

    def test_top_k_limit(self):
        s = QuerySuggester(config=SuggestionConfig(method="frequency"))
        for i in range(10):
            s.log_query(f"query_{i}")

        result = s._frequency_suggestions(3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# QuerySuggester — LLM suggestions
# ---------------------------------------------------------------------------

class TestLLMSuggestions:
    @pytest.mark.asyncio
    async def test_empty_context_returns_empty(self):
        s = QuerySuggester(config=SuggestionConfig(method="llm"))
        result = await s._llm_suggestions("", 5)
        assert result == []

    @pytest.mark.asyncio
    async def test_llm_string_response(self):
        mock_response = MagicMock()
        mock_response.content = "1. What is RAPTOR?\n2. How does HyDE work?\n3. Explain vector search"

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch(PATCH_CHAT, return_value=mock_llm):
            s = QuerySuggester(config=SuggestionConfig(method="llm"), api_key="key")
            result = await s._llm_suggestions("RAG systems", 3)

        assert len(result) == 3
        assert "What is RAPTOR?" in result[0]

    @pytest.mark.asyncio
    async def test_llm_list_response(self):
        """Test handling of LangChain list content blocks."""
        block1 = MagicMock()
        block1.text = "1. Question one about RAG\n2. Question two about graphs\n3. Question three about search"

        mock_response = MagicMock()
        mock_response.content = [block1]

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch(PATCH_CHAT, return_value=mock_llm):
            s = QuerySuggester(config=SuggestionConfig(method="llm"), api_key="key")
            result = await s._llm_suggestions("test query", 3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_llm_passes_api_key(self):
        mock_response = MagicMock()
        mock_response.content = "1. Question one?\n2. Question two?"

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch(PATCH_CHAT, return_value=mock_llm) as mock_cls:
            s = QuerySuggester(config=SuggestionConfig(method="llm"), api_key="my-api-key")
            await s._llm_suggestions("test", 2)

            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["api_key"] == "my-api-key"

    @pytest.mark.asyncio
    async def test_llm_error_returns_empty(self):
        with patch(PATCH_CHAT, side_effect=Exception("API error")):
            s = QuerySuggester(config=SuggestionConfig(method="llm"), api_key="key")
            result = await s._llm_suggestions("test query", 3)

        assert result == []

    @pytest.mark.asyncio
    async def test_llm_filters_short_lines(self):
        mock_response = MagicMock()
        mock_response.content = "1. OK\n2. This is a valid question about RAG?\n3. Yes"

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch(PATCH_CHAT, return_value=mock_llm):
            s = QuerySuggester(config=SuggestionConfig(method="llm"), api_key="key")
            result = await s._llm_suggestions("test", 5)

        # Only lines > 5 chars should be included
        assert len(result) == 1
        assert "valid question" in result[0]


# ---------------------------------------------------------------------------
# QuerySuggester — Related suggestions (delegates to LLM)
# ---------------------------------------------------------------------------

class TestRelatedSuggestions:
    @pytest.mark.asyncio
    async def test_related_delegates_to_llm(self):
        mock_response = MagicMock()
        mock_response.content = "1. Follow-up question one?\n2. Follow-up question two?"

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch(PATCH_CHAT, return_value=mock_llm):
            s = QuerySuggester(config=SuggestionConfig(method="related"), api_key="key")
            result = await s._related_suggestions("context", 2)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# QuerySuggester — suggest() main method
# ---------------------------------------------------------------------------

class TestSuggestMain:
    @pytest.mark.asyncio
    async def test_entity_method(self):
        graph = AsyncMock()
        graph.get_statistics.return_value = {"entity_count": 5}

        s = QuerySuggester(config=SuggestionConfig(method="entity"))
        result = await s.suggest(graph_store=graph, k=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_frequency_method(self):
        s = QuerySuggester(config=SuggestionConfig(method="frequency"))
        s.log_query("test query")
        s.log_query("test query")

        result = await s.suggest(k=5)
        assert result == ["test query"]

    @pytest.mark.asyncio
    async def test_k_capped_by_max_suggestions(self):
        s = QuerySuggester(config=SuggestionConfig(method="frequency", max_suggestions=2))
        for i in range(10):
            s.log_query(f"query_{i}")

        result = await s.suggest(k=10)
        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_unknown_method(self):
        """Unknown method falls through to empty list."""
        s = QuerySuggester()
        # Manually set to bypass validation
        s._config = SuggestionConfig.__new__(SuggestionConfig)
        object.__setattr__(s._config, "method", "unknown")
        object.__setattr__(s._config, "max_suggestions", 5)
        object.__setattr__(s._config, "cache_ttl", 3600)
        object.__setattr__(s._config, "llm_model", "test")
        result = await s.suggest(k=5)
        assert result == []


# ---------------------------------------------------------------------------
# QuerySuggester — Caching
# ---------------------------------------------------------------------------

class TestSuggesterCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        s = QuerySuggester(config=SuggestionConfig(method="frequency"))
        s.log_query("cached query")

        # First call — populates cache
        result1 = await s.suggest(k=5)
        assert len(s._cache) == 1

        # Second call — should hit cache
        result2 = await s.suggest(k=5)
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_cache_expired(self):
        s = QuerySuggester(config=SuggestionConfig(method="frequency", cache_ttl=0))
        s.log_query("query1")

        result1 = await s.suggest(k=5)
        # Cache TTL is 0, so next call should re-generate
        result2 = await s.suggest(k=5)
        assert result1 == result2  # Same data, but regenerated

    def test_clear_cache(self):
        s = QuerySuggester()
        s._cache["key"] = (["test"], time.time())
        assert len(s._cache) == 1
        s.clear_cache()
        assert len(s._cache) == 0


# ---------------------------------------------------------------------------
# QuerySuggester — log_query
# ---------------------------------------------------------------------------

class TestLogQuery:
    def test_log_new_query(self):
        s = QuerySuggester()
        s.log_query("hello")
        assert s._query_counts["hello"] == 1

    def test_log_repeated_query(self):
        s = QuerySuggester()
        s.log_query("test")
        s.log_query("test")
        s.log_query("test")
        assert s._query_counts["test"] == 3


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSuggesterSingleton:
    def test_get_query_suggester(self):
        import src.pdf_framework.search.suggestions as mod
        mod._query_suggester = None

        s1 = get_query_suggester(api_key="key1")
        s2 = get_query_suggester(api_key="key2")
        assert s1 is s2
        assert s1._api_key == "key1"  # First call wins

        mod._query_suggester = None  # Cleanup
