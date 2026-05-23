"""Resilience module for pipeline orchestrator.

Provides error handling, retry logic, fallback strategies,
state persistence and recovery capabilities.
"""

from .error_handler import (
    DegradationLevel,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    FatalError,
    GracefulDegradationHandler,
    PipelineError,
    RecoverableError,
    with_graceful_degradation,
)
from .fallback_strategy import (
    FallbackChain,
    FallbackRegistry,
    FallbackResult,
    FallbackStrategy,
    with_fallback,
)
from .recovery_handler import (
    RecoveryHandler,
    RecoveryPlan,
    RecoveryResult,
    RecoveryStrategy,
)
from .retry_handler import (
    RetryConfig,
    RetryHandler,
    RetryResult,
    with_retry,
)
from .state_manager import (
    CheckpointMetadata,
    StateCheckpoint,
    StateManager,
)

__all__ = [
    # Error Handler
    "ErrorSeverity",
    "ErrorCategory",
    "ErrorContext",
    "PipelineError",
    "RecoverableError",
    "FatalError",
    "GracefulDegradationHandler",
    "DegradationLevel",
    "with_graceful_degradation",
    # Retry Handler
    "RetryConfig",
    "RetryResult",
    "RetryHandler",
    "with_retry",
    # Fallback Strategy
    "FallbackStrategy",
    "FallbackResult",
    "FallbackChain",
    "FallbackRegistry",
    "with_fallback",
    # State Manager
    "StateCheckpoint",
    "CheckpointMetadata",
    "StateManager",
    # Recovery Handler
    "RecoveryStrategy",
    "RecoveryPlan",
    "RecoveryResult",
    "RecoveryHandler",
]
