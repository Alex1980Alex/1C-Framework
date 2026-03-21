"""
Unit tests for BackoffStrategy, RateLimitError (Iteration 2),
and Health Check integration (Iteration 3).

Tests:
- Exponential delay growth
- Jitter bounds
- Max delay cap
- Retry-After header support
- RateLimitError exception
"""

import random

from src.shared.llm_rotation.backoff import BackoffStrategy, RateLimitError


class TestBackoffStrategy:
    def test_first_attempt_base_delay(self):
        random.seed(42)
        bs = BackoffStrategy(base_delay=1.0, jitter=0.0)
        delay = bs.compute_delay(attempt=0)
        assert delay == 1.0

    def test_exponential_growth(self):
        bs = BackoffStrategy(base_delay=1.0, multiplier=2.0, jitter=0.0)
        assert bs.compute_delay(0) == 1.0   # 1 * 2^0
        assert bs.compute_delay(1) == 2.0   # 1 * 2^1
        assert bs.compute_delay(2) == 4.0   # 1 * 2^2
        assert bs.compute_delay(3) == 8.0   # 1 * 2^3

    def test_max_delay_cap(self):
        bs = BackoffStrategy(base_delay=1.0, multiplier=2.0, max_delay=5.0, jitter=0.0)
        assert bs.compute_delay(0) == 1.0
        assert bs.compute_delay(1) == 2.0
        assert bs.compute_delay(2) == 4.0
        assert bs.compute_delay(3) == 5.0  # capped at max_delay
        assert bs.compute_delay(10) == 5.0  # still capped

    def test_jitter_adds_randomness(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=1.0, multiplier=2.0)
        delays = [bs.compute_delay(0) for _ in range(100)]
        # All delays should be in [1.0, 2.0) (base + jitter range)
        assert all(1.0 <= d < 2.0 for d in delays)
        # Not all the same (jitter adds variation)
        assert len(set(delays)) > 1

    def test_jitter_bounds(self):
        bs = BackoffStrategy(base_delay=2.0, jitter=3.0, multiplier=1.0)
        delays = [bs.compute_delay(0) for _ in range(1000)]
        assert all(2.0 <= d < 5.0 for d in delays)

    def test_retry_after_overrides_exponential(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=0.0, multiplier=2.0)
        delay = bs.compute_delay(attempt=5, retry_after=10.0)
        assert delay == 10.0  # retry_after used, not exponential

    def test_retry_after_with_jitter(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=2.0)
        delays = [bs.compute_delay(attempt=0, retry_after=5.0) for _ in range(100)]
        assert all(5.0 <= d < 7.0 for d in delays)

    def test_retry_after_zero_falls_back_to_exponential(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=0.0, multiplier=2.0)
        delay = bs.compute_delay(attempt=2, retry_after=0.0)
        assert delay == 4.0  # 0 or negative → use exponential

    def test_retry_after_negative_falls_back(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=0.0, multiplier=2.0)
        delay = bs.compute_delay(attempt=1, retry_after=-1.0)
        assert delay == 2.0  # negative → use exponential

    def test_custom_multiplier(self):
        bs = BackoffStrategy(base_delay=1.0, multiplier=3.0, jitter=0.0)
        assert bs.compute_delay(0) == 1.0   # 1 * 3^0
        assert bs.compute_delay(1) == 3.0   # 1 * 3^1
        assert bs.compute_delay(2) == 9.0   # 1 * 3^2

    def test_default_values(self):
        bs = BackoffStrategy()
        assert bs.base_delay == 1.0
        assert bs.max_delay == 30.0
        assert bs.jitter == 1.0
        assert bs.multiplier == 2.0


class TestRateLimitError:
    def test_basic(self):
        err = RateLimitError("rate limited")
        assert str(err) == "rate limited"
        assert err.retry_after is None

    def test_with_retry_after(self):
        err = RateLimitError("429 Too Many Requests", retry_after=30.0)
        assert err.retry_after == 30.0
        assert isinstance(err, RuntimeError)

    def test_no_retry_after(self):
        err = RateLimitError("429")
        assert err.retry_after is None


