from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"


@dataclass
class CircuitBreaker:
    fail_threshold: int = 3
    window_seconds: float = 600.0
    reset_timeout: float = 60.0
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_times: list[float] = field(default_factory=list, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _clock: object = field(default=time, init=False)

    def is_open(self) -> bool:
        """Check if circuit is open; auto-reset after reset_timeout."""
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            now = self._now()
            if now - self._opened_at >= self.reset_timeout:
                self._state = CircuitState.CLOSED
                self._failure_times.clear()
                self._opened_at = None
                return False
            return True
        return False

    def record_success(self) -> None:
        """Record a successful operation; clear failure window when closed."""
        if self._state == CircuitState.CLOSED:
            self._failure_times.clear()

    def record_failure(self) -> None:
        """Record a failure; trip breaker when threshold reached within window."""
        if self._state == CircuitState.OPEN:
            return
        now = self._now()
        self._failure_times.append(now)
        cutoff = now - self.window_seconds
        self._failure_times = [t for t in self._failure_times if t >= cutoff]
        if len(self._failure_times) >= self.fail_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = now

    def force_open(self, reason: str = "") -> None:
        """Force the circuit into open state."""
        self._state = CircuitState.OPEN
        self._opened_at = self._now()

    def reset(self) -> None:
        """Reset the circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_times.clear()
        self._opened_at = None

    def _now(self) -> float:
        return self._clock.monotonic()  # type: ignore[attr-defined]

    @property
    def failure_count(self) -> int:
        """Return pruned count of failures within the current window."""
        now = self._now()
        cutoff = now - self.window_seconds
        self._failure_times = [t for t in self._failure_times if t >= cutoff]
        return len(self._failure_times)
