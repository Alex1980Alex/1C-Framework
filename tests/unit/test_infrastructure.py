"""
Unit tests for memory infrastructure: retry.py and timeout.py.
"""

import pytest

from src.memory.infrastructure.retry import (
    MemoryError,
    PermanentError,
    RetryableError,
    RetryConfig,
    async_retry,
    classify_exception,
)
from src.memory.infrastructure.timeout import TimeoutConfig, get_timeout_config

# ===== RetryConfig Tests =====


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 0.5
        assert cfg.max_delay == 10.0
        assert cfg.jitter is True

    def test_get_delay_increases(self):
        cfg = RetryConfig(base_delay=1.0, jitter=False)
        d0 = cfg.get_delay(0)
        d1 = cfg.get_delay(1)
        d2 = cfg.get_delay(2)
        assert d0 < d1 < d2

    def test_get_delay_capped(self):
        cfg = RetryConfig(base_delay=100.0, max_delay=5.0, jitter=False)
        assert cfg.get_delay(10) == 5.0


# ===== Exception Hierarchy =====


class TestExceptionHierarchy:
    def test_memory_error_has_timestamp(self):
        err = MemoryError("test")
        assert err.timestamp > 0
        assert str(err) == "test"

    def test_memory_error_original(self):
        orig = ValueError("original")
        err = MemoryError("wrapped", original_exception=orig)
        assert err.original_exception is orig

    def test_retryable_is_memory_error(self):
        assert issubclass(RetryableError, MemoryError)

    def test_permanent_is_memory_error(self):
        assert issubclass(PermanentError, MemoryError)


# ===== Exception Classification =====


class TestClassifyException:
    def test_timeout_is_retryable(self):
        result = classify_exception(TimeoutError("timed out"))
        assert isinstance(result, RetryableError)

    def test_connection_error_is_retryable(self):
        result = classify_exception(ConnectionError("connection refused"))
        assert isinstance(result, RetryableError)

    def test_rate_limit_message_is_retryable(self):
        result = classify_exception(Exception("rate limit exceeded"))
        assert isinstance(result, RetryableError)

    def test_404_is_permanent(self):
        result = classify_exception(Exception("not found 404"))
        assert isinstance(result, PermanentError)

    def test_unknown_defaults_retryable(self):
        result = classify_exception(Exception("some random error"))
        assert isinstance(result, RetryableError)

    def test_already_classified(self):
        orig = RetryableError("already retryable")
        result = classify_exception(orig)
        assert result is orig


# ===== @async_retry Decorator =====


class TestAsyncRetry:
    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        calls = 0

        @async_retry()
        async def succeed():
            nonlocal calls
            calls += 1
            return "ok"

        result = await succeed()
        assert result == "ok"
        assert calls == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable(self):
        calls = 0

        @async_retry(RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        async def fail_then_succeed():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RetryableError("temporary")
            return "recovered"

        result = await fail_then_succeed()
        assert result == "recovered"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        @async_retry(RetryConfig(max_retries=1, base_delay=0.01, jitter=False))
        async def always_fail():
            raise RetryableError("permanent failure")

        with pytest.raises(RetryableError, match="permanent failure"):
            await always_fail()

    @pytest.mark.asyncio
    async def test_permanent_not_retried(self):
        calls = 0

        @async_retry(RetryConfig(max_retries=3, base_delay=0.01))
        async def permanent():
            nonlocal calls
            calls += 1
            raise PermanentError("bad request")

        with pytest.raises(PermanentError):
            await permanent()
        assert calls == 1

    @pytest.mark.asyncio
    async def test_smart_classify(self):
        calls = 0

        @async_retry(RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        async def timeout_then_ok():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("timed out")
            return "ok"

        result = await timeout_then_ok()
        assert result == "ok"
        assert calls == 2


# ===== TimeoutConfig Tests =====


class TestTimeoutConfig:
    def test_defaults(self):
        cfg = TimeoutConfig()
        assert cfg.search == 5.0
        assert cfg.backend_default == 10.0
        assert cfg.circuit_breaker_timeout == 60.0

    def test_to_dict(self):
        cfg = TimeoutConfig()
        d = cfg.to_dict()
        assert "search" in d
        assert "backend_default" in d
        assert len(d) >= 10

    def test_singleton(self):
        cfg1 = get_timeout_config()
        cfg2 = get_timeout_config()
        assert cfg1 is cfg2
