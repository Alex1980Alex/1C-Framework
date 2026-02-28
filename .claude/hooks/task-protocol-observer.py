#!/usr/bin/env python3
"""
Hook: task-protocol-observer
Event: PostToolUse
Matcher: TaskCreate
Purpose: Record decomposition fact in session state when TaskCreate is called.
Timeout: 3s

Part of Task Protocol enforcement system.
When Claude creates subtasks via TaskCreate, this observer records the fact
in SessionState so that task-protocol-enforcer can allow Write/Edit.

Silent observer: returns None (no output), never blocks.
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base.protocol import BaseHook, HookInput, HookOutput  # noqa: E402
from typing import Optional  # noqa: E402


class TaskProtocolObserver(BaseHook):
    """PostToolUse:TaskCreate → records decomposition in session state."""

    def execute(self, inp: HookInput) -> Optional[HookOutput]:
        # Only act on TaskCreate
        if inp.tool_name != "TaskCreate":
            return None

        try:
            from shared.session_state import SessionState
            SessionState.record_decomposition()
        except Exception:
            pass  # Graceful degradation: never fail

        return None  # Silent — no output to Claude


if __name__ == "__main__":
    TaskProtocolObserver().run()