class TestParseRetryAfter:
    def test_valid_integer(self):
        from src.shared.llm_rotation.service import _parse_retry_after
        assert _parse_retry_after("30") == 30.0

    def test_valid_float(self):
        from src.shared.llm_rotation.service import _parse_retry_after
        assert _parse_retry_after("1.5") == 1.5

    def test_none(self):
        from src.shared.llm_rotation.service import _parse_retry_after
        assert _parse_retry_after(None) is None

    def test_empty_string(self):
        from src.shared.llm_rotation.service import _parse_retry_after
        assert _parse_retry_after("") is None

    def test_invalid(self):
        from src.shared.llm_rotation.service import _parse_retry_after
        assert _parse_retry_after("not-a-number") is None


# ========== Health Check Tests (Iteration 3) ==========

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.shared.llm_rotation.circuit_breaker import CircuitBreaker, CircuitState
from src.shared.llm_rotation.config import LLMRotationSettings
from src.shared.llm_rotation.service import (
    LLMRotationService,
    ProviderConfig,
)


class TestHealthCheck:
    def _make_service(self, **kwargs) -> LLMRotationService:
        configs = [
            ProviderConfig(
                name="test-provider", base_url="http://test",
                api_key_env="", default_model="m", requires_key=False,
            ),
        ]
        defaults = dict(health_check_enabled=True, health_check_interval=1)
        defaults.update(kwargs)
        settings = LLMRotationSettings(**defaults)
        return LLMRotationService(providers=configs, settings=settings)

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        service = self._make_service()
        service.start_health_checks()
        assert service._health_task is not None
        assert not service._health_task.done()
        service.stop_health_checks()
        assert service._health_task is None

    def test_start_disabled(self):
        service = self._make_service(health_check_enabled=False)
        service.start_health_checks()
        assert service._health_task is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        service = self._make_service()
        service.start_health_checks()
        task1 = service._health_task
        service.start_health_checks()  # should not create new task
        assert service._health_task is task1
        service.stop_health_checks()

    @pytest.mark.asyncio
    async def test_health_loop_recovers_provider(self):
        """OPEN provider recovers after successful health probe."""
        service = self._make_service()
        state = service._providers["test-provider"]
        state.circuit_breaker = CircuitBreaker(fail_threshold=1, reset_timeout=0.01)
        state.circuit_breaker.record_failure()
        assert state.circuit_breaker.state == CircuitState.OPEN

        import time
        time.sleep(0.02)

        mock_response = {
            "provider": "test-provider", "model": "m", "text": "pong",
            "response_time": 0.1, "usage": {},
        }

        async def mock_call_provider(*args, **kwargs):
            # _call_provider calls state.record_success() internally
            state.record_success(0.1)
            return mock_response

        with patch.object(service, "_call_provider", new_callable=AsyncMock, side_effect=mock_call_provider):
            await service._health_check_loop_once()

        assert state.circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_health_loop_keeps_open_on_failure(self):
        """OPEN provider stays open if health probe fails."""
        service = self._make_service()
        state = service._providers["test-provider"]
        state.circuit_breaker = CircuitBreaker(fail_threshold=1, reset_timeout=0.01)
        state.circuit_breaker.record_failure()

        import time
        time.sleep(0.02)

        with patch.object(service, "_call_provider", new_callable=AsyncMock, side_effect=RuntimeError("down")):
            await service._health_check_loop_once()

        assert state.circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_health_skips_closed_providers(self):
        """Healthy providers should not be probed."""
        service = self._make_service()
        state = service._providers["test-provider"]
        assert state.circuit_breaker.state == CircuitState.CLOSED

        with patch.object(service, "_call_provider", new_callable=AsyncMock) as mock_call:
            await service._health_check_loop_once()
            mock_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_health_skips_providers_in_timeout(self):
        """OPEN provider within reset_timeout should not be probed."""
        service = self._make_service()
        state = service._providers["test-provider"]
        state.circuit_breaker = CircuitBreaker(fail_threshold=1, reset_timeout=999)
        state.circuit_breaker.record_failure()
        assert state.circuit_breaker.state == CircuitState.OPEN

        with patch.object(service, "_call_provider", new_callable=AsyncMock) as mock_call:
            await service._health_check_loop_once()
            mock_call.assert_not_called()  # still within timeout

    @pytest.mark.asyncio
    async def test_close_stops_health_checks(self):
        service = self._make_service()
        service.start_health_checks()
        assert service._health_task is not None
        await service.close()
        assert service._health_task is None


# ========== Multi-level Failover Tests (Iteration 4) ==========


