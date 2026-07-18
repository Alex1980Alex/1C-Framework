"""Пин формы block-вывода хуков: БЕЗ ``continue: false`` (фикс 2026-07-18).

Симптом (мандат пользователя): каждый блокирующий PreToolUse-хук (SKILL REQUIRED,
TASK PROTOCOL, z-ai-write-guard …) ОБРЫВАЛ ход Claude — «PreToolUse hook stopped
continuation», сессия замирала до ручного «продолжай». Корень: `HookOutput.block()`
ставил ``continue: false``, а по контракту Claude Code это поле имеет приоритет над
``decision`` и останавливает обработку целиком (reason уходит пользователю, не модели).
Чистый ``decision: block`` + ``reason`` отклоняет только ВЫЗОВ инструмента: reason
получает МОДЕЛЬ и в том же ходе исправляется (активирует скилл → ретраит).

САБОТАЖ-ИНВАРИАНТ: возврат строки ``self._data["continue"] = False`` в block()
валит test_block_has_no_continue_false.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[3]
_PROTOCOL = _ROOT / ".claude" / "hooks" / "base" / "protocol.py"

_spec = importlib.util.spec_from_file_location("_proto_blockform", _PROTOCOL)
proto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proto)


def test_block_has_no_continue_false():
    """САБОТАЖ-ИНВАРИАНТ: block() НЕ содержит continue:false (обрыв хода)."""
    data = proto.HookOutput().block("причина")._data
    assert data.get("continue") is not False, (
        "continue:false в block() обрывает ход Claude (stopped continuation) — "
        "reason уходит пользователю вместо модели, сессия замирает до «продолжай»"
    )
    # строже: ключа вообще нет (block не управляет continue)
    assert "continue" not in data


def test_block_keeps_decision_and_reason():
    """Контракт блокировки цел: decision=block + reason (его видит модель)."""
    data = proto.HookOutput().block("нужен Skill('deployment')")._data
    assert data["decision"] == "block"
    assert "deployment" in data["reason"]


def test_allow_still_continues():
    """allow() по-прежнему явно продолжает (continue:true безвреден)."""
    assert proto.HookOutput().allow()._data.get("continue") is True


def test_live_guard_pipe_emits_block_without_continue_false():
    """Живой pipe-probe: реальный блокирующий хук (z-ai-write-guard, окно
    делегирования форсированно истекло) эмитит JSON с decision=block и БЕЗ
    continue:false — т.е. блок вызова, не обрыв сессии."""
    import os

    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "session_id": "blockform-probe",
        "tool_input": {
            "file_path": str(_ROOT / "scripts" / "_blockform_probe.py"),
            "content": "\n".join(f"x{i} = {i}" for i in range(30)),
        },
    }
    env = dict(os.environ, LLM_DELEGATION_FRESH_MINUTES="0")
    p = subprocess.run(
        [sys.executable, str(_ROOT / ".claude" / "hooks" / "z-ai-write-guard.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )
    out = json.loads(p.stdout.strip())
    assert out.get("decision") == "block"
    assert out.get("continue") is not False
