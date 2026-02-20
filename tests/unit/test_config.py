"""Unit tests for configuration settings (F2.2).

Tests:
- F2.2.1: Settings loading from .env
- F2.2.2: EmbeddingSettings validation
- F2.2.3: VectorStoreSettings (qdrant vs chroma)
- F2.2.4: SearchSettings defaults
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.pdf_framework.config import (
    EmbeddingSettings,
    SearchSettings,
    Settings,
    VectorStoreSettings,
    get_settings,
)


# =============================================================================
# F2.2.1: Settings loading from .env
# =============================================================================


class TestSettingsLoading:
    """Test Settings loading from environment variables."""

    def test_settings_load_default_values(self, mock_settings):
        """Settings should load with default values."""
        settings = Settings()

        assert settings.log_level == "INFO"
        assert settings.log_format == "text"
        assert isinstance(settings.data_dir, Path)
        assert isinstance(settings.temp_dir, Path)

    def test_settings_load_from_env(self):
        """Settings should load from environment variables."""
        original_env = os.environ.copy()

        try:
            os.environ["LOG_LEVEL"] = "DEBUG"
            os.environ["EMBEDDING__MODEL"] = "test-model"
            os.environ["VECTOR_STORE__PROVIDER"] = "chroma"

            settings = Settings()

            assert settings.log_level == "DEBUG"
            assert settings.embedding.model == "test-model"
            assert settings.vector_store.provider == "chroma"
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_settings_singleton(self):
        """get_settings() should return cached singleton."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2


# =============================================================================
# F2.2.2: EmbeddingSettings validation
# =============================================================================


class TestEmbeddingSettings:
    """Test EmbeddingSettings validation."""

    def test_default_embedding_settings(self):
        """EmbeddingSettings should have sensible defaults."""
        settings = EmbeddingSettings()

        assert settings.model == "intfloat/multilingual-e5-large"
        assert settings.dimensions == 1024
        assert settings.device == "auto"
        assert settings.batch_size == 64
        assert settings.provider == "local"
        assert settings.backend == "torch"

    def test_custom_embedding_settings(self):
        """EmbeddingSettings should accept custom values."""
        settings = EmbeddingSettings(
            model="BAAI/bge-m3",
            dimensions=1536,
            device="cuda",
            batch_size=32,
            provider="voyage",
        )

        assert settings.model == "BAAI/bge-m3"
        assert settings.dimensions == 1536
        assert settings.device == "cuda"
        assert settings.batch_size == 32
        assert settings.provider == "voyage"

    def test_embedding_backend_validation(self):
        """Embedding backend must be valid option (torch, onnx, openvino)."""
        settings = EmbeddingSettings(backend="onnx")
        assert settings.backend == "onnx"

        settings = EmbeddingSettings(backend="openvino")
        assert settings.backend == "openvino"

    def test_embedding_cache_settings(self):
        """Embedding cache should be configurable."""
        settings = EmbeddingSettings(
            cache_enabled=False,
        )

        assert settings.cache_enabled is False


# =============================================================================
# F2.2.3: VectorStoreSettings (qdrant vs chroma)
# =============================================================================


class TestVectorStoreSettings:
    """Test VectorStoreSettings for different providers."""

    def test_qdrant_settings(self):
        """Qdrant settings should be properly configured."""
        settings = VectorStoreSettings(
            provider="qdrant",
            qdrant_url="http://localhost:6333",
        )

        assert settings.provider == "qdrant"
        assert settings.qdrant_url == "http://localhost:6333"
        assert settings.collection_name == "pdf_documents"

    def test_chroma_settings(self):
        """Chroma settings should be properly configured."""
        from pathlib import Path

        settings = VectorStoreSettings(
            provider="chroma",
            persist_dir=Path("/data/chroma"),
        )

        assert settings.provider == "chroma"
        assert "/data" in str(settings.persist_dir)

    def test_pgvector_settings(self):
        """PgVector settings should be properly configured."""
        settings = VectorStoreSettings(
            provider="pgvector",
            pgvector_dsn="postgresql://user:pass@localhost/db",
        )

        assert settings.provider == "pgvector"
        assert "postgresql" in settings.pgvector_dsn

    def test_qdrant_bm25_settings(self):
        """Qdrant BM25 settings should be configurable."""
        settings = VectorStoreSettings(
            provider="qdrant",
            qdrant_bm25_enabled=True,
            qdrant_bm25_language="russian",
        )

        assert settings.qdrant_bm25_enabled is True
        assert settings.qdrant_bm25_language == "russian"

    def test_distance_metric(self):
        """Distance metric should be configurable."""
        settings = VectorStoreSettings(
            distance_metric="euclidean",
        )

        assert settings.distance_metric == "euclidean"


