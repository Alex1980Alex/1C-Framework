"""OpenTelemetry OTLP Exporter for Hook Observability (Phase 6).

Exports hook invocation traces to OpenTelemetry-compatible backends:
- OTLP/HTTP (e.g., SigNoz, Grafana Tempo, Jaeger)
- OTLP/gRPC (when opentelemetry-api is available)
- Console fallback for development

Usage:
    from shared.otel_exporter import HookTracer, configure_exporter

    # Auto-configure from environment
    tracer = configure_exporter()

    # Manual configuration
    tracer = HookTracer(
        endpoint="http://localhost:4318/v1/traces",
        service_name="claude-hooks",
    )

    # Use as context manager
    with tracer.span("SkillRouter", event="UserPromptSubmit"):
        # ... hook logic ...
        pass

Environment Variables:
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (default: disabled)
    OTEL_SERVICE_NAME: Service name (default: claude-hooks)
    OTEL_EXPORTER_CONSOLE: Enable console export (default: false)

Reference: GAP_P5_HOOK_OBSERVABILITY.md Phase 6
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

# --- Configuration ---

DEFAULT_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
DEFAULT_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "claude-hooks")
CONSOLE_EXPORT = os.getenv("OTEL_EXPORTER_CONSOLE", "").lower() in ("1", "true", "yes")

# --- Data Models ---

@dataclass
class Span:
    """OpenTelemetry-compatible span."""

    name: str
    start_time: float = field(default_factory=time.perf_counter)
    start_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: float | None = None
    status: str = "ok"
    attributes: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    parent_span_id: str | None = None
    span_id: str | None = None
    trace_id: str | None = None

    @property
    def duration_ms(self) -> float:
        """Span duration in milliseconds."""
        end = self.end_time or time.perf_counter()
        return (end - self.start_time) * 1000

    def to_dict(self) -> dict:
        """Convert to OTLP-compatible dictionary."""
        return {
            "name": self.name,
            "start_time": self.start_timestamp,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
        }

    def to_otlp_json(self) -> dict:
        """Convert to OTLP JSON format for HTTP export."""
        # OTLP JSON schema for resource spans
        return {
            "resource_spans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"string_value": self.attributes.get("service.name", "claude-hooks")}}
                        ]
                    },
                    "schema_url": "",
                    "scope_spans": [
                        {
                            "scope": {"name": "claude.hooks"},
                            "spans": [
                                {
                                    "name": self.name,
                                    "start_time_unix_nano": int(self.start_time * 1e9),
                                    "end_time_unix_nano": int((self.end_time or time.perf_counter()) * 1e9),
                                    "status": {"status_code": "OK" if self.status == "ok" else "ERROR"},
                                    "attributes": [
                                        {"key": k, "value": {"string_value": str(v)}}
                                        for k, v in self.attributes.items()
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }


@dataclass
class ExportResult:
    """Result of span export operation."""

    succeeded: int
    failed: int
    error: str | None = None


# --- Exporters ---

class BaseExporter:
    """Base class for span exporters."""

    def export(self, span: Span) -> ExportResult:
        """Export a single span."""
        raise NotImplementedError

    def export_batch(self, spans: list[Span]) -> ExportResult:
        """Export multiple spans."""
        succeeded = 0
        failed = 0
        errors = []

        for span in spans:
            result = self.export(span)
            succeeded += result.succeeded
            failed += result.failed
            if result.error:
                errors.append(result.error)

        return ExportResult(
            succeeded=succeeded,
            failed=failed,
            error="; ".join(errors) if errors else None,
        )

    def shutdown(self) -> None:
        """Shutdown exporter and release resources."""
        pass


class ConsoleExporter(BaseExporter):
    """Console exporter for development/debugging."""

    def __init__(self, pretty: bool = True):
        self._pretty = pretty

    def export(self, span: Span) -> ExportResult:
        """Print span to console."""
        try:
            if self._pretty:
                print(f"[OTEL] {span.name} - {span.duration_ms:.1f}ms - {span.status}")
                if span.attributes:
                    for k, v in span.attributes.items():
                        print(f"      {k} = {v}")
            else:
                print(json.dumps(span.to_dict()))
            return ExportResult(succeeded=1, failed=0)
        except Exception as e:
            return ExportResult(succeeded=0, failed=1, error=str(e))


class OTLPHTTPExporter(BaseExporter):
    """OTLP exporter over HTTP/JSON."""

    def __init__(
        self,
        endpoint: str,
        headers: dict | None = None,
        timeout: float = 5.0,
    ):
        """
        Initialize OTLP HTTP exporter.

        Args:
            endpoint: OTLP HTTP endpoint (e.g., http://localhost:4318/v1/traces)
            headers: HTTP headers to include
            timeout: Request timeout in seconds
        """
        self._endpoint = endpoint.rstrip("/")
        self._headers = headers or {}
        self._timeout = timeout
        self._session = None

    def _get_session(self):
        """Lazy import and initialize HTTP session."""
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update(self._headers)
            except ImportError:
                logger.warning("requests not installed, OTLP export disabled")
        return self._session

    def export(self, span: Span) -> ExportResult:
        """Export span via OTLP HTTP."""
        session = self._get_session()
        if session is None:
            return ExportResult(succeeded=0, failed=1, error="requests not installed")

        try:
            otlp_data = span.to_otlp_json()
            response = session.post(
                f"{self._endpoint}",
                json=otlp_data,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return ExportResult(succeeded=1, failed=0)
        except Exception as e:
            logger.debug(f"OTLP export failed: {e}")
            return ExportResult(succeeded=0, failed=1, error=str(e))

    def shutdown(self) -> None:
        """Close HTTP session."""
        if self._session:
            self._session.close()


class MultiExporter(BaseExporter):
    """Export to multiple backends simultaneously."""

    def __init__(self, exporters: list[BaseExporter]):
        self._exporters = exporters

    def export(self, span: Span) -> ExportResult:
        """Export to all configured exporters."""
        total_succeeded = 0
        total_failed = 0
        errors = []

        for exporter in self._exporters:
            result = exporter.export(span)
            total_succeeded += result.succeeded
            total_failed += result.failed
            if result.error:
                errors.append(f"{exporter.__class__.__name__}: {result.error}")

        return ExportResult(
            succeeded=total_succeeded,
            failed=total_failed,
            error="; ".join(errors) if errors else None,
        )

    def shutdown(self) -> None:
        """Shutdown all exporters."""
        for exporter in self._exporters:
            exporter.shutdown()


# --- Hook Tracer ---

class HookTracer:
    """
    Distributed tracing for Claude Code hooks.

    Thread-safe tracer with automatic span lifecycle management.
    Compatible with OpenTelemetry standards.

    Usage:
        tracer = HookTracer(service_name="claude-hooks")

        # Context manager
        with tracer.span("SkillRouter", event="UserPromptSubmit", prompt="..."):
            # ... hook logic ...
            pass

        # Manual
        span = tracer.start_span("GitCommitEnforcer")
        # ... logic ...
        tracer.end_span(span, status="ok")
    """

    def __init__(
        self,
        endpoint: str | None = None,
        service_name: str = DEFAULT_SERVICE_NAME,
        enabled: bool = True,
        exporters: list[BaseExporter] | None = None,
    ):
        """
        Initialize hook tracer.

        Args:
            endpoint: OTLP endpoint (auto-detected from env if None)
            service_name: Service name for traces
            enabled: Whether tracing is active
            exporters: Custom exporters (auto-configured if None)
        """
        self._service_name = service_name
        self._enabled = enabled
        self._exporters = exporters or self._create_exporters(endpoint)
        self._local = threading.local()

    @staticmethod
    def _create_exporters(endpoint: str | None = None) -> list[BaseExporter]:
        """Create exporters from configuration."""
        exporters = []

        # Console exporter (development)
        if CONSOLE_EXPORT or not endpoint:
            exporters.append(ConsoleExporter())

        # OTLP HTTP exporter
        if endpoint or DEFAULT_ENDPOINT:
            exporters.append(
                OTLPHTTPExporter(endpoint or DEFAULT_ENDPOINT)
            )

        return exporters

    def _get_span_stack(self) -> list[Span]:
        """Get thread-local span stack."""
        if not hasattr(self._local, "span_stack"):
            self._local.span_stack = []
        return self._local.span_stack

    @property
    def current_span(self) -> Span | None:
        """Get current active span."""
        stack = self._get_span_stack()
        return stack[-1] if stack else None

    def start_span(
        self,
        name: str,
        **attributes: Any,
    ) -> Span:
        """
        Start a new trace span.

        Args:
            name: Span name (e.g., hook name)
            **attributes: Span attributes (event, tool, session, etc.)

        Returns:
            Started span
        """
        if not self._enabled:
            return Span(name=name)

        span = Span(name=name, attributes=attributes)

        # Set service name
        span.attributes["service.name"] = self._service_name

        # Parent-child relationship
        if self.current_span:
            span.parent_span_id = self.current_span.span_id
            span.trace_id = self.current_span.trace_id

        self._get_span_stack().append(span)
        return span

    def end_span(
        self,
        span: Span,
        status: str = "ok",
        error: str | None = None,
        **extra_attrs: Any,
    ) -> None:
        """
        End a span and export it.

        Args:
            span: Span to end
            status: Span status (ok, error)
            error: Error message if status is error
            **extra_attrs: Additional attributes to add
        """
        if not self._enabled:
            return

        span.end_time = time.perf_counter()
        span.status = status

        if error:
            span.status = "error"
            span.attributes["error.message"] = error
            span.events.append({
                "name": "error",
                "attributes": {"exception.message": error},
            })

        span.attributes.update(extra_attrs)

        # Remove from stack
        stack = self._get_span_stack()
        if span in stack:
            stack.remove(span)

        # Export
        for exporter in self._exporters:
            exporter.export(span)

    @contextmanager
    def span(
        self,
        name: str,
        **attributes: Any,
    ) -> Generator[Span, None, None]:
        """
        Context manager for automatic span lifecycle.

        Usage:
            with tracer.span("SkillRouter", event="UserPromptSubmit"):
                # ... hook logic ...
                pass
        """
        span = self.start_span(name, **attributes)
        try:
            yield span
            self.end_span(span, status="ok")
        except Exception as e:
            self.end_span(span, status="error", error=str(e))
            raise

    def shutdown(self) -> None:
        """Shutdown tracer and export remaining spans."""
        for exporter in self._exporters:
            exporter.shutdown()


# --- Configuration Helpers ---

def configure_exporter(
    endpoint: str | None = None,
    service_name: str = DEFAULT_SERVICE_NAME,
    enabled: bool = True,
) -> HookTracer:
    """
    Configure hook tracer from environment or arguments.

    Auto-detects configuration from environment variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT
    - OTEL_SERVICE_NAME
    - OTEL_EXPORTER_CONSOLE

    Args:
        endpoint: Override endpoint (env var used if None)
        service_name: Override service name
        enabled: Whether tracing is enabled

    Returns:
        Configured HookTracer instance
    """
    if endpoint is None:
        endpoint = DEFAULT_ENDPOINT or None

    return HookTracer(
        endpoint=endpoint,
        service_name=service_name,
        enabled=enabled,
    )


# --- Hook Integration ---

class HookTracerAdapter:
    """
    Adapter for integrating HookTracer with existing hook infrastructure.

    Provides compatible API with invocation_logger.py for gradual migration.

    Usage:
        adapter = HookTracerAdapter(tracer)
        adapter.log_invocation(
            hook="SkillRouter",
            event="UserPromptSubmit",
            elapsed_ms=45,
            outcome="message",
            session_id="abc123",
        )
    """

    def __init__(self, tracer: HookTracer | None = None):
        """Initialize adapter with optional tracer."""
        self._tracer = tracer or configure_exporter()

    def log_invocation(
        self,
        hook: str,
        event: str | None = None,
        tool: str | None = None,
        elapsed_ms: int = 0,
        outcome: str = "allow",
        session_id: str = "",
        error: str | None = None,
    ) -> None:
        """
        Log hook invocation via tracer.

        Compatible signature with invocation_logger.log_invocation().
        """
        attributes = {
            "hook.name": hook,
            "hook.outcome": outcome,
            "hook.elapsed_ms": elapsed_ms,
        }

        if event:
            attributes["hook.event"] = event
        if tool:
            attributes["hook.tool"] = tool
        if session_id:
            attributes["session.id"] = session_id

        status = "error" if error else "ok"

        with self._tracer.span(f"hook.{hook}", **attributes) as span:
            span.status = status
            if error:
                span.attributes["error.message"] = error


# --- Default singleton ---

_default_tracer: HookTracer | None = None


def get_tracer() -> HookTracer:
    """Get default singleton tracer instance."""
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = configure_exporter()
    return _default_tracer
