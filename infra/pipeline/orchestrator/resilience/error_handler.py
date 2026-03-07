"""Error Handler with Graceful Degradation.

Implements error classification, severity levels, and graceful
degradation patterns for the pipeline orchestrator.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Any, TypeVar, Dict, List
from functools import wraps
import asyncio
import logging
import traceback

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def numeric_value(self) -> int:
        """Get numeric value for comparison."""
        return {
            ErrorSeverity.LOW: 1,
            ErrorSeverity.MEDIUM: 2,
            ErrorSeverity.HIGH: 3,
            ErrorSeverity.CRITICAL: 4,
        }[self]

    def __lt__(self, other: "ErrorSeverity") -> bool:
        return self.numeric_value < other.numeric_value

    def __le__(self, other: "ErrorSeverity") -> bool:
        return self.numeric_value <= other.numeric_value


class ErrorCategory(Enum):
    """Error category classification."""

    NETWORK = "network"          # Network-related errors
    TIMEOUT = "timeout"          # Timeout errors
    VALIDATION = "validation"    # Input validation errors
    RESOURCE = "resource"        # Resource exhaustion
    PERMISSION = "permission"    # Permission/auth errors
    DEPENDENCY = "dependency"    # External dependency errors
    CONFIGURATION = "configuration"  # Config errors
    INTERNAL = "internal"        # Internal logic errors
    UNKNOWN = "unknown"          # Unclassified errors


class DegradationLevel(Enum):
    """Degradation levels for graceful degradation."""

    FULL = "full"           # Full functionality
    REDUCED = "reduced"     # Reduced functionality
    MINIMAL = "minimal"     # Minimal functionality
    OFFLINE = "offline"     # Offline/cached mode
    FAILED = "failed"       # Complete failure


@dataclass
class ErrorContext:
    """Context information about an error."""

    error_id: str
    error_type: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    timestamp: datetime = field(default_factory=datetime.now)

    # Location info
    file_path: Optional[str] = None
    function_name: Optional[str] = None
    line_number: Optional[int] = None

    # Additional context
    task_id: Optional[str] = None
    agent_type: Optional[str] = None
    phase: Optional[str] = None

    # Error details
    original_exception: Optional[Exception] = None
    stack_trace: Optional[str] = None

    # Recovery hints
    is_recoverable: bool = True
    suggested_action: Optional[str] = None
    retry_after_seconds: Optional[float] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_id": self.error_id,
            "error_type": self.error_type,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "file_path": self.file_path,
            "function_name": self.function_name,
            "line_number": self.line_number,
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "phase": self.phase,
            "stack_trace": self.stack_trace,
            "is_recoverable": self.is_recoverable,
            "suggested_action": self.suggested_action,
            "retry_after_seconds": self.retry_after_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        error_id: str,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        **kwargs
    ) -> "ErrorContext":
        """Create ErrorContext from an exception."""
        # Auto-classify if not provided
        if severity is None:
            severity = cls._classify_severity(exception)
        if category is None:
            category = cls._classify_category(exception)

        return cls(
            error_id=error_id,
            error_type=type(exception).__name__,
            message=str(exception),
            severity=severity,
            category=category,
            original_exception=exception,
            stack_trace=traceback.format_exc(),
            is_recoverable=cls._is_recoverable(exception),
            **kwargs
        )

    @staticmethod
    def _classify_severity(exception: Exception) -> ErrorSeverity:
        """Auto-classify error severity."""
        error_type = type(exception).__name__

        critical_types = {"SystemExit", "KeyboardInterrupt", "MemoryError"}
        high_types = {"RuntimeError", "RecursionError", "OSError"}
        medium_types = {"ValueError", "TypeError", "AttributeError"}

        if error_type in critical_types:
            return ErrorSeverity.CRITICAL
        elif error_type in high_types:
            return ErrorSeverity.HIGH
        elif error_type in medium_types:
            return ErrorSeverity.MEDIUM
        return ErrorSeverity.LOW

    @staticmethod
    def _classify_category(exception: Exception) -> ErrorCategory:
        """Auto-classify error category."""
        error_type = type(exception).__name__
        error_msg = str(exception).lower()

        # Network errors
        if any(kw in error_type.lower() for kw in ["connection", "network", "socket"]):
            return ErrorCategory.NETWORK

        # Timeout errors
        if "timeout" in error_type.lower() or "timeout" in error_msg:
            return ErrorCategory.TIMEOUT

        # Validation errors
        if error_type in {"ValueError", "ValidationError", "TypeError"}:
            return ErrorCategory.VALIDATION

        # Resource errors
        if error_type in {"MemoryError", "ResourceError"} or "resource" in error_msg:
            return ErrorCategory.RESOURCE

        # Permission errors
        if error_type in {"PermissionError", "AuthenticationError"}:
            return ErrorCategory.PERMISSION

        # Config errors
        if "config" in error_msg or "configuration" in error_msg:
            return ErrorCategory.CONFIGURATION

        return ErrorCategory.UNKNOWN

    @staticmethod
    def _is_recoverable(exception: Exception) -> bool:
        """Determine if error is recoverable."""
        non_recoverable = {
            "SystemExit", "KeyboardInterrupt", "MemoryError",
            "SyntaxError", "IndentationError"
        }
        return type(exception).__name__ not in non_recoverable


class PipelineError(Exception):
    """Base exception for pipeline errors."""

    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.context = context
        self.cause = cause

    @property
    def is_recoverable(self) -> bool:
        """Check if error is recoverable."""
        if self.context:
            return self.context.is_recoverable
        return True


class RecoverableError(PipelineError):
    """Error that can be recovered from."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after

    @property
    def is_recoverable(self) -> bool:
        return True


