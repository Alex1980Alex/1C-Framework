"""Pure-function helpers for Beta-posterior confidence lifecycle.

Decision: roadmap §22.9.1 — store sufficient statistics (succ/fail counts),
derive confidence as Beta(PRIOR_SUCCESS, PRIOR_FAILURE) posterior mean;
lazy multiplicative decay on access.  No Qdrant I/O here.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

# Beta prior hyper-parameters: prior mean = 7/(7+3) = 0.70
PRIOR_SUCCESS: float = 7.0
PRIOR_FAILURE: float = 3.0

# Default per-collection decay rate (env-overridable at call-site)
DEFAULT_DECAY_RATE: float = 0.05

# Floor below which a decayed count is treated as zero (avoids subnormals)
COUNT_FLOOR: float = 1e-6


def derive_confidence(succ: float, fail: float) -> float:
    """Return Beta(PRIOR_SUCCESS+succ, PRIOR_FAILURE+fail) posterior mean.

    Always lies strictly in (0, 1) regardless of succ/fail values.
    No clamping needed — the prior absorbs edge cases.

    Args:
        succ: Observed success count (may be decayed float).
        fail: Observed failure count (may be decayed float).

    Returns:
        Posterior mean confidence in (0, 1).
    """
    return (PRIOR_SUCCESS + succ) / (PRIOR_SUCCESS + PRIOR_FAILURE + succ + fail)


def decay_counts(
    succ: float,
    fail: float,
    last_decay_at: datetime | None,
    now: datetime,
    decay_rate: float = DEFAULT_DECAY_RATE,
) -> tuple[float, float]:
    """Apply multiplicative time-decay to raw success/failure counts.

    Uses integer days elapsed (``timedelta.days``) so tests with exact
    timedelta(days=N) produce fully-deterministic results.

    Args:
        succ: Current success count.
        fail: Current failure count.
        last_decay_at: Datetime when counts were last decayed; None → 0 days.
        now: Current datetime reference.
        decay_rate: Decay-rate constant (default DEFAULT_DECAY_RATE=0.05).

    Returns:
        ``(succ, fail)`` after decay and COUNT_FLOOR application.
    """
    if last_decay_at is None:
        days = 0
    else:
        days = max(0, (now - last_decay_at).days)

    d = math.exp(-decay_rate * days / 30.0)
    succ *= d
    fail *= d

    if succ < COUNT_FLOOR:
        succ = 0.0
    if fail < COUNT_FLOOR:
        fail = 0.0

    return (succ, fail)


def apply_outcome(
    succ: float,
    fail: float,
    last_decay_at: datetime | None,
    now: datetime,
    decay_rate: float,
    success: bool,
) -> tuple[float, float]:
    """Decay counts then record one outcome observation.

    Args:
        succ: Current success count.
        fail: Current failure count.
        last_decay_at: Datetime of last decay (passed to decay_counts).
        now: Current datetime reference.
        decay_rate: Decay-rate constant.
        success: True = success observation; False = failure observation.

    Returns:
        Updated ``(succ, fail)`` after decay + increment.
    """
    succ, fail = decay_counts(succ, fail, last_decay_at, now, decay_rate)
    if success:
        succ += 1.0
    else:
        fail += 1.0
    return (succ, fail)


def effective_confidence(
    succ: float,
    fail: float,
    last_decay_at: datetime | None,
    now: datetime,
    decay_rate: float = DEFAULT_DECAY_RATE,
) -> float:
    """Lazy read-time confidence: decay counts then derive posterior mean.

    Intended for P2 read-path (search results display); does NOT persist
    the decayed counts — call site must decide whether to write back.

    Args:
        succ: Stored success count.
        fail: Stored failure count.
        last_decay_at: Datetime of last persisted decay.
        now: Current datetime reference.
        decay_rate: Decay-rate constant.

    Returns:
        Posterior mean confidence after applying time decay.
    """
    s, f = decay_counts(succ, fail, last_decay_at, now, decay_rate)
    return derive_confidence(s, f)


def seed_counts_from_legacy(confidence: float, application_count: int) -> tuple[float, float]:
    """Derive initial succ/fail counts from legacy confidence + application_count.

    Preserves the observed success ratio:
        succ = confidence * n
        fail = (1 - confidence) * n

    When n=0 both counts are 0.0, so derive_confidence returns 0.70 (the prior).

    Args:
        confidence: Legacy stored confidence (float in [0, 1]).
        application_count: Total applications recorded in legacy payload.

    Returns:
        ``(succ, fail)`` float counts compatible with derive_confidence.
    """
    n = max(0, application_count)
    succ = confidence * n
    fail = (1.0 - confidence) * n
    return (succ, fail)


def _resolve_state(
    payload: dict[str, Any],
    default_decay_rate: float = DEFAULT_DECAY_RATE,
) -> tuple[float, float, datetime | None, float]:
    """Return (succ, fail, last_decay_at, decay_rate) from a Qdrant payload.

    Lazily migrates legacy points (no succ/fail keys) via
    :func:`seed_counts_from_legacy`.  Used by both :func:`apply_to_payload`
    (write-path) and :func:`payload_effective_confidence` (read-path) to
    avoid duplicating the resolution logic.

    Args:
        payload: Qdrant point payload dict (read-only; not mutated).
        default_decay_rate: Fallback decay rate when payload lacks ``decay_rate``.

    Returns:
        ``(succ, fail, last_decay_at, decay_rate)`` ready for
        :func:`decay_counts` / :func:`apply_outcome`.
    """
    # Resolve succ/fail — lazy migration for legacy points without the fields.
    raw_succ = payload.get("succ")
    raw_fail = payload.get("fail")
    if raw_succ is None or raw_fail is None:
        succ, fail = seed_counts_from_legacy(
            payload.get("confidence", 0.5),
            payload.get("application_count", 0),
        )
    else:
        succ, fail = float(raw_succ), float(raw_fail)

    # Resolve last_decay_at — prefer explicit field, fall back through chain.
    last_decay_at: datetime | None = None
    for key in ("last_decay_at", "last_applied", "updated_at", "created_at"):
        raw = payload.get(key)
        if raw:
            last_decay_at = datetime.fromisoformat(raw)
            break

    decay_rate = float(payload.get("decay_rate", default_decay_rate))
    return (succ, fail, last_decay_at, decay_rate)


def is_invariant(pattern_type: str) -> bool:
    """Return True for pattern types exempt from time-based archival (§22.9.2).

    Invariant types (architectural-principle, bsl-pattern) encode stable
    domain knowledge that should not be time-archived even when idle.
    They can still be fail-archived if effective confidence falls below
    fail_floor — that branch applies to ALL classes.

    Args:
        pattern_type: Pattern type string (e.g. ``"bsl-pattern"``).

    Returns:
        True iff the pattern type is exempt from staleness-based archival.
    """
    return pattern_type in ("architectural-principle", "bsl-pattern")


def should_archive(
    payload: dict[str, Any],
    now: datetime | None = None,
    *,
    staleness_days: int = 180,
    staleness_conf: float = 0.75,
    fail_floor: float = 0.40,
) -> bool:
    """Return True when a pattern should be marked expired (invalidate-not-delete).

    Two independent archival triggers:
    - **fail_breach**: effective confidence < fail_floor — applies to ALL
      pattern types including invariants (accumulated failures → untrustworthy).
    - **stale**: idle > staleness_days AND effective conf < staleness_conf AND
      NOT invariant — time-archival exempts architectural/bsl patterns.

    Either trigger alone is sufficient.  The caller (handle_decay_confidence)
    sets ``expired_at`` when this returns True; it never hard-deletes.

    # TODO P3: neighbor-aware gate (needs link_registry) — before archiving,
    # check if pattern has downstream dependents; if yes, downweight rather
    # than archive.  Deferred pending link_registry API.

    Args:
        payload: Qdrant point payload dict (read-only).
        now: Reference datetime; defaults to :func:`datetime.now`.
        staleness_days: Days idle threshold for staleness check (default 180).
        staleness_conf: Effective-confidence ceiling for staleness (default 0.75).
        fail_floor: Effective-confidence floor below which any pattern archives
            (default 0.40).

    Returns:
        True iff the pattern should be archived.
    """
    now = now or datetime.now()
    eff = payload_effective_confidence(payload, now)

    # Resolve idle anchor: prefer last_applied, then last_decay_at, updated_at, created_at.
    anchor_raw: str | None = None
    for key in ("last_applied", "last_decay_at", "updated_at", "created_at"):
        val = payload.get(key)
        if val:
            anchor_raw = val
            break
    if anchor_raw is None:
        days_idle = 0
    else:
        days_idle = max(0, (now - datetime.fromisoformat(anchor_raw)).days)

    inv = is_invariant(payload.get("pattern_type", ""))

    # Fail-breach: any type (even invariant) with eff < fail_floor is archived.
    fail_breach = eff < fail_floor

    # Staleness: only non-invariant patterns, and only when idle long + conf low.
    stale = (days_idle > staleness_days) and (eff < staleness_conf) and (not inv)

    return fail_breach or stale


def payload_effective_confidence(
    payload: dict[str, Any],
    now: datetime | None = None,
) -> float:
    """Lazy decay-on-read: effective confidence from a payload's stored counts.

    Computes the Beta-posterior confidence after applying time-decay to the
    stored counts, decayed to *now*.  No I/O, no write — suitable for the
    search/get read-path (§22 P2).

    Args:
        payload: Qdrant point payload dict (read-only; not mutated).
        now: Reference datetime; defaults to :func:`datetime.now`.

    Returns:
        Effective posterior mean confidence after lazy decay.
    """
    now = now or datetime.now()
    succ, fail, lda, rate = _resolve_state(payload)
    return effective_confidence(succ, fail, lda, now, rate)


def apply_to_payload(
    payload: dict[str, Any],
    success: bool,
    now: datetime,
    *,
    default_decay_rate: float = DEFAULT_DECAY_RATE,
) -> dict[str, Any]:
    """Pure: given a Qdrant point payload + outcome, return the payload-field
    updates for a decayed-Beta confidence step. No I/O. Single source of the
    apply math (used by handle_apply_pattern and the reinforcement hook).

    Args:
        payload: Qdrant point payload dict (read-only; not mutated).
        success: True = success observation; False = failure observation.
        now: Current datetime reference (injected for testability).
        default_decay_rate: Fallback decay rate when payload lacks ``decay_rate``.

    Returns:
        Dict of field updates suitable for ``client.set_payload(...)``.
    """
    succ, fail, last_decay_at, decay_rate = _resolve_state(payload, default_decay_rate)
    succ, fail = apply_outcome(succ, fail, last_decay_at, now, decay_rate, success)
    new_conf = derive_confidence(succ, fail)

    return {
        "succ": succ,
        "fail": fail,
        "last_decay_at": now.isoformat(),
        "confidence": new_conf,
        "application_count": int(payload.get("application_count", 0)) + 1,
        "last_applied": now.isoformat(),
        "updated_at": now.isoformat(),
        # Revive-on-apply: any application un-archives the pattern (§22 P3).
        "expired_at": None,
    }
