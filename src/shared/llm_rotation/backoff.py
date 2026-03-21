"""
Exponential backoff with jitter for LLM provider retries.

Prevents thundering herd by adding random jitter to retry delays.
Supports Retry-After header from rate-limited responses.
"""

import random
from dataclasses import dataclass


class RateLimitError(RuntimeError):
    """Raised on HTTP 429 with optional Retry-After value."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class BackoffStrategy:
    """Exponential backoff with jitter and cap.

    Formula: min(base_delay * multiplier^attempt, max_delay) + uniform(0, jitter)
    If retry_after is provided (from HTTP header), uses that + jitter instead.
    """

    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: float = 1.0
    multiplier: float = 2.0

    def compute_delay(self, attempt: int, retry_after: float | None = None) -> float:
        """Compute delay for given attempt number (0-based).

        Args:
            attempt: Zero-based attempt index.
            retry_after: Optional Retry-After value from HTTP 429 response.

        Returns:
            Delay in seconds (always > 0).
        """
        if retry_after is not None and retry_after > 0:
            return retry_after + random.uniform(0, self.jitter)
        delay = min(
            self.base_delay * (self.multiplier ** attempt),
            self.max_delay,
        )
        return delay + random.uniform(0, self.jitter)
