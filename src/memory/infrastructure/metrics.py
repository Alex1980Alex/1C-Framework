"""In-memory metrics collector for memory subsystem.

Counters, gauges, timers, and JSON export.
No Prometheus dependency -- lightweight alternative.

Migrated from: unified-memory-mcp/src/utils/metrics.py (265 lines)
Simplified: removed Prometheus text export, kept core metrics.

Version: 1.0 (2026-04-04) -- P2 migration
"""

import json
import logging
import threading
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Thread-safe metrics collector with counters, gauges, and timers.

    Usage:
        metrics = MetricsCollector()
        metrics.counter("search_requests")
        metrics.gauge("cache_size", 42)
        with metrics.timer("search_duration"):
            await do_search()
        print(metrics.export_json())
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._timer_counts: dict[str, int] = defaultdict(int)
        self._timer_sums: dict[str, float] = defaultdict(float)
        self._start_time = time.time()

    def counter(self, name: str, delta: int = 1) -> int:
        """Increment a counter. Returns new value."""
        with self._lock:
            self._counters[name] += delta
            return self._counters[name]

    def gauge(self, name: str, value: float) -> None:
        """Set a gauge value."""
        with self._lock:
            self._gauges[name] = value

    def observe_duration(self, name: str, duration: float) -> None:
        """Record an observed duration."""
        with self._lock:
            self._timer_counts[name] += 1
            self._timer_sums[name] += duration

    def timer(self, name: str) -> "MetricsTimer":
        """Create a context manager for timing an operation."""
        return MetricsTimer(self, name)

    def get_all(self) -> dict[str, Any]:
        """Get all metrics as a dict."""
        with self._lock:
            avg_durations = {}
            for name, count in self._timer_counts.items():
                avg_durations[name] = round(self._timer_sums[name] / count, 6) if count > 0 else 0.0

            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "durations": {
                    name: {
                        "count": self._timer_counts[name],
                        "total": round(self._timer_sums[name], 6),
                        "average": avg_durations.get(name, 0.0),
                    }
                    for name in self._timer_counts
                },
                "uptime_seconds": round(time.time() - self._start_time, 2),
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timer_counts.clear()
            self._timer_sums.clear()
            self._start_time = time.time()

    def export_json(self) -> str:
        """Export metrics as JSON string."""
        return json.dumps(self.get_all(), indent=2, ensure_ascii=False)

    def __repr__(self) -> str:
        return (
            f"<MetricsCollector counters={len(self._counters)} "
            f"gauges={len(self._gauges)} durations={len(self._timer_counts)}>"
        )


class MetricsTimer:
    """Context manager for timing operations."""

    def __init__(self, collector: MetricsCollector, operation: str):
        self.collector = collector
        self.operation = operation
        self.start_time: float = 0.0
        self.duration: float = 0.0

    def __enter__(self) -> "MetricsTimer":
        self.start_time = time.time()
        self.collector.counter(f"{self.operation}_calls")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.duration = time.time() - self.start_time
        self.collector.observe_duration(self.operation, self.duration)
        if exc_type is not None:
            self.collector.counter(f"{self.operation}_errors")
        return False  # Don't suppress exceptions


# Global singleton
_global_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def reset_metrics() -> None:
    """Reset the global metrics collector."""
    global _global_collector
    if _global_collector is not None:
        _global_collector.reset()


__all__ = ["MetricsCollector", "MetricsTimer", "get_metrics_collector", "reset_metrics"]
