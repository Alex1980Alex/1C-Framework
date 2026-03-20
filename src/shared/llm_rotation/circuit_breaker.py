"""
Circuit Breaker pattern for LLM provider resilience.

Three states:
- CLOSED: normal operation, requests pass through
- OPEN: provider failing, requests rejected (fast fail)
- HALF_OPEN: testing recovery, one probe request allowed

Transitions:
- CLOSED → OPEN: after `fail_threshold` consecutive failures
- OPEN → HALF_OPEN: after `reset_timeout` seconds
- HALF_OPEN → CLOSED: after `success_threshold` successful probes
- HALF_OPEN → OPEN: on any failure during probe
"""

import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-provider circuit breaker with configurable thresholds."""

    __slots__ = (
        "state", "fail_count", "success_count",
        "fail_threshold", "success_threshold", "reset_timeout",
        "opened_at",
    )

    def __init__(
        self,
        fail_threshold: int = 3,
        success_threshold: int = 1,
        reset_timeout: float = 60.0,
    ):
        self.state = CircuitState.CLOSED
        self.fail_count = 0
        self.success_count = 0
        self.fail_threshold = fail_threshold
        self.success_threshold = success_threshold
        self.reset_timeout = reset_timeout
        self.opened_at: float | None = None

    def can_execute(self) -> bool:
        """Check if a request is allowed through the breaker."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self.opened_at is not None and time.monotonic() - self.opened_at >= self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        # HALF_OPEN: allow one probe request
        return True

    def record_success(self) -> None:
        """Record a successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.fail_count = 0
                self.success_count = 0
        else:
            self.fail_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self.success_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self._open()
        else:
            self.fail_count += 1
            if self.fail_count >= self.fail_threshold:
                self._open()

    def force_open(self, reset_timeout: float | None = None) -> None:
        """Force breaker open (e.g. on rate limit — immediate trip)."""
        if reset_timeout is not None:
            self.reset_timeout = reset_timeout
        self._open()

    def reset(self) -> None:
        """Reset breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.fail_count = 0
        self.success_count = 0
        self.opened_at = None

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self.opened_at = time.monotonic()
