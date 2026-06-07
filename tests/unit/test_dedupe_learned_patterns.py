"""Unit tests for the learned_patterns dedupe planner (Qdrant-independent)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _ROOT / "scripts" / "dedupe_learned_patterns.py"


def _load():
    spec = importlib.util.spec_from_file_location("dedupe_learned_patterns", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


D = _load()


def _pt(pid, content, *, pattern_id=False, created="2026-01-01", succ=0, fail=0, appc=0):
    pl = {
        "content": content,
        "created_at": created,
        "succ": succ,
        "fail": fail,
        "application_count": appc,
    }
    if pattern_id:
        pl["pattern_id"] = pid
    return {"id": pid, "payload": pl}


def test_content_key_groups_identical():
    assert D.content_key({"content": "x"}) == D.content_key({"description": "x"})
    assert D.content_key({"content": "x"}) != D.content_key({"content": "y"})


def test_pick_survivor_prefers_pattern_schema_then_oldest():
    g = [
        _pt("a", "c", pattern_id=False, created="2026-01-01"),
        _pt("b", "c", pattern_id=True, created="2026-02-01"),  # richer schema wins despite newer
        _pt("c", "c", pattern_id=False, created="2025-12-01"),
    ]
    assert D.pick_survivor(g)["id"] == "b"
    # No pattern schema -> earliest created_at wins.
    g2 = [_pt("a", "c", created="2026-03-01"), _pt("b", "c", created="2026-01-01")]
    assert D.pick_survivor(g2)["id"] == "b"


def test_build_plan_dedup_counts():
    points = [
        _pt("a", "dup", created="2026-01-01"),
        _pt("b", "dup", created="2026-02-01"),
        _pt("c", "dup", created="2026-03-01"),
        _pt("d", "unique", created="2026-01-01"),
    ]
    plan = D.build_plan(points, drop_test=False)
    assert plan["total"] == 4
    assert plan["unique_groups"] == 2
    assert plan["dup_groups"] == 1
    assert set(plan["dup_delete_ids"]) == {"b", "c"}  # 'a' (oldest) survives
    assert plan["final_count"] == 2


def test_build_plan_merges_nonzero_stats_and_recomputes_confidence():
    points = [
        _pt("a", "dup", created="2026-01-01", succ=2, fail=1, appc=3),
        _pt("b", "dup", created="2026-02-01", succ=1, fail=0, appc=1),
    ]
    plan = D.build_plan(points, drop_test=False)
    assert plan["dup_delete_ids"] == ["b"]
    upd = plan["survivor_updates"][0]
    assert upd["id"] == "a"
    assert upd["succ"] == 3 and upd["fail"] == 1 and upd["application_count"] == 4
    # Beta(7,3): (7+3)/(10+3+1) = 10/14 ≈ 0.7143
    assert upd["confidence"] == pytest.approx(10 / 14, abs=1e-3)


def test_build_plan_no_stat_update_when_all_zero():
    points = [_pt("a", "dup", created="2026-01-01"), _pt("b", "dup", created="2026-02-01")]
    plan = D.build_plan(points, drop_test=False)
    assert plan["survivor_updates"] == []  # 0+0 == existing 0 -> no write


def test_drop_test_exact_match_only_and_opt_in():
    points = [
        _pt("a", "Entity lookup test content", created="2026-01-01"),
        _pt("b", "a real pattern that mentions test content inline", created="2026-01-01"),
    ]
    # opt-out: nothing dropped
    assert D.build_plan(points, drop_test=False)["test_delete_ids"] == []
    # opt-in: only the EXACT marker, not the substring match
    plan = D.build_plan(points, drop_test=True)
    assert plan["test_delete_ids"] == ["a"]


def test_derive_confidence_prior():
    assert D.derive_confidence(0, 0) == pytest.approx(0.70, abs=1e-6)
