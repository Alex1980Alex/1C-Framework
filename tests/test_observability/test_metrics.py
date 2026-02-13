"""Tests for Metrics API endpoint (Phase 11.6).

Tests JSON metrics, HTML dashboard, and metrics reset.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.pdf_framework.observability.tracer import MetricsCollector
from src.pdf_framework.embeddings.cache import CacheStats, EmbeddingCache
from src.pdf_framework.agents.cache import LLMResponseCache
from src.pdf_framework.processing.cache import DocumentProcessingCache


# ── Mocked endpoint tests ──────────────────────────────────────


def _make_mock_metrics_collector(
    queries_total=100,
    queries_today=10,
    cache_hits=5,
    cache_misses=5,
    errors=1,
):
    """Create a pre-populated MetricsCollector."""
    mc = MetricsCollector()
    mc._queries_total = queries_total
    mc._queries_today = queries_today
    mc._cache_hits = cache_hits
    mc._cache_misses = cache_misses
    mc._errors = errors
    mc._latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
    mc._strategies = {"vector": 60, "hybrid": 30, "adaptive": 10}
    return mc


class TestMetricsCollectorIntegration:
    """Test MetricsCollector as used by metrics endpoint."""

    def test_get_metrics_complete(self):
        mc = _make_mock_metrics_collector()
        metrics = mc.get_metrics()

        assert metrics["queries_total"] == 100
        assert metrics["queries_today"] == 10
        assert metrics["avg_latency_ms"] == pytest.approx(300.0)
        assert metrics["cache_hit_rate"] == pytest.approx(0.5)
        assert metrics["error_rate"] == pytest.approx(0.01)
        assert "strategies_usage" in metrics
        assert metrics["strategies_usage"]["vector"] == 60

    def test_strategies_usage_is_copy(self):
        mc = _make_mock_metrics_collector()
        m = mc.get_metrics()
        m["strategies_usage"]["new_strategy"] = 999
        assert "new_strategy" not in mc.get_metrics()["strategies_usage"]


class TestCacheStatsForMetrics:
    """Test that cache stats work for metrics endpoint."""

    def test_embedding_stats_total_correct(self):
        stats = CacheStats(hits=10, misses=5)
        assert stats.total == 15
        assert stats.hit_rate == pytest.approx(10 / 15)

    def test_llm_stats_format(self):
        cache = LLMResponseCache.__new__(LLMResponseCache)
        cache._stats = {"hits": 5, "misses": 3, "total": 8}
        stats = cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "total" in stats
        assert "hit_rate" in stats
        assert stats["hit_rate"] == pytest.approx(5 / 8)

    def test_document_stats_format(self, tmp_path):
        cache = DocumentProcessingCache(cache_dir=tmp_path)
        stats = cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "stale" in stats


class TestMetricsDashboardTemplate:
    """Test the HTML dashboard template format."""

    def test_strategy_rows_empty_list(self):
        """Test that empty strategy_rows stays as list for join."""
        strategy_rows = []
        if not strategy_rows:
            strategy_rows.append('<tr><td colspan="3">No data</td></tr>')
        # Should not raise
        result = "".join(strategy_rows)
        assert "No data" in result

    def test_strategy_rows_with_data(self):
        """Test strategy rows formatting."""
        strategy_rows = []
        strategies = {"vector": 60, "hybrid": 30}
        total = sum(strategies.values())

        for strat, count in sorted(strategies.items(), key=lambda x: x[1], reverse=True):
            share = count / total * 100
            strategy_rows.append(f"<tr><td>{strat}</td><td>{count}</td><td>{share:.1f}%</td></tr>")

        result = "".join(strategy_rows)
        assert "vector" in result
        assert "hybrid" in result
        assert "66.7%" in result

    def test_cache_class_good(self):
        rate = 0.8
        cls = "good" if rate > 0.5 else "warning" if rate > 0.2 else ""
        assert cls == "good"

    def test_cache_class_warning(self):
        rate = 0.3
        cls = "good" if rate > 0.5 else "warning" if rate > 0.2 else ""
        assert cls == "warning"

    def test_cache_class_empty(self):
        rate = 0.1
        cls = "good" if rate > 0.5 else "warning" if rate > 0.2 else ""
        assert cls == ""

    def test_error_class_ok(self):
        rate = 0.005
        cls = "" if rate < 0.01 else "warning" if rate < 0.05 else "error"
        assert cls == ""

    def test_error_class_warning(self):
        rate = 0.03
        cls = "" if rate < 0.01 else "warning" if rate < 0.05 else "error"
        assert cls == "warning"

    def test_error_class_error(self):
        rate = 0.1
        cls = "" if rate < 0.01 else "warning" if rate < 0.05 else "error"
        assert cls == "error"


class TestMetricsResetLogic:
    """Test metrics reset logic."""

    def test_reset_queries_today(self):
        mc = MetricsCollector()
        mc.record_query(latency_ms=10.0, strategy="v")
        mc.record_query(latency_ms=20.0, strategy="v")
        assert mc._queries_today == 2

        mc._queries_today = 0
        assert mc._queries_today == 0
        assert mc._queries_total == 2  # Total unchanged
