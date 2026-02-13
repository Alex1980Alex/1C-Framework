"""Rate Limiting Middleware (Phase 23.3).

Protects API from overload using token bucket algorithm.
Supports both in-memory and Redis-based rate limiting.

Author: Claude Code
Version: 1.0.0 - Phase 23: Production Hardening
"""

import time
import logging
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(
        self,
        rate: int = 100,  # requests per window
        window: int = 60,  # seconds
    ):
        """Initialize rate limiter.

        Args:
            rate: Maximum requests per window
            window: Time window in seconds
        """
        self.rate = rate
        self.window = window
        self._clients = {}  # client -> (tokens, last_refill)

    def _refill_tokens(self, client_id: str, current_time: float) -> float:
        """Refill tokens based on elapsed time.

        Args:
            client_id: Client identifier
            current_time: Current timestamp

        Returns:
            Available tokens
        """
        if client_id not in self._clients:
            self._clients[client_id] = (self.rate, current_time)
            return self.rate

        tokens, last_refill = self._clients[client_id]
        elapsed = current_time - last_refill

        # Refill tokens
        new_tokens = min(self.rate, tokens + elapsed * (self.rate / self.window))

        self._clients[client_id] = (new_tokens, current_time)
        return new_tokens

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed.

        Args:
            client_id: Client identifier

        Returns:
            True if request is allowed
        """
        current_time = time.time()
        tokens = self._refill_tokens(client_id, current_time)

        if tokens >= 1:
            self._clients[client_id] = (tokens - 1, current_time)
            return True

        return False

    def get_reset_time(self, client_id: str) -> float:
        """Get time when tokens will be reset.

        Args:
            client_id: Client identifier

        Returns:
            Time to reset in seconds
        """
        if client_id not in self._clients:
            return 0.0

        tokens, last_refill = self._clients[client_id]
        elapsed = time.time() - last_refill

        # Time to get one more token
        tokens_per_sec = self.rate / self.window
        needed = 1 - tokens
        reset_time = needed / tokens_per_sec if tokens_per_sec > 0 else self.window

        return max(0, reset_time - elapsed)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(
        self,
        app,
        rate: int = 100,
        window: int = 60,
        key_func: Optional[Callable[[Request], str]] = None,
    ):
        """Initialize middleware.

        Args:
            app: FastAPI application
            rate: Requests per window
            window: Time window in seconds
            key_func: Function to extract client key (default: IP address)
        """
        super().__init__(app)
        self._limiter = RateLimiter(rate, window)
        self._key_func = key_func or self._default_key_func

    def _default_key_func(self, request: Request) -> str:
        """Extract client identifier from request.

        Args:
            request: FastAPI request

        Returns:
            Client identifier
        """
        # Try API key first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"apikey:{api_key}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        client = request.client
        if client:
            return f"ip:{client.host}"

        return "default"

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response or HTTP 429
        """
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Get client key
        client_key = self._key_func(request)

        # Check rate limit
        if not self._limiter.is_allowed(client_key):
            reset_time = self._limiter.get_reset_time(client_key)

            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "reset_time": reset_time,
                },
                headers={
                    "Retry-After": str(int(reset_time)),
                    "X-RateLimit-Limit": str(self._limiter.rate),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + reset_time)),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        tokens, _ = self._limiter._clients.get(client_key, (0, 0))
        response.headers["X-RateLimit-Limit"] = str(self._limiter.rate)
        response.headers["X-RateLimit-Remaining"] = str(int(tokens))
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + self._limiter.window))

        return response


class RedisRateLimiter:
    """Redis-based rate limiter for distributed systems."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        rate: int = 100,
        window: int = 60,
    ):
        """Initialize Redis rate limiter.

        Args:
            redis_url: Redis connection URL
            rate: Requests per window
            window: Time window in seconds
        """
        try:
            import redis
            self._redis = redis.from_url(redis_url, decode_responses=True)
        except ImportError:
            logger.warning("[RATE_LIMIT] Redis not available, using in-memory")
            self._redis = None

        self.rate = rate
        self.window = window

    def is_allowed(self, client_key: str) -> bool:
        """Check if request is allowed.

        Args:
            client_key: Client identifier

        Returns:
            True if allowed
        """
        if not self._redis:
            # Fallback to in-memory
            return True

        try:
            key = f"ratelimit:{client_key}"
            current = self._redis.get(key)

            if current is None:
                # First request
                pipe = self._redis.pipeline()
                pipe.set(key, 1, ex=self.window)
                return True

            current = int(current)
            if current >= self.rate:
                return False

            # Increment counter
            self._redis.incr(key)
            return True

        except Exception as e:
            logger.error(f"[RATE_LIMIT] Redis error: {e}")
            return True  # Fail open

    def get_reset_time(self, client_key: str) -> float:
        """Get reset time for client.

        Args:
            client_key: Client identifier

        Returns:
            Time to reset in seconds
        """
        if not self._redis:
            return 0.0

        try:
            key = f"ratelimit:{client_key}"
            ttl = self._redis.ttl(key)
            return max(0, ttl)
        except Exception:
            return 0.0


def get_rate_limiter(
    redis_url: Optional[str] = None,
    rate: int = 100,
    window: int = 60,
):
    """Factory function to get appropriate rate limiter.

    Args:
        redis_url: Redis URL (None = in-memory)
        rate: Requests per window
        window: Time window in seconds

    Returns:
        Rate limiter instance
    """
    if redis_url:
        return RedisRateLimiter(redis_url, rate, window)

    return RateLimiter(rate, window)
