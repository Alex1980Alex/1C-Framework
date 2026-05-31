"""Unit tests for Beta-posterior confidence lifecycle (pure functions, no Qdrant).

Covers §22.9.1: derive_confidence, decay_counts, apply_outcome,
effective_confidence, seed_counts_from_legacy, apply_to_payload,
reinforce_pattern (stub-client, no live Qdrant).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import pytest

from src.memory.vector_memory.confidence import (
    apply_outcome,
    apply_to_payload,
    decay_counts,
    derive_confidence,
    effective_confidence,
    payload_effective_confidence,
    seed_counts_from_legacy,
)
from src.memory.vector_memory.reinforce import reinforce_pattern

pytestmark = pytest.mark.unit

t0 = datetime(2026, 1, 1)


def test_derive_confidence_prior() -> None:
    assert derive_confidence(0.0, 0.0) == pytest.approx(0.70)


def test_derive_confidence_five_successes() -> None:
    assert derive_confidence(5.0, 0.0) == pytest.approx(0.80)


def test_derive_confidence_five_succ_one_fail() -> None:
    assert derive_confidence(5.0, 1.0) == pytest.approx(0.75)


def test_apply_outcome_chained_no_decay() -> None:
    """5 successes with days=0 each → succ==5.0, confidence==0.80."""
    succ, fail = 0.0, 0.0
    for _ in range(5):
        succ, fail = apply_outcome(succ, fail, last_decay_at=t0, now=t0, decay_rate=0.05, success=True)
    assert succ == pytest.approx(5.0)
    assert derive_confidence(succ, fail) == pytest.approx(0.80)


def test_effective_confidence_decay_drift() -> None:
    """After 90 days of decay, confidence should drop but stay above prior floor."""
    now = t0 + timedelta(days=90)
    expected = derive_confidence(5.674 * math.exp(-0.05 * 90 / 30), 0.0)
    result = effective_confidence(5.674, 0.0, last_decay_at=t0, now=now, decay_rate=0.05)
    assert 0.70 < result < 0.80
    assert result == pytest.approx(expected)


def test_seed_counts_from_legacy_70pct() -> None:
    succ, fail = seed_counts_from_legacy(0.7, 10)
    assert succ == pytest.approx(7.0)
    assert fail == pytest.approx(3.0)
    assert derive_confidence(succ, fail) == pytest.approx(0.70)


def test_seed_counts_from_legacy_85pct() -> None:
    succ, fail = seed_counts_from_legacy(0.85, 10)
    assert derive_confidence(succ, fail) == pytest.approx(0.775)


def test_decay_counts_floor() -> None:
    """Count near zero floors to exactly 0.0 after one day decay."""
    succ, fail = decay_counts(1e-9, 0.0, t0, t0 + timedelta(days=1), 0.05)
    assert succ == 0.0
    assert fail == 0.0


# ---------------------------------------------------------------------------
# apply_to_payload — §22 P1 Pass 1
# ---------------------------------------------------------------------------


def test_apply_to_payload_success_fresh() -> None:
    """Full payload with succ/fail/last_decay_at: success increments succ."""
    payload = {
        "succ": 0.0,
        "fail": 0.0,
        "last_decay_at": t0.isoformat(),
        "application_count": 0,
        "confidence": 0.70,
    }
    result = apply_to_payload(payload, True, t0)
    assert result["succ"] == pytest.approx(1.0)
    assert result["fail"] == 0.0
    # Beta(7+1, 3+0) / (7+1+3+0) = 8/11
    assert result["confidence"] == pytest.approx(8 / 11)
    assert result["application_count"] == 1
    assert result["last_decay_at"] == t0.isoformat()


def test_apply_to_payload_legacy_migration() -> None:
    """Legacy payload (no succ/fail): seed from confidence+application_count."""
    payload = {
        "confidence": 0.7,
        "application_count": 10,
        "updated_at": t0.isoformat(),
    }
    result = apply_to_payload(payload, True, t0)
    # seed: succ=7.0, fail=3.0; same t0 so no decay; success → succ=8.0
    assert result["succ"] == pytest.approx(8.0)
    assert result["fail"] == pytest.approx(3.0)
    # Beta(7+8, 3+3) / (7+8+3+3) = 15/21
    assert result["confidence"] == pytest.approx(15 / 21)
    assert result["application_count"] == 11


def test_apply_to_payload_failure() -> None:
    """Failure observation increments fail and lowers confidence."""
    payload = {
        "succ": 5.0,
        "fail": 0.0,
        "last_decay_at": t0.isoformat(),
        "application_count": 5,
    }
    result = apply_to_payload(payload, False, t0)
    assert result["fail"] == pytest.approx(1.0)
    # Beta(7+5, 3+1) / (7+5+3+1) = 12/16 = 0.75
    assert result["confidence"] == pytest.approx(0.75)
    assert result["application_count"] == 6


# ---------------------------------------------------------------------------
# payload_effective_confidence — §22 P2 lazy decay-on-read
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_payload_effective_confidence_fresh() -> None:
    """Fresh payload read at t0: no decay elapsed → approx 0.80 (5 successes)."""
    payload = {
        "succ": 5.0,
        "fail": 0.0,
        "last_decay_at": t0.isoformat(),
        "application_count": 5,
    }
    result = payload_effective_confidence(payload, now=t0)
    # Beta(7+5, 3+0)/(7+5+3+0) = 12/15 = 0.80
    assert result == pytest.approx(0.80)


@pytest.mark.unit
def test_payload_effective_confidence_decayed_90d() -> None:
    """Same payload read 90 days later drifts toward prior (0.70 < eff < 0.80)."""
    payload = {
        "succ": 5.0,
        "fail": 0.0,
        "last_decay_at": t0.isoformat(),
        "application_count": 5,
    }
    now_90 = t0 + timedelta(days=90)
    result = payload_effective_confidence(payload, now=now_90)
    expected = effective_confidence(5.0, 0.0, last_decay_at=t0, now=now_90)
    assert result > 0.70
    assert result < 0.80
    assert result == pytest.approx(expected)


@pytest.mark.unit
def test_payload_effective_confidence_legacy_migration() -> None:
    """Legacy payload (no succ/fail) migrates via seed_counts_from_legacy."""
    payload = {
        "confidence": 0.85,
        "application_count": 10,
        "updated_at": t0.isoformat(),
    }
    # seed: succ=8.5, fail=1.5; no decay (t0→t0); Beta(7+8.5,3+1.5)/(7+8.5+3+1.5)=15.5/20
    result = payload_effective_confidence(payload, now=t0)
    assert result == pytest.approx(15.5 / 20)


@pytest.mark.unit
def test_payload_effective_confidence_fail_heavy_drifts_up() -> None:
    """Fail-heavy pattern: effective drifts UP toward 0.70 over time.

    This documents why search cannot server-prefilter on stored confidence:
    effective confidence can be HIGHER than stored for patterns that were
    penalised but then left idle (counts decay toward zero → prior 0.70).
    """
    payload = {
        "succ": 0.0,
        "fail": 5.0,
        "last_decay_at": t0.isoformat(),
    }
    eff_t0 = payload_effective_confidence(payload, now=t0)
    # Beta(7+0, 3+5)/(7+0+3+5) = 7/15 ≈ 0.4667
    assert eff_t0 == pytest.approx(7 / 15)

    now_90 = t0 + timedelta(days=90)
    eff_90 = payload_effective_confidence(payload, now=now_90)
    # Fail counts decay → posterior drifts back toward prior 0.70
    assert eff_90 > eff_t0


# ---------------------------------------------------------------------------
# reinforce_pattern — stub-client tests (no live Qdrant)
# ---------------------------------------------------------------------------


class _FakePoint:
    """Minimal stand-in for a Qdrant ScoredPoint / Record."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload


