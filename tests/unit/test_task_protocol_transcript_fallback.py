"""task-protocol-enforcer: фолбэк на факт вызова Skill из транскрипта.

Инцидент 2026-07-26: скилл активирован (имя легло в `activated_skills`), но мутация
`task_protocol` не сохранилась — UPS-цепочка в окне НЕ фаерила (лог: фаеры 13:16 и 13:47,
активация 13:25, блок 13:32), то есть запись потерялась, а не была законно сброшена новым
промптом. Энфорсер блокировал Write, требуя того, что уже сделано.

Пинятся обе стороны: факт после промпта открывает гейт (+self-heal state), а вызов ДО
последнего промпта / отсутствие якоря — нет (обход протокола запрещён).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

pytestmark = pytest.mark.unit

from shared import transcript_skills as ts  # импорт после правки sys.path выше

# ── фикстуры записей транскрипта (форма — с живого транскрипта 2026-07-26) ─────


def _prompt(text: str = "почини гейт") -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _injected(text: str = "Stop hook feedback:\n[TASK-ENFORCER] ...") -> dict:
    """Системная инъекция: та же роль, но помечена isMeta → не якорь."""
    return {"type": "user", "message": {"role": "user", "content": text}, "isMeta": True}


def _tool_result() -> dict:
    """Результат инструмента: роль user, но content — СПИСОК блоков → не якорь."""
    return {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]},
    }


def _skill(name: str = "hook-enforcement-pattern") -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": name}}],
        },
    }


def _write(path: Path, entries: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8"
    )
    return path


# ── shared/transcript_skills ───────────────────────────────────────────────────


def test_skill_after_prompt_detected(tmp_path):
    p = _write(tmp_path / "t.jsonl", [_prompt(), _skill()])
    assert ts.skill_checked_after_last_prompt(str(p)) is True


def test_skill_before_last_prompt_not_counted(tmp_path):
    """Активация прошлой задачи не открывает гейт новой (иначе это обход, не фолбэк)."""
    p = _write(tmp_path / "t.jsonl", [_prompt("задача A"), _skill(), _prompt("задача B")])
    assert ts.skill_checked_after_last_prompt(str(p)) is False


def test_injected_meta_turn_is_not_an_anchor(tmp_path):
    """Инъекция (feedback Stop-хука) после активации не сбрасывает якорь."""
    p = _write(tmp_path / "t.jsonl", [_prompt(), _skill(), _injected()])
    assert ts.skill_checked_after_last_prompt(str(p)) is True


def test_tool_result_entry_is_not_an_anchor(tmp_path):
    p = _write(tmp_path / "t.jsonl", [_prompt(), _tool_result(), _skill()])
    assert ts.skill_checked_after_last_prompt(str(p)) is True


def test_no_prompt_anchor_fail_closed(tmp_path):
    """Якоря нет (хвост срезан) → False: лишний блок безопаснее тихого обхода."""
    p = _write(tmp_path / "t.jsonl", [_skill()])
    assert ts.skill_checked_after_last_prompt(str(p)) is False


def test_no_skill_call_at_all(tmp_path):
    p = _write(tmp_path / "t.jsonl", [_prompt(), _tool_result()])
    assert ts.skill_checked_after_last_prompt(str(p)) is False


def test_missing_file_is_safe(tmp_path):
    assert ts.skill_checked_after_last_prompt(str(tmp_path / "нет.jsonl")) is False
    assert ts.skill_checked_after_last_prompt("") is False


def test_skill_in_transcript_is_name_specific(tmp_path):
    p = _write(tmp_path / "t.jsonl", [_prompt(), _skill("deployment")])
    assert ts.skill_in_transcript(str(p), "deployment") is True
    assert ts.skill_in_transcript(str(p), "code-verify") is False
    assert ts.skill_in_transcript(str(p), "") is False


def test_is_user_prompt_shapes():
    assert ts.is_user_prompt(_prompt()) is True
    # фикстуры без поля role (как в тестах code-skill-enforcer) тоже валидны
    assert ts.is_user_prompt({"type": "user", "message": {"content": "текст"}}) is True
    assert ts.is_user_prompt(_injected()) is False
    assert ts.is_user_prompt(_tool_result()) is False
    assert ts.is_user_prompt(_skill()) is False


# ── e2e энфорсера ──────────────────────────────────────────────────────────────


def _load_enforcer(monkeypatch, tmp_path):
    """Свежий session_state в tmp + модуль энфорсера (имя файла с дефисами)."""
    monkeypatch.setenv("SESSION_STATE_PATH", str(tmp_path))
    from shared import session_state as ss

    importlib.reload(ss)
    ss.SessionState._state_cache = None
    spec = importlib.util.spec_from_file_location(
        "task_protocol_enforcer", _ROOT / ".claude" / "hooks" / "task-protocol-enforcer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, ss


def _payload(transcript: Path, file_path: str = "scripts/x.py") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
        "transcript_path": str(transcript),
    }


def test_enforcer_allows_on_transcript_evidence_and_self_heals(monkeypatch, tmp_path):
    mod, ss = _load_enforcer(monkeypatch, tmp_path)
    ss.SessionState.set_task_classified("medium")  # phase=classified, активации в state нет
    transcript = _write(tmp_path / "t.jsonl", [_prompt(), _skill()])

    res = mod.TaskProtocolEnforcer().execute(mod.HookInput(_payload(transcript)))

    assert res is None  # пропущено по факту из транскрипта
    ss.SessionState._state_cache = None
    assert ss.SessionState.get_task_protocol()["phase"] == "skill_checked"  # self-heal


def test_enforcer_blocks_without_evidence(monkeypatch, tmp_path):
    mod, ss = _load_enforcer(monkeypatch, tmp_path)
    ss.SessionState.set_task_classified("medium")
    transcript = _write(tmp_path / "t.jsonl", [_prompt(), _tool_result()])

    res = mod.TaskProtocolEnforcer().execute(mod.HookInput(_payload(transcript)))

    assert res is not None
    assert "TASK PROTOCOL" in str(res._data)


def test_enforcer_blocks_when_skill_predates_prompt(monkeypatch, tmp_path):
    """Скилл активирован в ПРОШЛОЙ задаче сессии → протокол текущей не соблюдён."""
    mod, ss = _load_enforcer(monkeypatch, tmp_path)
    ss.SessionState.set_task_classified("medium")
    transcript = _write(tmp_path / "t.jsonl", [_prompt("A"), _skill(), _prompt("B")])

    res = mod.TaskProtocolEnforcer().execute(mod.HookInput(_payload(transcript)))

    assert res is not None
    assert "TASK PROTOCOL" in str(res._data)


def test_enforcer_state_path_still_wins(monkeypatch, tmp_path):
    """Обычный путь не сломан: phase=skill_checked → пропуск без транскрипта."""
    mod, ss = _load_enforcer(monkeypatch, tmp_path)
    ss.SessionState.record_skill_checked()

    res = mod.TaskProtocolEnforcer().execute(mod.HookInput(_payload(tmp_path / "нет.jsonl")))

    assert res is None
