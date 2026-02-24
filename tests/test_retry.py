"""Tests for retry utilities (src.pdf_framework.utils.retry)."""

from __future__ import annotations

import pytest

from src.pdf_framework.utils.retry import (
    create_retry,
    retry_db_operation,
    retry_embedding,
    retry_llm_call,
    retry_network,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeRateLimitError(ConnectionError):
    """Simulates an API rate-limit (subclass of ConnectionError)."""


class FakeTimeoutError(TimeoutError):
    """Simulates an API timeout."""


# ---------------------------------------------------------------------------
# retry_llm_call
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRetryLLMCall:
    """Tests for the retry_llm_call decorator."""

    def test_succeeds_without_retry(self):
        """Function that succeeds on first call should return normally."""
        call_count = 0

        @retry_llm_call
        def always_ok() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = always_ok()
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_connection_error(self):
        """Should retry on ConnectionError and succeed when error clears."""
        call_count = 0

        @retry_llm_call
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise FakeRateLimitError("rate limit")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 3

    def test_retries_on_timeout_error(self):
        """Should retry on TimeoutError."""
        call_count = 0

        @retry_llm_call
        def slow_api() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise FakeTimeoutError("timeout")
            return "done"

        result = slow_api()
        assert result == "done"
        assert call_count == 2

    def test_does_not_retry_on_value_error(self):
        """ValueError is a programming error and must NOT be retried."""

        @retry_llm_call
        def bad_input() -> None:
            raise ValueError("invalid argument")

        with pytest.raises(ValueError, match="invalid argument"):
            bad_input()

    def test_reraises_after_exhaustion(self):
        """When all attempts fail, the original exception is re-raised."""

        @retry_llm_call
        def always_fails() -> None:
            raise ConnectionError("permanently down")

        with pytest.raises(ConnectionError, match="permanently down"):
            always_fails()


# ---------------------------------------------------------------------------
# retry_db_operation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRetryDBOperation:
    """Tests for the retry_db_operation decorator."""

    def test_stops_after_max_attempts(self):
        """Should stop after exactly 3 attempts (the configured maximum)."""
        call_count = 0

        @retry_db_operation
        def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("db unavailable")

        with pytest.raises(ConnectionError):
            always_fails()

        assert call_count == 3

    def test_succeeds_on_last_attempt(self):
        """Should succeed when the function recovers on the last attempt."""
        call_count = 0

        @retry_db_operation
        def recovers_on_third() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("db timeout")
            return "connected"

        result = recovers_on_third()
        assert result == "connected"
        assert call_count == 3


# ---------------------------------------------------------------------------
# Async retry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAsyncRetry:
    """Tests that retry decorators work with async functions."""

    async def test_async_retry_llm_call(self):
        """retry_llm_call should work transparently with async functions."""
        call_count = 0

        @retry_llm_call
        async def async_llm() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("rate limit")
            return "async ok"

        result = await async_llm()
        assert result == "async ok"
        assert call_count == 2

    async def test_async_retry_db_operation(self):
        """retry_db_operation should work transparently with async functions."""
        call_count = 0

        @retry_db_operation
        async def async_db() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("db timeout")
            return "stored"

        result = await async_db()
        assert result == "stored"
        assert call_count == 2

    async def test_async_reraises_after_exhaustion(self):
        """Async: original exception is re-raised when all attempts fail."""

        @retry_db_operation
        async def always_fails() -> None:
            raise OSError("disk full")

        with pytest.raises(OSError, match="disk full"):
            await always_fails()


# ---------------------------------------------------------------------------
# create_retry (factory)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateRetry:
    """Tests for the create_retry factory function."""

    def test_custom_max_attempts(self):
        """create_retry should respect custom max_attempts."""
        call_count = 0
        custom = create_retry(max_attempts=7, retry_on=(RuntimeError,))

        @custom
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 7:
                raise RuntimeError("transient")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 7

    def test_custom_exception_types(self):
        """create_retry should only retry specified exception types."""
        custom = create_retry(max_attempts=5, retry_on=(KeyError,))

        @custom
        def raises_type_error() -> None:
            raise TypeError("wrong type")

        # TypeError is NOT in retry_on, so it should propagate immediately
        with pytest.raises(TypeError, match="wrong type"):
            raises_type_error()

    def test_custom_retry_on_key_error(self):
        """create_retry should retry the specified exception type."""
        call_count = 0
        custom = create_retry(max_attempts=3, retry_on=(KeyError,))

        @custom
        def sometimes_missing() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise KeyError("missing")
            return "found"

        result = sometimes_missing()
        assert result == "found"
        assert call_count == 2

    async def test_custom_retry_async(self):
        """create_retry should work with async functions."""
        call_count = 0
        custom = create_retry(max_attempts=4, retry_on=(ConnectionError,))

        @custom
        async def async_flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("flaky")
            return "stable"

        result = await async_flaky()
        assert result == "stable"
        assert call_count == 3


# ---------------------------------------------------------------------------
# retry_embedding & retry_network (smoke tests)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRetryEmbeddingAndNetwork:
    """Smoke tests for retry_embedding and retry_network."""

    def test_retry_embedding_retries_runtime_error(self):
        """retry_embedding should retry on RuntimeError (model loading)."""
        call_count = 0

        @retry_embedding
        def load_model() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("CUDA OOM")
            return "loaded"

        result = load_model()
        assert result == "loaded"
        assert call_count == 2

    def test_retry_network_retries_os_error(self):
        """retry_network should retry on OSError."""
        call_count = 0

        @retry_network
        def fetch() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("network unreachable")
            return "fetched"

        result = fetch()
        assert result == "fetched"
        assert call_count == 2
