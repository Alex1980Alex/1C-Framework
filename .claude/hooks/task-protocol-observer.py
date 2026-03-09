#!/usr/bin/env python3
"""
Hook: task-protocol-observer
Event: PostToolUse
Matcher: TaskCreate|Skill
Purpose: Track task protocol phases via tool usage.
Timeout: 3s

Part of Task Protocol enforcement system.
Observes two events:
  - TaskCreate → records decomposition (phase=decomposed)
  - Skill      → records skill check (phase=skill_checked)

skill_checked is the ONLY phase that allows Write/Edit through the enforcer gate.

Silent observer: returns None (no output), never blocks.
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base.protocol import BaseHook, HookInput, HookOutput  # noqa: E402
from typing import Optional  # noqa: E402


class TaskProtocolObserver(BaseHook):
    """PostToolUse observer for TaskCreate and Skill events."""

    def execute(self, inp: HookInput) -> Optional[HookOutput]:
        try:
            from shared.session_state import SessionState

            if inp.tool_name == "TaskCreate":
                SessionState.record_decomposition()

            elif inp.tool_name == "Skill":
                SessionState.record_skill_checked()
                # Register skill name in activated_skills for code-skill-enforcer
                skill_name = (inp.tool_input or {}).get("skill", "")
                if skill_name:
                    SessionState.add_activated_skill(skill_name)

            else:
                return None

        except Exception:
            pass  # Graceful degradation: never fail

        return None  # Silent — no output to Claude


if __name__ == "__main__":
    TaskProtocolObserver().run()
