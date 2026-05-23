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

from .dashboard import (
    Dashboard,
    DashboardConfig,
    DashboardPanel,
    create_dashboard,
)
from .logger import (
    LogContext,
    LogEntry,
    LogLevel,
    PipelineLogger,
    configure_logging,
    get_logger,
)
from .metrics import (
    Counter,
    Gauge,
    Histogram,
    Metric,
    MetricsCollector,
    MetricType,
    MetricUnit,
    MetricValue,
    Timer,
    get_metrics,
)
from .tracer import (
    Span,
    SpanContext,
    SpanKind,
    SpanStatus,
    Tracer,
    get_tracer,
    trace,
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
