"""Pin constructor validation and credential forwarding without Anthropic calls."""

from unittest.mock import Mock, patch, sentinel

import pytest

from src.pdf_framework.chains.qa import retrieval_qa
from src.pdf_framework.config import AgentSettings, GraphRAGSettings
from src.pdf_framework.graph_store import summarizer
from src.pdf_framework.processing.extractors import entity_extractor

pytestmark = pytest.mark.unit


@pytest.fixture
def agent_settings():
    return AgentSettings(
        model="claude-sonnet-4-5-20250929",
        temperature=0.37,
        max_tokens=731,
        base_url="https://proxy.example.test/anthropic",
    )


@pytest.mark.parametrize(
    ("module", "constructor", "temperature", "max_tokens"),
    [
        (retrieval_qa, retrieval_qa.RetrievalQAChain, 0.37, 731),
        (entity_extractor, entity_extractor.LLMEntityExtractor, 0.0, 4096),
    ],
    ids=["qa", "extractor"],
)
@pytest.mark.parametrize("with_credentials", [True, False], ids=["proxy", "default"])
def test_agent_constructor_validates_exact_configuration(
    module, constructor, temperature, max_tokens, with_credentials, agent_settings
):
    """Prevent dropped proxy credentials and accidental QA/extraction policy unification."""
    settings = agent_settings.model_copy(update={} if with_credentials else {"base_url": ""})
    expected = {
        "model": "claude-sonnet-4-5-20250929",
        "temperature": temperature,
        "max_tokens": max_tokens,
        "api_key": "test-explicit-key" if with_credentials else None,
    }
    if with_credentials:
        expected["base_url"] = "https://proxy.example.test/anthropic"

    with patch.object(
        module.ChatAnthropic, "model_validate", return_value=sentinel.llm
    ) as validate:
        instance = constructor(
            settings=settings, api_key="test-explicit-key" if with_credentials else ""
        )

    validate.assert_called_once_with(expected)
    assert instance._llm is sentinel.llm


@pytest.mark.parametrize("with_credentials", [True, False], ids=["proxy", "default"])
def test_summarizer_validates_exact_configuration(with_credentials):
    """Keep optional credentials absent by default while preserving proxy overrides."""
    expected = {
        "model": "claude-haiku-4-5-20251001",
        "temperature": 0.0,
        "max_tokens": 1024,
    }
    if with_credentials:
        expected.update(
            api_key="test-explicit-key", base_url="https://proxy.example.test/anthropic"
        )

    with patch.object(
        summarizer.ChatAnthropic, "model_validate", return_value=sentinel.llm
    ) as validate:
        instance = summarizer.CommunitySummarizer(
            settings=GraphRAGSettings(summary_cache_enabled=False),
            api_key="test-explicit-key" if with_credentials else "",
            base_url="https://proxy.example.test/anthropic" if with_credentials else "",
        )

    validate.assert_called_once_with(expected)
    assert instance.llm is sentinel.llm


def test_summarizer_injected_llm_bypasses_validation():
    """Dependency injection must not require SDK credentials or replace the supplied LLM."""
    with patch.object(summarizer.ChatAnthropic, "model_validate") as validate:
        instance = summarizer.CommunitySummarizer(
            llm=sentinel.injected_llm,
            settings=GraphRAGSettings(summary_cache_enabled=False),
            api_key="unused-key",
            base_url="https://unused.example.test",
        )

    validate.assert_not_called()
    assert instance.llm is sentinel.injected_llm


def test_qa_validation_failure_enables_free_llm_fallback(agent_settings):
    """An unavailable paid SDK must leave QA constructible for free rotation."""
    validate = Mock(side_effect=ValueError("invalid SDK configuration"))
    with patch.object(retrieval_qa.ChatAnthropic, "model_validate", validate):
        instance = retrieval_qa.RetrievalQAChain(settings=agent_settings)

    validate.assert_called_once()
    assert instance._llm is None


def test_extractor_validation_failure_propagates(agent_settings):
    """Do not silently give extraction QA's fallback when SDK validation fails."""
    error = ValueError("invalid SDK configuration")
    with patch.object(
        entity_extractor.ChatAnthropic, "model_validate", side_effect=error
    ) as validate:
        with pytest.raises(ValueError, match="invalid SDK configuration") as raised:
            entity_extractor.LLMEntityExtractor(settings=agent_settings)

    validate.assert_called_once()
    assert raised.value is error
