#!/usr/bin/env python3
"""
Hook: session-context-enforcer
Event: UserPromptSubmit
Purpose: When user asks about previous session context, instruct Claude
         to use MCP memory-orchestrator FIRST, then git/files as supplement.
Timeout: 2s
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# Phrase triggers (lowercased substrings)
_SESSION_PHRASES = [
    "предыдущ",        # предыдущая сессия, предыдущий контекст
    "прошл",           # прошлая сессия, прошлый раз
    "что было",
    "что делали",
    "контекст сессии",
    "контекст сесии",  # typo variant
    "previous session",
    "last session",
    "session context",
    "что было в прошл",
    "что было раньше",
    "восстанови контекст",
    "продолжим с прошл",
]

# Additional word-pair triggers: both words must be present
_WORD_PAIRS = [
    ("сессия", "контекст"),
    ("сессия", "предыдущ"),
    ("session", "context"),
    ("session", "previous"),
]

_INSTRUCTION = """[SESSION-CONTEXT-ENFORCER] Обнаружен запрос о предыдущей сессии.

ОБЯЗАТЕЛЬНЫЙ ПОРЯДОК получения контекста:
1. MCP memory-orchestrator → unified_search("session") + memory_event_history(limit=20)
2. MCP memory-ai → search_messages("session context")
3. ПОТОМ git log + .claude/data/session-skills.json как дополнение

НЕ начинай с git log или чтения файлов — сначала MCP memory tools."""


class SessionContextEnforcer(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt.strip()) < 10:
            return None

        prompt_lower = prompt.lower()

        # Check phrase triggers
        matched = any(phrase in prompt_lower for phrase in _SESSION_PHRASES)

        # Check word-pair triggers
        if not matched:
            for w1, w2 in _WORD_PAIRS:
                if w1 in prompt_lower and w2 in prompt_lower:
                    matched = True
                    break

        if not matched:
            return None

        return HookOutput().system_message(_INSTRUCTION)


if __name__ == "__main__":
    SessionContextEnforcer().run()