class FatalError(PipelineError):
    """Error that cannot be recovered from."""

    @property
    def is_recoverable(self) -> bool:
        return False


@dataclass
class DegradationState:
    """Current state of degradation."""

    level: DegradationLevel
    reason: Optional[str] = None
    since: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    last_error: Optional[ErrorContext] = None
    disabled_features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "reason": self.reason,
            "since": self.since.isoformat(),
            "error_count": self.error_count,
            "disabled_features": self.disabled_features,
        }


class GracefulDegradationHandler:
    """Handler for graceful degradation."""

    def __init__(
        self,
        initial_level: DegradationLevel = DegradationLevel.FULL,
        error_threshold_reduced: int = 3,
        error_threshold_minimal: int = 5,
        error_threshold_offline: int = 10,
        recovery_interval_seconds: float = 60.0,
    ):
        self._state = DegradationState(level=initial_level)
        self._error_threshold_reduced = error_threshold_reduced
        self._error_threshold_minimal = error_threshold_minimal
        self._error_threshold_offline = error_threshold_offline
        self._recovery_interval = recovery_interval_seconds
        self._error_history: List[ErrorContext] = []
        self._listeners: List[Callable[[DegradationState], None]] = []
        self._lock = asyncio.Lock()

    @property
    def current_level(self) -> DegradationLevel:
        """Get current degradation level."""
        return self._state.level

    @property
    def state(self) -> DegradationState:
        """Get current degradation state."""
        return self._state

    def add_listener(self, listener: Callable[[DegradationState], None]) -> None:
        """Add listener for degradation state changes."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[DegradationState], None]) -> None:
        """Remove listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def handle_error(self, error: ErrorContext) -> DegradationLevel:
        """Handle an error and update degradation level."""
        async with self._lock:
            self._error_history.append(error)
            self._state.error_count += 1
            self._state.last_error = error

            # Determine new level based on error count and severity
            new_level = self._calculate_level(error)

            if new_level != self._state.level:
                old_level = self._state.level
                self._state.level = new_level
                self._state.since = datetime.now()
                self._state.reason = f"Error: {error.message}"

                logger.warning(
                    f"Degradation level changed: {old_level.value} -> {new_level.value}"
                )

                # Notify listeners
                for listener in self._listeners:
                    try:
                        listener(self._state)
                    except Exception as e:
                        logger.error(f"Error in degradation listener: {e}")

            return self._state.level

    def _calculate_level(self, error: ErrorContext) -> DegradationLevel:
        """Calculate degradation level based on errors."""
        # Critical errors immediately trigger offline
        if error.severity == ErrorSeverity.CRITICAL:
            return DegradationLevel.FAILED

        # Count recent errors
        recent_errors = len(self._error_history)

        if recent_errors >= self._error_threshold_offline:
            return DegradationLevel.OFFLINE
        elif recent_errors >= self._error_threshold_minimal:
            return DegradationLevel.MINIMAL
        elif recent_errors >= self._error_threshold_reduced:
            return DegradationLevel.REDUCED

        return self._state.level

    async def attempt_recovery(self) -> bool:
        """Attempt to recover to higher degradation level."""
        async with self._lock:
            if self._state.level == DegradationLevel.FULL:
                return True

            # Check if enough time has passed
            time_in_state = (datetime.now() - self._state.since).total_seconds()
            if time_in_state < self._recovery_interval:
                return False

            # Try to upgrade level
            current = self._state.level
            if current == DegradationLevel.FAILED:
                new_level = DegradationLevel.OFFLINE
            elif current == DegradationLevel.OFFLINE:
                new_level = DegradationLevel.MINIMAL
            elif current == DegradationLevel.MINIMAL:
                new_level = DegradationLevel.REDUCED
            elif current == DegradationLevel.REDUCED:
                new_level = DegradationLevel.FULL
            else:
                return True

            self._state.level = new_level
            self._state.since = datetime.now()
            self._state.reason = "Recovery attempt"
            self._state.error_count = 0
            self._error_history.clear()

            logger.info(f"Recovered to level: {new_level.value}")

            # Notify listeners
            for listener in self._listeners:
                try:
                    listener(self._state)
                except Exception as e:
                    logger.error(f"Error in degradation listener: {e}")

            return new_level == DegradationLevel.FULL

    def reset(self) -> None:
        """Reset to full functionality."""
        self._state = DegradationState(level=DegradationLevel.FULL)
        self._error_history.clear()
        logger.info("Degradation handler reset to FULL")

    def is_feature_available(self, feature: str) -> bool:
        """Check if a feature is available at current degradation level."""
        return feature not in self._state.disabled_features

    def disable_feature(self, feature: str) -> None:
        """Disable a feature."""
        if feature not in self._state.disabled_features:
            self._state.disabled_features.append(feature)

    def enable_feature(self, feature: str) -> None:
        """Enable a feature."""
        if feature in self._state.disabled_features:
            self._state.disabled_features.remove(feature)


