"""Tracing backends for pipeline observability (Phase 11).

Provides multiple tracing implementations:
- JsonFileTracer: local JSONL files for dev/testing
- LangSmithTracer: LangSmith dashboard integration
- OpenTelemetryTracer: standard observability (optional)

Author: Claude Code
Version: 1.2.0 - Phase 11.1: Tracing
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Literal

logger = logging.getLogger(__name__)


class SpanStatus(str, Enum):
    """Status of a traced span."""

    OK = "ok"
    ERROR = "error"


@dataclass
class Span:
    """Single trace span representing a timed operation."""

    name: str
    start_time: float = field(default_factory=time.perf_counter)
    start_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: float | None = None
    status: SpanStatus = SpanStatus.OK
    attributes: dict = field(default_factory=dict)
    output: Any = None
    error: str | None = None
    parent: Span | None = None
    children: list[Span] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Span duration in milliseconds."""
        end = self.end_time or time.perf_counter()
        return (end - self.start_time) * 1000

    def to_dict(self) -> dict:
        """Convert span to dictionary for serialization."""
        return {
            "name": self.name,
            "timestamp": self.start_timestamp,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "parent": self.parent.name if self.parent else None,
        }

    def end(self, status: SpanStatus = SpanStatus.OK, output: Any = None, error: str | None = None) -> None:
        """End the span."""
        self.end_time = time.perf_counter()
        self.status = status
        self.output = output
        self.error = error


