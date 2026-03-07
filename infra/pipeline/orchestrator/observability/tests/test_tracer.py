"""Tests for distributed tracing module."""

import pytest
import time
import asyncio
from datetime import datetime

from .tracer import (
    SpanStatus,
    SpanKind,
    SpanContext,
    SpanEvent,
    SpanLink,
    Span,
    SpanProcessor,
    SimpleSpanProcessor,
    ConsoleSpanProcessor,
    Tracer,
    trace,
    configure_tracing,
    get_tracer,
    get_span_processor,
)


class TestSpanEnums:
    """Tests for span enums."""

    def test_span_status_values(self):
        """Test span status values."""
        assert SpanStatus.UNSET.value == "unset"
        assert SpanStatus.OK.value == "ok"
        assert SpanStatus.ERROR.value == "error"

    def test_span_kind_values(self):
        """Test span kind values."""
        assert SpanKind.INTERNAL.value == "internal"
        assert SpanKind.SERVER.value == "server"
        assert SpanKind.CLIENT.value == "client"
        assert SpanKind.PRODUCER.value == "producer"
        assert SpanKind.CONSUMER.value == "consumer"


class TestSpanContext:
    """Tests for SpanContext."""

    def test_create_new_context(self):
        """Test creating new context."""
        ctx = SpanContext.new()

        assert ctx.trace_id is not None
        assert ctx.span_id is not None
        assert ctx.parent_span_id is None
        assert ctx.baggage == {}

    def test_create_child_context(self):
        """Test creating child context."""
        parent = SpanContext.new()
        child = SpanContext.new(parent)

        assert child.trace_id == parent.trace_id
        assert child.span_id != parent.span_id
        assert child.parent_span_id == parent.span_id

    def test_context_baggage_inheritance(self):
        """Test baggage is inherited."""
        parent = SpanContext.new()
        parent.baggage["user_id"] = "123"

        child = SpanContext.new(parent)
        assert child.baggage["user_id"] == "123"

    def test_context_to_dict(self):
        """Test context serialization."""
        ctx = SpanContext.new()
        ctx.baggage["key"] = "value"

        result = ctx.to_dict()
        assert "trace_id" in result
        assert "span_id" in result
        assert result["baggage"]["key"] == "value"

    def test_context_from_dict(self):
        """Test context deserialization."""
        data = {
            "trace_id": "trace-123",
            "span_id": "span-456",
            "parent_span_id": "parent-789",
            "baggage": {"env": "prod"},
        }
        ctx = SpanContext.from_dict(data)

        assert ctx.trace_id == "trace-123"
        assert ctx.span_id == "span-456"
        assert ctx.parent_span_id == "parent-789"
        assert ctx.baggage["env"] == "prod"

    def test_context_to_headers(self):
        """Test HTTP header propagation."""
        ctx = SpanContext(
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id="parent-789",
        )
        headers = ctx.to_headers()

        assert headers["X-Trace-Id"] == "trace-123"
        assert headers["X-Span-Id"] == "span-456"
        assert headers["X-Parent-Span-Id"] == "parent-789"

    def test_context_from_headers(self):
        """Test extracting context from headers."""
        headers = {
            "X-Trace-Id": "trace-abc",
            "X-Span-Id": "span-def",
        }
        ctx = SpanContext.from_headers(headers)

        assert ctx.trace_id == "trace-abc"
        assert ctx.span_id == "span-def"
        assert ctx.parent_span_id is None

    def test_context_from_headers_missing(self):
        """Test extracting from incomplete headers."""
        headers = {"X-Trace-Id": "trace-abc"}
        ctx = SpanContext.from_headers(headers)

        assert ctx is None


class TestSpanEvent:
    """Tests for SpanEvent."""

    def test_create_event(self):
        """Test creating event."""
        event = SpanEvent(
            name="connection_established",
            attributes={"host": "server1"},
        )

        assert event.name == "connection_established"
        assert isinstance(event.timestamp, datetime)
        assert event.attributes["host"] == "server1"

    def test_event_to_dict(self):
        """Test event serialization."""
        event = SpanEvent(name="test")
        result = event.to_dict()

        assert result["name"] == "test"
        assert "timestamp" in result


class TestSpanLink:
    """Tests for SpanLink."""

    def test_create_link(self):
        """Test creating link."""
        ctx = SpanContext.new()
        link = SpanLink(
            context=ctx,
            attributes={"reason": "async_continuation"},
        )

        assert link.context == ctx
        assert link.attributes["reason"] == "async_continuation"

    def test_link_to_dict(self):
        """Test link serialization."""
        ctx = SpanContext.new()
        link = SpanLink(context=ctx)
        result = link.to_dict()

        assert "context" in result
        assert result["context"]["trace_id"] == ctx.trace_id


