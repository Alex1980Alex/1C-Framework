"""In-memory metrics collector for framework operations."""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricEntry:
    """A single metric measurement."""

    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collect and query in-memory metrics."""

    def __init__(self) -> None:
        self._entries: list[MetricEntry] = []
        self._counters: dict[str, int] = {}
        self._timers: dict[str, float] = {}

    def record(self, name: str, value: float, **tags: str) -> None:
        """Record a metric value."""
        self._entries.append(MetricEntry(name=name, value=value, tags=tags))

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment a counter."""
        self._counters[name] = self._counters.get(name, 0) + amount

    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        self._timers[name] = time.perf_counter()

    def stop_timer(self, name: str) -> float:
        """Stop a named timer and record the elapsed time in milliseconds."""
        start = self._timers.pop(name, None)
        if start is None:
            return 0.0
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.record(f"{name}_ms", elapsed_ms)
        return elapsed_ms

    def get_counter(self, name: str) -> int:
        """Get current counter value."""
        return self._counters.get(name, 0)

    def get_metrics(self, name: str | None = None) -> list[dict[str, Any]]:
        """Get recorded metrics, optionally filtered by name."""
        entries = self._entries
        if name:
            entries = [e for e in entries if e.name == name]
        return [
            {"name": e.name, "value": e.value, "timestamp": e.timestamp, "tags": e.tags}
            for e in entries
        ]

    def summary(self) -> dict[str, Any]:
        """Get a summary of all metrics."""
        result: dict[str, Any] = {"counters": dict(self._counters)}
        metric_names = {e.name for e in self._entries}
        for mname in metric_names:
            values = [e.value for e in self._entries if e.name == mname]
            if values:
                result[mname] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }
        return result

    def clear(self) -> None:
        """Clear all collected metrics."""
        self._entries.clear()
        self._counters.clear()
        self._timers.clear()
