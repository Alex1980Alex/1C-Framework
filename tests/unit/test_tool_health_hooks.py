"""Регрессия P1.1 хуков (roadmap 260713): Stop-аналайзер (cooldown) + SessionStart-баннер (эскалация).

Баннер: broken/degraded → system_message; всё healthy → молчит; broken → авто-задача
с cooldown-дедупом на тул; degraded НЕ эскалируется. Stop: cooldown 24ч гейтит спавн.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _HOOKS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── SessionStart banner ──────────────────────────────────────────────────────


def _banner(monkeypatch, tmp_path, sidecar: dict | None, task_calls: list):
    """Загрузить banner-хук с подменёнными путями + фейк task_master."""
    mod = _load("_thb", "tool-health-banner-on-start.py")
    if sidecar is not None:
        p = tmp_path / "_latest.json"
        p.write_text(json.dumps(sidecar), encoding="utf-8")
        monkeypatch.setattr(mod, "SIDECAR", p)
    else:
        monkeypatch.setattr(mod, "SIDECAR", tmp_path / "missing.json")
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    # фейк shared.task_master.add_task
    tm = ModuleType("shared.task_master")
    tm.add_task = lambda **k: task_calls.append(k)
    monkeypatch.setitem(sys.modules, "shared.task_master", tm)
    return mod


def test_banner_quiet_when_all_healthy(monkeypatch, tmp_path):
    mod = _banner(monkeypatch, tmp_path, {"window_days": 14, "alerts": []}, [])
    out = mod.ToolHealthBanner().execute(mod.HookInput({}))
    assert out is None  # молчит


def test_banner_quiet_when_no_report(monkeypatch, tmp_path):
    mod = _banner(monkeypatch, tmp_path, None, [])
    out = mod.ToolHealthBanner().execute(mod.HookInput({}))
    assert out is None


def test_banner_surfaces_broken_and_degraded(monkeypatch, tmp_path):
    task_calls: list = []
    sidecar = {
        "window_days": 14,
        "generated": datetime.now().isoformat(),
        "alerts": [
            {"tool": "mcp__x__y", "verdict": "broken", "reason": "0 успешных из 5"},
            {"tool": "Bash", "verdict": "degraded", "reason": "error-rate 15%"},
        ],
    }
    mod = _banner(monkeypatch, tmp_path, sidecar, task_calls)
    out = mod.ToolHealthBanner().execute(mod.HookInput({}))
    assert out is not None
    msg = out._data.get("systemMessage", "")
    assert "broken" in msg and "mcp__x__y" in msg
    assert "degraded" in msg and "Bash" in msg


def test_banner_escalates_broken_only(monkeypatch, tmp_path):
    """broken → авто-задача; degraded → НЕ создаёт задачу."""
    task_calls: list = []
    sidecar = {
        "window_days": 14,
        "generated": datetime.now().isoformat(),
        "alerts": [
            {"tool": "mcp__x__y", "verdict": "broken", "reason": "r"},
            {"tool": "Bash", "verdict": "degraded", "reason": "r"},
        ],
    }
    mod = _banner(monkeypatch, tmp_path, sidecar, task_calls)
    mod.ToolHealthBanner().execute(mod.HookInput({}))
    assert len(task_calls) == 1
    assert task_calls[0]["title"].startswith("Диагностировать инструмент mcp__x__y")
    assert task_calls[0]["priority"] == "high"


def test_banner_escalation_cooldown_dedup(monkeypatch, tmp_path):
    """Повторный запуск в пределах cooldown НЕ создаёт задачу повторно."""
    task_calls: list = []
    sidecar = {
        "window_days": 14,
        "generated": datetime.now().isoformat(),
        "alerts": [{"tool": "mcp__x__y", "verdict": "broken", "reason": "r"}],
    }
    mod = _banner(monkeypatch, tmp_path, sidecar, task_calls)
    mod.ToolHealthBanner().execute(mod.HookInput({}))
    mod.ToolHealthBanner().execute(mod.HookInput({}))  # второй раз — cooldown
    assert len(task_calls) == 1  # не 2


# ── Stop analyzer cooldown ───────────────────────────────────────────────────


def test_stop_cooldown_blocks_respawn(monkeypatch, tmp_path):
    mod = _load("_thas", "tool-health-analyzer-stop.py")
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    spawned = []
    monkeypatch.setattr(mod, "_spawn", lambda: spawned.append(1) or True)
    # свежий last_fire (только что) → cooldown → нет спавна
    mod._save_last_fire(datetime.now())
    out = mod.ToolHealthAnalyzerStop().execute(mod.HookInput({"reason": "stop"}))
    assert out is None
    assert spawned == []


def test_stop_spawns_when_stale(monkeypatch, tmp_path):
    mod = _load("_thas2", "tool-health-analyzer-stop.py")
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    spawned = []
    monkeypatch.setattr(mod, "_spawn", lambda: spawned.append(1) or True)
    # last_fire 2 дня назад → cooldown прошёл → спавн
    mod._save_last_fire(datetime.now() - timedelta(hours=48))
    out = mod.ToolHealthAnalyzerStop().execute(mod.HookInput({"reason": "stop"}))
    assert spawned == [1]
    assert out is not None  # system_message о запуске


def test_stop_opt_out(monkeypatch, tmp_path):
    mod = _load("_thas3", "tool-health-analyzer-stop.py")
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    spawned = []
    monkeypatch.setattr(mod, "_spawn", lambda: spawned.append(1) or True)
    monkeypatch.setenv("TOOL_HEALTH_ANALYZER_DISABLE", "1")
    out = mod.ToolHealthAnalyzerStop().execute(mod.HookInput({"reason": "stop"}))
    assert out is None and spawned == []
