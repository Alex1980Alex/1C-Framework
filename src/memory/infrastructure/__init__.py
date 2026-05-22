"""
Memory Infrastructure -- resilience and configuration utilities.

Provides retry logic, timeout configuration, circuit breaker, and shared helpers
for the Unified Memory System.
"""

from .cache import LRUCache
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
)
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
from .retry import (
    MemoryError,
    PermanentError,
    RetryableError,
    RetryConfig,
    async_retry,
    classify_exception,
)
from .subscription_manager import (
    ManagedSubscription,
    SubscriptionManager,
    SubscriptionManagerConfig,
)
from .timeout import TimeoutConfig, get_timeout_config

__all__ = [
    # Cache (P2)
    "LRUCache",
    # Circuit Breaker (P1)
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    # Conflict Resolver (P3)
    "ConflictRecord",
    "ConflictResolver",
    "ConflictResult",
    "ConflictStrategy",
    # Event Bus (P3)
    "Event",
    "EventBus",
    "EventBusConfig",
    "EventBusStats",
    "Subscription",
    "get_event_bus",
    "reset_event_bus",
    # Event Store (P3)
    "EventStore",
    "EventStoreConfig",
    # Metrics (P2)
    "MetricsCollector",
    "MetricsTimer",
    "get_metrics_collector",
    "reset_metrics",
    # Retry (P0)
    "MemoryError",
    "RetryableError",
    "PermanentError",
    "RetryConfig",
    "async_retry",
    "classify_exception",
    # Subscription Manager (P3)
    "ManagedSubscription",
    "SubscriptionManager",
    "SubscriptionManagerConfig",
    # Timeout (P0)
    "TimeoutConfig",
    "get_timeout_config",
]