class TestSpan:
    """Tests for Span."""

    def test_create_span(self):
        """Test creating span."""
        ctx = SpanContext.new()
        span = Span(name="test_operation", context=ctx)

        assert span.name == "test_operation"
        assert span.context == ctx
        assert span.kind == SpanKind.INTERNAL
        assert span.status == SpanStatus.UNSET

    def test_span_with_kind(self):
        """Test span with specific kind."""
        ctx = SpanContext.new()
        span = Span(name="api_call", context=ctx, kind=SpanKind.CLIENT)

        assert span.kind == SpanKind.CLIENT

    def test_span_set_attribute(self):
        """Test setting span attribute."""
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)

        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"

    def test_span_set_attributes(self):
        """Test setting multiple attributes."""
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)

        span.set_attributes({"a": 1, "b": 2})
        assert span.attributes["a"] == 1
        assert span.attributes["b"] == 2

    def test_span_add_event(self):
        """Test adding event to span."""
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)

        span.add_event("checkpoint", {"step": 1})
        assert len(span.events) == 1
        assert span.events[0].name == "checkpoint"

    def test_span_add_link(self):
        """Test adding link to span."""
        ctx = SpanContext.new()
        other_ctx = SpanContext.new()
        span = Span(name="test", context=ctx)

        span.add_link(other_ctx, {"type": "follows_from"})
        assert len(span.links) == 1
        assert span.links[0].context.trace_id == other_ctx.trace_id

    def test_span_set_status(self):
        """Test setting span status."""
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)

        span.set_status(SpanStatus.OK)
        assert span.status == SpanStatus.OK

        span.set_status(SpanStatus.ERROR, "Something went wrong")
        assert span.status == SpanStatus.ERROR
        assert span.status_message == "Something went wrong"

    def test_span_record_exception(self):
        """Test recording exception."""
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)

        try:
            raise ValueError("Test error")
        except Exception as e:
            span.record_exception(e)

        assert span.status == SpanStatus.ERROR
        assert len(span.events) == 1
        assert span.events[0].name == "exception"
        assert "ValueError" in span.events[0].attributes["exception.type"]

    def test_span_end(self):
        """Test ending span."""
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)

        assert not span.is_ended
        span.end()

        assert span.is_ended
        assert span.end_time is not None

    def test_span_duration(self):
        """Test span duration calculation."""
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)

        time.sleep(0.01)  # 10ms
        span.end()

        assert span.duration_ms is not None
        assert span.duration_ms >= 10.0

    def test_span_to_dict(self):
        """Test span serialization."""
        ctx = SpanContext.new()
        span = Span(
            name="test",
            context=ctx,
            kind=SpanKind.SERVER,
            attributes={"key": "value"},
        )
        span.add_event("checkpoint")
        span.set_status(SpanStatus.OK)
        span.end()

        result = span.to_dict()
        assert result["name"] == "test"
        assert result["kind"] == "server"
        assert result["status"] == "ok"
        assert result["attributes"]["key"] == "value"
        assert "duration_ms" in result


class TestSimpleSpanProcessor:
    """Tests for SimpleSpanProcessor."""

    def test_processor_stores_spans(self):
        """Test that processor stores completed spans."""
        processor = SimpleSpanProcessor()
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)
        span.end()

        processor.on_end(span)

        spans = processor.get_spans()
        assert len(spans) == 1
        assert spans[0].name == "test"

    def test_processor_max_spans(self):
        """Test max spans limit."""
        processor = SimpleSpanProcessor(max_spans=3)

        for i in range(5):
            ctx = SpanContext.new()
            span = Span(name=f"span_{i}", context=ctx)
            span.end()
            processor.on_end(span)

        spans = processor.get_spans()
        assert len(spans) == 3
        assert spans[0].name == "span_2"

    def test_processor_filter_by_trace(self):
        """Test filtering by trace ID."""
        processor = SimpleSpanProcessor()

        # Create spans in two traces
        ctx1 = SpanContext.new()
        span1 = Span(name="trace1_span", context=ctx1)
        span1.end()
        processor.on_end(span1)

        ctx2 = SpanContext.new()
        span2 = Span(name="trace2_span", context=ctx2)
        span2.end()
        processor.on_end(span2)

        trace1_spans = processor.get_trace(ctx1.trace_id)
        assert len(trace1_spans) == 1
        assert trace1_spans[0].name == "trace1_span"

    def test_processor_clear(self):
        """Test clearing spans."""
        processor = SimpleSpanProcessor()
        ctx = SpanContext.new()
        span = Span(name="test", context=ctx)
        span.end()
        processor.on_end(span)

        processor.clear()
        assert len(processor.get_spans()) == 0


