"""
Unit tests for CircuitBreaker (Iteration 1 of LLM Rotation improvements).

Tests state transitions:
  CLOSED → OPEN (after fail_threshold failures)
  OPEN → HALF_OPEN (after reset_timeout)
  HALF_OPEN → CLOSED (after success_threshold successes)
  HALF_OPEN → OPEN (on failure)
"""

import time

from src.shared.llm_rotation.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreakerStates:
    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker(fail_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.fail_count == 2
        assert cb.can_execute()

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(fail_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

    def test_open_rejects_requests(self):
        cb = CircuitBreaker(fail_threshold=1, reset_timeout=999)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()
        assert not cb.can_execute()  # still rejects

    def test_open_to_half_open_after_timeout(self):
        cb = CircuitBreaker(fail_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_one_request(self):
        cb = CircuitBreaker(fail_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.can_execute()  # transitions to HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute()  # HALF_OPEN allows probe

    def test_half_open_to_closed_on_success(self):
        cb = CircuitBreaker(fail_threshold=1, success_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # → HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.fail_count == 0
        assert cb.success_count == 0

    def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker(fail_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # → HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.opened_at is not None

    def test_success_threshold_multiple(self):
        cb = CircuitBreaker(fail_threshold=1, success_threshold=3, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # → HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerSuccessInClosed:
    def test_success_resets_fail_count(self):
        cb = CircuitBreaker(fail_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.fail_count == 2
        cb.record_success()
        assert cb.fail_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_interleaved_success_prevents_opening(self):
        cb = CircuitBreaker(fail_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # resets fail_count
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED  # never reached 3 consecutive


class TestForceOpen:
    def test_force_open(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        cb.force_open()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

    def test_force_open_custom_timeout(self):
        cb = CircuitBreaker(reset_timeout=999)
        cb.force_open(reset_timeout=0.01)
        assert cb.state == CircuitState.OPEN
        assert cb.reset_timeout == 0.01
        time.sleep(0.02)
        assert cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN


class TestReset:
    def test_reset_from_open(self):
        cb = CircuitBreaker(fail_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.fail_count == 0
        assert cb.opened_at is None
        assert cb.can_execute()

    def test_reset_from_half_open(self):
        cb = CircuitBreaker(fail_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # → HALF_OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestFullCycle:
    def test_closed_open_halfopen_closed(self):
        """Full lifecycle: normal → fail → recover → normal."""
        cb = CircuitBreaker(fail_threshold=2, success_threshold=1, reset_timeout=0.01)

        # CLOSED: normal
        assert cb.can_execute()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

        # CLOSED → OPEN: 2 failures
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

        # OPEN → HALF_OPEN: timeout expires
        time.sleep(0.02)
        assert cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

        # HALF_OPEN → CLOSED: success
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_closed_open_halfopen_open_again(self):
        """Recovery fails → back to OPEN."""
        cb = CircuitBreaker(fail_threshold=2, reset_timeout=0.01)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.02)
        cb.can_execute()  # → HALF_OPEN

        cb.record_failure()  # probe fails
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()
