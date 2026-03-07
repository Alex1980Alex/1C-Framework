"""Distributed tracing for pipeline observability.

Provides comprehensive tracing capabilities:
- Span creation and management
- Context propagation
- Trace correlation
- Timing and annotations
"""

from __future__ import annotations

import uuid
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from contextlib import contextmanager
from functools import wraps


class SpanStatus(Enum):
    """Status of a span."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class SpanKind(Enum):
    """Kind of span in the trace."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


@dataclass
class SpanContext:
    """Context for trace propagation."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def new(cls, parent: Optional["SpanContext"] = None) -> "SpanContext":
        """Create a new span context."""
        trace_id = parent.trace_id if parent else str(uuid.uuid4())
        parent_span_id = parent.span_id if parent else None

        return cls(
            trace_id=trace_id,
            span_id=str(uuid.uuid4())[:16],
            parent_span_id=parent_span_id,
            baggage=dict(parent.baggage) if parent else {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }
        if self.parent_span_id:
            result["parent_span_id"] = self.parent_span_id
        if self.baggage:
            result["baggage"] = self.baggage
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpanContext":
        """Create from dictionary."""
        return cls(
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            parent_span_id=data.get("parent_span_id"),
            baggage=data.get("baggage", {}),
        )

    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers for propagation."""
        return {
            "X-Trace-Id": self.trace_id,
            "X-Span-Id": self.span_id,
            "X-Parent-Span-Id": self.parent_span_id or "",
        }

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> Optional["SpanContext"]:
        """Extract from HTTP headers."""
        trace_id = headers.get("X-Trace-Id")
        span_id = headers.get("X-Span-Id")

        if not trace_id or not span_id:
            return None

        return cls(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=headers.get("X-Parent-Span-Id") or None,
        )


@dataclass
class SpanEvent:
    """An event within a span."""

    name: str
    timestamp: datetime = field(default_factory=datetime.now)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }


@dataclass
class SpanLink:
    """A link to another span."""

    context: SpanContext
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "context": self.context.to_dict(),
            "attributes": self.attributes,
        }


