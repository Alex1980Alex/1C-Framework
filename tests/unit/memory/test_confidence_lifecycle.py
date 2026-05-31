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
    is_invariant,
    payload_effective_confidence,
    seed_counts_from_legacy,
    should_archive,
    stability_adjusted_rate,
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
    """Same payload read 90 days later drifts toward prior (0.70 < eff < 0.80).

    §22 P4: stability_adjusted_rate is used because application_count=5 > 0.
    """
    payload = {
        "succ": 5.0,
        "fail": 0.0,
        "last_decay_at": t0.isoformat(),
        "application_count": 5,
    }
    now_90 = t0 + timedelta(days=90)
    result = payload_effective_confidence(payload, now=now_90)
    rate = stability_adjusted_rate(0.05, 5)
    expected = effective_confidence(5.0, 0.0, last_decay_at=t0, now=now_90, decay_rate=rate)
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


# ── §22 P3: forgetting (is_invariant / should_archive / revive) ──────────────


def test_is_invariant_classification() -> None:
    assert is_invariant("architectural-principle") is True
    assert is_invariant("bsl-pattern") is True
    assert is_invariant("workflow-pattern") is False
    assert is_invariant("code-convention") is False
    assert is_invariant("") is False


def test_should_archive_fresh_no() -> None:
    payload = {"succ": 5.0, "fail": 0.0, "last_applied": t0.isoformat(),
               "pattern_type": "workflow-pattern"}
    assert should_archive(payload, t0) is False


def test_should_archive_stale_non_invariant_yes() -> None:
    # Weak pattern (succ=1 → conf≈0.727 < 0.75) left idle >180d → effective
    # drifts further toward prior, stays < staleness_conf → archive.
    # (A strong succ=5/conf=0.80 pattern needs ~550d to cross 0.75 — by design
    # trusted patterns persist far longer; see test below.)
    payload = {"succ": 1.0, "fail": 0.0, "last_applied": t0.isoformat(),
               "pattern_type": "workflow-pattern"}
    assert should_archive(payload, t0 + timedelta(days=200)) is True


def test_should_archive_invariant_exempt_from_staleness() -> None:
    payload = {"succ": 1.0, "fail": 0.0, "last_applied": t0.isoformat(),
               "pattern_type": "bsl-pattern"}
    # same staleness, but invariant → NOT time-archived
    assert should_archive(payload, t0 + timedelta(days=200)) is False


def test_should_archive_strong_pattern_persists() -> None:
    # Strong pattern (succ=5/conf 0.80) idle 200d → eff still ≈0.78 > 0.75 → kept.
    payload = {"succ": 5.0, "fail": 0.0, "last_applied": t0.isoformat(),
               "pattern_type": "workflow-pattern"}
    assert should_archive(payload, t0 + timedelta(days=200)) is False


def test_should_archive_fail_floor_applies_to_invariant() -> None:
    payload = {"succ": 0.0, "fail": 20.0, "last_applied": t0.isoformat(),
               "pattern_type": "bsl-pattern"}
    # eff = 7/27 ≈ 0.259 < 0.40 → fail-floor archive even for invariant
    assert payload_effective_confidence(payload, t0) < 0.40
    assert should_archive(payload, t0) is True


def test_apply_to_payload_revives_archived() -> None:
    payload = {"succ": 1.0, "fail": 0.0, "last_decay_at": t0.isoformat(),
               "expired_at": t0.isoformat(), "application_count": 1}
    result = apply_to_payload(payload, True, t0)
    assert result["expired_at"] is None  # any apply un-archives


def test_should_archive_never_applied_uses_created_at() -> None:
    # No last_applied — idle measured from created_at (NOT decay bookkeeping).
    # Weak pattern saved 200d ago, never used → stale → archive.
    payload = {"succ": 1.0, "fail": 0.0, "created_at": t0.isoformat(),
               "last_decay_at": (t0 + timedelta(days=199)).isoformat(),
               "pattern_type": "workflow-pattern"}
    # last_decay_at is recent (199d in) but must be IGNORED for idle → still stale
    assert should_archive(payload, t0 + timedelta(days=200)) is True


def test_should_archive_fresh_never_applied_no() -> None:
    payload = {"succ": 1.0, "fail": 0.0, "created_at": t0.isoformat(),
               "pattern_type": "workflow-pattern"}
    assert should_archive(payload, t0) is False


