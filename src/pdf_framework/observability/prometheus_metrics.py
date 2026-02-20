"""Prometheus metrics instrumentation for PDF Framework (Phase 46).

Provides Prometheus counters, histograms, and gauges for:
- Query latency and throughput
- Cache hit rates
- Token usage
- Error rates
- Resource utilization

Author: Claude Code
Version: 1.0.0 - Phase 46: Prometheus Metrics
"""

import logging
import time
from functools import wraps
from typing import Callable

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import CollectorRegistry

logger = logging.getLogger(__name__)

# Create a custom registry for the application
_registry = CollectorRegistry()

# =============================================================================
# Query Metrics
# =============================================================================

query_latency = Histogram(
    "query_latency_seconds",
    "Query execution latency in seconds",
    ["strategy", "status"],
    registry=_registry,
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

query_total = Counter(
    "query_total",
    "Total number of queries",
    ["strategy", "status"],
    registry=_registry,
)

# =============================================================================
# Cache Metrics
# =============================================================================

cache_hit_total = Counter(
    "cache_hit_total",
    "Total number of cache hits",
    ["cache_type"],  # embedding, llm, semantic
    registry=_registry,
)

cache_miss_total = Counter(
    "cache_miss_total",
    "Total number of cache misses",
    ["cache_type"],
    registry=_registry,
)

cache_size = Gauge(
    "cache_size",
    "Current cache size",
    ["cache_type"],
    registry=_registry,
)

# =============================================================================
# Token Usage Metrics
# =============================================================================

token_usage_total = Counter(
    "token_usage_total",
    "Total token usage",
    ["model", "token_type"],  # token_type: input, output
    registry=_registry,
)

llm_request_total = Counter(
    "llm_request_total",
    "Total LLM API requests",
    ["model", "status"],
    registry=_registry,
)

# =============================================================================
# Model Routing Metrics (Phase 54)
# =============================================================================

model_routing_total = Counter(
    "model_routing_total",
    "Total model routing decisions by complexity level",
    ["model", "complexity"],
    registry=_registry,
)

# =============================================================================
# Error Metrics
# =============================================================================

error_total = Counter(
    "error_total",
    "Total number of errors",
    ["error_type", "component"],
    registry=_registry,
)

# =============================================================================
# System Metrics
# =============================================================================

active_connections = Gauge(
    "active_connections",
    "Number of active connections",
    registry=_registry,
)

queue_depth = Gauge(
    "queue_depth",
    "Current processing queue depth",
    registry=_registry,
)


# =============================================================================
# Decorators
# =============================================================================

def track_query(strategy: str = "unknown"):
    """
    Decorator to track query metrics.

    Args:
        strategy: Search strategy name

    Usage:
        @track_query(strategy="hybrid")
        async def search(query: str) -> results:
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error_total.labels(
                    error_type=type(e).__name__,
                    component="search",
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                query_latency.labels(strategy=strategy, status=status).observe(duration)
                query_total.labels(strategy=strategy, status=status).inc()

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error_total.labels(
                    error_type=type(e).__name__,
                    component="search",
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                query_latency.labels(strategy=strategy, status=status).observe(duration)
                query_total.labels(strategy=strategy, status=status).inc()

        # Return appropriate wrapper based on whether function is async
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def track_llm_call(model: str = "unknown"):
    """
    Decorator to track LLM API metrics.

    Args:
        model: Model name

    Usage:
        @track_llm_call(model="claude-sonnet-4-5")
        async def generate(prompt: str) -> str:
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            status = "success"

            try:
                result = await func(*args, **kwargs)

                # Extract token usage if available
                if hasattr(result, "usage") or isinstance(result, dict):
                    usage = result.get("usage", {}) if isinstance(result, dict) else result.usage
                    if usage:
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)

                        token_usage_total.labels(model=model, token_type="input").inc(input_tokens)
                        token_usage_total.labels(model=model, token_type="output").inc(output_tokens)

                return result
            except Exception as e:
                status = "error"
                error_total.labels(
                    error_type=type(e).__name__,
                    component="llm",
                ).inc()
                raise
            finally:
                llm_request_total.labels(model=model, status=status).inc()

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            status = "success"

            try:
                result = func(*args, **kwargs)

                # Extract token usage if available
                if hasattr(result, "usage") or isinstance(result, dict):
                    usage = result.get("usage", {}) if isinstance(result, dict) else result.usage
                    if usage:
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)

                        token_usage_total.labels(model=model, token_type="input").inc(input_tokens)
                        token_usage_total.labels(model=model, token_type="output").inc(output_tokens)

                return result
            except Exception as e:
                status = "error"
                error_total.labels(
                    error_type=type(e).__name__,
                    component="llm",
                ).inc()
                raise
            finally:
                llm_request_total.labels(model=model, status=status).inc()

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# =============================================================================
# Metrics Endpoint
# =============================================================================

def get_metrics_text() -> bytes:
    """
    Generate Prometheus exposition format metrics text.

    Returns:
        Bytes containing metrics in Prometheus format
    """
    return generate_latest(_registry)


def get_content_type() -> str:
    """
    Get content type for metrics endpoint.

    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST


# =============================================================================
# Cache Tracking
# =============================================================================

def record_cache_hit(cache_type: str) -> None:
    """Record a cache hit."""
    cache_hit_total.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str) -> None:
    """Record a cache miss."""
    cache_miss_total.labels(cache_type=cache_type).inc()


def set_cache_size(cache_type: str, size: int) -> None:
    """Set current cache size."""
    cache_size.labels(cache_type=cache_type).set(size)


# =============================================================================
# System Metrics
# =============================================================================

def set_active_connections(count: int) -> None:
    """Set number of active connections."""
    active_connections.set(count)


def set_queue_depth(depth: int) -> None:
    """Set current queue depth."""
    queue_depth.set(depth)