class Span:
    """A single span in a trace."""

    def __init__(
        self,
        name: str,
        context: SpanContext,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.context = context
        self.kind = kind
        self.status = SpanStatus.UNSET
        self.status_message: Optional[str] = None
        self.attributes: Dict[str, Any] = attributes or {}
        self.events: List[SpanEvent] = []
        self.links: List[SpanLink] = []

        self.start_time: datetime = datetime.now()
        self.end_time: Optional[datetime] = None
        self._start_ns: int = time.perf_counter_ns()
        self._end_ns: Optional[int] = None

    @property
    def duration_ms(self) -> Optional[float]:
        """Get duration in milliseconds."""
        if self._end_ns is None:
            return None
        return (self._end_ns - self._start_ns) / 1_000_000

    @property
    def is_ended(self) -> bool:
        """Check if span has ended."""
        return self.end_time is not None

    def set_attribute(self, key: str, value: Any) -> "Span":
        """Set a span attribute."""
        self.attributes[key] = value
        return self

    def set_attributes(self, attributes: Dict[str, Any]) -> "Span":
        """Set multiple span attributes."""
        self.attributes.update(attributes)
        return self

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> "Span":
        """Add an event to the span."""
        self.events.append(SpanEvent(
            name=name,
            attributes=attributes or {},
        ))
        return self

    def add_link(
        self,
        context: SpanContext,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> "Span":
        """Add a link to another span."""
        self.links.append(SpanLink(
            context=context,
            attributes=attributes or {},
        ))
        return self

    def set_status(
        self,
        status: SpanStatus,
        message: Optional[str] = None,
    ) -> "Span":
        """Set the span status."""
        self.status = status
        self.status_message = message
        return self

    def record_exception(
        self,
        exception: Exception,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> "Span":
        """Record an exception in the span."""
        import traceback

        exc_attributes = {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
            "exception.stacktrace": traceback.format_exc(),
        }
        if attributes:
            exc_attributes.update(attributes)

        self.add_event("exception", exc_attributes)
        self.set_status(SpanStatus.ERROR, str(exception))
        return self

    def end(self) -> None:
        """End the span."""
        if not self.is_ended:
            self._end_ns = time.perf_counter_ns()
            self.end_time = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "context": self.context.to_dict(),
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "attributes": self.attributes,
        }

        if self.status_message:
            result["status_message"] = self.status_message

        if self.end_time:
            result["end_time"] = self.end_time.isoformat()

        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms

        if self.events:
            result["events"] = [e.to_dict() for e in self.events]

        if self.links:
            result["links"] = [l.to_dict() for l in self.links]

        return result


class SpanProcessor:
    """Base class for span processors."""

    def on_start(self, span: Span) -> None:
        """Called when a span starts."""
        pass

    def on_end(self, span: Span) -> None:
        """Called when a span ends."""
        pass

    def shutdown(self) -> None:
        """Shutdown the processor."""
        pass


class SimpleSpanProcessor(SpanProcessor):
    """Processor that stores spans in memory."""

    def __init__(self, max_spans: int = 1000) -> None:
        self.max_spans = max_spans
        self._spans: List[Span] = []
        self._lock = threading.Lock()

    def on_end(self, span: Span) -> None:
        """Store completed span."""
        with self._lock:
            self._spans.append(span)
            if len(self._spans) > self.max_spans:
                self._spans = self._spans[-self.max_spans:]

    def get_spans(
        self,
        trace_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Span]:
        """Get stored spans."""
        with self._lock:
            spans = list(self._spans)

        if trace_id:
            spans = [s for s in spans if s.context.trace_id == trace_id]

        if limit:
            spans = spans[-limit:]

        return spans

    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace."""
        return self.get_spans(trace_id=trace_id)

    def clear(self) -> None:
        """Clear all stored spans."""
        with self._lock:
            self._spans.clear()


class ConsoleSpanProcessor(SpanProcessor):
    """Processor that prints spans to console."""

    def __init__(self, detailed: bool = False) -> None:
        self.detailed = detailed

    def on_end(self, span: Span) -> None:
        """Print span to console."""
        duration = f"{span.duration_ms:.2f}ms" if span.duration_ms else "?"
        status = "✓" if span.status == SpanStatus.OK else "✗" if span.status == SpanStatus.ERROR else "○"

        print(f"[TRACE] {status} {span.name} ({duration}) [{span.context.trace_id[:8]}]")

        if self.detailed and span.attributes:
            for key, value in span.attributes.items():
                print(f"        {key}: {value}")


class Tracer:
    """Tracer for creating and managing spans."""

    def __init__(
        self,
        name: str,
        processors: Optional[List[SpanProcessor]] = None,
    ):
        self.name = name
        self._processors = processors or []
        self._local = threading.local()

    @property
    def current_span(self) -> Optional[Span]:
        """Get the current active span."""
        stack = getattr(self._local, "span_stack", [])
        return stack[-1] if stack else None

    def add_processor(self, processor: SpanProcessor) -> None:
        """Add a span processor."""
        self._processors.append(processor)

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[SpanContext] = None,
    ) -> Span:
        """Start a new span."""
        # Use provided parent or current span's context
        if parent is None and self.current_span:
            parent = self.current_span.context

        context = SpanContext.new(parent)

        span = Span(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes,
        )

        # Notify processors
        for processor in self._processors:
            try:
                processor.on_start(span)
            except Exception:
                pass

        return span

    def _push_span(self, span: Span) -> None:
        """Push span onto the context stack."""
        if not hasattr(self._local, "span_stack"):
            self._local.span_stack = []
        self._local.span_stack.append(span)

    def _pop_span(self) -> Optional[Span]:
        """Pop span from the context stack."""
        stack = getattr(self._local, "span_stack", [])
        return stack.pop() if stack else None

    def _end_span(self, span: Span) -> None:
        """End a span and notify processors."""
        span.end()

        for processor in self._processors:
            try:
                processor.on_end(span)
            except Exception:
                pass

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        end_on_exit: bool = True,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ):
        """Start a span and make it the current span."""
        span = self.start_span(name, kind, attributes)
        self._push_span(span)

        try:
            yield span
            if span.status == SpanStatus.UNSET:
                span.set_status(SpanStatus.OK)
        except Exception as e:
            if record_exception:
                span.record_exception(e)
            if set_status_on_exception:
                span.set_status(SpanStatus.ERROR, str(e))
            raise
        finally:
            self._pop_span()
            if end_on_exit:
                self._end_span(span)

    def shutdown(self) -> None:
        """Shutdown the tracer and all processors."""
        for processor in self._processors:
            try:
                processor.shutdown()
            except Exception:
                pass


def trace(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True,
):
    """Decorator for tracing a function."""
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes,
                record_exception=record_exception,
            ) as span:
                # Add function arguments as attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                result = func(*args, **kwargs)
                return result

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()

            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes,
                record_exception=record_exception,
            ) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                result = await func(*args, **kwargs)
                return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


# Global tracer registry
_tracers: Dict[str, Tracer] = {}
_default_processors: List[SpanProcessor] = []
_tracer_lock = threading.Lock()


def configure_tracing(
    console: bool = False,
    console_detailed: bool = False,
    memory: bool = True,
    memory_max_spans: int = 1000,
) -> None:
    """Configure global tracing settings."""
    global _default_processors

    with _tracer_lock:
        _default_processors.clear()

        if console:
            _default_processors.append(ConsoleSpanProcessor(detailed=console_detailed))

        if memory:
            _default_processors.append(SimpleSpanProcessor(max_spans=memory_max_spans))


def get_tracer(name: str = "default") -> Tracer:
    """Get or create a tracer by name."""
    with _tracer_lock:
        if name not in _tracers:
            tracer = Tracer(
                name=name,
                processors=list(_default_processors),
            )
            _tracers[name] = tracer

        return _tracers[name]


def get_span_processor() -> Optional[SimpleSpanProcessor]:
    """Get the global memory span processor."""
    for processor in _default_processors:
        if isinstance(processor, SimpleSpanProcessor):
            return processor
    return None