# ── §22 P4: FSRS-lite stability_adjusted_rate ────────────────────────────────


@pytest.mark.unit
def test_stability_adjusted_rate_zero_count() -> None:
    """count=0 → rate unchanged (no history = no discount)."""
    assert stability_adjusted_rate(0.05, 0) == pytest.approx(0.05)


@pytest.mark.unit
def test_stability_adjusted_rate_monotonic_decreasing() -> None:
    """Higher application_count → strictly lower decay rate."""
    r5 = stability_adjusted_rate(0.05, 5)
    r50 = stability_adjusted_rate(0.05, 50)
    assert r50 < r5 < 0.05


@pytest.mark.unit
def test_stability_established_decays_slower() -> None:
    """Established pattern (high application_count) retains more confidence.

    Core §22 P4 property: two payloads identical except application_count.
    After 180 days the established one has higher effective confidence,
    but both have decayed below 0.80 (neither is frozen).
    """
    base_payload = {
        "succ": 5.0,
        "fail": 0.0,
        "last_decay_at": t0.isoformat(),
    }
    rookie = {**base_payload, "application_count": 2}
    established = {**base_payload, "application_count": 100}
    now_180 = t0 + timedelta(days=180)

    eff_rookie = payload_effective_confidence(rookie, now=now_180)
    eff_established = payload_effective_confidence(established, now=now_180)

    assert eff_established > eff_rookie  # established retained more confidence
    assert eff_established < 0.80        # both decayed somewhat
    assert eff_rookie < 0.80


# ── §22 Fix #2: _pattern_to_payload round-trips expired_at ──────────────────


@pytest.mark.unit
def test_pattern_to_payload_expired_at_set() -> None:
    """_pattern_to_payload must include expired_at when set on the model."""
    from src.memory.vector_memory.models import LearnedPattern, PatternType
    from src.memory.vector_memory.server import _pattern_to_payload

    pattern = LearnedPattern(
        pattern_id="test-id",
        pattern_type=PatternType.WORKFLOW_PATTERN,
        name="test",
        description="",
        content="test content",
        confidence=0.70,
        succ=0.0,
        fail=0.0,
        last_decay_at=t0,
        expired_at=t0,
    )
    payload = _pattern_to_payload(pattern)
    assert "expired_at" in payload
    assert payload["expired_at"] == t0.isoformat()


@pytest.mark.unit
def test_pattern_to_payload_expired_at_none() -> None:
    """_pattern_to_payload emits expired_at=None when unset."""
    from src.memory.vector_memory.models import LearnedPattern, PatternType
    from src.memory.vector_memory.server import _pattern_to_payload

    pattern = LearnedPattern(
        pattern_id="test-id-2",
        pattern_type=PatternType.WORKFLOW_PATTERN,
        name="test",
        description="",
        content="test content",
        confidence=0.70,
        succ=0.0,
        fail=0.0,
        last_decay_at=t0,
        expired_at=None,
    )
    payload = _pattern_to_payload(pattern)
    assert "expired_at" in payload
    assert payload["expired_at"] is None


# ── §22 Fix #3: should_archive recover/stay decision ────────────────────────


@pytest.mark.unit
def test_should_archive_recovered_fail_pattern_false() -> None:
    """A pattern whose fail counts decayed back to zero is not archived.

    Documents the un-archive condition: sweep sets expired_at=None when
    should_archive transitions False on a previously-archived pattern.
    """
    # succ=5 fail=0 → eff=0.80, not stale (last_applied=t0, read at t0)
    # → sweep would un-archive
    payload = {
        "succ": 5.0,
        "fail": 0.0,
        "last_applied": t0.isoformat(),
        "expired_at": t0.isoformat(),  # was archived
        "pattern_type": "workflow-pattern",
    }
    assert should_archive(payload, t0) is False


@pytest.mark.unit
def test_should_archive_still_failing_pattern_true() -> None:
    """A pattern with heavy fail counts stays archived (should_archive=True)."""
    payload = {
        "succ": 0.0,
        "fail": 20.0,
        "last_applied": t0.isoformat(),
        "expired_at": t0.isoformat(),
        "pattern_type": "workflow-pattern",
    }
    assert should_archive(payload, t0) is True
