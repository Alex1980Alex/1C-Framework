"""Metrics collection and aggregation for pipeline observability.

Provides comprehensive metrics capabilities:
- Counter: Monotonically increasing values
- Gauge: Point-in-time values
- Histogram: Distribution of values
- Timer: Duration measurements
- Metric aggregation and export
"""

from __future__ import annotations

import time
import threading
import statistics
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from contextlib import contextmanager


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class MetricUnit(Enum):
    """Units of measurement."""

    COUNT = "count"
    BYTES = "bytes"
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    PERCENT = "percent"
    RATIO = "ratio"
    NONE = "none"


@dataclass
class MetricValue:
    """A single metric value with timestamp."""

    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.labels:
            result["labels"] = self.labels
        return result


@dataclass
class Metric:
    """Metric definition and metadata."""

    name: str
    metric_type: MetricType
    description: str = ""
    unit: MetricUnit = MetricUnit.NONE
    labels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "description": self.description,
            "unit": self.unit.value,
            "labels": self.labels,
        }


class Counter:
    """A monotonically increasing counter metric."""

    def __init__(self, name: str, description: str = "", labels: List[str] = None) -> None:
        self.metric = Metric(
            name=name,
            metric_type=MetricType.COUNTER,
            description=description,
            unit=MetricUnit.COUNT,
            labels=labels or [],
        )
        self._values: Dict[tuple, float] = {}
        self._lock = threading.Lock()

    def _key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels."""
        return tuple(sorted(labels.items()))

    def inc(self, value: float = 1.0, labels: Dict[str, str] = None) -> None:
        """Increment the counter."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def get(self, labels: Dict[str, str] = None) -> float:
        """Get current counter value."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            return self._values.get(key, 0.0)

    def get_all(self) -> List[MetricValue]:
        """Get all counter values with labels."""
        with self._lock:
            return [
                MetricValue(
                    value=value,
                    labels=dict(key),
                )
                for key, value in self._values.items()
            ]

    def reset(self, labels: Dict[str, str] = None) -> None:
        """Reset counter (use with caution)."""
        if labels:
            key = self._key(labels)
            with self._lock:
                if key in self._values:
                    del self._values[key]
        else:
            with self._lock:
                self._values.clear()


class Gauge:
    """A point-in-time value metric."""

    def __init__(self, name: str, description: str = "", labels: List[str] = None) -> None:
        self.metric = Metric(
            name=name,
            metric_type=MetricType.GAUGE,
            description=description,
            unit=MetricUnit.NONE,
            labels=labels or [],
        )
        self._values: Dict[tuple, float] = {}
        self._lock = threading.Lock()

    def _key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels."""
        return tuple(sorted(labels.items()))

    def set(self, value: float, labels: Dict[str, str] = None) -> None:
        """Set the gauge value."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1.0, labels: Dict[str, str] = None) -> None:
        """Increment the gauge."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def dec(self, value: float = 1.0, labels: Dict[str, str] = None) -> None:
        """Decrement the gauge."""
        self.inc(-value, labels)

    def get(self, labels: Dict[str, str] = None) -> float:
        """Get current gauge value."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            return self._values.get(key, 0.0)

    def get_all(self) -> List[MetricValue]:
        """Get all gauge values with labels."""
        with self._lock:
            return [
                MetricValue(
                    value=value,
                    labels=dict(key),
                )
                for key, value in self._values.items()
            ]

    @contextmanager
    def track_inprogress(self, labels: Dict[str, str] = None):
        """Track in-progress operations."""
        self.inc(1.0, labels)
        try:
            yield
        finally:
            self.dec(1.0, labels)


class Histogram:
    """Distribution of values with configurable buckets."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf"))

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
        buckets: tuple = None,
    ):
        self.metric = Metric(
            name=name,
            metric_type=MetricType.HISTOGRAM,
            description=description,
            unit=MetricUnit.NONE,
            labels=labels or [],
        )
        self._buckets = buckets or self.DEFAULT_BUCKETS
        self._values: Dict[tuple, List[float]] = {}
        self._lock = threading.Lock()

    def _key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels."""
        return tuple(sorted(labels.items()))

    def observe(self, value: float, labels: Dict[str, str] = None) -> None:
        """Record an observation."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            if key not in self._values:
                self._values[key] = []
            self._values[key].append(value)

    def get_buckets(self, labels: Dict[str, str] = None) -> Dict[float, int]:
        """Get bucket counts."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            values = self._values.get(key, [])

        buckets = {b: 0 for b in self._buckets}
        for value in values:
            for bucket in self._buckets:
                if value <= bucket:
                    buckets[bucket] += 1
                    break

        return buckets

    def get_count(self, labels: Dict[str, str] = None) -> int:
        """Get total count of observations."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            return len(self._values.get(key, []))

    def get_sum(self, labels: Dict[str, str] = None) -> float:
        """Get sum of all observations."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            values = self._values.get(key, [])
            return sum(values)

    def get_statistics(self, labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get statistical summary."""
        labels = labels or {}
        key = self._key(labels)

        with self._lock:
            values = self._values.get(key, [])

        if not values:
            return {
                "count": 0,
                "sum": 0.0,
                "min": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "median": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        sorted_values = sorted(values)
        count = len(values)

        return {
            "count": count,
            "sum": sum(values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p95": sorted_values[int(count * 0.95)] if count > 1 else sorted_values[0],
            "p99": sorted_values[int(count * 0.99)] if count > 1 else sorted_values[0],
        }

    def reset(self, labels: Dict[str, str] = None) -> None:
        """Reset histogram."""
        if labels:
            key = self._key(labels)
            with self._lock:
                if key in self._values:
                    del self._values[key]
        else:
            with self._lock:
                self._values.clear()


class Timer:
    """Timer metric for measuring durations."""

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
        buckets: tuple = None,
    ):
        self.metric = Metric(
            name=name,
            metric_type=MetricType.TIMER,
            description=description,
            unit=MetricUnit.SECONDS,
            labels=labels or [],
        )
        self._histogram = Histogram(
            name=f"{name}_seconds",
            description=description,
            labels=labels,
            buckets=buckets or (0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, float("inf")),
        )
        self._lock = threading.Lock()

    def observe(self, duration_seconds: float, labels: Dict[str, str] = None) -> None:
        """Record a duration observation."""
        self._histogram.observe(duration_seconds, labels)

    @contextmanager
    def time(self, labels: Dict[str, str] = None):
        """Context manager for timing operations."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.observe(duration, labels)

    def get_statistics(self, labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get timing statistics."""
        return self._histogram.get_statistics(labels)

    def get_count(self, labels: Dict[str, str] = None) -> int:
        """Get count of timings."""
        return self._histogram.get_count(labels)


class MetricsCollector:
    """Central collector for all metrics."""

    def __init__(self, prefix: str = "pipeline") -> None:
        self.prefix = prefix
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._timers: Dict[str, Timer] = {}
        self._lock = threading.Lock()

    def _prefixed_name(self, name: str) -> str:
        """Add prefix to metric name."""
        if self.prefix:
            return f"{self.prefix}_{name}"
        return name

    def counter(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ) -> Counter:
        """Get or create a counter."""
        full_name = self._prefixed_name(name)

        with self._lock:
            if full_name not in self._counters:
                self._counters[full_name] = Counter(
                    name=full_name,
                    description=description,
                    labels=labels,
                )
            return self._counters[full_name]

    def gauge(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ) -> Gauge:
        """Get or create a gauge."""
        full_name = self._prefixed_name(name)

        with self._lock:
            if full_name not in self._gauges:
                self._gauges[full_name] = Gauge(
                    name=full_name,
                    description=description,
                    labels=labels,
                )
            return self._gauges[full_name]

    def histogram(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
        buckets: tuple = None,
    ) -> Histogram:
        """Get or create a histogram."""
        full_name = self._prefixed_name(name)

        with self._lock:
            if full_name not in self._histograms:
                self._histograms[full_name] = Histogram(
                    name=full_name,
                    description=description,
                    labels=labels,
                    buckets=buckets,
                )
            return self._histograms[full_name]

    def timer(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
        buckets: tuple = None,
    ) -> Timer:
        """Get or create a timer."""
        full_name = self._prefixed_name(name)

        with self._lock:
            if full_name not in self._timers:
                self._timers[full_name] = Timer(
                    name=full_name,
                    description=description,
                    labels=labels,
                    buckets=buckets,
                )
            return self._timers[full_name]

    def collect_all(self) -> Dict[str, Any]:
        """Collect all metric values."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "counters": {},
            "gauges": {},
            "histograms": {},
            "timers": {},
        }

        with self._lock:
            for name, counter in self._counters.items():
                values = counter.get_all()
                result["counters"][name] = {
                    "metric": counter.metric.to_dict(),
                    "values": [v.to_dict() for v in values],
                }

            for name, gauge in self._gauges.items():
                values = gauge.get_all()
                result["gauges"][name] = {
                    "metric": gauge.metric.to_dict(),
                    "values": [v.to_dict() for v in values],
                }

            for name, histogram in self._histograms.items():
                result["histograms"][name] = {
                    "metric": histogram.metric.to_dict(),
                    "statistics": histogram.get_statistics(),
                }

            for name, timer in self._timers.items():
                result["timers"][name] = {
                    "metric": timer.metric.to_dict(),
                    "statistics": timer.get_statistics(),
                }

        return result

    def reset_all(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()
            for gauge in self._gauges.values():
                gauge.set(0.0)
            for histogram in self._histograms.values():
                histogram.reset()


# Global metrics collector
_metrics: Optional[MetricsCollector] = None
_metrics_lock = threading.Lock()


def get_metrics(prefix: str = "pipeline") -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics

    with _metrics_lock:
        if _metrics is None:
            _metrics = MetricsCollector(prefix=prefix)
        return _metrics


def reset_metrics() -> None:
    """Reset the global metrics collector."""
    global _metrics

    with _metrics_lock:
        _metrics = None
