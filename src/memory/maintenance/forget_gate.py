"""ForgetGate decay/archive planner — pure core (§26 P4, D4.2).

The bounded-growth gate: given ``learned_patterns`` payloads, decide which to
**archive** (invalidate-not-delete — set ``expired_at``) using the §22 P3
``should_archive`` policy. Invariant patterns (``architectural-principle`` /
``bsl-pattern``) are exempt from *time-based* staleness archival (they are still
fail-archived when effective confidence breaches the floor — that branch applies
to every type).

I/O-free: the CLI (``scripts/memory_maintenance.py``) scrolls Qdrant, calls
:func:`plan_forget`, and applies the plan via ``set_payload``. Reusing
``should_archive`` keeps the archival policy single-sourced with §22.

Roadmap: ``docs/roadmap/260602_ROADMAP_MEMORY_INGESTION_SYNC.md`` (§26 P4, D4.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.memory.vector_memory.confidence import (
    is_invariant,
    payload_effective_confidence,
    should_archive,
)


@dataclass(frozen=True)
class ForgetPlan:
    """Classification of learned_patterns points for the ForgetGate sweep."""

    archive: list[str] = field(default_factory=list)  # ids to mark expired_at
    keep: list[str] = field(default_factory=list)
    already_archived: list[str] = field(default_factory=list)
    invariant_protected: list[str] = field(default_factory=list)  # kept but would-be-stale


def _days_idle(payload: dict[str, Any], now: datetime) -> int:
    """Days since last actual use (last_applied → created_at). Mirrors should_archive."""
    for key in ("last_applied", "created_at"):
        val = payload.get(key)
        if val:
            try:
                return max(0, (now - datetime.fromisoformat(val)).days)
            except (ValueError, TypeError):
                return 0
    return 0


def _would_be_stale(
    payload: dict[str, Any],
    now: datetime,
    *,
    staleness_days: int = 180,
    staleness_conf: float = 0.75,
) -> bool:
    """Staleness condition IGNORING the invariant exemption (for the report only)."""
    return (
        _days_idle(payload, now) > staleness_days
        and payload_effective_confidence(payload, now) < staleness_conf
    )


def plan_forget(
    points: list[dict[str, Any]],
    now: datetime | None = None,
    *,
    staleness_days: int = 180,
    staleness_conf: float = 0.75,
    fail_floor: float = 0.40,
) -> ForgetPlan:
    """Classify points into archive / keep (ForgetGate, D4.2).

    ``points`` is a list of ``{"id", "payload"}`` dicts (Qdrant scroll shape).
    Already-archived points (``expired_at`` set) are reported separately and not
    re-archived. ``invariant_protected`` lists kept points that an invariant
    exemption rescued from staleness (so the report shows the bound working).
    """
    now = now or datetime.now()
    archive: list[str] = []
    keep: list[str] = []
    already: list[str] = []
    protected: list[str] = []
    for pt in points:
        payload = pt.get("payload") or {}
        pid = str(pt.get("id"))
        if payload.get("expired_at"):
            already.append(pid)
            continue
        if should_archive(
            payload,
            now,
            staleness_days=staleness_days,
            staleness_conf=staleness_conf,
            fail_floor=fail_floor,
        ):
            archive.append(pid)
        else:
            keep.append(pid)
            if is_invariant(payload.get("pattern_type", "")) and _would_be_stale(
                payload, now, staleness_days=staleness_days, staleness_conf=staleness_conf
            ):
                protected.append(pid)
    return ForgetPlan(
        archive=archive,
        keep=keep,
        already_archived=already,
        invariant_protected=protected,
    )


def summarize_forget(plan: ForgetPlan) -> dict[str, int]:
    """Counts for the dashboard."""
    return {
        "archive": len(plan.archive),
        "keep": len(plan.keep),
        "already_archived": len(plan.already_archived),
        "invariant_protected": len(plan.invariant_protected),
    }


__all__ = ["ForgetPlan", "plan_forget", "summarize_forget"]
