"""Resilience module for pipeline orchestrator.

Provides error handling, retry logic, fallback strategies,
state persistence and recovery capabilities.
"""

from .error_handler import (
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    PipelineError,
    RecoverableError,
    FatalError,
    GracefulDegradationHandler,
    DegradationLevel,
    with_graceful_degradation,
)
from .retry_handler import (
    RetryConfig,
    RetryResult,
    RetryHandler,
    with_retry,
)
from .fallback_strategy import (
    FallbackStrategy,
    FallbackResult,
    FallbackChain,
    FallbackRegistry,
    with_fallback,
)
from .state_manager import (
    StateCheckpoint,
    CheckpointMetadata,
    StateManager,
)
from .recovery_handler import (
    RecoveryStrategy,
    RecoveryPlan,
    RecoveryResult,
    RecoveryHandler,
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