class _FakeClient:
    """Stub Qdrant client that records set_payload calls."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.set_payload_calls: list[dict[str, Any]] = []

    def retrieve(
        self,
        *,
        collection_name: str,
        ids: list[Any],
        with_payload: bool = True,
    ) -> list[_FakePoint]:
        return [_FakePoint(self._payload)]

    def set_payload(
        self,
        *,
        collection_name: str,
        payload: dict[str, Any],
        points: list[Any],
    ) -> None:
        self.set_payload_calls.append({"payload": payload, "points": points})


class _ErrorClient:
    """Stub client whose retrieve() always raises."""

    def retrieve(self, **kwargs: Any) -> list[Any]:
        raise RuntimeError("connection refused")


def test_reinforce_pattern_success() -> None:
    """Stub client: returns True and new_confidence matches apply_to_payload."""
    init_payload: dict[str, Any] = {
        "succ": 3.0,
        "fail": 1.0,
        "last_decay_at": t0.isoformat(),
        "application_count": 4,
        "confidence": 0.71,
    }
    stub = _FakeClient(init_payload)
    result = reinforce_pattern("pid-1", True, client=stub, collection="test_col", now=t0)

    assert result["success"] is True
    assert result["pattern_id"] == "pid-1"

    # Verify new_confidence matches pure function
    expected_updates = apply_to_payload(init_payload, True, t0)
    assert result["new_confidence"] == pytest.approx(expected_updates["confidence"])
    assert result["application_count"] == expected_updates["application_count"]

    # set_payload was called exactly once with the right updates
    assert len(stub.set_payload_calls) == 1
    assert stub.set_payload_calls[0]["points"] == ["pid-1"]


def test_reinforce_pattern_fail_soft_on_error() -> None:
    """Stub client that raises: reinforce_pattern returns success=False."""
    result = reinforce_pattern(
        "pid-err",
        True,
        client=_ErrorClient(),
        collection="test_col",
        now=t0,
    )
    assert result["success"] is False
    assert "error" in result
    assert result["pattern_id"] == "pid-err"
