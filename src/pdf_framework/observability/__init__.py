"""Observability and tracing for PDF Framework (Phase 11).

Provides:
- BaseTracer: abstract interface for tracing backends
- JsonFileTracer: JSON Lines file tracing
- LangSmithTracer: LangSmith integration
- MetricsCollector: lightweight metrics for dashboards
- get_tracer(): factory for configured tracer
- get_metrics_collector(): global metrics instance
"""

from src.pdf_framework.observability.tracer import (
    BaseTracer,
    JsonFileTracer,
    LangSmithTracer,
    MetricsCollector,
    Span,
    SpanStatus,
    get_metrics_collector,
    get_tracer,
)

__all__ = [
    "BaseTracer",
    "JsonFileTracer",
    "LangSmithTracer",
    "MetricsCollector",
    "Span",
    "SpanStatus",
    "get_metrics_collector",
    "get_tracer",
]
