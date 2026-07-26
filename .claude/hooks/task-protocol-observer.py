#!/usr/bin/env python3
"""
Hook: task-protocol-observer
Event: PreToolUse + PostToolUse (dual-registered workaround)
Matcher: PreToolUse:Skill | PostToolUse:TaskCreate|Skill|llm_complete
Purpose: Track task protocol phases via tool usage.
Timeout: 3s

PostToolUse broken on Windows (github #6305, 0 invocations ever).
PreToolUse added as workaround - tool_input has skill name before execution.

Silent observer: returns None (no output), never blocks.
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)


from base.protocol import BaseHook, HookInput, HookOutput


class TaskProtocolObserver(BaseHook):
    """PostToolUse observer for TaskCreate and Skill events."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        try:
            from shared.session_state import SessionState
        except Exception:
            return None  # Graceful degradation: never fail

        if inp.tool_name == "TaskCreate":
            self._try(SessionState.record_decomposition)

        elif inp.tool_name == "Skill":
            # ДВА независимых try (2026-07-26): раньше обе мутации жили в одном блоке, и
            # падение первой (потеря записи фазы — гонка ~4 хуков на PreToolUse:Skill)
            # уносило вторую, хотя они питают РАЗНЫЕ энфорсеры: фаза → task-protocol-enforcer,
            # имя скилла → code-skill-enforcer. Живой инцидент: фаза осталась classified, и
            # add_activated_skill даже не вызывался. Факт провала пишет сам session_state.
            self._try(SessionState.record_skill_checked)
            skill_name = (inp.tool_input or {}).get("skill", "")
            if skill_name:
                self._try(SessionState.add_activated_skill, skill_name)

        elif inp.tool_name == "mcp__llm-rotation__llm_complete":
            self._try(SessionState.record_llm_delegation)

        return None  # Silent — no output to Claude

    @staticmethod
    def _try(fn, *args) -> None:
        """Мутация «никогда не ронять хук». Диагностика провала — в session_state
        (`.claude/cache/session-state-failures.jsonl`), здесь глушим осознанно."""
        try:
            fn(*args)
        except Exception:
            pass


if __name__ == "__main__":
    TaskProtocolObserver().run()