class TestIsTransient:
    def test_timeout(self):
        assert LLMRotationService._is_transient(RuntimeError("Connection timeout"))

    def test_rate_limit(self):
        assert LLMRotationService._is_transient(RuntimeError("HTTP 429 rate limit"))

    def test_server_errors(self):
        assert LLMRotationService._is_transient(RuntimeError("HTTP 500 Internal"))
        assert LLMRotationService._is_transient(RuntimeError("HTTP 502 Bad Gateway"))
        assert LLMRotationService._is_transient(RuntimeError("HTTP 503 Unavailable"))

    def test_connection_error(self):
        assert LLMRotationService._is_transient(RuntimeError("Connection refused"))

    def test_non_transient(self):
        assert not LLMRotationService._is_transient(RuntimeError("HTTP 400 Bad Request"))
        assert not LLMRotationService._is_transient(RuntimeError("Invalid API key"))
        assert not LLMRotationService._is_transient(RuntimeError("Model not found"))


class TestMultiLevelFailover:
    @pytest.mark.asyncio
    async def test_model_fallback_on_transient(self):
        """Transient error on default model → tries alt model of same provider."""
        configs = [
            ProviderConfig(
                name="multi", base_url="http://m", api_key_env="",
                default_model="model-a", models=["model-a", "model-b"],
                requires_key=False,
            ),
        ]
        service = LLMRotationService(providers=configs)
        call_models = []

        async def mock_call(state, prompt, system_prompt=None, model=None, temperature=0.7, max_tokens=2048):
            call_models.append(model)
            if model == "model-a":
                raise RuntimeError("HTTP 500 Internal Server Error")
            return {
                "provider": "multi", "model": model, "text": "ok",
                "response_time": 0.1, "usage": {},
            }

        with patch.object(service, "_call_provider", side_effect=mock_call):
            result = await service.complete("test")
            assert result["model"] == "model-b"
            assert "model-a" in call_models
            assert "model-b" in call_models

    @pytest.mark.asyncio
    async def test_no_model_fallback_on_non_transient(self):
        """Non-transient error → skip to next provider, don't try alt model."""
        configs = [
            ProviderConfig(
                name="p1", base_url="http://p1", api_key_env="",
                default_model="m1", models=["m1", "m1-alt"],
                requires_key=False, priority=0,
            ),
            ProviderConfig(
                name="p2", base_url="http://p2", api_key_env="",
                default_model="m2", models=["m2"],
                requires_key=False, priority=1,
            ),
        ]
        service = LLMRotationService(providers=configs)
        call_log = []

        async def mock_call(state, prompt, system_prompt=None, model=None, temperature=0.7, max_tokens=2048):
            call_log.append(f"{state.config.name}/{model}")
            if state.config.name == "p1":
                raise RuntimeError("HTTP 400 Bad Request")  # non-transient
            return {
                "provider": "p2", "model": model, "text": "ok",
                "response_time": 0.1, "usage": {},
            }

        with patch.object(service, "_call_provider", side_effect=mock_call):
            result = await service.complete("test")
            assert result["provider"] == "p2"
            # p1/m1-alt should NOT have been tried (non-transient → skip provider)
            assert "p1/m1-alt" not in call_log


# ========== Adaptive Scoring + Budget Tests (Iteration 5) ==========

from src.shared.llm_rotation.adaptive import (
    AdaptiveScorer,
    BudgetTracker,
    PRICE_PER_1K_TOKENS,
)


