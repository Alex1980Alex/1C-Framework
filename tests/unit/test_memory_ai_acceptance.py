"""Unit tests for the memory-ai acceptance criteria (roadmap 260612 §P4).

The file had zero coverage until 2026-07-17, which mattered: `acceptance_watch`
swallows any exception from collect_metrics/evaluate and simply prints no banner, so a
renamed key degrades into silence — the same "reports nothing, looks fine" failure the
criteria themselves exist to catch.

Criteria 5/6 were reworked the same day; see the module docstring for why an in-window
edge count is unsatisfiable for an idempotent job.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.memory_ai_acceptance import _reflection_wrote, evaluate

pytestmark = pytest.mark.unit


def _m(**over: Any) -> dict[str, Any]:
    """All-passing metrics; override one key per test."""
    base = {
        "episodes_non_session": 22,
        "surfacing_sqlite_fired": 460,
        "dup_events": 1,
        "rows_without_hash": 0,
        "reflection_clusters_triggered": 2,
        "reflection_write_events": 3,
        "archive_runs": 31,
    }
    base.update(over)
    return base


def test_all_green() -> None:
    crit = evaluate(_m())
    assert all(crit.values()), crit


def test_criteria_keys_are_the_contract() -> None:
    """evaluate() keys are rendered into the banner and the §18 verdict line."""
    assert set(evaluate(_m())) == {
        "episodes>=5",
        "surfacing_sqlite_fired",
        "dup_nonzero",
        "hash_complete",
        "reflection_reachable",
        "reflection_wrote",
        "archive_ran",
    }


@pytest.mark.parametrize(
    ("key", "value", "criterion"),
    [
        ("episodes_non_session", 4, "episodes>=5"),
        ("surfacing_sqlite_fired", 0, "surfacing_sqlite_fired"),
        ("dup_events", 0, "dup_nonzero"),
        ("rows_without_hash", 1, "hash_complete"),
        ("reflection_clusters_triggered", 0, "reflection_reachable"),
        ("reflection_write_events", 0, "reflection_wrote"),
        ("archive_runs", 0, "archive_ran"),
    ],
)
def test_each_criterion_can_fail(key: str, value: Any, criterion: str) -> None:
    """No criterion may be structurally unfalsifiable — that is how the old
    `archive_ran` (vacuously true) and `reflection>=1` (unsatisfiable) both slipped."""
    crit = evaluate(_m(**{key: value}))
    assert crit[criterion] is False
    assert not all(crit.values())


def test_reflection_reachable_catches_the_unreachable_trigger() -> None:
    """min_cluster=3 against a corpus whose largest cluster is 2 -> triggered=0."""
    assert evaluate(_m(reflection_clusters_triggered=0))["reflection_reachable"] is False


def test_reflection_write_events_are_windowed(tmp_path, monkeypatch) -> None:
    """Counting all history would latch green after one write and stop detecting the
    dry-run regression — the only thing this criterion is for."""
    import json as _json
    from datetime import datetime, timedelta

    import scripts.memory_ai_acceptance as mod

    now = datetime(2026, 7, 17, 12, 0, 0)
    log = tmp_path / "memory-ingestion.log"

    def _write(age_days: int) -> None:
        rec = {
            "ts": (now - timedelta(days=age_days)).isoformat(),
            "store": "learned_patterns",
            "action": "dup",
            "harvester": "reflection",
        }
        with log.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps(rec) + "\n")

    monkeypatch.setattr(mod, "INGEST_LOG", log)
    monkeypatch.setattr(mod, "REFLECTION_WRITE_MAX_AGE_DAYS", 30)

    _write(100)  # stale: reflect wrote once, long ago, then went quiet
    assert _reflection_wrote(now=now) == 0, "a stale write must not keep the gate green"

    _write(3)  # fresh: the cadence is still writing
    assert _reflection_wrote(now=now) == 1


def test_reflection_wrote_ignores_other_harvesters(tmp_path, monkeypatch) -> None:
    """Before harvester= was passed, reflect's writes fell back to "ingest_items" and
    were indistinguishable from every other caller's."""
    import json as _json
    from datetime import datetime

    import scripts.memory_ai_acceptance as mod

    now = datetime(2026, 7, 17, 12, 0, 0)
    log = tmp_path / "memory-ingestion.log"
    with log.open("w", encoding="utf-8") as fh:
        for harvester in ("patterns", "ingest_items", "skills-harvester"):
            fh.write(
                _json.dumps(
                    {
                        "ts": now.isoformat(),
                        "store": "learned_patterns",
                        "action": "dup",
                        "harvester": harvester,
                    }
                )
                + "\n"
            )
    monkeypatch.setattr(mod, "INGEST_LOG", log)

    assert _reflection_wrote(now=now) == 0


def test_reflection_wrote_catches_the_return_to_dry_run() -> None:
    """The enabling flag lives in gitignored settings.local.json: a clone, another
    machine, or a deleted line silently puts reflect back to dry-run (rc=0, writes 0).
    Corpus-derived checks stay green through that; this one must not.
    """
    m = _m(reflection_write_events=0)
    crit = evaluate(m)
    assert crit["reflection_reachable"] is True  # corpus unchanged...
    assert crit["reflection_wrote"] is False  # ...but nothing was written
    assert not all(crit.values())
