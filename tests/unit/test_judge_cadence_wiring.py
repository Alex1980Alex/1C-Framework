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


# ── execute(): проводка на месте ──────────────────────────────────────────────
# Тесты выше проверяют функции ИЗОЛИРОВАННО — они останутся зелёными, если удалить
# вызовы из execute() (дыра, найденная code-verify, Р4). Здесь пинится сама проводка.


def _fire_cadence(hook_mod, monkeypatch, tmp_path, state: dict, calls: dict):
    """Прогнать execute() на пороге фаера, подменив ввод-вывод состояния и спавны."""
    monkeypatch.setattr(hook_mod, "_load_state", lambda: dict(state))
    monkeypatch.setattr(hook_mod, "_save_state", lambda s: calls.setdefault("saved", []).append(s))
    monkeypatch.setattr(hook_mod, "_launch", lambda apply: True)
    monkeypatch.setattr(hook_mod, "_check_regressions", lambda *a, **k: None)
    monkeypatch.setattr(
        hook_mod,
        "_launch_judge",
        lambda: calls.setdefault("judge", 0) or calls.update(judge=1) or True,
    )
    monkeypatch.setenv("MEMORY_MAINTENANCE_EVERY", "2")
    monkeypatch.delenv("TOOL_LLM_JUDGE_CADENCE_DISABLE", raising=False)

    inp = type("I", (), {"detected_event": "Stop", "session_id": "s-new"})()
    return hook_mod.MemoryMaintenanceCadence().execute(inp)


def test_execute_spawns_judge_and_records_timestamp(hook_mod, monkeypatch, tmp_path):
    """Фаер каденса + судья due → судья запущен и отметка сохранена."""
    calls: dict = {}
    monkeypatch.setattr(hook_mod, "_provider_down", lambda: False)
    out = _fire_cadence(
        hook_mod, monkeypatch, tmp_path, {"pending_sessions": ["a"], "last_fire": None}, calls
    )
    assert calls.get("judge") == 1, "execute() не вызывает _launch_judge — проводка потеряна"
    assert any("last_judge" in s for s in calls.get("saved", [])), "отметка last_judge не записана"
    assert out is not None and "LLM-judge" in out._data.get("systemMessage", "")


def test_execute_skips_judge_when_provider_down(hook_mod, monkeypatch, tmp_path):
    """Провайдер лежит → спавна нет, но пользователь об этом узнаёт (не тишина)."""
    calls: dict = {}
    monkeypatch.setattr(hook_mod, "_provider_down", lambda: True)
    out = _fire_cadence(
        hook_mod, monkeypatch, tmp_path, {"pending_sessions": ["a"], "last_fire": None}, calls
    )
    assert "judge" not in calls
    assert out is not None and "провайдер недоступен" in out._data.get("systemMessage", "")


def test_execute_respects_judge_cooldown(hook_mod, monkeypatch, tmp_path):
    """Судья отработал час назад → каденс памяти фаерит, судья молчит."""
    calls: dict = {}
    monkeypatch.setattr(hook_mod, "_provider_down", lambda: False)
    state = {
        "pending_sessions": ["a"],
        "last_fire": None,
        "last_judge": datetime.now().isoformat(timespec="seconds"),
    }
    _fire_cadence(hook_mod, monkeypatch, tmp_path, state, calls)
    assert "judge" not in calls
