"""
Unit tests for LLM Rotation modules:
- circuit_breaker.py
- backoff.py
- adaptive.py
- rate_limiter.py
"""

import json
import time

import pytest

from src.shared.llm_rotation.backoff import BackoffStrategy, RateLimitError
from src.shared.llm_rotation.circuit_breaker import CircuitBreaker, CircuitState
from src.shared.llm_rotation.rate_limiter import ProviderRateLimiter, TokenBucket


# ============================================================
# CircuitBreaker Tests
# ============================================================


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_single_failure_stays_closed(self):
        cb = CircuitBreaker(fail_threshold=3)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.fail_count == 1

    def test_threshold_failures_opens(self):
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

    def test_open_to_half_open_after_timeout(self):
        cb = CircuitBreaker(fail_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(fail_threshold=1, success_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.fail_count == 0

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(fail_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_half_open_needs_multiple_successes(self):
        cb = CircuitBreaker(fail_threshold=1, success_threshold=3, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # not yet
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_fail_count(self):
        cb = CircuitBreaker(fail_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.fail_count == 0

    def test_force_open(self):
        cb = CircuitBreaker(fail_threshold=10)
        cb.force_open()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

    def test_force_open_custom_timeout(self):
        cb = CircuitBreaker(fail_threshold=10, reset_timeout=999)
        cb.force_open(reset_timeout=0.01)
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

    def test_reset(self):
        cb = CircuitBreaker(fail_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.fail_count == 0
        assert cb.can_execute()


# ============================================================
# BackoffStrategy Tests
# ============================================================


class TestBackoffStrategy:
    def test_first_attempt_base_delay(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=0.0, multiplier=2.0)
        delay = bs.compute_delay(0)
        assert delay == 1.0

    def test_exponential_growth(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=0.0, multiplier=2.0, max_delay=100)
        assert bs.compute_delay(0) == 1.0
        assert bs.compute_delay(1) == 2.0
        assert bs.compute_delay(2) == 4.0
        assert bs.compute_delay(3) == 8.0

    def test_max_delay_cap(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=0.0, multiplier=2.0, max_delay=5.0)
        assert bs.compute_delay(10) == 5.0

    def test_jitter_adds_randomness(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=2.0, multiplier=2.0)
        delays = [bs.compute_delay(0) for _ in range(20)]
        # All should be in [1.0, 3.0]
        assert all(1.0 <= d <= 3.0 for d in delays)
        # Should not all be identical (extremely unlikely with jitter)
        assert len(set(round(d, 6) for d in delays)) > 1

    def test_retry_after_overrides(self):
        bs = BackoffStrategy(base_delay=1.0, jitter=0.0)
        delay = bs.compute_delay(0, retry_after=10.0)
        assert delay == 10.0

    def test_retry_after_with_jitter(self):
        bs = BackoffStrategy(jitter=1.0)
        delay = bs.compute_delay(0, retry_after=5.0)
        assert 5.0 <= delay <= 6.0

    def test_retry_after_zero_ignored(self):
        bs = BackoffStrategy(base_delay=2.0, jitter=0.0)
        delay = bs.compute_delay(0, retry_after=0.0)
        # retry_after=0 is falsy but > 0 check means it falls through to normal calc
        assert delay == 2.0


class TestRateLimitError:
    def test_basic(self):
        err = RateLimitError("429 too many", retry_after=5.0)
        assert "429" in str(err)
        assert err.retry_after == 5.0

    def test_no_retry_after(self):
        err = RateLimitError("rate limited")
        assert err.retry_after is None


# ============================================================
# AdaptiveScorer Tests
# ============================================================


class TestAdaptiveScorer:
    def _make_scorer(self):
        from src.shared.llm_rotation.adaptive import AdaptiveScorer
        return AdaptiveScorer(min_samples=3, window_size=5)

    def test_insufficient_samples_returns_default(self):
        scorer = self._make_scorer()
        scorer.record("p1", 1.0, 100, 0.8)
        scorer.record("p1", 1.0, 100, 0.8)
        assert scorer.score("p1") == 0.5  # default

    def test_unknown_provider_returns_default(self):
        scorer = self._make_scorer()
        assert scorer.score("nonexistent") == 0.5

    def test_enough_samples_computes_score(self):
        scorer = self._make_scorer()
        for _ in range(5):
            scorer.record("p1", 2.0, 100, 0.9)
        score = scorer.score("p1")
        assert 0.0 <= score <= 1.0
        assert score != 0.5  # should differ from default

    def test_high_quality_gets_higher_score(self):
        scorer = self._make_scorer()
        for _ in range(5):
            scorer.record("good", 1.0, 100, 1.0)
            scorer.record("bad", 1.0, 100, 0.1)
        assert scorer.score("good") > scorer.score("bad")

    def test_low_latency_gets_higher_score(self):
        scorer = self._make_scorer()
        for _ in range(5):
            scorer.record("fast", 0.5, 100, 0.8)
            scorer.record("slow", 25.0, 100, 0.8)
        assert scorer.score("fast") > scorer.score("slow")

    def test_window_uses_recent(self):
        scorer = self._make_scorer()
        # 5 bad, then 5 good
        for _ in range(5):
            scorer.record("p1", 20.0, 100, 0.1)
        for _ in range(5):
            scorer.record("p1", 1.0, 100, 0.9)
        # Window=5, so only the recent 5 good ones count
        score = scorer.score("p1")
        assert score > 0.7

    def test_get_stats(self):
        scorer = self._make_scorer()
        for _ in range(5):
            scorer.record("p1", 2.0, 200, 0.8)
        stats = scorer.get_stats("p1")
        assert stats["samples"] == 5
        assert "score" in stats
        assert "avg_quality" in stats
        assert "total_tokens" in stats

    def test_get_stats_empty(self):
        scorer = self._make_scorer()
        stats = scorer.get_stats("none")
        assert stats["samples"] == 0

    def test_save_load_roundtrip(self, tmp_path):
        scorer = self._make_scorer()
        for i in range(5):
            scorer.record("p1", float(i), 100 + i, 0.5 + i * 0.1)
        path = tmp_path / "adaptive.json"
        scorer.save(path)

        scorer2 = self._make_scorer()
        scorer2.load(path)
        assert len(scorer2.history["p1"]) == 5
        assert abs(scorer.score("p1") - scorer2.score("p1")) < 0.001

    def test_load_nonexistent_noop(self, tmp_path):
        scorer = self._make_scorer()
        scorer.load(tmp_path / "no_such_file.json")
        assert len(scorer.history) == 0

    def test_load_corrupted_noop(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json at all", encoding="utf-8")
        scorer = self._make_scorer()
        scorer.load(path)
        assert len(scorer.history) == 0


# ============================================================
# BudgetTracker Tests
# ============================================================


class TestBudgetTracker:
    def _make_tracker(self, budget=1.0):
        from src.shared.llm_rotation.adaptive import BudgetTracker
        return BudgetTracker(daily_budget=budget, alert_threshold=0.8)

    def test_initial_state(self):
        bt = self._make_tracker()
        assert bt.total_spent == 0.0
        assert bt.budget_remaining == 1.0
        assert not bt.is_over_budget

    def test_record_cost(self):
        bt = self._make_tracker(budget=1.0)
        bt.record_cost("p1", 0.3)
        bt.record_cost("p2", 0.2)
        assert abs(bt.total_spent - 0.5) < 1e-9

    def test_over_budget(self):
        bt = self._make_tracker(budget=0.5)
        bt.record_cost("p1", 0.6)
        assert bt.is_over_budget
        assert bt.budget_remaining == 0.0

    def test_get_stats(self):
        bt = self._make_tracker()
        bt.record_cost("p1", 0.1)
        stats = bt.get_stats()
        assert "daily_budget" in stats
        assert "per_provider" in stats
        assert "p1" in stats["per_provider"]

    def test_reset(self):
        bt = self._make_tracker()
        bt.record_cost("p1", 0.5)
        bt.reset()
        assert bt.total_spent == 0.0

    def test_daily_reset_same_day(self):
        bt = self._make_tracker()
        bt.record_cost("p1", 0.5)
        assert not bt.check_daily_reset()
        assert bt.total_spent == 0.5  # not reset

    def test_save_load_roundtrip(self, tmp_path):
        bt = self._make_tracker(budget=2.0)
        bt.record_cost("p1", 0.3)
        bt.record_cost("p2", 0.7)
        path = tmp_path / "budget.json"
        bt.save(path)

        bt2 = self._make_tracker(budget=2.0)
        bt2.load(path)
        assert abs(bt2.total_spent - 1.0) < 1e-9

    def test_load_nonexistent_noop(self, tmp_path):
        bt = self._make_tracker()
        bt.load(tmp_path / "no.json")
        assert bt.total_spent == 0.0

    def test_load_old_date_resets(self, tmp_path):
        """Saved data from yesterday should trigger auto-reset on load."""
        path = tmp_path / "budget.json"
        data = {"spending": {"p1": 0.5}, "reset_date": "2020-01-01"}
        path.write_text(json.dumps(data), encoding="utf-8")
        bt = self._make_tracker()
        bt.load(path)
        assert bt.total_spent == 0.0  # reset because different day


# ============================================================
# TokenBucket Tests
# ============================================================


class TestTokenBucket:
    def test_initial_full(self):
        tb = TokenBucket(rate=1.0, capacity=5)
        assert tb.available >= 4.9

    def test_consume_decrements(self):
        tb = TokenBucket(rate=1.0, capacity=5)
        assert tb.consume()
        assert tb.available < 5.0

    def test_consume_until_empty(self):
        tb = TokenBucket(rate=0.0, capacity=3)  # no refill
        assert tb.consume()
        assert tb.consume()
        assert tb.consume()
        assert not tb.consume()  # empty

    def test_refill_over_time(self):
        tb = TokenBucket(rate=100.0, capacity=5)  # 100/sec
        # Drain all
        for _ in range(5):
            tb.consume()
        time.sleep(0.05)  # 5 tokens at 100/sec
        assert tb.consume()  # should have refilled

    def test_wait_time_zero_when_available(self):
        tb = TokenBucket(rate=1.0, capacity=5)
        assert tb.wait_time() == 0.0

    def test_wait_time_positive_when_empty(self):
        tb = TokenBucket(rate=1.0, capacity=1)
        tb.consume()
        wait = tb.wait_time()
        assert wait > 0.0

    def test_capacity_cap(self):
        tb = TokenBucket(rate=1000.0, capacity=5)
        time.sleep(0.1)  # would add 100 tokens, but capped at 5
        assert tb.available <= 5.0

    def test_reset(self):
        tb = TokenBucket(rate=0.0, capacity=10)
        for _ in range(10):
            tb.consume()
        assert not tb.consume()
        tb.reset()
        assert tb.consume()


# ============================================================
# ProviderRateLimiter Tests
# ============================================================


class TestProviderRateLimiter:
    def test_unregistered_always_allowed(self):
        rl = ProviderRateLimiter()
        assert rl.can_request("any")
        assert rl.wait_time("any") == 0.0

    def test_registered_with_rpm(self):
        rl = ProviderRateLimiter()
        rl.register("p1", rpm=60)
        assert rl.can_request("p1")  # first request OK

    def test_registered_none_rpm(self):
        rl = ProviderRateLimiter()
        rl.register("p1", rpm=None)
        assert rl.can_request("p1")

    def test_stats_unlimited(self):
        rl = ProviderRateLimiter()
        stats = rl.get_stats("unregistered")
        assert stats == {"limited": False}

    def test_stats_limited(self):
        rl = ProviderRateLimiter()
        rl.register("p1", rpm=30)
        stats = rl.get_stats("p1")
        assert stats["limited"] is True
        assert stats["rpm"] == 30
        assert stats["capacity"] == 30

    def test_reset_provider(self):
        rl = ProviderRateLimiter()
        rl.register("p1", rpm=1)
        rl.can_request("p1")  # consume the 1 token
        rl.reset("p1")
        assert rl.can_request("p1")  # should work after reset

    def test_exhaust_and_wait(self):
        rl = ProviderRateLimiter()
        rl.register("p1", rpm=60)  # 1/sec
        # Consume all capacity (60)
        for _ in range(60):
            rl.can_request("p1")
        wait = rl.wait_time("p1")
        assert wait > 0.0
