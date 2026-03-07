"""Tests for metrics collection module."""

import pytest
import time
from datetime import datetime

from .metrics import (
    MetricType,
    MetricUnit,
    Metric,
    MetricValue,
    Counter,
    Gauge,
    Histogram,
    Timer,
    MetricsCollector,
    get_metrics,
    reset_metrics,
)


class TestMetricEnums:
    """Tests for metric enums."""

    def test_metric_types(self):
        """Test metric type values."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.TIMER.value == "timer"

    def test_metric_units(self):
        """Test metric unit values."""
        assert MetricUnit.COUNT.value == "count"
        assert MetricUnit.BYTES.value == "bytes"
        assert MetricUnit.SECONDS.value == "seconds"
        assert MetricUnit.MILLISECONDS.value == "milliseconds"
        assert MetricUnit.PERCENT.value == "percent"


class TestMetricValue:
    """Tests for MetricValue dataclass."""

    def test_create_value(self):
        """Test creating metric value."""
        value = MetricValue(value=42.5)
        assert value.value == 42.5
        assert isinstance(value.timestamp, datetime)
        assert value.labels == {}

    def test_value_with_labels(self):
        """Test value with labels."""
        value = MetricValue(
            value=100,
            labels={"host": "server1", "region": "us-east"},
        )
        assert value.labels["host"] == "server1"
        assert value.labels["region"] == "us-east"

    def test_value_to_dict(self):
        """Test value serialization."""
        value = MetricValue(
            value=50,
            labels={"env": "prod"},
        )
        result = value.to_dict()
        assert result["value"] == 50
        assert result["labels"]["env"] == "prod"
        assert "timestamp" in result


class TestMetric:
    """Tests for Metric metadata."""

    def test_create_metric(self):
        """Test creating metric metadata."""
        metric = Metric(
            name="requests_total",
            metric_type=MetricType.COUNTER,
            description="Total requests",
            unit=MetricUnit.COUNT,
            labels=["method", "status"],
        )
        assert metric.name == "requests_total"
        assert metric.metric_type == MetricType.COUNTER
        assert metric.description == "Total requests"
        assert "method" in metric.labels

    def test_metric_to_dict(self):
        """Test metric serialization."""
        metric = Metric(
            name="test",
            metric_type=MetricType.GAUGE,
        )
        result = metric.to_dict()
        assert result["name"] == "test"
        assert result["type"] == "gauge"


class TestCounter:
    """Tests for Counter metric."""

    def test_counter_increment(self):
        """Test counter increment."""
        counter = Counter("requests", "Total requests")

        counter.inc()
        assert counter.get() == 1.0

        counter.inc(5)
        assert counter.get() == 6.0

    def test_counter_with_labels(self):
        """Test counter with labels."""
        counter = Counter("requests", labels=["method"])

        counter.inc(1, {"method": "GET"})
        counter.inc(2, {"method": "POST"})
        counter.inc(1, {"method": "GET"})

        assert counter.get({"method": "GET"}) == 2.0
        assert counter.get({"method": "POST"}) == 2.0

    def test_counter_get_all(self):
        """Test getting all counter values."""
        counter = Counter("test", labels=["type"])

        counter.inc(5, {"type": "a"})
        counter.inc(10, {"type": "b"})

        values = counter.get_all()
        assert len(values) == 2

    def test_counter_reset(self):
        """Test counter reset."""
        counter = Counter("test")
        counter.inc(10)
        counter.reset()

        assert counter.get() == 0.0

    def test_counter_reset_with_labels(self):
        """Test reset specific label."""
        counter = Counter("test", labels=["type"])
        counter.inc(5, {"type": "a"})
        counter.inc(10, {"type": "b"})

        counter.reset({"type": "a"})

        assert counter.get({"type": "a"}) == 0.0
        assert counter.get({"type": "b"}) == 10.0


class TestGauge:
    """Tests for Gauge metric."""

    def test_gauge_set(self):
        """Test gauge set."""
        gauge = Gauge("temperature", "Current temperature")
        gauge.set(25.5)

        assert gauge.get() == 25.5

    def test_gauge_inc_dec(self):
        """Test gauge increment and decrement."""
        gauge = Gauge("active_connections")

        gauge.set(10)
        gauge.inc(5)
        assert gauge.get() == 15

        gauge.dec(3)
        assert gauge.get() == 12

    def test_gauge_with_labels(self):
        """Test gauge with labels."""
        gauge = Gauge("memory_usage", labels=["host"])

        gauge.set(1024, {"host": "server1"})
        gauge.set(2048, {"host": "server2"})

        assert gauge.get({"host": "server1"}) == 1024
        assert gauge.get({"host": "server2"}) == 2048

    def test_gauge_track_inprogress(self):
        """Test in-progress tracking."""
        gauge = Gauge("active_tasks")

        with gauge.track_inprogress():
            assert gauge.get() == 1.0

        assert gauge.get() == 0.0

    def test_gauge_get_all(self):
        """Test getting all gauge values."""
        gauge = Gauge("test", labels=["region"])

        gauge.set(100, {"region": "us"})
        gauge.set(200, {"region": "eu"})

        values = gauge.get_all()
        assert len(values) == 2


class TestHistogram:
    """Tests for Histogram metric."""

    def test_histogram_observe(self):
        """Test histogram observations."""
        histogram = Histogram("request_duration")

        histogram.observe(0.1)
        histogram.observe(0.5)
        histogram.observe(1.0)

        assert histogram.get_count() == 3
        assert histogram.get_sum() == 1.6

    def test_histogram_buckets(self):
        """Test histogram bucket counts."""
        histogram = Histogram(
            "latency",
            buckets=(0.1, 0.5, 1.0, float("inf")),
        )

        histogram.observe(0.05)  # <= 0.1
        histogram.observe(0.3)   # <= 0.5
        histogram.observe(0.8)   # <= 1.0
        histogram.observe(2.0)   # <= inf

        buckets = histogram.get_buckets()
        assert buckets[0.1] == 1
        assert buckets[0.5] == 2
        assert buckets[1.0] == 3
        assert buckets[float("inf")] == 4

    def test_histogram_with_labels(self):
        """Test histogram with labels."""
        histogram = Histogram("size", labels=["type"])

        histogram.observe(100, {"type": "small"})
        histogram.observe(1000, {"type": "large"})

        assert histogram.get_count({"type": "small"}) == 1
        assert histogram.get_count({"type": "large"}) == 1

    def test_histogram_statistics(self):
        """Test histogram statistics."""
        histogram = Histogram("values")

        for i in range(1, 101):
            histogram.observe(float(i))

        stats = histogram.get_statistics()
        assert stats["count"] == 100
        assert stats["sum"] == 5050.0
        assert stats["min"] == 1.0
        assert stats["max"] == 100.0
        assert stats["mean"] == 50.5
        assert stats["median"] == 50.5

    def test_histogram_empty_statistics(self):
        """Test statistics for empty histogram."""
        histogram = Histogram("empty")

        stats = histogram.get_statistics()
        assert stats["count"] == 0
        assert stats["sum"] == 0.0

    def test_histogram_reset(self):
        """Test histogram reset."""
        histogram = Histogram("test")
        histogram.observe(1.0)
        histogram.observe(2.0)

        histogram.reset()

        assert histogram.get_count() == 0


class TestTimer:
    """Tests for Timer metric."""

    def test_timer_observe(self):
        """Test timer observation."""
        timer = Timer("operation_duration")
        timer.observe(0.5)

        assert timer.get_count() == 1

    def test_timer_context_manager(self):
        """Test timer context manager."""
        timer = Timer("task_duration")

        with timer.time():
            time.sleep(0.01)  # 10ms

        stats = timer.get_statistics()
        assert stats["count"] == 1
        assert stats["min"] >= 0.01  # At least 10ms

    def test_timer_with_labels(self):
        """Test timer with labels."""
        timer = Timer("api_latency", labels=["endpoint"])

        with timer.time({"endpoint": "/users"}):
            time.sleep(0.01)

        stats = timer.get_statistics({"endpoint": "/users"})
        assert stats["count"] == 1

    def test_timer_get_count(self):
        """Test timer count."""
        timer = Timer("test")

        timer.observe(0.1)
        timer.observe(0.2)
        timer.observe(0.3)

        assert timer.get_count() == 3


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_collector_counter(self):
        """Test counter creation."""
        collector = MetricsCollector(prefix="test")
        counter = collector.counter("requests", "Total requests")

        assert counter.metric.name == "test_requests"
        counter.inc(5)
        assert counter.get() == 5.0

    def test_collector_gauge(self):
        """Test gauge creation."""
        collector = MetricsCollector(prefix="app")
        gauge = collector.gauge("connections", "Active connections")

        assert gauge.metric.name == "app_connections"
        gauge.set(42)
        assert gauge.get() == 42.0

    def test_collector_histogram(self):
        """Test histogram creation."""
        collector = MetricsCollector(prefix="api")
        histogram = collector.histogram("latency", "Request latency")

        assert histogram.metric.name == "api_latency"
        histogram.observe(0.5)
        assert histogram.get_count() == 1

    def test_collector_timer(self):
        """Test timer creation."""
        collector = MetricsCollector(prefix="task")
        timer = collector.timer("duration", "Task duration")

        assert timer.metric.name == "task_duration"

    def test_collector_reuses_metrics(self):
        """Test that collector reuses existing metrics."""
        collector = MetricsCollector()

        counter1 = collector.counter("requests")
        counter1.inc(10)

        counter2 = collector.counter("requests")
        assert counter2.get() == 10.0

    def test_collector_collect_all(self):
        """Test collecting all metrics."""
        collector = MetricsCollector(prefix="test")

        counter = collector.counter("requests")
        counter.inc(100)

        gauge = collector.gauge("active")
        gauge.set(5)

        timer = collector.timer("latency")
        timer.observe(0.1)

        result = collector.collect_all()
        assert "timestamp" in result
        assert "counters" in result
        assert "gauges" in result
        assert "timers" in result
        assert "test_requests" in result["counters"]
        assert "test_active" in result["gauges"]

    def test_collector_reset_all(self):
        """Test resetting all metrics."""
        collector = MetricsCollector()

        counter = collector.counter("test")
        counter.inc(50)

        gauge = collector.gauge("value")
        gauge.set(100)

        collector.reset_all()

        assert counter.get() == 0.0
        assert gauge.get() == 0.0

    def test_collector_no_prefix(self):
        """Test collector without prefix."""
        collector = MetricsCollector(prefix="")
        counter = collector.counter("raw_counter")

        assert counter.metric.name == "raw_counter"


class TestGlobalMetrics:
    """Tests for global metrics functions."""

    def test_get_metrics(self):
        """Test getting global metrics collector."""
        reset_metrics()  # Clean state

        collector = get_metrics("app")
        counter = collector.counter("requests")
        counter.inc(10)

        # Same collector should be returned
        collector2 = get_metrics()
        counter2 = collector2.counter("requests")
        assert counter2.get() == 10.0

    def test_reset_metrics(self):
        """Test resetting global metrics."""
        collector = get_metrics()
        counter = collector.counter("test")
        counter.inc(50)

        reset_metrics()

        new_collector = get_metrics()
        new_counter = new_collector.counter("test")
        assert new_counter.get() == 0.0
