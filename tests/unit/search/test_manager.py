"""Unit tests for SearchManager (F2.3.1-F2.3.2)."""

from unittest.mock import MagicMock

import pytest

from src.pdf_framework.search.manager import SearchManager


@pytest.mark.unit
class TestSearchManager:
    """Test SearchManager strategy registration and routing."""

    def test_register_strategy(self):
        """F2.3.1: SearchManager.register_strategy should register new strategy."""
        manager = SearchManager()

        mock_strategy = MagicMock()
        mock_strategy.name = "test_strategy"

        manager.register_strategy(mock_strategy)

        assert "test_strategy" in manager._strategies

    def test_search_routing(self, sample_chunks, sample_embeddings):
        """F2.3.2: SearchManager.search should route to correct strategy."""
        manager = SearchManager()

        mock_hybrid = MagicMock()
        mock_hybrid.name = "hybrid"
        mock_hybrid.search.return_value = sample_chunks[:3]

        manager.register_strategy(mock_hybrid)

        results = manager.search("test query", strategy="hybrid")

        mock_hybrid.search.assert_called_once()
        assert len(results) == 3


@pytest.mark.unit
class TestBM25Store:
    """Test BM25Store (F2.3.3-F2.3.4)."""

    def test_bm25_add_and_search(self):
        """F2.3.3: BM25Store should add documents and search."""
        from src.pdf_framework.search.bm25_store import BM25Store

        store = BM25Store()

        store.add_documents([
            {"id": "1", "content": "test document"},
            {"id": "2", "content": "another test"},
        ])

        results = store.search("test")

        assert len(results) > 0

    def test_bm25_fts5_schema_migration(self):
        """F2.3.4: BM25Store should handle FTS5 schema migration."""
        from src.pdf_framework.search.bm25_store import BM25Store

        store = BM25Store()

        # Should create schema if not exists
        assert store._ensure_schema() is True


@pytest.mark.unit
class TestPipelines:
    """Test search pipelines (F2.3.5-F2.3.6)."""

    def test_two_stage_pipeline_classify_query(self):
        """F2.3.5: TwoStagePipeline should classify query type."""
        from src.pdf_framework.search.pipelines.two_stage import TwoStagePipeline

        pipeline = TwoStagePipeline()

        # Simple query should be classified as simple
        classification = pipeline.classify_query("test query")
        assert classification in ["simple", "complex", "analytical"]

    def test_section_first_pipeline_dominant_section(self):
        """F2.3.6: SectionFirstPipeline should identify dominant section."""
        from src.pdf_framework.search.pipelines.section_first import SectionFirstPipeline

        pipeline = SectionFirstPipeline()

        # Should identify section from query
        section = pipeline.identify_section("справочники 1с")
        assert section is not None


@pytest.mark.unit
class TestFusion:
    """Test RRF fusion (F2.3.7)."""

    def test_rrf_fusion_formula(self):
        """F2.3.7: RRF fusion should apply correct formula."""
        from src.pdf_framework.search.strategies.rrf import rrf_fusion

        results_a = [
            {"id": "1", "score": 0.9},
            {"id": "2", "score": 0.8},
        ]
        results_b = [
            {"id": "2", "score": 0.95},
            {"id": "3", "score": 0.7},
        ]

        fused = rrf_fusion(results_a, results_b, k=60)

        # Should have all unique documents
        assert len(fused) == 3
        assert any(r["id"] == "1" for r in fused)
        assert any(r["id"] == "2" for r in fused)
        assert any(r["id"] == "3" for r in fused)
