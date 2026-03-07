"""Retry Handler with Exponential Backoff.

Implements retry logic with configurable backoff strategies,
jitter, and circuit breaker integration.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Any, TypeVar, Type, Tuple, List
from functools import wraps
import asyncio
import random
import logging
import time

from .error_handler import ErrorContext, ErrorSeverity, RecoverableError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BackoffStrategy(Enum):
    """Backoff strategy types."""

    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0

    # Jitter to prevent thundering herd
    jitter: bool = True
    jitter_factor: float = 0.25

    # Exception handling
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (
        KeyboardInterrupt,
        SystemExit,
    )

    # Callbacks
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
    on_failure: Optional[Callable[[Exception], None]] = None

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        if self.backoff_strategy == BackoffStrategy.CONSTANT:
            delay = self.initial_delay

        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.initial_delay * attempt

        elif self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.initial_delay * (self.backoff_multiplier ** (attempt - 1))

        elif self.backoff_strategy == BackoffStrategy.FIBONACCI:
            delay = self.initial_delay * self._fibonacci(attempt)

        else:
            delay = self.initial_delay

        # Apply max delay cap
        delay = min(delay, self.max_delay)

        # Apply jitter
        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay = delay + random.uniform(-jitter_range, jitter_range)
            delay = max(0.1, delay)  # Ensure minimum delay

        return delay

    @staticmethod
    def _fibonacci(n: int) -> int:
        """Calculate nth Fibonacci number."""
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Any = None
    attempts: int = 0
    total_delay: float = 0.0
    last_exception: Optional[Exception] = None
    exceptions: List[Exception] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        """Check if operation failed."""
        return not self.success


class RetryHandler:
    """Handler for retry operations."""

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        self._config = config or RetryConfig()
        self._attempt_count = 0
        self._total_delay = 0.0
        self._exceptions: List[Exception] = []

    @property
    def config(self) -> RetryConfig:
        """Get retry configuration."""
        return self._config

    @property
    def attempt_count(self) -> int:
        """Get current attempt count."""
        return self._attempt_count

    def reset(self) -> None:
        """Reset retry state."""
        self._attempt_count = 0
        self._total_delay = 0.0
        self._exceptions.clear()

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> RetryResult:
        """Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            RetryResult with success status and result
        """
        self.reset()

        for attempt in range(1, self._config.max_retries + 1):
            self._attempt_count = attempt

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt,
                    total_delay=self._total_delay,
                    exceptions=self._exceptions.copy(),
                )

            except self._config.non_retryable_exceptions as e:
                # Non-retryable, raise immediately
                logger.error(f"Non-retryable exception: {e}")
                raise

            except self._config.retryable_exceptions as e:
                self._exceptions.append(e)

                if attempt >= self._config.max_retries:
                    # Max retries reached
                    logger.error(
                        f"Max retries ({self._config.max_retries}) reached for {func.__name__}"
                    )
                    if self._config.on_failure:
                        self._config.on_failure(e)

                    return RetryResult(
                        success=False,
                        attempts=attempt,
                        total_delay=self._total_delay,
                        last_exception=e,
                        exceptions=self._exceptions.copy(),
                    )

                # Calculate delay
                delay = self._config.calculate_delay(attempt)
                self._total_delay += delay

                logger.warning(
                    f"Attempt {attempt}/{self._config.max_retries} failed: {e}. "
                    f"Retrying in {delay:.2f}s"
                )

                # Call retry callback
                if self._config.on_retry:
                    self._config.on_retry(attempt, e, delay)

                # Wait before retry
                await asyncio.sleep(delay)

        # Should not reach here
        return RetryResult(
            success=False,
            attempts=self._attempt_count,
            total_delay=self._total_delay,
            exceptions=self._exceptions.copy(),
        )

    def execute_sync(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> RetryResult:
        """Synchronous version of execute.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            RetryResult with success status and result
        """
        self.reset()

        for attempt in range(1, self._config.max_retries + 1):
            self._attempt_count = attempt

            try:
                result = func(*args, **kwargs)

                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt,
                    total_delay=self._total_delay,
                    exceptions=self._exceptions.copy(),
                )

            except self._config.non_retryable_exceptions:
                raise

            except self._config.retryable_exceptions as e:
                self._exceptions.append(e)

                if attempt >= self._config.max_retries:
                    if self._config.on_failure:
                        self._config.on_failure(e)

                    return RetryResult(
                        success=False,
                        attempts=attempt,
                        total_delay=self._total_delay,
                        last_exception=e,
                        exceptions=self._exceptions.copy(),
                    )

                delay = self._config.calculate_delay(attempt)
                self._total_delay += delay

                logger.warning(
                    f"Attempt {attempt}/{self._config.max_retries} failed: {e}. "
                    f"Retrying in {delay:.2f}s"
                )

                if self._config.on_retry:
                    self._config.on_retry(attempt, e, delay)

                time.sleep(delay)

        return RetryResult(
            success=False,
            attempts=self._attempt_count,
            total_delay=self._total_delay,
            exceptions=self._exceptions.copy(),
        )


def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_strategy: Backoff strategy to use
        retryable_exceptions: Tuple of retryable exception types
        on_retry: Callback called on each retry

    Returns:
        Decorated function
    """
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_strategy=backoff_strategy,
        retryable_exceptions=retryable_exceptions,
        on_retry=on_retry,
    )
    handler = RetryHandler(config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            result = await handler.execute(func, *args, **kwargs)
            if result.failed:
                if result.last_exception:
                    raise result.last_exception
                raise RuntimeError(f"Retry failed after {result.attempts} attempts")
            return result.result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            result = handler.execute_sync(func, *args, **kwargs)
            if result.failed:
                if result.last_exception:
                    raise result.last_exception
                raise RuntimeError(f"Retry failed after {result.attempts} attempts")
            return result.result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 30.0
    half_open_max_calls: int = 3


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures."""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None) -> None:
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    async def call(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise CircuitOpenError("Circuit breaker is OPEN")

            # Check half-open call limit
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._config.half_open_max_calls:
                    raise CircuitOpenError("Circuit breaker HALF_OPEN limit reached")
                self._half_open_calls += 1

        # Execute the function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    logger.info("Circuit breaker CLOSED after recovery")

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            self._success_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN after HALF_OPEN failure")

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self._config.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit breaker OPEN after {self._failure_count} failures"
                    )

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self._config.timeout_seconds

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        logger.info("Circuit breaker manually reset to CLOSED")


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


def with_circuit_breaker(
    circuit: CircuitBreaker
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for circuit breaker protection.

    Args:
        circuit: CircuitBreaker instance

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await circuit.call(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return asyncio.run(circuit.call(func, *args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
