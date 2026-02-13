"""Tests for Phase 14 configuration (UISettings, OpenAICompat, Suggestions)."""

import pytest

from src.pdf_framework.config import (
    OpenAICompatSettings,
    Settings,
    SuggestionSettings,
    UISettings,
)


# ---------------------------------------------------------------------------
# UISettings
# ---------------------------------------------------------------------------

class TestUISettings:
    def test_defaults(self):
        s = UISettings()
        assert s.enabled is True
        assert s.host == "0.0.0.0"
        assert s.port == 7860
        assert s.share is False
        assert s.theme == "default"
        assert s.api_backend_url == "http://localhost:8000"

    def test_custom(self):
        s = UISettings(
            enabled=False,
            host="127.0.0.1",
            port=8080,
            share=True,
            theme="dark",
        )
        assert s.enabled is False
        assert s.host == "127.0.0.1"
        assert s.port == 8080
        assert s.share is True
        assert s.theme == "dark"


# ---------------------------------------------------------------------------
# OpenAICompatSettings
# ---------------------------------------------------------------------------

class TestOpenAICompatSettings:
    def test_defaults(self):
        s = OpenAICompatSettings()
        assert s.enabled is True
        assert s.model_name == "pdf-rag"
        assert "PDF RAG" in s.model_description

    def test_custom(self):
        s = OpenAICompatSettings(
            enabled=False,
            model_name="custom-model",
            model_description="Custom description",
        )
        assert s.enabled is False
        assert s.model_name == "custom-model"
        assert s.model_description == "Custom description"


# ---------------------------------------------------------------------------
# SuggestionSettings
# ---------------------------------------------------------------------------

class TestSuggestionSettings:
    def test_defaults(self):
        s = SuggestionSettings()
        assert s.enabled is False
        assert s.method == "entity"
        assert s.cache_ttl == 3600
        assert s.max_suggestions == 5
        assert s.llm_model == "claude-sonnet-4-5-20250929"

    def test_custom(self):
        s = SuggestionSettings(
            enabled=True,
            method="llm",
            cache_ttl=60,
            max_suggestions=10,
        )
        assert s.enabled is True
        assert s.method == "llm"
        assert s.cache_ttl == 60
        assert s.max_suggestions == 10

    def test_method_validation(self):
        for method in ("entity", "frequency", "llm", "related"):
            s = SuggestionSettings(method=method)
            assert s.method == method


# ---------------------------------------------------------------------------
# Root Settings Integration
# ---------------------------------------------------------------------------

class TestSettingsPhase14Integration:
    def test_ui_in_settings(self):
        s = Settings()
        assert isinstance(s.ui, UISettings)

    def test_openai_compat_in_settings(self):
        s = Settings()
        assert isinstance(s.openai_compat, OpenAICompatSettings)

    def test_suggestions_in_settings(self):
        s = Settings()
        assert isinstance(s.suggestions, SuggestionSettings)

    def test_all_phase14_defaults(self):
        s = Settings()
        assert s.ui.port == 7860
        assert s.openai_compat.model_name == "pdf-rag"
        assert s.suggestions.enabled is False
