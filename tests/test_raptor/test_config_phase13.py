"""Tests for Phase 13 configuration (RAPTORSettings, SummaryIndexSettings)."""

import pytest

from src.pdf_framework.config import (
    RAPTORSettings,
    SummaryIndexSettings,
    Settings,
)


class TestRAPTORSettings:
    def test_defaults(self):
        s = RAPTORSettings()
        assert s.enabled is False
        assert s.max_levels == 4
        assert s.search_mode == "collapsed"
        assert s.cluster_method == "kmeans"
        assert s.summarization_model == "claude-sonnet-4-5-20250929"

    def test_custom(self):
        s = RAPTORSettings(
            enabled=True,
            max_levels=2,
            search_mode="tree_traversal",
            cluster_method="umap_gmm",
        )
        assert s.enabled is True
        assert s.max_levels == 2
        assert s.search_mode == "tree_traversal"


class TestSummaryIndexSettings:
    def test_defaults(self):
        s = SummaryIndexSettings()
        assert s.enabled is False
        assert s.collection_name == "document_summaries"
        assert s.summarization_model == "claude-sonnet-4-5-20250929"
        assert s.min_chunks_for_summary == 10

    def test_custom(self):
        s = SummaryIndexSettings(
            enabled=True,
            collection_name="my_summaries",
            min_chunks_for_summary=5,
        )
        assert s.enabled is True
        assert s.collection_name == "my_summaries"


class TestSettingsIntegration:
    def test_raptor_in_settings(self):
        s = Settings()
        assert hasattr(s, "raptor")
        assert isinstance(s.raptor, RAPTORSettings)

    def test_summary_index_in_settings(self):
        s = Settings()
        assert hasattr(s, "summary_index")
        assert isinstance(s.summary_index, SummaryIndexSettings)
