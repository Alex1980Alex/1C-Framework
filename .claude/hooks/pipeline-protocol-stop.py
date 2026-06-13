#!/usr/bin/env python3
"""
Hook: pipeline-protocol-stop
Event: Stop
Matcher: (none)
Purpose: ADR-018 — hard-enforce обязательной пайплайн-парадигмы. Если в ЭТОЙ сессии
  были правки кода/файлов (Write/Edit — сигнал «была задача») БЕЗ использования
  пайплайна (ни один `pipeline/<slug>/.pipeline-state.json` не обновлён за сессию) →
  block с инструкцией. Чистые вопросы (нет Write за сессию) → exempt (нет deadlock).

  Анти-deadlock: (1) opt-out env; (2) keyed на реальный Write-сигнал из invocation-лога,
  а не на эвристику текста; (3) graceful degradation (исключение/нет данных → allow);
  (4) выход всегда достижим — создать pipeline-артефакт и завершить снова.
Timeout: 8s
Opt-out: PIPELINE_PROTOCOL_DISABLE=1
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INVOCATIONS = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
_TAIL_BYTES = 2_000_000  # ~5-6k последних записей (CloudEvents-конверт ~300-400 байт/строка)
# NB: MultiEdit/NotebookEdit включены для будущего, но сейчас НЕ имеют PreToolUse-матчера
# в settings.json → правки ими не логируются → enforcer их не видит (осознанный недо-блок,
# безопасная сторона). При добавлении матчера на них детект заработает автоматически.
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _parse_dt(s: str) -> datetime | None:
    """ISO → naive datetime (tz-agnostic): снимает offset, чтобы сравнения log-ts vs
    state-updated_at не падали TypeError при смешении naive/aware меток (fail-safe)."""
    try:
        dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _read_tail_lines() -> list[str]:
    try:
        with open(INVOCATIONS, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _TAIL_BYTES))
            return f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _session_writes_and_start(sid: str) -> tuple[bool, datetime | None]:
    """(были_правки, время_старта_сессии) для sid из invocation-лога."""
    start: datetime | None = None
    had_write = False
    for line in _read_tail_lines():
        line = line.strip()
        if not line or sid not in line:
            continue
        try:
            o = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        if o.get("session") != sid:
            continue
        dt = _parse_dt(o.get("ts", ""))
        if dt is not None and (start is None or dt < start):
            start = dt
        if o.get("event") == "PreToolUse" and o.get("tool") in _WRITE_TOOLS:
            had_write = True
    return had_write, start


def _pipeline_used_since(start: datetime | None) -> bool:
    """Был ли хоть один pipeline/<slug>/.pipeline-state.json обновлён за сессию."""
    if not PIPELINE_DIR.is_dir():
        return False
    for sf in PIPELINE_DIR.glob("*/.pipeline-state.json"):
        try:
            d = json.loads(sf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        dt = _parse_dt(d.get("updated_at", ""))
        if dt is None:
            continue
        if start is None or dt >= start:
            return True
    return False


class PipelineProtocolStop(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("PIPELINE_PROTOCOL_DISABLE") == "1":
            return None
        sid = inp.session_id or ""
        if not sid:
            return None  # не можем привязать к сессии → allow (без deadlock)
        had_write, start = _session_writes_and_start(sid)
        if not had_write:
            return None  # нет правок за сессию → не задача → exempt
        if _pipeline_used_since(start):
            return None  # пайплайн использован → ok
        return HookOutput().block(
            "[PIPELINE-PROTOCOL] В этой сессии были правки кода без пайплайна (ADR-018, "
            "обязательная парадигма). Оформи задачу через пайплайн перед завершением:\n"
            '  .venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py init <slug> --title "..."\n'
            "  trivial → создай pipeline/<slug>/pipeline.md (4 секции: План/Дизайн/Реализация/Тест);\n"
            "  medium/complex → 01-architecture…04-testing.\n"
            "  затем: pipeline_state.py done <slug> <N> <файл>\n"
            "Аварийный обход (если правка не была задачей): PIPELINE_PROTOCOL_DISABLE=1."
        )


if __name__ == "__main__":
    PipelineProtocolStop().run()
