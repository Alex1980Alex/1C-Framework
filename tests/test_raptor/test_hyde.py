"""Tests for HyDE Generator (Phase 13.3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.search.hyde import (
    HyDEConfig,
    HyDEGenerator,
    QueryExpander,
    get_hyde_generator,
)

# ChatAnthropic is imported lazily inside methods, patch at source
PATCH_CHAT = "langchain_anthropic.ChatAnthropic"


# ---------------------------------------------------------------------------
# HyDEConfig
# ---------------------------------------------------------------------------

class TestHyDEConfig:
    def test_defaults(self):
        config = HyDEConfig()
        assert config.model == "claude-haiku-4-5-20251001"
        assert config.temperature == 0.3
        assert config.max_tokens == 512
        assert "Question: {query}" in config.prompt_template

    def test_custom(self):
        config = HyDEConfig(model="custom-model", temperature=0.7)
        assert config.model == "custom-model"
        assert config.temperature == 0.7


# ---------------------------------------------------------------------------
# HyDEGenerator
# ---------------------------------------------------------------------------

class TestHyDEGenerator:
    def test_init_defaults(self):
        gen = HyDEGenerator()
        assert gen._api_key == ""
        assert isinstance(gen._config, HyDEConfig)

    def test_init_custom(self):
        config = HyDEConfig(model="test-model")
        gen = HyDEGenerator(api_key="key123", config=config)
        assert gen._api_key == "key123"
        assert gen._config.model == "test-model"

    @pytest.mark.asyncio
    async def test_generate_hypothetical_success(self):
        gen = HyDEGenerator(api_key="test-key")

        mock_response = MagicMock()
        mock_response.content = "This is a hypothetical answer about AI."

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            result = await gen.generate_hypothetical("What is AI?")

        assert result == "This is a hypothetical answer about AI."

    @pytest.mark.asyncio
    async def test_generate_hypothetical_list_content(self):
        """Handle LangChain returning list[ContentBlock]."""
        gen = HyDEGenerator(api_key="test-key")

        mock_block = MagicMock()
        mock_block.text = "Hypothetical block text"

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            result = await gen.generate_hypothetical("query")

        assert result == "Hypothetical block text"

    @pytest.mark.asyncio
    async def test_generate_hypothetical_error_returns_empty(self):
        gen = HyDEGenerator(api_key="")

        with patch(PATCH_CHAT) as mock_cls:
            mock_cls.side_effect = Exception("API error")

            result = await gen.generate_hypothetical("test query")

        assert result == ""

    @pytest.mark.asyncio
    async def test_embed_hypothetical_success(self):
        gen = HyDEGenerator(api_key="test-key")

        mock_response = MagicMock()
        mock_response.content = "hypothetical text"

        mock_engine = AsyncMock()
        mock_engine.embed_text = AsyncMock(return_value=[0.1] * 384)

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            result = await gen.embed_hypothetical("query", mock_engine)

        assert len(result) == 384
        mock_engine.embed_text.assert_awaited_once_with("hypothetical text")

    @pytest.mark.asyncio
    async def test_embed_hypothetical_fallback_on_error(self):
        """When hypothetical generation fails, embed the original query."""
        gen = HyDEGenerator(api_key="")

        mock_engine = AsyncMock()
        mock_engine.embed_text = AsyncMock(return_value=[0.5] * 384)

        with patch(PATCH_CHAT) as mock_cls:
            mock_cls.side_effect = Exception("fail")

            result = await gen.embed_hypothetical("original query", mock_engine)

        assert len(result) == 384
        mock_engine.embed_text.assert_awaited_once_with("original query")

    @pytest.mark.asyncio
    async def test_expand_query_success(self):
        gen = HyDEGenerator(api_key="test-key")

        mock_response = MagicMock()
        mock_response.content = "Expanded hypothetical text"

        mock_engine = AsyncMock()
        mock_engine.embed_text = AsyncMock(return_value=[0.2] * 384)

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            text, embedding = await gen.expand_query("query", mock_engine)

        assert text == "Expanded hypothetical text"
        assert len(embedding) == 384

    @pytest.mark.asyncio
    async def test_expand_query_with_cache_hit(self):
        gen = HyDEGenerator(api_key="test-key")

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value="cached hypothetical")

        mock_engine = AsyncMock()
        mock_engine.embed_text = AsyncMock(return_value=[0.3] * 384)

        text, embedding = await gen.expand_query(
            "query", mock_engine, llm_cache=mock_cache,
        )

        assert text == "cached hypothetical"
        mock_cache.get.assert_awaited_once_with("hyde:query")

    @pytest.mark.asyncio
    async def test_expand_query_with_cache_miss(self):
        gen = HyDEGenerator(api_key="test-key")

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        mock_response = MagicMock()
        mock_response.content = "Generated hypothetical"

        mock_engine = AsyncMock()
        mock_engine.embed_text = AsyncMock(return_value=[0.4] * 384)

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            text, embedding = await gen.expand_query(
                "query", mock_engine, llm_cache=mock_cache,
            )

        assert text == "Generated hypothetical"
        mock_cache.set.assert_awaited_once_with("hyde:query", "Generated hypothetical")

    @pytest.mark.asyncio
    async def test_expand_query_fallback_on_error(self):
        gen = HyDEGenerator(api_key="")

        mock_engine = AsyncMock()
        mock_engine.embed_text = AsyncMock(return_value=[0.5] * 384)

        with patch(PATCH_CHAT) as mock_cls:
            mock_cls.side_effect = Exception("fail")

            text, embedding = await gen.expand_query("original", mock_engine)

        assert text == "original"
        assert len(embedding) == 384


# ---------------------------------------------------------------------------
# QueryExpander
# ---------------------------------------------------------------------------

class TestQueryExpander:
    @pytest.mark.asyncio
    async def test_expand_hyde_method(self):
        expander = QueryExpander()

        mock_response = MagicMock()
        mock_response.content = "Hypothetical passage"

        mock_engine = AsyncMock()
        mock_engine.embed_text = AsyncMock(return_value=[0.1] * 384)

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            text, embedding = await expander.expand(
                "query", method="hyde",
                embedding_engine=mock_engine,
                api_key="key",
            )

        assert text == "Hypothetical passage"
        assert len(embedding) == 384

    @pytest.mark.asyncio
    async def test_expand_hyde_requires_embedding_engine(self):
        expander = QueryExpander()

        with pytest.raises(ValueError, match="embedding_engine required"):
            await expander.expand("query", method="hyde", embedding_engine=None)

    @pytest.mark.asyncio
    async def test_expand_unknown_method(self):
        expander = QueryExpander()

        text, embedding = await expander.expand("query", method="synonyms")

        assert text is None
        assert embedding is None


# ---------------------------------------------------------------------------
# get_hyde_generator singleton
# ---------------------------------------------------------------------------

class TestGetHydeGenerator:
    def test_returns_instance(self):
        import src.pdf_framework.search.hyde as mod
        mod._hyde_generator = None

        gen = get_hyde_generator()
        assert isinstance(gen, HyDEGenerator)
        mod._hyde_generator = None

    def test_returns_same_instance(self):
        import src.pdf_framework.search.hyde as mod
        mod._hyde_generator = None

        g1 = get_hyde_generator()
        g2 = get_hyde_generator()
        assert g1 is g2
        mod._hyde_generator = None

    def test_accepts_kwargs(self):
        import src.pdf_framework.search.hyde as mod
        mod._hyde_generator = None

        gen = get_hyde_generator(api_key="my-key")
        assert gen._api_key == "my-key"
        mod._hyde_generator = None
