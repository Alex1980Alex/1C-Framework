"""
Circuit Breaker for memory subsystem protection.

States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- CLOSED: normal execution, counting failures
- OPEN: skip calls entirely (too many failures)
- HALF_OPEN: try one probe after cooldown

Migrated from:
  - unified-memory-mcp/circuit_breaker.py (496 lines, Redis-backed)
  - .claude/hooks/shared/circuit_breaker.py (142 lines, file-backed)

This version: in-memory state, no external dependencies.

Version: 2.1 (2026-07-17) — HALF_OPEN state machine made real (R1 / roadmap 260716 §3.3,
pipeline fix-circuit-breaker-half-open). Before: `_transition_to(HALF_OPEN)` had no
callers (state stayed raw-OPEN forever), `record_success` tested the raw state so the
CLOSED branch was dead, and `allow_request` gated probes on the LIFETIME success_count —
a breaker with any successful history rejected probes forever. Now the gates
(`allow_request`/`call_async`) COMMIT the OPEN→HALF_OPEN transition via `_sync_state()`
(the `state` property stays a pure view), probes are counted per-episode
(`half_open_probes`), and success/failure branches are reachable again. Reference
semantics: src/shared/llm_rotation/circuit_breaker.py (the working sibling).

Version: 2.0 (2026-04-04) — P1 migration
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    success_threshold: int = 2
    reset_timeout: float = 60.0  # seconds before HALF_OPEN probe
    half_open_max_probes: int = 1


@dataclass
class CircuitStats:
    """Runtime statistics for a circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0  # lifetime telemetry — NOT used for gating (v2.1)
    consecutive_successes: int = 0
    half_open_probes: int = 0  # per-episode probe slots taken (reset on transitions)
    last_failure_time: float = 0.0
    last_failure_error: str = ""
    last_state_change: float = field(default_factory=time.time)
    total_calls: int = 0
    total_failures: int = 0
    total_rejected: int = 0


class CircuitBreakerError(Exception):
    """Raised when circuit is OPEN and call is rejected."""


class CircuitBreaker:
    """
    In-memory circuit breaker with 3 states.

    Thread-safe via asyncio.Lock. No Redis/file dependencies.

    Usage:
        cb = CircuitBreaker("memory-ai", failure_threshold=5)

        # As decorator
        @cb
        async def risky_call():
            ...

        # Manual usage
        if cb.allow_request():
            try:
                result = await some_call()
                cb.record_success()
            except Exception as e:
                cb.record_failure(str(e))
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._stats = CircuitStats()
        self._lock = asyncio.Lock()
        logger.debug(
            "CircuitBreaker '%s' initialized: threshold=%d, timeout=%.0fs",
            name,
            self.config.failure_threshold,
            self.config.reset_timeout,
        )

    @property
    def state(self) -> CircuitState:
        """Current circuit state (with automatic OPEN -> HALF_OPEN transition)."""
        if self._stats.state == CircuitState.OPEN:
            elapsed = time.time() - self._stats.last_failure_time
            if elapsed >= self.config.reset_timeout:
                return CircuitState.HALF_OPEN
        return self._stats.state

    @property
    def stats(self) -> dict[str, Any]:
        """Snapshot of circuit statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._stats.failure_count,
            "success_count": self._stats.success_count,
            "total_calls": self._stats.total_calls,
            "total_failures": self._stats.total_failures,
            "total_rejected": self._stats.total_rejected,
            "last_failure_error": self._stats.last_failure_error,
            "last_state_change": self._stats.last_state_change,
        }

    def allow_request(self) -> bool:
        """Check if a request should be allowed (non-async for sync contexts)."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            # Allow limited probes
            return self._stats.success_count < self.config.half_open_max_probes
        # OPEN
        self._stats.total_rejected += 1
        return False

    async def call_async(self, coro: Awaitable[R]) -> R:
        """
        Execute a coroutine with circuit breaker protection.

        Raises CircuitBreakerError if circuit is OPEN.
        """
        async with self._lock:
            current = self.state
            if current == CircuitState.OPEN:
                self._stats.total_rejected += 1
                # Close unawaited coroutine to prevent ResourceWarning
                if asyncio.iscoroutine(coro):
                    coro.close()
                raise CircuitBreakerError(
                    f"Circuit '{self.name}' is OPEN — rejected after "
                    f"{self._stats.failure_count} failures"
                )

        # total_calls is tracked in record_success/record_failure only
        # to avoid double-counting
        try:
            result = await coro
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(str(e))
            raise

    def record_success(self) -> None:
        """Record successful execution."""
        self._stats.success_count += 1
        self._stats.consecutive_successes += 1
        self._stats.total_calls += 1

        if self._stats.state == CircuitState.HALF_OPEN:
            if self._stats.consecutive_successes >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                logger.info(
                    "Circuit '%s' CLOSED after %d successes",
                    self.name,
                    self._stats.consecutive_successes,
                )
            else:
                # Ниже порога закрытия: освободить probe-слот, иначе при
                # max_probes=1 и success_threshold=2 второй пробе некуда войти
                # и цепь зависает в HALF_OPEN навсегда.
                self._stats.half_open_probes = 0
        elif self._stats.state == CircuitState.CLOSED:
            self._stats.failure_count = 0  # reset on success

    def record_failure(self, error: str = "") -> None:
        """Record failed execution. May transition to OPEN."""
        self._stats.failure_count += 1
        self._stats.consecutive_successes = 0
        self._stats.total_calls += 1
        self._stats.total_failures += 1
        self._stats.last_failure_time = time.time()
        self._stats.last_failure_error = error[:200]

        if self._stats.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
            logger.warning("Circuit '%s' back to OPEN (probe failed)", self.name)
        elif self._stats.state == CircuitState.CLOSED:
            if self._stats.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    "Circuit '%s' OPEN after %d failures: %s",
                    self.name,
                    self._stats.failure_count,
                    error[:100],
                )

    def reset(self) -> None:
        """Force reset to CLOSED state."""
        self._transition_to(CircuitState.CLOSED)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old = self._stats.state
        self._stats.state = new_state
        self._stats.last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            self._stats.failure_count = 0
            self._stats.consecutive_successes = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._stats.consecutive_successes = 0

        logger.debug("Circuit '%s': %s -> %s", self.name, old.value, new_state.value)
        # §27 P1 D1.4: persist real state transitions (reliability incidents) — fail-soft.
        if old != new_state:
            try:
                from .trace_log import write_trace

                write_trace(
                    "memory-circuit.log",
                    "transition",
                    disable_env="MEMORY_CIRCUIT_LOG_DISABLE",
                    circuit=self.name,
                    old=old.value,
                    new=new_state.value,
                    failure_count=self._stats.failure_count,
                    total_failures=self._stats.total_failures,
                    last_error=self._stats.last_failure_error[:160],
                )
            except Exception:
                pass

    def __call__(self, func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        """Decorator for async functions."""

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await self.call_async(func(*args, **kwargs))

        return wrapper

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name='{self.name}' state={self.state.value} "
            f"failures={self._stats.failure_count}/{self.config.failure_threshold}>"
        )


class CircuitBreakerRegistry:
    """
    Registry of named circuit breakers.

    Usage:
        registry = CircuitBreakerRegistry()
        cb = registry.get_or_create("memory-ai", CircuitBreakerConfig(failure_threshold=3))
        status = registry.get_all_stats()
    """

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self, name: str, config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        return self._breakers.get(name)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        return {name: cb.stats for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        for cb in self._breakers.values():
            cb.reset()


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    "CircuitStats",
]
