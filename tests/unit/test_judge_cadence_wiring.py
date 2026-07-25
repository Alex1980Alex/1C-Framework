"""J-P1 (roadmap 260725): проводка LLM-судьи в каденс обслуживания.

Инварианты:
  - у судьи СВОЙ cooldown (24ч) и свой ключ состояния — он не привязан к
    счётчику сессий каденса памяти (ревью-п.5: раздельные лимиты, не общий);
  - провайдер down → спавна нет, но и тишины нет (fail-soft с пометкой);
  - opt-out выключает ТОЛЬКО судью, каденс памяти продолжает работать.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "memory-maintenance-cadence.py"


@pytest.fixture(scope="module")
def hook_mod():
    sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
    spec = importlib.util.spec_from_file_location("memory_maintenance_cadence", HOOK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── cooldown судьи ────────────────────────────────────────────────────────────


def test_judge_due_on_first_run(hook_mod):
    assert hook_mod._judge_due({}) is True


def test_judge_not_due_within_cooldown(hook_mod):
    now = datetime(2026, 7, 25, 12, 0, 0)
    state = {"last_judge": (now - timedelta(hours=5)).isoformat()}
    assert hook_mod._judge_due(state, now) is False


def test_judge_due_after_cooldown(hook_mod):
    now = datetime(2026, 7, 25, 12, 0, 0)
    state = {"last_judge": (now - timedelta(hours=25)).isoformat()}
    assert hook_mod._judge_due(state, now) is True


def test_corrupt_timestamp_does_not_disable_judge_forever(hook_mod):
    """Битая отметка не должна навсегда выключить судью (иначе тихая смерть слоя)."""
    assert hook_mod._judge_due({"last_judge": "не дата"}) is True


def test_judge_cooldown_independent_of_memory_cadence(hook_mod):
    """Ключ судьи отдельный: заполненный memory-стейт сам по себе его не блокирует."""
    state = {"pending_sessions": ["a", "b"], "last_fire": datetime.now().isoformat()}
    assert hook_mod._judge_due(state) is True


def test_optout_disables_only_judge(hook_mod, monkeypatch):
    monkeypatch.setenv("TOOL_LLM_JUDGE_CADENCE_DISABLE", "1")
    assert hook_mod._judge_due({}) is False
    # каденс памяти живёт своей жизнью — его выключатель другой
    assert hook_mod._every() > 0


# ── fail-soft при недоступном провайдере ──────────────────────────────────────


def test_provider_down_detected(hook_mod, monkeypatch):
    fake = type(sys)("shared.llm_health")
    fake.is_provider_down = lambda: True  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "shared.llm_health", fake)
    assert hook_mod._provider_down() is True


def test_provider_check_failure_is_not_fatal(hook_mod, monkeypatch):
    """Нет хелпера/ошибка импорта → не считаем провайдер упавшим (решает судья)."""
    broken = type(sys)("shared.llm_health")

    def _boom():
        raise RuntimeError("нет данных")

    broken.is_provider_down = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "shared.llm_health", broken)
    assert hook_mod._provider_down() is False


# ── спавн ─────────────────────────────────────────────────────────────────────


def test_launch_judge_uses_detached_spawn(hook_mod, monkeypatch, tmp_path):
    captured: dict = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(hook_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(hook_mod, "JUDGE_LOG", tmp_path / "_judge.log")
    assert hook_mod._launch_judge() is True
    assert "tool_llm_judge.py" in " ".join(captured["cmd"])
    assert "--source" in captured["cmd"] and "auto" in captured["cmd"]
    assert "--cap" in captured["cmd"], "без потолка судья может сжечь бюджет"
    assert captured["kwargs"]["close_fds"] is True


def test_launch_judge_survives_os_error(hook_mod, monkeypatch, tmp_path):
    """Spawn-фейл не роняет Stop-хук — возвращаем False, вызывающий сообщит."""

    def boom(*_a, **_k):
        raise OSError("no fork")

    monkeypatch.setattr(hook_mod.subprocess, "Popen", boom)
    monkeypatch.setattr(hook_mod, "JUDGE_LOG", tmp_path / "_judge.log")
    assert hook_mod._launch_judge() is False


def test_missing_script_is_graceful(hook_mod, monkeypatch, tmp_path):
    monkeypatch.setattr(hook_mod, "JUDGE_SCRIPT", tmp_path / "нет-такого.py")
    assert hook_mod._launch_judge() is False
