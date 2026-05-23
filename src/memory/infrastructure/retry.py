"""
Retry utilities for the Unified Memory System.

Provides exponential backoff with jitter, smart exception classification,
and a convenient @async_retry decorator.

CircuitBreaker is NOT here — use ``src.shared.llm_rotation.circuit_breaker.CircuitBreaker``
directly when needed.
"""

import asyncio
import functools
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class MemoryError(Exception):
    """Base exception for memory subsystem errors."""

    def __init__(self, message: str, original_exception: Exception | None = None):
        super().__init__(message)
        self.original_exception = original_exception
        self.timestamp: float = time.time()


class RetryableError(MemoryError):
    """Temporary error — safe to retry (timeout, connection refused, rate-limit)."""


class PermanentError(MemoryError):
    """Permanent error — do NOT retry (400, 401, 404, malformed data)."""


# ---------------------------------------------------------------------------
# Exception classification
# ---------------------------------------------------------------------------

_RETRYABLE_PATTERNS = (
    "timeout",
    "connection refused",
    "connection reset",
    "rate limit",
    "too many requests",
    "service unavailable",
    "503",
    "502",
    "429",
    "temporary",
    "retry",
    "econnrefused",
    "econnreset",
    "etimedout",
)

_PERMANENT_PATTERNS = (
    "invalid request",
    "unauthorized",
    "forbidden",
    "not found",
    "400",
    "401",
    "403",
    "404",
    "malformed",
    "validation error",
    "schema error",
)


def classify_exception(exc: Exception) -> MemoryError:
    """Classify an exception as RetryableError or PermanentError."""
    msg = str(exc).lower()
    exc_type = type(exc).__name__.lower()

    # Already classified
    if isinstance(exc, MemoryError):
        return exc

    # Known retryable types
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)):
        return RetryableError(str(exc), original_exception=exc)

    # Pattern matching on message
    for pattern in _RETRYABLE_PATTERNS:
        if pattern in msg or pattern in exc_type:
            return RetryableError(str(exc), original_exception=exc)

    for pattern in _PERMANENT_PATTERNS:
        if pattern in msg or pattern in exc_type:
            return PermanentError(str(exc), original_exception=exc)

    # Default: retryable (safer choice for transient failures)
    return RetryableError(str(exc), original_exception=exc)


# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------


@dataclass
class RetryConfig:
    """Configuration for retry with exponential backoff."""

    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 10.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on: tuple[type[Exception], ...] = (RetryableError,)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for *attempt* (0-based) with jitter."""
        delay = min(
            self.base_delay * (self.exponential_base**attempt),
            self.max_delay,
        )
        if self.jitter:
            delay += random.uniform(0, delay * 0.25)
        return delay


# ---------------------------------------------------------------------------
# @async_retry decorator
# ---------------------------------------------------------------------------


def async_retry(
    config: RetryConfig | None = None,
    *,
    smart_classify: bool = True,
) -> Callable:
    """Decorator: retry an async function with exponential backoff.

    Args:
        config: Retry configuration (uses defaults if None).
        smart_classify: When True, unknown exceptions are auto-classified
            via ``classify_exception`` before deciding whether to retry.
    """
    cfg = config or RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(cfg.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc

                    # Classify if needed
                    classified = exc
                    if smart_classify and not isinstance(exc, MemoryError):
                        classified = classify_exception(exc)

                    # Check if retryable
                    if not isinstance(classified, cfg.retry_on):
                        raise classified from exc

                    if attempt < cfg.max_retries:
                        delay = cfg.get_delay(attempt)
                        logger.warning(
                            "Retry %d/%d for %s in %.2fs: %s",
                            attempt + 1,
                            cfg.max_retries,
                            func.__qualname__,
                            delay,
                            str(exc)[:120],
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise classified from exc

            # Should not reach here, but just in case
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
