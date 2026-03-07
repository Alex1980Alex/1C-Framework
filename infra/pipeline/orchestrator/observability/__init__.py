"""Observability module for pipeline monitoring and debugging.

This module provides comprehensive observability capabilities:
- Structured logging with context
- Metrics collection and aggregation
- Distributed tracing
- Dashboard for visualization

Components:
    - PipelineLogger: Structured logging with JSON output
    - MetricsCollector: Metrics collection and aggregation
    - Tracer: Distributed tracing with spans
    - Dashboard: Real-time monitoring dashboard
"""

from .logger import (
    LogLevel,
    LogContext,
    LogEntry,
    PipelineLogger,
    get_logger,
    configure_logging,
)

from .metrics import (
    MetricType,
    MetricUnit,
    Metric,
    MetricValue,
    MetricsCollector,
    Counter,
    Gauge,
    Histogram,
    Timer,
    get_metrics,
)

from .tracer import (
    SpanStatus,
    SpanKind,
    SpanContext,
    Span,
    Tracer,
    get_tracer,
    trace,
)

from .dashboard import (
    DashboardConfig,
    DashboardPanel,
    Dashboard,
    create_dashboard,
)

__all__ = [
    # Logger
    "LogLevel",
    "LogContext",
    "LogEntry",
    "PipelineLogger",
    "get_logger",
    "configure_logging",
    # Metrics
    "MetricType",
    "MetricUnit",
    "Metric",
    "MetricValue",
    "MetricsCollector",
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    "get_metrics",
    # Tracer
    "SpanStatus",
    "SpanKind",
    "SpanContext",
    "Span",
    "Tracer",
    "get_tracer",
    "trace",
    # Dashboard
    "DashboardConfig",
    "DashboardPanel",
    "Dashboard",
    "create_dashboard",
]
