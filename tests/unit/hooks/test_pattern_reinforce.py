"""Unit tests for .claude/hooks/shared/pattern_reinforce.py (§22 P1 Pass 2a).

Covers:
- record_surfaced / load_surfaced round-trip (max-score merge)
- no-op guard: empty session_id or empty items list
- detect_session_success heuristic (commits / completed_tasks / both empty)
- reinforce_session: filtering by SCORE_THRESHOLD, cap, applied count
- Idempotency: second call for same session_id → already-processed
- Per-pattern cooldown: pre-seeded recent timestamp → pattern skipped
- Opt-out env var P1_REINFORCE_DISABLE=1
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Load the module under test via importlib (hook lives outside package tree)
# ---------------------------------------------------------------------------

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
_MODULE_PATH = _HOOKS_DIR / "shared" / "pattern_reinforce.py"


def _load_pr_module():
    """Load pattern_reinforce fresh with shared/ importable."""
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("pattern_reinforce", _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


pr = _load_pr_module()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redirect_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the module's CACHE_DIR to a tmp directory for isolation."""
    monkeypatch.setattr(pr, "CACHE_DIR", tmp_path)


def _fake_reinforce(calls: list[tuple[str, bool]]) -> Any:
    """Return a reinforce_fn that records calls and reports success."""

    def _fn(pid: str, success: bool, **_kw: Any) -> dict[str, Any]:
        calls.append((pid, success))
        return {"success": True, "pattern_id": pid}

    return _fn


# ---------------------------------------------------------------------------
# record_surfaced / load_surfaced
# ---------------------------------------------------------------------------


