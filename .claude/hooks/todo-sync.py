#!/usr/bin/env python3
"""
Hook: todo-sync
Event: UserPromptSubmit
Matcher: (none — fires on every user message)
Purpose: Sync pending mandatory tasks from hook-todos.json → Claude's TodoWrite.
         Hooks cannot write to TodoWrite directly (it's session-scoped, in-memory).
         This hook injects a systemMessage on every user message listing
         all pending mandatory tasks with explicit instruction to add them
         to TodoWrite. This survives context compaction.

Timeout: 3s

Exit codes:
  0 = allow (always — this hook never blocks)

Pattern: Bridge (hook-todos.json → systemMessage → TodoWrite).
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput
from shared.task_master import get_pending_tasks, MANDATORY_HOOKS


class TodoSync(BaseHook):
    """Sync pending mandatory tasks to Claude's TodoWrite via systemMessage.

    Fires on every UserPromptSubmit. If pending mandatory tasks exist,
    returns a systemMessage instructing Claude to add them to TodoWrite.
    If no pending tasks — silent (no output).
    """

    def execute(self, inp: HookInput) -> HookOutput | None:
        # Get ALL pending mandatory tasks
        pending = []
        for hook_id in MANDATORY_HOOKS:
            tasks = get_pending_tasks(created_by=hook_id)
            pending.extend(tasks)

        if not pending:
            return None  # No pending tasks — silent

        # Build task list for systemMessage
        task_lines = []
        for t in pending[:10]:  # Max 10 tasks
            hook = t.get("createdBy", "unknown").replace("-hook", "")
            content = t.get("content", "")[:100]
            desc = t.get("description", "")[:150]
            task_lines.append(f"  - [{hook}] {content}")
            if desc:
                task_lines.append(f"    {desc}")

        tasks_str = "\n".join(task_lines)

        msg = (
            f"[TODO-SYNC] {len(pending)} обязательных задач ожидают выполнения:\n"
            f"{tasks_str}\n\n"
            "ДЕЙСТВИЕ: Добавь ВСЕ эти задачи в свой TodoWrite список "
            "(status: pending) если их там ещё нет. "
            "Выполни их перед завершением работы. "
            "task-enforcer заблокирует остановку пока задачи не выполнены."
        )

        return HookOutput().system_message(msg)


if __name__ == "__main__":
    TodoSync().run()
