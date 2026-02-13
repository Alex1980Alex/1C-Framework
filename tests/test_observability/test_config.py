"""Tests for Phase 11 configuration settings.

Tests ObservabilitySettings and CacheSettings in config.py.
"""

import pytest

from src.pdf_framework.config import (
    CacheSettings,
    ObservabilitySettings,
    Settings,
)


class TestObservabilitySettings:
    """Test ObservabilitySettings defaults."""

    def test_default_tracer(self):
        settings = ObservabilitySettings()
        assert settings.tracer == "jsonfile"

    def test_default_langsmith_disabled(self):
        settings = ObservabilitySettings()
        assert settings.langsmith_enabled is False

    def test_default_trace_dir(self):
        settings = ObservabilitySettings()
        assert "traces" in str(settings.trace_dir)

    def test_tracer_literal_values(self):
        for value in ("jsonfile", "langsmith", "none"):
            settings = ObservabilitySettings(tracer=value)
            assert settings.tracer == value


class TestCacheSettings:
    """Test CacheSettings defaults."""

    def test_embedding_enabled_by_default(self):
        settings = CacheSettings()
        assert settings.embedding_enabled is True

    def test_embedding_ttl_days(self):
        settings = CacheSettings()
        assert settings.embedding_ttl_days == 30

    def test_llm_enabled_by_default(self):
        settings = CacheSettings()
        assert settings.llm_enabled is True

    def test_llm_ttl_seconds(self):
        settings = CacheSettings()
        assert settings.llm_ttl_seconds == 3600

    def test_document_enabled_by_default(self):
        settings = CacheSettings()
        assert settings.document_enabled is True

    def test_prompt_caching_enabled_by_default(self):
        settings = CacheSettings()
        assert settings.prompt_caching_enabled is True

    def test_custom_ttl(self):
        settings = CacheSettings(embedding_ttl_days=7, llm_ttl_seconds=120)
        assert settings.embedding_ttl_days == 7
        assert settings.llm_ttl_seconds == 120


class TestSettingsIntegration:
    """Test that Settings includes Phase 11 settings."""

    def test_has_observability(self):
        settings = Settings()
        assert hasattr(settings, "observability")
        assert isinstance(settings.observability, ObservabilitySettings)

    def test_has_cache(self):
        settings = Settings()
        assert hasattr(settings, "cache")
        assert isinstance(settings.cache, CacheSettings)

    def test_observability_defaults(self):
        settings = Settings()
        assert settings.observability.tracer == "jsonfile"

    def test_cache_defaults(self):
        settings = Settings()
        assert settings.cache.embedding_enabled is True
        assert settings.cache.llm_enabled is True
