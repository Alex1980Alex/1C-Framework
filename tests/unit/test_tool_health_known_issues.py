"""Tests for the known-issues ('xfail for tools') suppression layer (ADR-055).

Covers _review_expired + _apply_known_issues overlay: broken→known-issue,
healthy→recovered (xpass), expired→leaves verdict, missing-date→fail-closed,
config-absent=noop, tool-absent=skip.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "analyze_tool_health.py"
_spec = importlib.util.spec_from_file_location("analyze_tool_health", _SCRIPT)
ath = importlib.util.module_from_spec(_spec)
sys.modules["analyze_tool_health"] = ath
_spec.loader.exec_module(ath)

_TVH_SPEC = importlib.util.spec_from_file_location(
    "tool_verdict_history", _ROOT / "scripts" / "tool_verdict_history.py"
)
tvh = importlib.util.module_from_spec(_TVH_SPEC)
sys.modules["tool_verdict_history"] = tvh
_TVH_SPEC.loader.exec_module(tvh)

NOW = datetime(2026, 7, 19, 12, 0, 0)
FUTURE = "2026-08-31"
PAST = "2026-01-01"


# ── _review_expired ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "review_by,expected",
    [
        (FUTURE, False),
        (PAST, True),
        ("", True),  # missing → fail-closed to visibility
        (None, True),
        ("not-a-date", True),  # unparseable → fail-closed
    ],
)
def test_review_expired(review_by, expected):
    assert ath._review_expired(review_by, NOW) is expected


# ── _apply_known_issues overlay ─────────────────────────────────────────
def _tool(verdict, reason="orig"):
    return {"verdict": verdict, "reason": reason, "calls": 5, "success": 0}


def test_broken_becomes_known_issue():
    tools = {"T": _tool("broken")}
    known = {"T": {"reason": "upstream bug", "ref": "W13", "review_by": FUTURE}}
    ath._apply_known_issues(tools, NOW, known=known)
    assert tools["T"]["verdict"] == "known-issue"
    assert tools["T"]["underlying_verdict"] == "broken"
    assert "upstream bug" in tools["T"]["reason"] and "W13" in tools["T"]["reason"]
    assert tools["T"]["known_issue"]["expired"] is False


def test_healthy_flags_recovered_xpass():
    tools = {"T": _tool("healthy")}
    known = {"T": {"reason": "r", "ref": "W13", "review_by": FUTURE}}
    ath._apply_known_issues(tools, NOW, known=known)
    assert tools["T"]["verdict"] == "healthy"  # verdict untouched
    assert tools["T"]["recovered_known_issue"] is True


def test_expired_leaves_real_verdict():
    tools = {"T": _tool("broken")}
    known = {"T": {"reason": "r", "ref": "W13", "review_by": PAST}}
    ath._apply_known_issues(tools, NOW, known=known)
    assert tools["T"]["verdict"] == "broken"  # re-escalates
    assert tools["T"]["known_issue"]["expired"] is True
    assert "underlying_verdict" not in tools["T"]


def test_missing_review_by_fail_closed():
    tools = {"T": _tool("broken")}
    known = {"T": {"reason": "r", "ref": "W13"}}  # no review_by
    ath._apply_known_issues(tools, NOW, known=known)
    assert tools["T"]["verdict"] == "broken"  # not suppressed (no permanent silent mute)


def test_config_absent_is_noop():
    tools = {"T": _tool("broken")}
    ath._apply_known_issues(tools, NOW, known={})
    assert tools["T"]["verdict"] == "broken"
    assert "known_issue" not in tools["T"]


def test_tool_not_present_is_skipped():
    tools = {"OTHER": _tool("healthy")}
    known = {"MISSING": {"reason": "r", "ref": "W13", "review_by": FUTURE}}
    ath._apply_known_issues(tools, NOW, known=known)  # must not raise
    assert "known_issue" not in tools["OTHER"]


def test_degraded_and_ineffective_also_suppressed():
    for v in ("degraded", "ineffective"):
        tools = {"T": _tool(v)}
        known = {"T": {"reason": "r", "ref": "W13", "review_by": FUTURE}}
        ath._apply_known_issues(tools, NOW, known=known)
        assert tools["T"]["verdict"] == "known-issue"
        assert tools["T"]["underlying_verdict"] == v


# ── verdict registry integrity (summary/emoji rendering won't KeyError) ──
def test_known_issue_in_verdict_registry():
    assert "known-issue" in ath._VERDICT_ORDER
    assert "known-issue" in ath._VERDICT_MARK
    # every ordered verdict must have a mark (render_md iterates _VERDICT_ORDER using _VERDICT_MARK)
    for v in ath._VERDICT_ORDER:
        assert v in ath._VERDICT_MARK


# ── trend: broken→known-issue is suppressed, NOT healed (ADR-055, code-verify rec.1) ──
def test_trend_known_issue_not_counted_as_healed():
    rows = [
        {"tool": "SUP", "ts": "2026-07-10T10:00:00", "verdict": "broken"},
        {"tool": "SUP", "ts": "2026-07-15T10:00:00", "verdict": "known-issue"},
        {"tool": "FIX", "ts": "2026-07-10T10:00:00", "verdict": "broken"},
        {"tool": "FIX", "ts": "2026-07-15T10:00:00", "verdict": "healthy"},
    ]
    tr = tvh.verdict_trend(datetime(2026, 7, 19), 30, rows)
    assert "SUP" not in tr["healed_tools"]  # suppressed, not healed
    assert "FIX" in tr["healed_tools"]  # genuine recovery still counts
