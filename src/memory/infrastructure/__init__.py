"""
Memory Infrastructure -- resilience and configuration utilities.

Provides retry logic, timeout configuration, circuit breaker, and shared helpers
for the Unified Memory System.
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
)
from .retry import (
    MemoryError,
    PermanentError,
    RetryableError,
    RetryConfig,
    async_retry,
    classify_exception,
)
from .timeout import TimeoutConfig, get_timeout_config
from .cache import LRUCache
from .conflict_resolver import (
    ConflictRecord,
    ConflictResolver,
    ConflictResult,
    ConflictStrategy,
)
from .event_bus import (
    Event,
    EventBus,
    EventBusConfig,
    EventBusStats,
    Subscription,
    get_event_bus,
    reset_event_bus,
)
from .event_store import EventStore, EventStoreConfig
from .metrics import MetricsCollector, MetricsTimer, get_metrics_collector, reset_metrics

__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    # Retry
    "MemoryError",
    "RetryableError",
    "PermanentError",
    "RetryConfig",
    "async_retry",
    "classify_exception",
    # Timeout
    "TimeoutConfig",
    "get_timeout_config",
    # Cache (P2)
    "LRUCache",
    # Metrics (P2)
    "MetricsCollector",
    "MetricsTimer",
    "get_metrics_collector",
    "reset_metrics",
]
