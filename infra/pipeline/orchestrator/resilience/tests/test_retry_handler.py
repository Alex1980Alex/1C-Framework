"""Tests for retry_handler module."""

import pytest
import asyncio
import time

from .retry_handler import (
    BackoffStrategy,
    RetryConfig,
    RetryResult,
    RetryHandler,
    with_retry,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitOpenError,
    with_circuit_breaker,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert config.jitter is True

    def test_constant_delay(self):
        """Test constant backoff strategy."""
        config = RetryConfig(
            backoff_strategy=BackoffStrategy.CONSTANT,
            initial_delay=2.0,
            jitter=False,
        )

        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 2.0
        assert config.calculate_delay(5) == 2.0

    def test_linear_delay(self):
        """Test linear backoff strategy."""
        config = RetryConfig(
            backoff_strategy=BackoffStrategy.LINEAR,
            initial_delay=1.0,
            jitter=False,
        )

        assert config.calculate_delay(1) == 1.0
        assert config.calculate_delay(2) == 2.0
        assert config.calculate_delay(3) == 3.0

    def test_exponential_delay(self):
        """Test exponential backoff strategy."""
        config = RetryConfig(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            initial_delay=1.0,
            backoff_multiplier=2.0,
            jitter=False,
        )

        assert config.calculate_delay(1) == 1.0
        assert config.calculate_delay(2) == 2.0
        assert config.calculate_delay(3) == 4.0
        assert config.calculate_delay(4) == 8.0

    def test_fibonacci_delay(self):
        """Test Fibonacci backoff strategy."""
        config = RetryConfig(
            backoff_strategy=BackoffStrategy.FIBONACCI,
            initial_delay=1.0,
            jitter=False,
        )

        # Current implementation fibonacci sequence: 1, 2, 3, 5, 8...
        # (starting from n=1, not n=0)
        assert config.calculate_delay(1) == 1.0
        assert config.calculate_delay(2) == 2.0
        assert config.calculate_delay(3) == 3.0
        assert config.calculate_delay(4) == 5.0
        assert config.calculate_delay(5) == 8.0

    def test_max_delay_cap(self):
        """Test max delay cap."""
        config = RetryConfig(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            initial_delay=10.0,
            max_delay=20.0,
            jitter=False,
        )

        # Delay would be 10 * 2^4 = 160, but capped at 20
        assert config.calculate_delay(5) == 20.0

    def test_jitter(self):
        """Test jitter adds randomness."""
        config = RetryConfig(
            backoff_strategy=BackoffStrategy.CONSTANT,
            initial_delay=10.0,
            jitter=True,
            jitter_factor=0.25,
        )

        delays = [config.calculate_delay(1) for _ in range(10)]
        # Should have variation due to jitter
        assert min(delays) != max(delays)
        # Should be within jitter range (10 +/- 25% = 7.5 to 12.5)
        assert all(7.5 <= d <= 12.5 for d in delays)


class TestRetryResult:
    """Tests for RetryResult."""

    def test_success_result(self):
        """Test successful result."""
        result = RetryResult(
            success=True,
            result="value",
            attempts=2,
            total_delay=1.5,
        )

        assert result.success is True
        assert result.failed is False
        assert result.result == "value"

    def test_failed_result(self):
        """Test failed result."""
        error = ValueError("Test error")
        result = RetryResult(
            success=False,
            attempts=3,
            last_exception=error,
            exceptions=[error],
        )

        assert result.success is False
        assert result.failed is True
        assert result.last_exception is error


class TestRetryHandler:
    """Tests for RetryHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler with fast retries."""
        config = RetryConfig(
            max_retries=3,
            initial_delay=0.01,
            jitter=False,
        )
        return RetryHandler(config)

    @pytest.mark.asyncio
    async def test_success_on_first_try(self, handler):
        """Test success on first attempt."""
        async def success_func():
            return "success"

        result = await handler.execute(success_func)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_success_on_retry(self, handler):
        """Test success after retry."""
        attempts = {"count": 0}

        async def fail_then_succeed():
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise ValueError("First attempt fails")
            return "success"

        result = await handler.execute(fail_then_succeed)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, handler):
        """Test failure after max retries."""
        async def always_fail():
            raise ValueError("Always fails")

        result = await handler.execute(always_fail)

        assert result.success is False
        assert result.attempts == 3
        assert len(result.exceptions) == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self, handler):
        """Test non-retryable exception raises immediately."""
        async def keyboard_interrupt():
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            await handler.execute(keyboard_interrupt)

        assert handler.attempt_count == 1

    def test_sync_execution(self, handler):
        """Test synchronous execution."""
        def sync_func():
            return "sync result"

        result = handler.execute_sync(sync_func)

        assert result.success is True
        assert result.result == "sync result"

    def test_callbacks(self):
        """Test retry callbacks."""
        retry_calls = []
        failure_calls = []

        config = RetryConfig(
            max_retries=2,
            initial_delay=0.01,
            on_retry=lambda attempt, exc, delay: retry_calls.append(attempt),
            on_failure=lambda exc: failure_calls.append(str(exc)),
        )
        handler = RetryHandler(config)

        def always_fail():
            raise ValueError("Fail")

        result = handler.execute_sync(always_fail)

        assert result.failed
        assert retry_calls == [1]  # One retry callback before final failure
        assert len(failure_calls) == 1


