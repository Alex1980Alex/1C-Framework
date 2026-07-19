"""Tests for the Saturday known-issue nudge hook (ADR-055 layer-2 reminder)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[3]
_HOOKS = _ROOT / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))  # for `from base import ...`
_spec = importlib.util.spec_from_file_location(
    "kin_nudge", _HOOKS / "known-issue-saturday-nudge-on-start.py"
)
kin = importlib.util.module_from_spec(_spec)
sys.modules["kin_nudge"] = kin
_spec.loader.exec_module(kin)

SAT = datetime(2026, 7, 25)  # Saturday
SUN = datetime(2026, 7, 19)  # Sunday
KNOWN = {"T": {"review_by": "2026-08-31"}}


def test_saturday_nudges_nonexpired():
    assert kin.active_nudges(KNOWN, SAT) == ["T"]


def test_non_saturday_is_silent():
    assert kin.active_nudges(KNOWN, SUN) == []


def test_saturday_expired_not_nudged():
    # expired review_by → escalation path handles it, not the nudge
    assert kin.active_nudges({"T": {"review_by": "2026-01-01"}}, SAT) == []


def test_saturday_missing_date_not_nudged():
    # no review_by → _review_expired True → not suppressed → not nudged (consistent w/ analyzer)
    assert kin.active_nudges({"T": {}}, SAT) == []


def test_multiple_tools_sorted():
    known = {"B": {"review_by": "2026-08-31"}, "A": {"review_by": "2026-08-31"}}
    assert kin.active_nudges(known, SAT) == ["A", "B"]


def test_load_skips_doc_string_key(tmp_path, monkeypatch):
    cfg = tmp_path / "known_issues.json"
    cfg.write_text('{"_doc": "note", "T": {"review_by": "2026-08-31"}}', encoding="utf-8")
    monkeypatch.setattr(kin, "KNOWN_ISSUES", cfg)
    assert kin._load_known_issues() == {"T": {"review_by": "2026-08-31"}}


def test_load_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(kin, "KNOWN_ISSUES", tmp_path / "nope.json")
    assert kin._load_known_issues() == {}


def test_dedup_marks_and_detects_per_day(tmp_path, monkeypatch):
    monkeypatch.setattr(kin, "STATE", tmp_path / "state.json")
    assert kin._already_nudged_today(SAT) is False
    kin._mark_nudged(SAT)
    assert kin._already_nudged_today(SAT) is True
    assert kin._already_nudged_today(SUN) is False  # different day → not deduped


# ── execute() orchestration (code-verify rec.1) ─────────────────────────
def test_execute_optout_returns_none(monkeypatch):
    monkeypatch.setenv("KNOWN_ISSUE_NUDGE_DISABLE", "1")
    assert kin.KnownIssueSaturdayNudge().execute(None) is None


def test_execute_emits_banner_when_active(tmp_path, monkeypatch):
    monkeypatch.delenv("KNOWN_ISSUE_NUDGE_DISABLE", raising=False)
    monkeypatch.setattr(kin, "active_nudges", lambda known, now: ["T"])
    monkeypatch.setattr(kin, "_already_nudged_today", lambda now: False)
    monkeypatch.setattr(kin, "STATE", tmp_path / "state.json")
    out = kin.KnownIssueSaturdayNudge().execute(None)
    assert out is not None  # HookOutput with a systemMessage


def test_execute_deduped_returns_none(monkeypatch):
    monkeypatch.delenv("KNOWN_ISSUE_NUDGE_DISABLE", raising=False)
    monkeypatch.setattr(kin, "active_nudges", lambda known, now: ["T"])
    monkeypatch.setattr(kin, "_already_nudged_today", lambda now: True)
    assert kin.KnownIssueSaturdayNudge().execute(None) is None


def test_execute_silent_when_no_tools(monkeypatch):
    monkeypatch.delenv("KNOWN_ISSUE_NUDGE_DISABLE", raising=False)
    monkeypatch.setattr(kin, "active_nudges", lambda known, now: [])
    assert kin.KnownIssueSaturdayNudge().execute(None) is None
