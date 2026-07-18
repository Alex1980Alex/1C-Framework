"""Регрессия N-P1 (roadmap 260718): досборка §6 decision layer.

N-P1.1 — probe (MCP-down≥2д→broken) + sink-регрессия (stale→degraded) сведены
         в единый infra_alerts (раньше жили параллельно, в вердикты не сходились).
N-P1.2 — verdicts.jsonl получил ЧИТАТЕЛЯ: повтор broken за 30д → p1, тренд
         broken↔healthy, healed-детект (петля закрыта).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import tool_verdict_history as tvh

_spec = importlib.util.spec_from_file_location("_ath_np1", _SCRIPTS / "analyze_tool_health.py")
ath = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ath)

NOW = datetime(2026, 7, 18, 12, 0, 0)


# ── N-P1.1: mcp_down_deps ─────────────────────────────────────────────────────


def _write_health(tmp_path, entries):
    p = tmp_path / "mcp-health.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    return p


def test_mcp_down_ge_2days_detected(tmp_path):
    entries = [
        {
            "ts": (NOW - timedelta(days=d)).isoformat(),
            "target": "qdrant",
            "ok": False,
            "affects": ["vector-memory"],
            "error": "refused",
        }
        for d in (4, 3, 2, 1, 0)
    ]
    down = ath.mcp_down_deps(NOW, log=_write_health(tmp_path, entries))
    assert len(down) == 1 and down[0]["dep"] == "qdrant"
    assert down[0]["affects"] == ["vector-memory"]


def test_mcp_recovered_not_flagged(tmp_path):
    entries = [
        {"ts": (NOW - timedelta(days=3)).isoformat(), "target": "tei", "ok": False, "affects": []},
        {"ts": NOW.isoformat(), "target": "tei", "ok": True, "affects": []},  # восстановился
    ]
    assert ath.mcp_down_deps(NOW, log=_write_health(tmp_path, entries)) == []


def test_mcp_down_under_2days_not_flagged(tmp_path):
    entries = [
        {"ts": (NOW - timedelta(hours=20)).isoformat(), "target": "tei", "ok": False, "affects": []}
    ]
    assert ath.mcp_down_deps(NOW, log=_write_health(tmp_path, entries)) == []


def test_mcp_no_history_empty(tmp_path):
    assert ath.mcp_down_deps(NOW, log=tmp_path / "missing.jsonl") == []


def test_apply_infra_broken_only_active_tools(tmp_path):
    tools = {
        "mcp__vector-memory__search": {"verdict": "healthy", "reason": "ok"},
        "mcp__vector-memory__save": {"verdict": "unused", "reason": "idle"},
        "Bash": {"verdict": "healthy", "reason": "ok"},
    }
    alerts = [{"level": "broken", "affects": ["vector-memory"], "reason": "qdrant down"}]
    ath.apply_infra_to_tools(tools, alerts)
    assert tools["mcp__vector-memory__search"]["verdict"] == "broken"
    assert tools["mcp__vector-memory__save"]["verdict"] == "unused"  # unused не трогаем
    assert tools["Bash"]["verdict"] == "healthy"  # чужой сервер


def test_gather_infra_alerts_all_up_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ath, "MCP_HEALTH_LOG", tmp_path / "none.jsonl")
    assert ath.gather_infra_alerts(NOW, with_sinks=False) == []


# ── N-P1.2: verdicts.jsonl reader ─────────────────────────────────────────────


def _verdicts(rows):
    return [{"ts": ts, "tool": t, "verdict": v} for ts, t, v in rows]


def test_repeat_broken_two_runs_true():
    rows = _verdicts(
        [
            ((NOW - timedelta(days=5)).isoformat(), "Bash", "broken"),
            ((NOW - timedelta(days=1)).isoformat(), "Bash", "broken"),
        ]
    )
    assert tvh.broken_repeat_within("Bash", NOW, 30, rows) is True


def test_repeat_broken_single_run_false():
    rows = _verdicts([((NOW - timedelta(days=1)).isoformat(), "Bash", "broken")])
    assert tvh.broken_repeat_within("Bash", NOW, 30, rows) is False


def test_repeat_broken_outside_window_false():
    rows = _verdicts(
        [
            ((NOW - timedelta(days=40)).isoformat(), "Bash", "broken"),
            ((NOW - timedelta(days=35)).isoformat(), "Bash", "broken"),
        ]
    )
    assert tvh.broken_repeat_within("Bash", NOW, 30, rows) is False


def test_verdict_trend_healed_and_regressed():
    rows = _verdicts(
        [
            ((NOW - timedelta(days=6)).isoformat(), "Bash", "broken"),
            ((NOW - timedelta(days=1)).isoformat(), "Bash", "healthy"),  # healed
            ((NOW - timedelta(days=6)).isoformat(), "Grep", "healthy"),
            ((NOW - timedelta(days=1)).isoformat(), "Grep", "broken"),  # regressed
        ]
    )
    tr = tvh.verdict_trend(NOW, 30, rows)
    assert tr["healed"] == 1 and "Bash" in tr["healed_tools"]
    assert tr["regressed"] == 1


def test_verdict_trend_persistent_broken():
    rows = _verdicts(
        [
            ((NOW - timedelta(days=6)).isoformat(), "X", "broken"),
            ((NOW - timedelta(days=1)).isoformat(), "X", "broken"),
        ]
    )
    assert tvh.verdict_trend(NOW, 30, rows)["persistent_broken"] == 1


def test_read_verdicts_skips_garbage(tmp_path):
    p = tmp_path / "verdicts.jsonl"
    p.write_text(
        '{"tool":"A","verdict":"broken","ts":"x"}\nNOT JSON\n{"no_tool":1}\n', encoding="utf-8"
    )
    rows = tvh.read_verdicts(p)
    assert len(rows) == 1 and rows[0]["tool"] == "A"


# ── N-P1.2: banner escalation logic (repeat→p1, healed) ───────────────────────


def _load_banner(monkeypatch):
    """Импортировать хук как модуль с замоканным task_master.add_task."""
    path = _ROOT / ".claude" / "hooks" / "tool-health-banner-on-start.py"
    hooks_dir = str(path.parent)
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    spec = importlib.util.spec_from_file_location("_banner_np1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_escalate_repeat_uses_p1(monkeypatch):
    mod = _load_banner(monkeypatch)
    captured = {}

    def fake_add_task(**kw):
        captured.update(kw)

    import shared.task_master as tm

    monkeypatch.setattr(tm, "add_task", fake_add_task)
    state = {}
    assert mod._escalate_broken("Bash", "0 из 5", NOW, state, repeat=True) is True
    assert captured["priority"] == "p1"
    assert "ПОВТОР" in captured["title"]
    assert isinstance(state["Bash"], dict) and state["Bash"]["escalated"] is True


def test_escalate_first_incident_high(monkeypatch):
    mod = _load_banner(monkeypatch)
    captured = {}
    import shared.task_master as tm

    monkeypatch.setattr(tm, "add_task", lambda **kw: captured.update(kw))
    assert mod._escalate_broken("Grep", "reason", NOW, {}, repeat=False) is True
    assert captured["priority"] == "high"


def test_escalate_cooldown_blocks_repeat(monkeypatch):
    mod = _load_banner(monkeypatch)
    import shared.task_master as tm

    monkeypatch.setattr(tm, "add_task", lambda **kw: None)
    recent = (NOW - timedelta(hours=1)).isoformat()
    state = {"Bash": {"ts": recent, "escalated": True}}
    assert mod._escalate_broken("Bash", "r", NOW, state) is False  # cooldown 336ч


def _run_banner_execute(mod, tmp_path, monkeypatch, sidecar, state):
    """Прогнать execute() баннера на подложенных sidecar/state (tmp), вернуть итоговый state."""
    import types

    sc = tmp_path / "_latest.json"
    stf = tmp_path / "state.json"
    vd = tmp_path / "verdicts.jsonl"
    sc.write_text(json.dumps(sidecar), encoding="utf-8")
    stf.write_text(json.dumps(state), encoding="utf-8")
    vd.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod, "SIDECAR", sc)
    monkeypatch.setattr(mod, "STATE_FILE", stf)
    monkeypatch.setattr(mod, "VERDICTS", vd)
    import shared.task_master as tm

    monkeypatch.setattr(tm, "add_task", lambda **kw: None)
    mod.ToolHealthBanner().execute(types.SimpleNamespace())
    return json.loads(stf.read_text(encoding="utf-8"))


def test_broken_to_degraded_not_healed(tmp_path, monkeypatch):
    """code-verify #1: тул был escalated (broken), теперь degraded — НЕ healed,
    cooldown-запись сохраняется (иначе флап degraded→broken обойдёт 336ч)."""
    mod = _load_banner(monkeypatch)
    sidecar = {
        "alerts": [{"tool": "Bash", "verdict": "degraded", "reason": "er 12%"}],
        "infra_alerts": [],
    }
    state = {"Bash": {"ts": (NOW - timedelta(hours=1)).isoformat(), "escalated": True}}
    out = _run_banner_execute(mod, tmp_path, monkeypatch, sidecar, state)
    assert "Bash" in out  # НЕ вылечен — degraded ≠ полное восстановление


def test_fully_recovered_is_healed(tmp_path, monkeypatch):
    """Полное восстановление (тул не в alerts вовсе) → healed, state очищается."""
    mod = _load_banner(monkeypatch)
    sidecar = {"alerts": [], "infra_alerts": []}
    state = {"Bash": {"ts": (NOW - timedelta(hours=1)).isoformat(), "escalated": True}}
    out = _run_banner_execute(mod, tmp_path, monkeypatch, sidecar, state)
    assert "Bash" not in out  # петля закрыта