class TestAdaptiveScorer:
    def test_insufficient_data_returns_default(self):
        scorer = AdaptiveScorer(min_samples=5)
        assert scorer.score("unknown") == 0.5

    def test_score_with_enough_data(self):
        scorer = AdaptiveScorer(min_samples=3)
        for _ in range(5):
            scorer.record("p1", latency=1.0, tokens=100, quality=0.9)
        score = scorer.score("p1")
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # high quality, low latency

    def test_high_latency_lowers_score(self):
        scorer = AdaptiveScorer(min_samples=3)
        for _ in range(5):
            scorer.record("fast", latency=1.0, tokens=100, quality=0.8)
            scorer.record("slow", latency=25.0, tokens=100, quality=0.8)
        assert scorer.score("fast") > scorer.score("slow")

    def test_high_cost_lowers_score(self):
        scorer = AdaptiveScorer(min_samples=3)
        for _ in range(5):
            scorer.record("cheap", latency=2.0, tokens=10, quality=0.8)
            scorer.record("expensive", latency=2.0, tokens=10000, quality=0.8)
        # "expensive" with many tokens costs more
        assert scorer.score("cheap") >= scorer.score("expensive")

    def test_window_uses_recent(self):
        scorer = AdaptiveScorer(min_samples=2, window_size=3)
        # Old bad data
        for _ in range(10):
            scorer.record("p1", latency=20.0, tokens=100, quality=0.1)
        # Recent good data
        for _ in range(3):
            scorer.record("p1", latency=1.0, tokens=100, quality=0.9)
        # Score should reflect recent good data
        assert scorer.score("p1") > 0.5

    def test_get_stats(self):
        scorer = AdaptiveScorer(min_samples=2)
        scorer.record("p1", latency=1.0, tokens=100, quality=0.8)
        scorer.record("p1", latency=2.0, tokens=200, quality=0.9)
        stats = scorer.get_stats("p1")
        assert stats["samples"] == 2
        assert "avg_quality" in stats
        assert "total_tokens" in stats
        assert stats["total_tokens"] == 300

    def test_get_stats_empty(self):
        scorer = AdaptiveScorer()
        stats = scorer.get_stats("nonexistent")
        assert stats["samples"] == 0


class TestBudgetTracker:
    def test_initial_state(self):
        bt = BudgetTracker(daily_budget=1.0)
        assert bt.total_spent == 0.0
        assert bt.budget_remaining == 1.0
        assert not bt.is_over_budget

    def test_record_cost(self):
        bt = BudgetTracker(daily_budget=1.0)
        bt.record_cost("p1", 0.3)
        bt.record_cost("p2", 0.2)
        assert bt.total_spent == 0.5
        assert bt.budget_remaining == 0.5

    def test_over_budget(self):
        bt = BudgetTracker(daily_budget=0.5)
        bt.record_cost("p1", 0.6)
        assert bt.is_over_budget

    def test_alert_at_threshold(self, caplog):
        bt = BudgetTracker(daily_budget=1.0, alert_threshold=0.8)
        bt.record_cost("p1", 0.5)
        assert "Budget alert" not in caplog.text
        bt.record_cost("p1", 0.4)  # total 0.9 >= 80%
        assert "Budget alert" in caplog.text

    def test_alert_only_once(self, caplog):
        bt = BudgetTracker(daily_budget=1.0, alert_threshold=0.5)
        bt.record_cost("p1", 0.6)  # triggers alert
        alert_count = caplog.text.count("Budget alert")
        bt.record_cost("p1", 0.3)  # should not re-alert
        assert caplog.text.count("Budget alert") == alert_count

    def test_reset(self):
        bt = BudgetTracker(daily_budget=1.0)
        bt.record_cost("p1", 0.5)
        bt.reset()
        assert bt.total_spent == 0.0

    def test_get_stats(self):
        bt = BudgetTracker(daily_budget=2.0)
        bt.record_cost("p1", 0.3)
        bt.record_cost("p2", 0.1)
        stats = bt.get_stats()
        assert stats["daily_budget"] == 2.0
        assert stats["total_spent"] == 0.4
        assert "p1" in stats["per_provider"]


class TestAdaptiveIntegration:
    @pytest.mark.asyncio
    async def test_stats_include_adaptive(self):
        configs = [
            ProviderConfig(
                name="test", base_url="http://t", api_key_env="",
                default_model="m", requires_key=False,
            ),
        ]
        settings = LLMRotationSettings(adaptive_routing=True)
        service = LLMRotationService(providers=configs, settings=settings)
        stats = service.get_stats()
        assert "adaptive" in stats["test"]
        assert "_budget" in stats

    @pytest.mark.asyncio
    async def test_completion_records_adaptive(self):
        configs = [
            ProviderConfig(
                name="mock", base_url="http://m", api_key_env="",
                default_model="m", requires_key=False,
            ),
        ]
        settings = LLMRotationSettings(adaptive_routing=True)
        service = LLMRotationService(providers=configs, settings=settings)

        mock_response = {
            "choices": [{"message": {"content": "Hello world response"}, "finish_reason": "stop"}],
            "model": "m",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        with patch.object(service, "_make_request_openai", new_callable=AsyncMock, return_value=mock_response):
            await service.complete("test")

        # Should have recorded one outcome
        assert len(service._scorer.history.get("mock", [])) == 1