class TestTracer:
    """Tests for Tracer."""

    def test_tracer_creation(self):
        """Test tracer creation."""
        tracer = Tracer("test-tracer")
        assert tracer.name == "test-tracer"

    def test_tracer_start_span(self):
        """Test starting a span."""
        tracer = Tracer("test")
        span = tracer.start_span("operation")

        assert span.name == "operation"
        assert span.context.trace_id is not None

    def test_tracer_start_span_with_parent(self):
        """Test starting span with parent context."""
        tracer = Tracer("test")
        parent_ctx = SpanContext.new()

        span = tracer.start_span("child", parent=parent_ctx)

        assert span.context.trace_id == parent_ctx.trace_id
        assert span.context.parent_span_id == parent_ctx.span_id

    def test_tracer_start_as_current_span(self):
        """Test context manager for current span."""
        processor = SimpleSpanProcessor()
        tracer = Tracer("test", processors=[processor])

        with tracer.start_as_current_span("operation") as span:
            assert tracer.current_span == span
            span.set_attribute("key", "value")

        assert tracer.current_span is None
        spans = processor.get_spans()
        assert len(spans) == 1
        assert spans[0].status == SpanStatus.OK

    def test_tracer_nested_spans(self):
        """Test nested spans."""
        processor = SimpleSpanProcessor()
        tracer = Tracer("test", processors=[processor])

        with tracer.start_as_current_span("parent") as parent:
            with tracer.start_as_current_span("child") as child:
                assert child.context.parent_span_id == parent.context.span_id

        spans = processor.get_spans()
        assert len(spans) == 2

    def test_tracer_exception_handling(self):
        """Test exception recording in spans."""
        processor = SimpleSpanProcessor()
        tracer = Tracer("test", processors=[processor])

        with pytest.raises(ValueError):
            with tracer.start_as_current_span("failing"):
                raise ValueError("Test error")

        spans = processor.get_spans()
        assert len(spans) == 1
        assert spans[0].status == SpanStatus.ERROR
        assert len(spans[0].events) == 1  # Exception event

    def test_tracer_add_processor(self):
        """Test adding processor after creation."""
        tracer = Tracer("test")
        processor = SimpleSpanProcessor()
        tracer.add_processor(processor)

        with tracer.start_as_current_span("test"):
            pass

        assert len(processor.get_spans()) == 1


class TestTraceDecorator:
    """Tests for @trace decorator."""

    def test_trace_decorator_sync(self):
        """Test tracing sync function."""
        configure_tracing(memory=True, console=False)

        @trace("decorated_function")
        def sample_function(x, y):
            return x + y

        result = sample_function(2, 3)
        assert result == 5

        processor = get_span_processor()
        spans = processor.get_spans()
        assert any(s.name == "decorated_function" for s in spans)

    def test_trace_decorator_async(self):
        """Test tracing async function."""
        configure_tracing(memory=True, console=False)

        @trace("async_function")
        async def async_sample():
            await asyncio.sleep(0.01)
            return "done"

        result = asyncio.run(async_sample())
        assert result == "done"

        processor = get_span_processor()
        spans = processor.get_spans()
        assert any(s.name == "async_function" for s in spans)

    def test_trace_decorator_exception(self):
        """Test exception recording in decorated function."""
        configure_tracing(memory=True, console=False)

        @trace("failing_function")
        def failing():
            raise RuntimeError("Error")

        with pytest.raises(RuntimeError):
            failing()

        processor = get_span_processor()
        spans = processor.get_spans()
        failing_span = next(s for s in spans if s.name == "failing_function")
        assert failing_span.status == SpanStatus.ERROR


class TestGlobalTracing:
    """Tests for global tracing functions."""

    def test_configure_tracing(self):
        """Test tracing configuration."""
        configure_tracing(console=False, memory=True)
        tracer = get_tracer("test")

        with tracer.start_as_current_span("test"):
            pass

        processor = get_span_processor()
        assert processor is not None

    def test_get_tracer_reuse(self):
        """Test tracer reuse."""
        tracer1 = get_tracer("shared")
        tracer2 = get_tracer("shared")

        assert tracer1 is tracer2