class TestRecordAndLoad:
    def test_round_trip(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        pr.record_surfaced("sess1", [("pid-a", 0.8), ("pid-b", 0.5)])
        result = pr.load_surfaced("sess1")
        assert result == {"pid-a": 0.8, "pid-b": 0.5}

    def test_keeps_max_score_on_duplicate(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        pr.record_surfaced("sess2", [("pid-x", 0.4)])
        pr.record_surfaced("sess2", [("pid-x", 0.9)])  # higher
        pr.record_surfaced("sess2", [("pid-x", 0.2)])  # lower — must NOT overwrite
        result = pr.load_surfaced("sess2")
        assert result["pid-x"] == 0.9

    def test_empty_session_id_noop(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        pr.record_surfaced("", [("pid-y", 0.7)])
        assert list(tmp_path.iterdir()) == []

    def test_empty_items_noop(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        pr.record_surfaced("sess3", [])
        assert list(tmp_path.iterdir()) == []

    def test_load_missing_file_returns_empty(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        assert pr.load_surfaced("nonexistent-session") == {}

    def test_load_corrupt_file_returns_empty(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        bad = tmp_path / "surfaced-patterns-corrupt.json"
        bad.write_text("not valid json", encoding="utf-8")
        assert pr.load_surfaced("corrupt") == {}


# ---------------------------------------------------------------------------
# detect_session_success
# ---------------------------------------------------------------------------


class TestDetectSessionSuccess:
    def test_commits_present(self):
        assert (
            pr.detect_session_success(
                {"commits": ["abc123"], "completed_tasks": [], "files_changed": []}
            )
            is True
        )

    def test_completed_tasks_present(self):
        assert (
            pr.detect_session_success(
                {"commits": [], "completed_tasks": ["do something"], "files_changed": []}
            )
            is True
        )

    def test_both_present(self):
        assert (
            pr.detect_session_success(
                {"commits": ["x"], "completed_tasks": ["t"], "files_changed": []}
            )
            is True
        )

    def test_both_empty(self):
        assert (
            pr.detect_session_success(
                {"commits": [], "completed_tasks": [], "files_changed": ["f.py"]}
            )
            is False
        )

    def test_missing_keys(self):
        assert pr.detect_session_success({}) is False


# ---------------------------------------------------------------------------
# reinforce_session — happy path
# ---------------------------------------------------------------------------


class TestReinforceSession:
    def test_applies_patterns_above_threshold(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        pr.record_surfaced(
            "s1",
            [
                ("high", 0.9),
                ("border", 0.3),  # exactly at threshold — should be included
                ("low", 0.29),  # just below — excluded
            ],
        )
        calls: list[tuple[str, bool]] = []
        result = pr.reinforce_session("s1", True, reinforce_fn=_fake_reinforce(calls))
        assert result["status"] == "ok"
        assert result["applied"] == 2
        pids_called = {pid for pid, _ in calls}
        assert "high" in pids_called
        assert "border" in pids_called
        assert "low" not in pids_called

    def test_respects_cap(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        items = [(f"pid-{i}", float(i) / 100) for i in range(60)]
        pr.record_surfaced("s-cap", items)
        calls: list[tuple[str, bool]] = []
        result = pr.reinforce_session("s-cap", True, cap=10, reinforce_fn=_fake_reinforce(calls))
        assert result["status"] == "ok"
        assert result["applied"] <= 10
        assert len(calls) <= 10

    def test_returns_ok_with_counts(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        pr.record_surfaced("s2", [("p1", 0.5), ("p2", 0.6)])
        calls: list[tuple[str, bool]] = []
        result = pr.reinforce_session("s2", False, reinforce_fn=_fake_reinforce(calls))
        assert result["status"] == "ok"
        assert "applied" in result
        assert "skipped" in result
        assert "errors" in result
        assert result["session_id"] == "s2"
        assert result["success"] is False

    def test_no_session_id(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        result = pr.reinforce_session("", True)
        assert result["status"] == "no-session"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_call_returns_already_processed(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        pr.record_surfaced("idem-sess", [("pid-q", 0.8)])
        calls: list[tuple[str, bool]] = []
        fn = _fake_reinforce(calls)

        first = pr.reinforce_session("idem-sess", True, reinforce_fn=fn)
        assert first["status"] == "ok"
        assert len(calls) == 1

        # Second call — same session_id — must NOT reinforce again
        second = pr.reinforce_session("idem-sess", True, reinforce_fn=fn)
        assert second["status"] == "already-processed"
        assert second["session_id"] == "idem-sess"
        assert len(calls) == 1  # fake_fn was NOT called again


# ---------------------------------------------------------------------------
# Per-pattern cooldown
# ---------------------------------------------------------------------------


class TestCooldown:
    def test_recently_reinforced_pattern_is_skipped(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        import json

        # Pre-seed sentinel: pid-cool was reinforced 1 minute ago
        recent_ts = (datetime.now() - timedelta(minutes=1)).isoformat()
        sentinel_data = {
            "sessions": [],
            "patterns": {"pid-cool": recent_ts},
        }
        sentinel_path = tmp_path / "p1-reinforcement-state.json"
        sentinel_path.write_text(json.dumps(sentinel_data), encoding="utf-8")

        pr.record_surfaced("cool-sess", [("pid-cool", 0.9), ("pid-fresh", 0.8)])
        calls: list[tuple[str, bool]] = []
        result = pr.reinforce_session(
            "cool-sess",
            True,
            cooldown_hours=1.0,  # 1 hour cooldown
            reinforce_fn=_fake_reinforce(calls),
        )
        assert result["status"] == "ok"
        pids_called = {pid for pid, _ in calls}
        assert "pid-cool" not in pids_called  # still in cooldown
        assert "pid-fresh" in pids_called  # no prior record → applied
        assert result["skipped"] == 1
        assert result["applied"] == 1


# ---------------------------------------------------------------------------
# Opt-out
# ---------------------------------------------------------------------------


class TestOptOut:
    def test_disable_env_var(self, monkeypatch, tmp_path):
        _redirect_cache(monkeypatch, tmp_path)
        monkeypatch.setenv("P1_REINFORCE_DISABLE", "1")
        calls: list[tuple[str, bool]] = []
        result = pr.reinforce_session("any-sess", True, reinforce_fn=_fake_reinforce(calls))
        assert result["status"] == "disabled"
        assert calls == []
