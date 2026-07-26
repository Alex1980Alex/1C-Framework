"""Потеря записи session_state перестала быть невидимой (2026-07-26).

`_save_state` честно ре-райзит провал `os.replace`, но ВСЕ вызывающие (наблюдатель,
энфорсеры, роутер) глушат исключение `except Exception: pass` — факт умирал там, и класс
лечился только фолбэками, а частота была неизвестна. Теперь единая точка `_mutate` пишет
крошку в `.claude/cache/session-state-failures.jsonl`, читатель её агрегирует, каденс
сюрфейсит.

Пинятся: факт пишется и исключение по-прежнему поднимается; провал записи крошки не
подменяет исходную ошибку; opt-out; ротация; `lock_fail_open` как ведущий индикатор;
независимость двух мутаций в наблюдателе; агрегаты читателя.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_HOOKS = _ROOT / ".claude" / "hooks"


@pytest.fixture
def ss(monkeypatch, tmp_path):
    """session_state с состоянием и логом аномалий в tmp (без сети и реального репо)."""
    import sys

    if str(_HOOKS) not in sys.path:
        sys.path.insert(0, str(_HOOKS))
    monkeypatch.setenv("SESSION_STATE_PATH", str(tmp_path / "state"))
    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("SESSION_STATE_FAILLOG_DISABLE", raising=False)
    from shared import session_state as mod

    importlib.reload(mod)
    mod.SessionState._state_cache = None
    monkeypatch.setattr(mod.time, "sleep", lambda *_a: None)  # ретраи os.replace без ожидания
    return mod


def _faillog(ss) -> Path:
    return ss._faillog_path()


def _events(ss) -> list[dict]:
    p = _faillog(ss)
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _break_replace(monkeypatch, ss):
    """os.replace всегда падает PermissionError — воспроизводит живую гонку на Windows."""

    def boom(*_a, **_k):
        raise PermissionError(13, "used by another process")

    monkeypatch.setattr(ss.os, "replace", boom)


# ── факт потери ────────────────────────────────────────────────────────────────


def test_lost_mutation_is_recorded_and_still_raises(ss, monkeypatch):
    _break_replace(monkeypatch, ss)

    with pytest.raises(PermissionError):
        ss.SessionState.record_skill_checked()

    events = _events(ss)
    assert len(events) == 1
    rec = events[0]
    assert rec["event"] == "mutation_lost"
    assert rec["op"] == "record_skill_checked"  # метка выведена из фрейма вызывающего
    assert rec["error_type"] == "PermissionError"
    assert rec["locked"] is True


def test_breadcrumb_failure_does_not_mask_original_error(ss, monkeypatch):
    """Диагностика не имеет права стать причиной сбоя и не должна подменять ошибку."""
    _break_replace(monkeypatch, ss)

    def boom_path():
        raise RuntimeError("лог недоступен")

    monkeypatch.setattr(ss, "_faillog_path", boom_path)

    with pytest.raises(PermissionError):  # именно исходная, не RuntimeError
        ss.SessionState.record_decomposition()


def test_optout_disables_log(ss, monkeypatch):
    monkeypatch.setenv("SESSION_STATE_FAILLOG_DISABLE", "1")
    _break_replace(monkeypatch, ss)

    with pytest.raises(PermissionError):
        ss.SessionState.record_skill_checked()

    assert not _faillog(ss).exists()


def test_successful_mutation_writes_nothing(ss):
    ss.SessionState.record_skill_checked()
    assert ss.SessionState.get_task_protocol()["phase"] == "skill_checked"
    assert _events(ss) == []  # happy path не шумит


def test_rotation_keeps_newest_half(ss, monkeypatch):
    log = _faillog(ss)
    log.parent.mkdir(parents=True, exist_ok=True)
    old = json.dumps({"event": "mutation_lost", "op": "САМАЯ-СТАРАЯ"}, ensure_ascii=False)
    filler = json.dumps({"event": "mutation_lost", "op": "x" * 200}, ensure_ascii=False)
    lines = [old] + [filler] * (ss._FAILLOG_CAP_BYTES // 200 + 20)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert log.stat().st_size > ss._FAILLOG_CAP_BYTES

    ss.SessionState._record_anomaly("mutation_lost", "после-ротации")

    text = log.read_text(encoding="utf-8", errors="replace")
    assert log.stat().st_size <= ss._FAILLOG_CAP_BYTES
    assert "САМАЯ-СТАРАЯ" not in text  # старое отрезано
    assert "после-ротации" in text  # новое дописано


# ── ведущий индикатор: лок не взят ─────────────────────────────────────────────


def test_lock_fail_open_recorded_on_success(ss, monkeypatch):
    @contextmanager
    def no_lock():
        yield False  # ожидание истекло → работаем без взаимного исключения

    monkeypatch.setattr(ss.SessionState, "_ipc_lock", classmethod(lambda cls: no_lock()))

    ss.SessionState.record_llm_delegation()  # мутация УДАЛАСЬ

    events = _events(ss)
    assert [e["event"] for e in events] == ["lock_fail_open"]
    assert events[0]["op"] == "record_llm_delegation"


def test_no_lock_event_when_lock_acquired(ss):
    ss.SessionState.set_task_classified("medium")
    assert _events(ss) == []


# ── независимость мутаций в наблюдателе ────────────────────────────────────────


def test_observer_registers_skill_even_if_phase_write_fails(ss, monkeypatch):
    """Живой инцидент: падение record_skill_checked уносило add_activated_skill в том же
    try, хотя они питают РАЗНЫЕ энфорсеры (фаза и имя скилла)."""
    spec = importlib.util.spec_from_file_location(
        "task_protocol_observer_t", _HOOKS / "task-protocol-observer.py"
    )
    obs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obs)

    calls: list[str] = []

    def boom():
        raise PermissionError("phase lost")

    monkeypatch.setattr(ss.SessionState, "record_skill_checked", staticmethod(boom))
    monkeypatch.setattr(
        ss.SessionState, "add_activated_skill", staticmethod(lambda name: calls.append(name))
    )

    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Skill",
        "tool_input": {"skill": "code-verify"},
    }
    assert obs.TaskProtocolObserver().execute(obs.HookInput(payload)) is None
    assert calls == ["code-verify"]  # вторая мутация всё равно выполнена


# ── читатель ───────────────────────────────────────────────────────────────────


@pytest.fixture
def reader(ss):
    from shared import session_state_failures as mod

    importlib.reload(mod)
    return mod


def _seed(ss, records: list[dict]) -> None:
    log = _faillog(ss)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )


def test_reader_window_and_summary(ss, reader):
    now = datetime.now()
    _seed(
        ss,
        [
            {
                "ts": (now - timedelta(days=1)).isoformat(),
                "event": "mutation_lost",
                "op": "record_skill_checked",
                "error_type": "PermissionError",
            },
            {
                "ts": (now - timedelta(days=2)).isoformat(),
                "event": "lock_fail_open",
                "op": "add_activated_skill",
            },
            {
                "ts": (now - timedelta(days=40)).isoformat(),  # вне окна
                "event": "mutation_lost",
                "op": "record_decomposition",
                "error_type": "OSError",
            },
        ],
    )

    stat = reader.summary(reader.read_events(7))
    assert stat["total"] == 2
    assert stat["lost"] == 1
    assert stat["fail_open"] == 1
    assert stat["by_op"] == {"record_skill_checked": 1}
    assert stat["by_error"] == {"PermissionError": 1}


def test_banner_silent_without_losses(ss, reader):
    _seed(ss, [{"ts": datetime.now().isoformat(), "event": "lock_fail_open", "op": "x"}])
    assert reader.banner_line(7) is None  # одинокий fail-open не поломка → не шумим


def test_banner_reports_losses(ss, reader):
    _seed(
        ss,
        [
            {
                "ts": datetime.now().isoformat(),
                "event": "mutation_lost",
                "op": "record_skill_checked",
                "error_type": "PermissionError",
            }
        ],
    )
    line = reader.banner_line(7)
    assert line is not None
    assert line.startswith("[STATE-WRITE]")
    assert "record_skill_checked×1" in line
    assert "PermissionError" in line


def test_reader_survives_garbage_and_missing_file(ss, reader):
    assert reader.read_events(7) == []  # файла нет
    log = _faillog(ss)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text('не json\n{"event": "mutation_lost", "op": "ok"}\n', encoding="utf-8")
    assert [e["op"] for e in reader.read_events(7)] == ["ok"]  # битая строка пропущена


def test_parse_since_units(reader):
    assert reader.parse_since("7d") == 7
    assert reader.parse_since("24h") == 1
    assert reader.parse_since("1440m") == 1
    assert reader.parse_since("мусор") == 7.0


# ── сюрфейс в каденсе ──────────────────────────────────────────────────────────


def test_cadence_surfaces_state_failures(ss, reader):
    _seed(
        ss,
        [
            {
                "ts": datetime.now().isoformat(),
                "event": "mutation_lost",
                "op": "record_skill_checked",
                "error_type": "PermissionError",
            }
        ],
    )
    spec = importlib.util.spec_from_file_location(
        "memory_maintenance_cadence_t", _HOOKS / "memory-maintenance-cadence.py"
    )
    cad = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cad)

    line = cad._check_state_failures(7)
    assert line is not None and line.startswith("[STATE-WRITE]")
