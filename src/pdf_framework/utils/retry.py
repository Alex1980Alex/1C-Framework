"""Retry utilities for PDF Framework based on tenacity.

Provides pre-configured retry decorators for common I/O scenarios:
LLM API calls, embedding API, database operations, network requests.

All decorators work transparently with both sync and async functions.

Usage::

    from src.pdf_framework.utils.retry import retry_llm_call, retry_db_operation

    @retry_llm_call
    async def call_llm(prompt: str) -> str:
        return await client.chat(prompt)

    @retry_db_operation
    async def upsert(collection: str, points: list) -> None:
        await qdrant.upsert(collection, points)

For custom retry logic::

    from src.pdf_framework.utils.retry import create_retry

    my_retry = create_retry(max_attempts=10, initial_wait=0.5, max_wait=30.0)

    @my_retry
    async def custom_operation() -> None: ...
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
    wait_fixed,
)

__all__ = [
    "retry_llm_call",
    "retry_embedding",
    "retry_db_operation",
    "retry_network",
    "create_retry",
]

logger = logging.getLogger("pdf_framework.retry")

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Logging callback
# ---------------------------------------------------------------------------


def _log_before_retry(retry_state: RetryCallState) -> None:
    """Log each retry attempt with context."""
    fn = retry_state.fn
    fn_name = getattr(fn, "__qualname__", getattr(fn, "__name__", str(fn)))
    attempt = retry_state.attempt_number
    outcome = retry_state.outcome

    if outcome and outcome.failed:
        exc = outcome.exception()
        logger.warning(
            "Retry %s attempt #%d after %s: %s",
            fn_name,
            attempt,
            type(exc).__name__,
            exc,
        )
    else:
        logger.info("Retry %s attempt #%d", fn_name, attempt)


# ---------------------------------------------------------------------------
# Exception groups for each scenario
# ---------------------------------------------------------------------------

# LLM API: rate limits, transient server errors, timeouts
_LLM_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
)

# Embedding API: similar to LLM but includes RuntimeError for model loading
_EMBEDDING_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
    RuntimeError,
)

# Database: connection and timeout issues
_DB_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
)

# Network: broad transport-level errors
_NETWORK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
)


# ---------------------------------------------------------------------------
# Pre-configured decorators
# ---------------------------------------------------------------------------


retry_llm_call = retry(
    stop=stop_after_attempt(5) | stop_after_delay(120),
    wait=wait_exponential_jitter(initial=1, max=60, jitter=2),
    retry=retry_if_exception_type(_LLM_EXCEPTIONS),
    before_sleep=_log_before_retry,
    reraise=True,
)
"""Retry for LLM API calls (rate limits, timeouts).

- Up to 5 attempts or 120 seconds total
- Exponential backoff: 1s -> 2s -> 4s ... capped at 60s, +/- 2s jitter
- Retries on: TimeoutError, ConnectionError, OSError
- Reraises original exception when exhausted
"""


retry_embedding = retry(
    stop=stop_after_attempt(5) | stop_after_delay(90),
    wait=wait_exponential_jitter(initial=0.5, max=30, jitter=1),
    retry=retry_if_exception_type(_EMBEDDING_EXCEPTIONS),
    before_sleep=_log_before_retry,
    reraise=True,
)
"""Retry for embedding API calls.

- Up to 5 attempts or 90 seconds total
- Exponential backoff: 0.5s -> 1s -> 2s ... capped at 30s, +/- 1s jitter
- Retries on: TimeoutError, ConnectionError, OSError, RuntimeError
- Reraises original exception when exhausted
"""


retry_db_operation = retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(0.5),
    retry=retry_if_exception_type(_DB_EXCEPTIONS),
    before_sleep=_log_before_retry,
    reraise=True,
)
"""Retry for database operations (Qdrant, SQLite).

- Up to 3 attempts
- Fixed 0.5s wait (DB ops are fast, no point in long backoff)
- Retries on: TimeoutError, ConnectionError, OSError
- Reraises original exception when exhausted
"""


retry_network = retry(
    stop=stop_after_attempt(4) | stop_after_delay(60),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    retry=retry_if_exception_type(_NETWORK_EXCEPTIONS),
    before_sleep=_log_before_retry,
    reraise=True,
)
"""Retry for HTTP/network operations.

- Up to 4 attempts or 60 seconds total
- Exponential backoff: 1s -> 2s -> 4s ... capped at 30s, +/- 2s jitter
- Retries on: TimeoutError, ConnectionError, OSError
- Reraises original exception when exhausted
"""


# ---------------------------------------------------------------------------
# Factory for custom retry configs
# ---------------------------------------------------------------------------


def create_retry(
    *,
    max_attempts: int = 3,
    max_delay: float | None = None,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: float = 1.0,
    retry_on: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError, OSError),
) -> retry:
    """Create a custom retry decorator.

    Args:
        max_attempts: Maximum number of retry attempts.
        max_delay: Optional overall time limit in seconds.
        initial_wait: Initial backoff wait in seconds.
        max_wait: Maximum wait between retries in seconds.
        jitter: Jitter added to wait time in seconds.
        retry_on: Tuple of exception types to retry on.

    Returns:
        A tenacity ``retry`` decorator configured with given parameters.

    Example::

        my_retry = create_retry(max_attempts=10, initial_wait=0.5)

        @my_retry
        async def fragile_call() -> str: ...
    """
    stop_condition = stop_after_attempt(max_attempts)
    if max_delay is not None:
        stop_condition = stop_condition | stop_after_delay(max_delay)

    return retry(
        stop=stop_condition,
        wait=wait_exponential_jitter(initial=initial_wait, max=max_wait, jitter=jitter),
        retry=retry_if_exception_type(retry_on),
        before_sleep=_log_before_retry,
        reraise=True,
    )