def with_graceful_degradation(
    handler: GracefulDegradationHandler,
    fallback_value: Any = None,
    min_level: DegradationLevel = DegradationLevel.REDUCED,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for graceful degradation.

    Args:
        handler: GracefulDegradationHandler instance
        fallback_value: Value to return when degraded
        min_level: Minimum level required to execute

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Check current level
            if handler.current_level.value == DegradationLevel.FAILED.value:
                logger.warning(f"Skipping {func.__name__}: system in FAILED state")
                return fallback_value

            # Check minimum level
            level_values = [l.value for l in DegradationLevel]
            current_idx = level_values.index(handler.current_level.value)
            min_idx = level_values.index(min_level.value)

            if current_idx > min_idx:
                logger.warning(
                    f"Skipping {func.__name__}: "
                    f"level {handler.current_level.value} < {min_level.value}"
                )
                return fallback_value

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Create error context
                import uuid
                error_ctx = ErrorContext.from_exception(
                    e,
                    error_id=str(uuid.uuid4()),
                    function_name=func.__name__,
                )

                # Handle error
                await handler.handle_error(error_ctx)

                # Re-raise if not recoverable
                if not error_ctx.is_recoverable:
                    raise

                return fallback_value

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return asyncio.run(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class ErrorAggregator:
    """Aggregates and analyzes errors."""

    def __init__(self, max_errors: int = 100) -> None:
        self._errors: List[ErrorContext] = []
        self._max_errors = max_errors

    def add(self, error: ErrorContext) -> None:
        """Add an error to the aggregator."""
        self._errors.append(error)
        if len(self._errors) > self._max_errors:
            self._errors.pop(0)

    @property
    def count(self) -> int:
        """Get total error count."""
        return len(self._errors)

    def by_severity(self) -> Dict[ErrorSeverity, int]:
        """Count errors by severity."""
        counts: Dict[ErrorSeverity, int] = {}
        for error in self._errors:
            counts[error.severity] = counts.get(error.severity, 0) + 1
        return counts

    def by_category(self) -> Dict[ErrorCategory, int]:
        """Count errors by category."""
        counts: Dict[ErrorCategory, int] = {}
        for error in self._errors:
            counts[error.category] = counts.get(error.category, 0) + 1
        return counts

    def recent(self, count: int = 10) -> List[ErrorContext]:
        """Get recent errors."""
        return self._errors[-count:]

    def clear(self) -> None:
        """Clear all errors."""
        self._errors.clear()