class TestWithRetryDecorator:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_async_decorator_success(self):
        """Test decorator with async function success."""
        @with_retry(max_retries=3, initial_delay=0.01)
        async def async_func():
            return "async result"

        result = await async_func()
        assert result == "async result"

    @pytest.mark.asyncio
    async def test_async_decorator_retry(self):
        """Test decorator retry behavior."""
        attempts = {"count": 0}

        @with_retry(max_retries=3, initial_delay=0.01)
        async def retry_func():
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise ValueError("Retry")
            return "success"

        result = await retry_func()
        assert result == "success"
        assert attempts["count"] == 2

    def test_sync_decorator(self):
        """Test decorator with sync function."""
        @with_retry(max_retries=2, initial_delay=0.01)
        def sync_func():
            return "sync"

        result = sync_func()
        assert result == "sync"


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.fixture
    def circuit(self):
        """Create circuit breaker with low thresholds."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0.1,
        )
        return CircuitBreaker(config)

    def test_initial_state(self, circuit):
        """Test initial state is CLOSED."""
        assert circuit.state == CircuitState.CLOSED
        assert circuit.is_closed is True
        assert circuit.is_open is False

    @pytest.mark.asyncio
    async def test_success_keeps_closed(self, circuit):
        """Test successful calls keep circuit closed."""
        async def success():
            return "ok"

        for _ in range(5):
            result = await circuit.call(success)
            assert result == "ok"

        assert circuit.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self, circuit):
        """Test failures open the circuit."""
        async def fail():
            raise ValueError("Fail")

        # Two failures should open circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit.call(fail)

        assert circuit.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects(self, circuit):
        """Test open circuit rejects calls."""
        async def fail():
            raise ValueError("Fail")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit.call(fail)

        # Now calls should be rejected
        async def any_call():
            return "ok"

        with pytest.raises(CircuitOpenError):
            await circuit.call(any_call)

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, circuit):
        """Test circuit goes to HALF_OPEN after timeout."""
        async def fail():
            raise ValueError("Fail")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit.call(fail)

        assert circuit.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Next call should transition to HALF_OPEN
        async def success():
            return "ok"

        result = await circuit.call(success)
        # After success in HALF_OPEN, might go back to CLOSED
        assert circuit.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]

    def test_reset(self, circuit):
        """Test manual reset."""
        circuit._state = CircuitState.OPEN
        circuit._failure_count = 5

        circuit.reset()

        assert circuit.state == CircuitState.CLOSED
        assert circuit._failure_count == 0


class TestCircuitBreakerDecorator:
    """Tests for with_circuit_breaker decorator."""

    @pytest.mark.asyncio
    async def test_decorator(self):
        """Test circuit breaker decorator."""
        config = CircuitBreakerConfig(failure_threshold=3)
        circuit = CircuitBreaker(config)

        @with_circuit_breaker(circuit)
        async def protected_func():
            return "protected"

        result = await protected_func()
        assert result == "protected"
