"""Unit: code-skill-enforcer — transcript-fallback активации (fix-session-state-skill-race).

Инцидент 2026-07-17: Skill('1c-doc-research') вызван успешно, но запись в
session-skills.json потерялась (гонка) → энфорсер ложно блокировал Edit «SKILL
REQUIRED» до повторной активации. Фолбэк: фактический tool_use Skill в транскрипте
сессии = активация; state чинится сам (self-heal).
"""

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

pytestmark = pytest.mark.unit

_QUERY_BSL = (
    'Запрос.Текст = "ВЫБРАТЬ Т.Ссылка, КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.Показатель) '
    'ИЗ Справочник.Тест КАК Т ГДЕ ЕСТЬNULL(Т.Поле, 0) <> 0";'
)


def _load(monkeypatch, tmp_path):
    """Свежие session_state (в tmp) + модуль энфорсера (дефисное имя файла)."""
    monkeypatch.setenv("SESSION_STATE_PATH", str(tmp_path))
    from shared import session_state as ss

    importlib.reload(ss)
    ss.SessionState._state_cache = None

    spec = importlib.util.spec_from_file_location(
        "code_skill_enforcer", _ROOT / ".claude" / "hooks" / "code-skill-enforcer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # модуль импортирует SessionState по значению — подменяем на перегруженный
    mod.SessionState = ss.SessionState
    return mod, ss


def _payload(transcript_path):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "CommonModules/ТестМодуль/Module.bsl",
            "new_string": _QUERY_BSL,
        },
        "transcript_path": str(transcript_path),
    }


def _write_transcript(path, with_skill: bool):
    lines = [
        json.dumps({"type": "user", "message": {"content": "правь запрос"}}, ensure_ascii=False)
    ]
    if with_skill:
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Skill",
                                "input": {"skill": "1c-doc-research"},
                            }
                        ]
                    },
                },
                ensure_ascii=False,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_blocks_without_activation_or_transcript(monkeypatch, tmp_path):
    """Сабботаж-инвариант: нет ни записи в state, ни Skill в транскрипте → блок жив."""
    mod, _ = _load(monkeypatch, tmp_path)
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, with_skill=False)

    res = mod.CodeSkillEnforcer().execute(mod.HookInput(_payload(transcript)))

    assert res is not None
    assert "SKILL REQUIRED" in str(res._data)


def test_transcript_fallback_allows_and_self_heals(monkeypatch, tmp_path):
    """Активация потеряна в state, но Skill('1c-doc-research') есть в транскрипте →
    НЕ блокируем + state дописан (self-heal)."""
    mod, ss = _load(monkeypatch, tmp_path)
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, with_skill=True)

    res = mod.CodeSkillEnforcer().execute(mod.HookInput(_payload(transcript)))

    assert res is None  # пропущено
    ss.SessionState._state_cache = None
    assert ss.SessionState.is_skill_activated("1c-doc-research")  # state починен


def test_state_activation_still_wins_without_transcript(monkeypatch, tmp_path):
    """Обычный путь не сломан: активация в state → пропуск, транскрипт не нужен."""
    mod, ss = _load(monkeypatch, tmp_path)
    ss.SessionState.add_activated_skill("1c-doc-research")

    payload = _payload(tmp_path / "no-such-transcript.jsonl")
    res = mod.CodeSkillEnforcer().execute(mod.HookInput(payload))

    assert res is None


def test_other_skill_in_transcript_does_not_unlock(monkeypatch, tmp_path):
    """Skill с ДРУГИМ именем в транскрипте не открывает гейт требуемого."""
    mod, _ = _load(monkeypatch, tmp_path)
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "deployment"}}
                    ]
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    res = mod.CodeSkillEnforcer().execute(mod.HookInput(_payload(transcript)))

    assert res is not None
    assert "SKILL REQUIRED" in str(res._data)
