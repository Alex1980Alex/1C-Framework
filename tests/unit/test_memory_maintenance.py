"""Unit tests for §26 P4 maintenance cores: ForgetGate planner + dashboard.

ForgetGate (D4.2): archive decisions reuse §22 P3 ``should_archive`` — fresh/
high-conf kept, fail-breached archived, stale non-invariant archived, stale
**invariant** protected (kept + flagged). Dashboard (D4.3): ingest aggregation,
store-size totals, report sections.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.memory.maintenance.dashboard import (
    aggregate_ingest_events,
    build_dashboard,
    render_dashboard,
)
from src.memory.maintenance.forget_gate import plan_forget, summarize_forget

pytestmark = pytest.mark.unit

NOW = datetime(2026, 6, 5, 12, 0, 0)


def _pt(
    pid: str,
    *,
    succ: float,
    fail: float,
    age_days: int = 0,
    pattern_type: str = "workflow-pattern",
    expired: bool = False,
) -> dict:
    payload = {
        "succ": succ,
        "fail": fail,
        "last_decay_at": NOW.isoformat(),  # no time-decay of counts -> eff = ratio
        "created_at": (NOW - timedelta(days=age_days)).isoformat(),
        "pattern_type": pattern_type,
    }
    if expired:
        payload["expired_at"] = (NOW - timedelta(days=10)).isoformat()
    return {"id": pid, "payload": payload}


class TestForgetGate:
    def test_fresh_high_conf_kept(self):
        # succ=10/fail=0 -> eff=0.85; fresh -> keep
        plan = plan_forget([_pt("a", succ=10, fail=0, age_days=0)], NOW)
        assert plan.keep == ["a"]
        assert plan.archive == []

    def test_fail_breach_archived_even_when_fresh(self):
        # succ=0/fail=20 -> eff≈0.23 < 0.40 -> archive regardless of age
        plan = plan_forget([_pt("b", succ=0, fail=20, age_days=0)], NOW)
        assert plan.archive == ["b"]

    def test_stale_non_invariant_archived(self):
        # eff≈0.47 (0.40<eff<0.75), idle 200d, ordinary type -> stale -> archive
        plan = plan_forget([_pt("c", succ=0, fail=5, age_days=200)], NOW)
        assert plan.archive == ["c"]

    def test_stale_invariant_protected(self):
        # same staleness but bsl-pattern -> kept + flagged invariant_protected
        plan = plan_forget(
            [_pt("d", succ=0, fail=5, age_days=200, pattern_type="bsl-pattern")], NOW
        )
        assert plan.archive == []
        assert plan.keep == ["d"]
        assert plan.invariant_protected == ["d"]

    def test_invariant_still_fail_archived(self):
        # invariants are exempt from STALENESS only — fail-breach still archives
        plan = plan_forget(
            [_pt("e", succ=0, fail=20, age_days=200, pattern_type="bsl-pattern")], NOW
        )
        assert plan.archive == ["e"]

    def test_already_archived_separated(self):
        plan = plan_forget([_pt("f", succ=0, fail=5, age_days=200, expired=True)], NOW)
        assert plan.already_archived == ["f"]
        assert plan.archive == [] and plan.keep == []

    def test_summarize(self):
        plan = plan_forget(
            [
                _pt("a", succ=10, fail=0),  # keep
                _pt("b", succ=0, fail=20),  # archive
                _pt("f", succ=0, fail=5, age_days=200, expired=True),  # already
            ],
            NOW,
        )
        s = summarize_forget(plan)
        assert s == {"archive": 1, "keep": 1, "already_archived": 1, "invariant_protected": 0}


class TestDashboard:
    def test_aggregate_ingest_events(self):
        events = [
            {"event": "ingest", "action": "saved"},
            {"event": "ingest", "action": "saved"},
            {"event": "ingest", "action": "saved"},
            {"event": "ingest", "action": "dup"},
            {"event": "store_size", "store": "learned_patterns", "size": 44},
        ]
        agg = aggregate_ingest_events(events)
        assert agg["attempted"] == 4
        assert agg["saved"] == 3
        assert agg["dup_rate"] == 0.25
        assert agg["logged_store_sizes"] == {"learned_patterns": 44}

    def test_aggregate_empty_safe(self):
        agg = aggregate_ingest_events([])
        assert agg["attempted"] == 0
        assert agg["dup_rate"] == 0.0

    def test_build_dashboard_totals(self):
        dash = build_dashboard(store_sizes={"learned_patterns": 44, "memory_ai": 98})
        assert dash["total_facts"] == 142

    def test_render_dashboard_sections(self):
        dash = build_dashboard(
            store_sizes={"learned_patterns": 44},
            cross_store={"cross_store_dup_rate": 0.2, "cross_store_dup_count": 19},
            forget={"archive": 1, "keep": 40, "already_archived": 0, "invariant_protected": 2},
            ingest={"attempted": 10, "saved": 7, "dup_rate": 0.3, "actions": {"saved": 7}},
        )
        out = render_dashboard(dash, "20260605_000000")
        assert "Store sizes" in out
        assert "total facts" in out
        assert "ForgetGate" in out
        assert "cross_store_dup_rate" in out
        assert "Ingestion" in out


class TestMergeJob:
    """§БП G2 (audit 260705) — background-consolidation job wired into the cadence.

    Guards that ``run_merge_patterns`` runs the previously-orphaned
    ``PatternMerger`` over the skill_learning SAVED silo: dry-run reports without
    writing, ``--apply`` rewrites the deduped silo (with .bak backup), fail-soft.
    """

    @staticmethod
    def _write_silo(path, records):
        import json

        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
            encoding="utf-8",
        )

    def _patched_module(self, monkeypatch, silo_path):
        import scripts.memory_maintenance as mm

        monkeypatch.setattr(mm, "SKILL_JSONL", silo_path)
        return mm

    def test_dry_run_finds_dupes_without_writing(self, tmp_path, monkeypatch):
        silo = tmp_path / "patterns.jsonl"
        # two records that normalize to the same content (whitespace/case) —
        # the exact-hash write-contract would NOT collapse these; the merger does.
        self._write_silo(
            silo,
            [
                {"pattern_id": "a", "name": "Alpha", "content": "Do  X", "confidence": 0.9},
                {"pattern_id": "b", "name": "Beta", "content": "do x", "confidence": 0.7},
                {"pattern_id": "c", "name": "Gamma", "content": "unique thing", "confidence": 0.8},
            ],
        )
        mm = self._patched_module(monkeypatch, silo)
        before = silo.read_text(encoding="utf-8")

        r = mm.run_merge_patterns(apply=False, now=NOW)

        assert "error" not in r
        assert r["duplicates_found"] == 1
        assert r["patterns_merged"] == 1
        assert r["patterns_kept"] == 2
        assert r["applied"] is False
        assert silo.read_text(encoding="utf-8") == before  # dry-run never writes
        assert not (tmp_path / "patterns.jsonl.bak").exists()

    def test_apply_writes_deduped_with_backup(self, tmp_path, monkeypatch):
        import json

        silo = tmp_path / "patterns.jsonl"
        self._write_silo(
            silo,
            [
                {"pattern_id": "a", "name": "Alpha", "content": "Do  X", "confidence": 0.9},
                {"pattern_id": "b", "name": "Beta", "content": "do x", "confidence": 0.7},
            ],
        )
        mm = self._patched_module(monkeypatch, silo)

        r = mm.run_merge_patterns(apply=True, now=NOW)

        assert r["applied"] is True
        assert r["patterns_merged"] == 1
        assert (tmp_path / "patterns.jsonl.bak").exists()  # snapshot before rewrite
        kept = [json.loads(x) for x in silo.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert len(kept) == 1
        assert kept[0]["confidence"] == 0.9  # keep-higher-confidence winner

    def test_fail_soft_on_bad_storage(self, tmp_path, monkeypatch):
        # storage_dir that cannot be read as a file → PatternMerger.load returns []
        # (missing file), so the job reports empty rather than raising.
        missing = tmp_path / "nope" / "patterns.jsonl"
        mm = self._patched_module(monkeypatch, missing)
        r = mm.run_merge_patterns(apply=True, now=NOW)
        assert "error" not in r
        assert r["patterns_kept"] == 0
        assert r["applied"] is False
