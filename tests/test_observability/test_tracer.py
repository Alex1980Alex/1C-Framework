"""Tests for tracing module (Phase 11.1).

Tests Span, BaseTracer, JsonFileTracer, LangSmithTracer,
NoOpTracer, MetricsCollector, and factory functions.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.pdf_framework.observability.tracer import (
    BaseTracer,
    JsonFileTracer,
    LangSmithTracer,
    MetricsCollector,
    NoOpTracer,
    Span,
    SpanStatus,
    get_metrics_collector,
    get_tracer,
)


# ── Span Tests ──────────────────────────────────────────────────


class TestSpanStatus:
    """Test SpanStatus enum."""

    def test_ok_value(self):
        assert SpanStatus.OK.value == "ok"

    def test_error_value(self):
        assert SpanStatus.ERROR.value == "error"

    def test_string_enum(self):
        assert isinstance(SpanStatus.OK, str)


class TestSpan:
    """Test Span dataclass."""

    def test_default_creation(self):
        span = Span(name="test_span")
        assert span.name == "test_span"
        assert span.start_time > 0
        assert span.end_time is None
        assert span.status == SpanStatus.OK
        assert span.attributes == {}
        assert span.output is None
        assert span.error is None
        assert span.parent is None
        assert span.children == []

    def test_with_attributes(self):
        span = Span(name="search", attributes={"query": "test", "k": 5})
        assert span.attributes["query"] == "test"
        assert span.attributes["k"] == 5

    def test_duration_ms_running(self):
        span = Span(name="test")
        time.sleep(0.01)
        assert span.duration_ms > 0

    def test_duration_ms_ended(self):
        span = Span(name="test")
        time.sleep(0.01)
        span.end()
        duration = span.duration_ms
        time.sleep(0.01)
        # Duration should be fixed after ending
        assert span.duration_ms == duration

    def test_end_sets_end_time(self):
        span = Span(name="test")
        assert span.end_time is None
        span.end()
        assert span.end_time is not None
        assert span.end_time >= span.start_time

    def test_end_with_status(self):
        span = Span(name="test")
        span.end(status=SpanStatus.ERROR, error="something failed")
        assert span.status == SpanStatus.ERROR
        assert span.error == "something failed"

    def test_end_with_output(self):
        span = Span(name="test")
        span.end(output={"result": 42})
        assert span.output == {"result": 42}

    def test_to_dict_has_correct_keys(self):
        span = Span(name="search", attributes={"strategy": "vector"})
        span.end()
        d = span.to_dict()
        assert d["name"] == "search"
        assert "timestamp" in d
        assert "duration_ms" in d
        assert d["status"] == "ok"
        assert d["attributes"] == {"strategy": "vector"}
        assert d["parent"] is None

    def test_to_dict_timestamp_is_iso_format(self):
        span = Span(name="test")
        d = span.to_dict()
        # Should be a valid ISO timestamp, not a perf_counter value
        timestamp = d["timestamp"]
        parsed = datetime.fromisoformat(timestamp)
        # Should be recent (within last minute)
        now = datetime.now(timezone.utc)
        diff = abs((now - parsed).total_seconds())
        assert diff < 60, f"Timestamp {timestamp} is not recent (diff={diff}s)"

    def test_to_dict_with_parent(self):
        parent = Span(name="parent_op")
        child = Span(name="child_op", parent=parent)
        d = child.to_dict()
        assert d["parent"] == "parent_op"

    def test_to_dict_duration_positive(self):
        span = Span(name="test")
        time.sleep(0.005)
        span.end()
        d = span.to_dict()
        assert d["duration_ms"] > 0

    def test_start_timestamp_is_iso_string(self):
        span = Span(name="test")
        assert isinstance(span.start_timestamp, str)
        # Should parse without error
        datetime.fromisoformat(span.start_timestamp)


# ── BaseTracer Tests ────────────────────────────────────────────


class TestBaseTracer:
    """Test that BaseTracer is abstract."""

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseTracer()

    def test_span_context_manager(self):
        tracer = NoOpTracer()
        with tracer.span("test_op", query="hello") as span:
            assert span.name == "test_op"
            assert span.attributes["query"] == "hello"
        # After context, span should be ended
        assert span.end_time is not None
        assert span.status == SpanStatus.OK

    def test_span_context_manager_on_error(self):
        tracer = NoOpTracer()
        with pytest.raises(ValueError):
            with tracer.span("failing_op") as span:
                raise ValueError("test error")
        assert span.status == SpanStatus.ERROR
        assert span.error == "test error"
        assert span.end_time is not None


# ── NoOpTracer Tests ────────────────────────────────────────────


class TestNoOpTracer:
    """Test NoOpTracer."""

    def test_start_span(self):
        tracer = NoOpTracer()
        span = tracer.start_span("test")
        assert isinstance(span, Span)
        assert span.name == "test"

    def test_start_span_with_attributes(self):
        tracer = NoOpTracer()
        span = tracer.start_span("search", {"k": 5})
        assert span.attributes["k"] == 5

    def test_end_span(self):
        tracer = NoOpTracer()
        span = tracer.start_span("test")
        tracer.end_span(span, SpanStatus.OK, output="result")
        assert span.end_time is not None
        assert span.output == "result"

    def test_flush(self):
        tracer = NoOpTracer()
        tracer.flush()  # Should not raise


# ── JsonFileTracer Tests ────────────────────────────────────────


class TestJsonFileTracer:
    """Test JsonFileTracer."""

    def test_init_creates_directory(self, tmp_path):
        trace_dir = tmp_path / "traces"
        tracer = JsonFileTracer(trace_dir=trace_dir, enabled=True)
        assert trace_dir.exists()

    def test_init_disabled(self, tmp_path):
        trace_dir = tmp_path / "traces_disabled"
        tracer = JsonFileTracer(trace_dir=trace_dir, enabled=False)
        assert not trace_dir.exists()

    def test_start_span(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)
        span = tracer.start_span("test_op", {"key": "value"})
        assert span.name == "test_op"
        assert span.attributes["key"] == "value"

    def test_end_span_buffers_trace(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)
        span = tracer.start_span("op")
        tracer.end_span(span, SpanStatus.OK)
        assert len(tracer._buffer) == 1

    def test_end_span_sets_end_time(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)
        span = tracer.start_span("op")
        tracer.end_span(span, SpanStatus.OK, output="done")
        assert span.end_time is not None
        assert span.output == "done"

    def test_end_span_disabled_no_buffer(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=False)
        span = tracer.start_span("op")
        tracer.end_span(span, SpanStatus.OK)
        assert len(tracer._buffer) == 0

    def test_flush_writes_jsonl(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)

        span = tracer.start_span("search", {"strategy": "vector"})
        tracer.end_span(span, SpanStatus.OK)
        tracer.flush()

        # Find the written file
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1

        with open(files[0]) as f:
            lines = f.readlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["name"] == "search"
        assert data["status"] == "ok"
        assert "duration_ms" in data
        assert data["attributes"]["strategy"] == "vector"

    def test_flush_clears_buffer(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)
        span = tracer.start_span("op")
        tracer.end_span(span, SpanStatus.OK)
        assert len(tracer._buffer) == 1
        tracer.flush()
        assert len(tracer._buffer) == 0

    def test_flush_empty_buffer_no_file(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)
        tracer.flush()
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 0

    def test_multiple_spans_same_file(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)

        for i in range(5):
            span = tracer.start_span(f"op_{i}")
            tracer.end_span(span, SpanStatus.OK)

        tracer.flush()

        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1

        with open(files[0]) as f:
            lines = f.readlines()
        assert len(lines) == 5

    def test_auto_flush_at_100(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)

        for i in range(100):
            span = tracer.start_span(f"op_{i}")
            tracer.end_span(span, SpanStatus.OK)

        # Should have auto-flushed
        assert len(tracer._buffer) == 0

    def test_file_rotation_daily(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)
        span = tracer.start_span("op")
        tracer.end_span(span, SpanStatus.OK)
        tracer.flush()

        # File should be named with today's date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        expected_file = tmp_path / f"{today}.jsonl"
        assert expected_file.exists()

    def test_error_span_recorded(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)
        span = tracer.start_span("failing_op")
        tracer.end_span(span, SpanStatus.ERROR, error="connection failed")
        tracer.flush()

        files = list(tmp_path.glob("*.jsonl"))
        with open(files[0]) as f:
            data = json.loads(f.readline())

        assert data["status"] == "error"

    def test_context_manager_integration(self, tmp_path):
        tracer = JsonFileTracer(trace_dir=tmp_path, enabled=True)
        with tracer.span("context_op", strategy="hybrid") as span:
            pass
        tracer.flush()

        files = list(tmp_path.glob("*.jsonl"))
        with open(files[0]) as f:
            data = json.loads(f.readline())
        assert data["name"] == "context_op"
        assert data["attributes"]["strategy"] == "hybrid"


# ── LangSmithTracer Tests ──────────────────────────────────────


class TestLangSmithTracer:
    """Test LangSmithTracer."""

    def test_init_disabled(self):
        tracer = LangSmithTracer(enabled=False)
        assert tracer._enabled is False

    def test_init_no_langsmith_installed(self):
        with patch.dict("sys.modules", {"langsmith": None}):
            tracer = LangSmithTracer(enabled=True)
            assert tracer._enabled is False

    def test_start_span(self):
        tracer = LangSmithTracer(enabled=False)
        span = tracer.start_span("test", {"key": "val"})
        assert span.name == "test"

    def test_end_span(self):
        tracer = LangSmithTracer(enabled=False)
        span = tracer.start_span("test")
        tracer.end_span(span, SpanStatus.OK, output="result")
        assert span.end_time is not None
        assert span.output == "result"

    def test_flush(self):
        tracer = LangSmithTracer(enabled=False)
        tracer.flush()  # No-op, should not raise


# ── MetricsCollector Tests ─────────────────────────────────────


class TestMetricsCollector:
    """Test MetricsCollector."""

    def test_initial_state(self):
        mc = MetricsCollector()
        metrics = mc.get_metrics()
        assert metrics["queries_total"] == 0
        assert metrics["queries_today"] == 0
        assert metrics["avg_latency_ms"] == 0.0
        assert metrics["p95_latency_ms"] == 0.0
        assert metrics["cache_hit_rate"] == 0.0
        assert metrics["error_rate"] == 0.0
        assert metrics["strategies_usage"] == {}

    def test_record_query_increments_total(self):
        mc = MetricsCollector()
        mc.record_query(latency_ms=100.0, strategy="vector")
        metrics = mc.get_metrics()
        assert metrics["queries_total"] == 1
        assert metrics["queries_today"] == 1

    def test_record_multiple_queries(self):
        mc = MetricsCollector()
        for i in range(10):
            mc.record_query(latency_ms=float(i * 10), strategy="vector")
        metrics = mc.get_metrics()
        assert metrics["queries_total"] == 10
        assert metrics["queries_today"] == 10

    def test_avg_latency(self):
        mc = MetricsCollector()
        mc.record_query(latency_ms=100.0, strategy="vector")
        mc.record_query(latency_ms=200.0, strategy="vector")
        mc.record_query(latency_ms=300.0, strategy="vector")
        metrics = mc.get_metrics()
        assert metrics["avg_latency_ms"] == pytest.approx(200.0)

    def test_p95_latency(self):
        mc = MetricsCollector()
        for i in range(100):
            mc.record_query(latency_ms=float(i), strategy="vector")
        metrics = mc.get_metrics()
        assert metrics["p95_latency_ms"] == 95.0

    def test_cache_hit_rate(self):
        mc = MetricsCollector()
        mc.record_query(latency_ms=10.0, strategy="v", cache_hit=True)
        mc.record_query(latency_ms=10.0, strategy="v", cache_hit=True)
        mc.record_query(latency_ms=10.0, strategy="v", cache_hit=False)
        metrics = mc.get_metrics()
        assert metrics["cache_hit_rate"] == pytest.approx(2.0 / 3.0)

    def test_cache_hit_none_ignored(self):
        mc = MetricsCollector()
        mc.record_query(latency_ms=10.0, strategy="v", cache_hit=None)
        metrics = mc.get_metrics()
        assert metrics["cache_hit_rate"] == 0.0  # No cache data

    def test_error_rate(self):
        mc = MetricsCollector()
        mc.record_query(latency_ms=10.0, strategy="v")
        mc.record_query(latency_ms=10.0, strategy="v", error=True)
        metrics = mc.get_metrics()
        assert metrics["error_rate"] == pytest.approx(0.5)

    def test_strategies_usage(self):
        mc = MetricsCollector()
        mc.record_query(latency_ms=10.0, strategy="vector")
        mc.record_query(latency_ms=10.0, strategy="vector")
        mc.record_query(latency_ms=10.0, strategy="hybrid")
        metrics = mc.get_metrics()
        assert metrics["strategies_usage"]["vector"] == 2
        assert metrics["strategies_usage"]["hybrid"] == 1

    def test_latency_buffer_limit(self):
        mc = MetricsCollector()
        for i in range(1500):
            mc.record_query(latency_ms=float(i), strategy="v")
        # Should keep only last 1000
        assert len(mc._latencies) == 1000

    def test_last_reset_timestamp(self):
        mc = MetricsCollector()
        metrics = mc.get_metrics()
        assert "last_reset" in metrics
        # Should parse as ISO timestamp
        datetime.fromisoformat(metrics["last_reset"])


# ── Factory Tests ──────────────────────────────────────────────


class TestGetTracer:
    """Test get_tracer factory."""

    def test_jsonfile_tracer(self, tmp_path):
        tracer = get_tracer("jsonfile", trace_dir=tmp_path)
        assert isinstance(tracer, JsonFileTracer)

    def test_langsmith_tracer(self):
        tracer = get_tracer("langsmith", enabled=False)
        assert isinstance(tracer, LangSmithTracer)

    def test_none_tracer(self):
        tracer = get_tracer("none")
        assert isinstance(tracer, NoOpTracer)

    def test_invalid_type_returns_noop(self):
        tracer = get_tracer("invalid_backend")
        assert isinstance(tracer, NoOpTracer)


class TestGetMetricsCollector:
    """Test get_metrics_collector singleton."""

    def test_returns_metrics_collector(self):
        mc = get_metrics_collector()
        assert isinstance(mc, MetricsCollector)

    def test_returns_same_instance(self):
        mc1 = get_metrics_collector()
        mc2 = get_metrics_collector()
        assert mc1 is mc2
