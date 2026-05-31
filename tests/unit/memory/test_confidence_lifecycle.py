"""Unit tests for Beta-posterior confidence lifecycle (pure functions, no Qdrant).

Covers §22.9.1: derive_confidence, decay_counts, apply_outcome,
effective_confidence, seed_counts_from_legacy.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from src.memory.vector_memory.confidence import (
    apply_outcome,
    decay_counts,
    derive_confidence,
    effective_confidence,
    seed_counts_from_legacy,
)

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