class BaseTracer(ABC):
    """Abstract base class for tracing backends."""

    @abstractmethod
    def start_span(self, name: str, attributes: dict | None = None) -> Span:
        """Start a new trace span."""
        pass

    @abstractmethod
    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK, output: Any = None, error: str | None = None) -> None:
        """End a trace span and record it."""
        pass

    @contextmanager
    def span(self, name: str, **attributes) -> Generator[Span, None, None]:
        """
        Context manager for automatic span lifecycle.

        Usage:
            with tracer.span("search", query="test", strategy="vector"):
                results = await search_manager.search(...)
        """
        span = self.start_span(name, attributes)
        try:
            yield span
            self.end_span(span, SpanStatus.OK, span.output)
        except Exception as e:
            self.end_span(span, SpanStatus.ERROR, error=str(e))
            raise

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered traces."""
        pass


class JsonFileTracer(BaseTracer):
    """
    Tracer that writes to JSON Lines files.

    One file per day with automatic rotation.
    """

    def __init__(
        self,
        trace_dir: str | Path = "data/traces",
        enabled: bool = True,
    ):
        """
        Initialize JSON file tracer.

        Args:
            trace_dir: Directory for trace files
            enabled: Whether tracing is active
        """
        self._trace_dir = Path(trace_dir)
        self._enabled = enabled
        self._buffer: list[dict] = []
        self._current_file: Path | None = None

        if self._enabled:
            self._trace_dir.mkdir(parents=True, exist_ok=True)

    def start_span(self, name: str, attributes: dict | None = None) -> Span:
        """Start a new span."""
        return Span(name=name, attributes=attributes or {})

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK, output: Any = None, error: str | None = None) -> None:
        """End span and write to buffer."""
        span.end(status=status, output=output, error=error)

        if self._enabled:
            self._buffer.append(span.to_dict())

            # Flush if buffer is large enough
            if len(self._buffer) >= 100:
                self.flush()

    def flush(self) -> None:
        """Flush buffered traces to file."""
        if not self._enabled or not self._buffer:
            return

        # Get current file path (rotates daily)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        trace_file = self._trace_dir / f"{today}.jsonl"

        count = len(self._buffer)

        # Append traces
        with open(trace_file, "a", encoding="utf-8") as f:
            for trace in self._buffer:
                f.write(json.dumps(trace, ensure_ascii=False) + "\n")

        self._buffer.clear()
        logger.debug(f"[TRACE] Flushed {count} traces to {trace_file}")


class LangSmithTracer(BaseTracer):
    """
    Tracer that integrates with LangSmith.

    Requires LANGCHAIN_TRACING_V2=true environment variable.
    """

    def __init__(
        self,
        enabled: bool = False,
        project_name: str = "pdf-framework",
    ):
        """
        Initialize LangSmith tracer.

        Args:
            enabled: Whether LangSmith tracing is active
            project_name: LangSmith project name
        """
        self._enabled = enabled
        self._project_name = project_name

        if self._enabled:
            try:
                import langsmith
                self._langsmith = langsmith
                logger.info(f"[TRACE] LangSmith tracing enabled (project: {project_name})")
            except ImportError:
                logger.warning("[TRACE] langsmith not installed, disabling LangSmith tracer")
                self._enabled = False

    def start_span(self, name: str, attributes: dict | None = None) -> Span:
        """Start a new span (delegates to LangChain)."""
        # LangSmith handles tracing automatically when enabled
        return Span(name=name, attributes=attributes or {})

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK, output: Any = None, error: str | None = None) -> None:
        """End span (no-op for LangSmith, automatic)."""
        span.end(status=status, output=output, error=error)
        # LangSmith traces automatically via callbacks

    def flush(self) -> None:
        """Flush (no-op for LangSmith)."""
        pass


class NoOpTracer(BaseTracer):
    """No-op tracer that discards all spans."""

    def start_span(self, name: str, attributes: dict | None = None) -> Span:
        """Start a span (no-op)."""
        return Span(name=name, attributes=attributes or {})

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK, output: Any = None, error: str | None = None) -> None:
        """End a span (no-op)."""
        span.end(status=status, output=output, error=error)

    def flush(self) -> None:
        """Flush (no-op)."""
        pass


class MetricsCollector:
    """
    Lightweight metrics collector for dashboards.

    Collects query counts, latencies, cache stats without external dependencies.
    """

    def __init__(self):
        """Initialize metrics collector."""
        self._queries_total = 0
        self._queries_today = 0
        self._latencies: list[float] = []
        self._cache_hits = 0
        self._cache_misses = 0
        self._errors = 0
        self._strategies: dict[str, int] = {}
        self._last_reset = datetime.now(timezone.utc)

        # Reset daily counters
        self._schedule_daily_reset()

    def _schedule_daily_reset(self) -> None:
        """Schedule daily reset of counters."""
        # In production, use a proper scheduler
        # For now, manual reset via API is sufficient
        pass

    def record_query(
        self,
        latency_ms: float,
        strategy: str,
        cache_hit: bool | None = None,
        error: bool = False,
    ) -> None:
        """Record a query execution."""
        self._queries_total += 1
        self._queries_today += 1
        self._latencies.append(latency_ms)

        if cache_hit is not None:
            if cache_hit:
                self._cache_hits += 1
            else:
                self._cache_misses += 1

        if error:
            self._errors += 1

        self._strategies[strategy] = self._strategies.get(strategy, 0) + 1

        # Keep only last 1000 latencies
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-1000:]

    def get_metrics(self) -> dict:
        """Get current metrics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

        # Calculate percentiles
        sorted_latencies = sorted(self._latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[p95_index] if sorted_latencies else 0.0

        return {
            "queries_total": self._queries_total,
            "queries_today": self._queries_today,
            "avg_latency_ms": sum(self._latencies) / len(self._latencies) if self._latencies else 0.0,
            "p95_latency_ms": p95_latency,
            "cache_hit_rate": hit_rate,
            "error_rate": self._errors / self._queries_total if self._queries_total > 0 else 0.0,
            "strategies_usage": self._strategies.copy(),
            "last_reset": self._last_reset.isoformat(),
        }


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_tracer(
    tracer_type: Literal["jsonfile", "langsmith", "none"] = "jsonfile",
    **kwargs,
) -> BaseTracer:
    """
    Factory function to get configured tracer.

    Args:
        tracer_type: Type of tracer to use
        **kwargs: Additional arguments for tracer

    Returns:
        Tracer instance
    """
    if tracer_type == "jsonfile":
        return JsonFileTracer(**kwargs)
    elif tracer_type == "langsmith":
        return LangSmithTracer(**kwargs)
    else:
        # No-op tracer
        return NoOpTracer()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    return _metrics_collector