# =============================================================================
# F2.2.4: SearchSettings defaults
# =============================================================================


class TestSearchSettings:
    """Test SearchSettings defaults and validation."""

    def test_default_search_settings(self):
        """SearchSettings should have sensible defaults."""
        settings = SearchSettings()

        assert settings.hybrid_vector_weight == 0.5
        assert settings.hybrid_graph_weight == 0.2
        assert settings.hybrid_rrf_k == 60
        assert settings.bm25_enabled is True
        assert settings.bm25_weight == 0.3

    def test_custom_search_settings(self):
        """SearchSettings should accept custom values."""
        settings = SearchSettings(
            hybrid_vector_weight=0.7,
            hybrid_graph_weight=0.1,
            bm25_weight=0.2,
        )

        assert settings.hybrid_vector_weight == 0.7
        assert settings.hybrid_graph_weight == 0.1
        assert settings.bm25_weight == 0.2

    def test_rrf_k_parameter(self):
        """RRF k parameter should be configurable."""
        settings = SearchSettings(hybrid_rrf_k=100)

        assert settings.hybrid_rrf_k == 100

    def test_bm25_settings(self):
        """BM25 settings should be configurable."""
        settings = SearchSettings(
            bm25_enabled=True,
            bm25_backend="fts5",
            bm25_two_pass=True,
        )

        assert settings.bm25_enabled is True
        assert settings.bm25_backend == "fts5"
        assert settings.bm25_two_pass is True

    def test_mmr_settings(self):
        """MMR settings should be configurable."""
        settings = SearchSettings(
            mmr_diversity_lambda=0.7,
            mmr_fetch_k=30,
        )

        assert settings.mmr_diversity_lambda == 0.7
        assert settings.mmr_fetch_k == 30


# =============================================================================
# F2.2.5: Settings integration
# =============================================================================


class TestSettingsIntegration:
    """Test Settings integration across modules."""

    def test_full_settings_tree(self):
        """Settings should properly initialize all sub-settings."""
        settings = Settings()

        # Check all sub-settings are initialized
        assert settings.embedding is not None
        assert settings.vector_store is not None
        assert settings.graph_store is not None
        assert settings.search is not None
        assert settings.agent is not None
        assert settings.cache is not None

    def test_settings_env_nested_delimiter(self):
        """Nested delimiter __ should work for env vars."""
        original_env = os.environ.copy()

        try:
            os.environ["EMBEDDING__MODEL"] = "test-model"
            os.environ["VECTOR_STORE__PROVIDER"] = "chroma"
            os.environ["SEARCH__BM25_WEIGHT"] = "0.5"

            settings = Settings()

            assert settings.embedding.model == "test-model"
            assert settings.vector_store.provider == "chroma"
            assert float(settings.search.bm25_weight) == 0.5
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_settings_extra_ignore(self):
        """Unknown env vars should be ignored, not raise error."""
        original_env = os.environ.copy()

        try:
            os.environ["UNKNOWN_VAR"] = "value"
            os.environ["ANOTHER__UNKNOWN"] = "value"

            # Should not raise ValidationError
            settings = Settings()
            assert settings is not None
        finally:
            os.environ.clear()
            os.environ.update(original_env)


@pytest.mark.unit
class TestSettingsUnit:
    """Marked unit tests for Settings."""

    def test_unit_settings_creation(self):
        """Unit test: Settings can be created."""
        settings = Settings()
        assert settings is not None
