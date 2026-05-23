#!/usr/bin/env python3
"""
Hook: session-context-enforcer (proactive memory recall)
Event: UserPromptSubmit
Purpose: Two modes:
  A) Direct session query → strong "MCP memory-orchestrator FIRST" instruction
  B) Substantive task prompt → lighter "check MCP memory for prior related work"
Timeout: 2s
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# ---------------------------------------------------------------------------
# Mode A: Direct session context queries
# ---------------------------------------------------------------------------
_SESSION_PHRASES = [
    "предыдущ",
    "прошл",
    "что было",
    "что делали",
    "контекст сессии",
    "контекст сесии",
    "previous session",
    "last session",
    "session context",
    "что было в прошл",
    "что было раньше",
    "восстанови контекст",
    "продолжим с прошл",
]

_SESSION_WORD_PAIRS = [
    ("сессия", "контекст"),
    ("сессия", "предыдущ"),
    ("session", "context"),
    ("session", "previous"),
]

_SESSION_INSTRUCTION = """[SESSION-CONTEXT-ENFORCER] Обнаружен запрос о предыдущей сессии.

ОБЯЗАТЕЛЬНЫЙ ПОРЯДОК получения контекста:
1. MCP memory-orchestrator → unified_search("session") + memory_event_history(limit=20)
2. MCP memory-ai → search_messages("session context")
3. ПОТОМ git log + .claude/data/session-skills.json как дополнение

НЕ начинай с git log или чтения файлов — сначала MCP memory tools."""

# ---------------------------------------------------------------------------
# Mode B: Substantive task prompts → proactive memory context
# ---------------------------------------------------------------------------
_TASK_VERBS = [
    "сделай",
    "добавь",
    "реализуй",
    "исправь",
    "создай",
    "настрой",
    "измени",
    "обнови",
    "удали",
    "перепиши",
    "рефакторинг",
    "оптимизируй",
    "implement",
    "fix",
    "add",
    "create",
    "update",
    "refactor",
    "build",
    "migrate",
    "configure",
    "setup",
    "develop",
    "write",
    "доработай",
    "допиши",
    "переделай",
    "интегрируй",
    "подключи",
]

# Prompts that look like slash commands or trivial — skip
_SKIP_PREFIXES = ("/", "!", "да", "нет", "ок", "ok", "yes", "no", "ладно")

_TASK_COOLDOWN_FILE = (
    Path(__file__).resolve().parent.parent / "cache" / "proactive-memory-cooldown.json"
)
_TASK_COOLDOWN_SECONDS = 300  # 5 minutes between task-mode triggers

_TASK_INSTRUCTION = """[PROACTIVE-MEMORY-RECALL] Обнаружена задача. Перед началом работы расширь контекст:

1. mcp__memory-orchestrator__unified_search(query="<ключевые слова задачи>") — найди что уже делалось по этой теме
2. Если найдено — учти при планировании (не дублируй, продолжай)
3. Если не найдено — работай как обычно

Это займёт 5 секунд но сэкономит повторную работу."""

MIN_TASK_PROMPT_LEN = 25


def _is_session_query(prompt_lower: str) -> bool:
    """Check if prompt is a direct question about previous session."""
    if any(phrase in prompt_lower for phrase in _SESSION_PHRASES):
        return True
    for w1, w2 in _SESSION_WORD_PAIRS:
        if w1 in prompt_lower and w2 in prompt_lower:
            return True
    return False


def _is_task_prompt(prompt_lower: str) -> bool:
    """Check if prompt looks like a substantive task request."""
    if len(prompt_lower) < MIN_TASK_PROMPT_LEN:
        return False
    return any(verb in prompt_lower for verb in _TASK_VERBS)


def _check_task_cooldown() -> bool:
    """Return True if within task-mode cooldown period."""
    try:
        if not _TASK_COOLDOWN_FILE.exists():
            return False
        data = json.loads(_TASK_COOLDOWN_FILE.read_text(encoding="utf-8"))
        return (time.time() - data.get("last_run", 0)) < _TASK_COOLDOWN_SECONDS
    except Exception:
        return False


def _update_task_cooldown():
    """Update task-mode cooldown timestamp."""
    try:
        _TASK_COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TASK_COOLDOWN_FILE.write_text(
            json.dumps({"last_run": time.time()}),
            encoding="utf-8",
        )
    except Exception:
        pass


class SessionContextEnforcer(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt.strip()) < 10:
            return None

        prompt_lower = prompt.strip().lower()

        # Skip slash commands, confirmations
        if any(prompt_lower.startswith(p) for p in _SKIP_PREFIXES):
            return None

        # Mode A: Direct session query (no cooldown — always fire)
        if _is_session_query(prompt_lower):
            return HookOutput().system_message(_SESSION_INSTRUCTION)

        # Mode B: Task prompt (with cooldown)
        if _is_task_prompt(prompt_lower):
            if _check_task_cooldown():
                return None
            _update_task_cooldown()
            return HookOutput().system_message(_TASK_INSTRUCTION)

        return None


if __name__ == "__main__":
    SessionContextEnforcer().run()
