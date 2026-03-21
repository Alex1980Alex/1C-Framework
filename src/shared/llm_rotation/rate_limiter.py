"""
Token Bucket rate limiter for LLM providers.

Proactive rate limiting: check BEFORE making a request,
not after getting a 429. Each provider gets its own bucket
based on rate_limit_rpm from ProviderConfig.
"""

import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Token bucket rate limiter.

    Args:
        rate: Tokens added per second (rpm / 60).
        capacity: Max tokens (burst size).
    """

    rate: float
    capacity: int
    _tokens: float = field(init=False, default=0.0)
    _last_refill: float = field(init=False, default=0.0)

    def __post_init__(self):
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def consume(self) -> bool:
        """Try to consume one token. Returns True if allowed."""
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def wait_time(self) -> float:
        """Seconds to wait before next token is available."""
        self._refill()
        if self._tokens >= 1.0:
            return 0.0
        return (1.0 - self._tokens) / self.rate if self.rate > 0 else 0.0

    @property
    def available(self) -> float:
        """Current available tokens (fractional)."""
        self._refill()
        return self._tokens

    def reset(self) -> None:
        """Refill bucket to capacity."""
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()


class ProviderRateLimiter:
    """Manages per-provider rate limit buckets.

    Creates a TokenBucket for each provider based on rate_limit_rpm.
    Providers without rpm limits get no bucket (always allowed).
    """

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}

    def register(self, name: str, rpm: int | None) -> None:
        """Register a provider with its RPM limit."""
        if rpm and rpm > 0:
            self._buckets[name] = TokenBucket(
                rate=rpm / 60.0,
                capacity=rpm,
            )

    def can_request(self, name: str) -> bool:
        """Check if provider has available rate limit quota."""
        bucket = self._buckets.get(name)
        if bucket is None:
            return True  # no limit
        return bucket.consume()

    def wait_time(self, name: str) -> float:
        """Get wait time in seconds for provider."""
        bucket = self._buckets.get(name)
        if bucket is None:
            return 0.0
        return bucket.wait_time()

    def get_stats(self, name: str) -> dict:
        """Get rate limit stats for a provider."""
        bucket = self._buckets.get(name)
        if bucket is None:
            return {"limited": False}
        return {
            "limited": True,
            "rpm": int(bucket.rate * 60),
            "available": round(bucket.available, 1),
            "capacity": bucket.capacity,
        }

    def reset(self, name: str) -> None:
        """Reset a provider's bucket to full capacity."""
        bucket = self._buckets.get(name)
        if bucket:
            bucket.reset()
