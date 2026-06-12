"""Episodic retention policy (roadmap 260612 P3) — pure functions, stdlib-only.

P3.1 **lazy importance-decay on read**: stored ``importance`` is static; readers
rank with :func:`effective_importance` instead — old ``session_summary`` rows
drift down without any hot-path write (same invariant as §22 lazy decay-on-read
for vector confidence).

P3.2 **archive gate**: :func:`should_archive` mirrors §22 invalidate-not-delete —
the maintenance job stamps ``metadata.archived_at`` and readers filter via
:func:`is_archived`. Curated categories (``decision``/``preference``/``feedback``
etc.) are invariant: never decayed, never age-archived (roadmap §6 risk).
"""

from __future__ import annotations

import math
from datetime import datetime

# Only the episodic log decays/archives by age; everything else is curated
# knowledge and stays at full weight until explicitly deleted.
DECAY_CATEGORIES = frozenset({"session_summary", "general"})

# importance halves every N days for decayable categories (lazy, read-time).
HALF_LIFE_DAYS = 90.0

# archive_episodic job thresholds (P3.2): decayable rows older than this AND
# below the importance bar get an archive stamp (invalidate-not-delete).
ARCHIVE_AFTER_DAYS = 90.0
ARCHIVE_IMPORTANCE_BELOW = 0.8


def _age_days(created_at: str | None, now: datetime | None = None) -> float:
    """Row age in days; malformed/absent timestamps → 0 (no decay, fail-soft)."""
    if not created_at:
        return 0.0
    try:
        created = datetime.fromisoformat(str(created_at))
    except ValueError:
        return 0.0
    now = now or datetime.now()
    return max(0.0, (now - created).total_seconds() / 86400.0)


def effective_importance(
    importance: float,
    category: str | None,
    created_at: str | None,
    now: datetime | None = None,
) -> float:
    """Read-time importance with exponential age-decay for episodic categories."""
    if (category or "general") not in DECAY_CATEGORIES:
        return importance
    decay = math.exp(-math.log(2) * _age_days(created_at, now) / HALF_LIFE_DAYS)
    return importance * decay


def is_archived(metadata: dict | None) -> bool:
    """True when the maintenance job has stamped the row (readers filter it)."""
    return bool(metadata and metadata.get("archived_at"))


def should_archive(
    category: str | None,
    created_at: str | None,
    importance: float,
    now: datetime | None = None,
) -> bool:
    """Archive gate for the maintenance job — age + importance, decayables only."""
    if (category or "general") not in DECAY_CATEGORIES:
        return False
    return _age_days(created_at, now) > ARCHIVE_AFTER_DAYS and importance < ARCHIVE_IMPORTANCE_BELOW


__all__ = [
    "ARCHIVE_AFTER_DAYS",
    "ARCHIVE_IMPORTANCE_BELOW",
    "DECAY_CATEGORIES",
    "HALF_LIFE_DAYS",
    "effective_importance",
    "is_archived",
    "should_archive",
]
