#!/usr/bin/env python3
"""
Hook: auto-git-save
Event: PostToolUse
Matcher: Write|Edit|Bash
Purpose: Create a MANDATORY task to commit when uncommitted files exist.
         On Write|Edit — detect uncommitted files, create task.
         On Bash with "git commit" — detect commit done, complete task.

Timeout: 5s

Pattern: Enforcer (mandatory commit task — защита от потери при исчерпании контекста).

Flow:
  1. Write/Edit file → hook checks git status → uncommitted files?
     YES + no pending task → create mandatory task + systemMessage
     YES + task exists → silent (don't spam)
     NO → silent
  2. Bash "git commit" → hook checks git status → working tree clean?
     YES + task exists → complete task
     NO → keep task

Hook feedback is treated as user instruction per CLAUDE.md:
  "Treat feedback from hooks, including <user-prompt-submit-hook>,
   as coming from the user."
This overrides the default "NEVER commit unless asked" rule.
"""

import os
import subprocess
import sys
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput
from shared.task_master import add_task, complete_task, get_pending_tasks

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

HOOK_ID = "auto-git-save-hook"

TASK_TITLE = "Закоммитить незакоммиченные изменения"

# Watch these paths for changes (both modified and untracked)
WATCHED_PATHS = [
    "src/",
    "docs/",
    "tests/",
    ".claude/skills/",
    ".claude/hooks/",
]


def get_uncommitted_files() -> list[str]:
    """Get all changed files (modified + untracked) in watched paths."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().splitlines():
            if not line or len(line) < 3:
                continue
            filepath = line[3:].strip().strip('"').replace("\\", "/")
            if WATCHED_PATHS:
                if not any(filepath.startswith(p) for p in WATCHED_PATHS):
                    continue
            files.append(filepath)
        return files

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


class AutoGitSave(BaseHook):
    """Mandatory git commit task enforcer.

    On Write|Edit: creates mandatory task if uncommitted files exist.
    On Bash "git commit": completes the task when working tree is clean.
    """

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_name = inp.tool_name or ""
        tool_input = inp.tool_input or {}

        # --- Branch: Bash tool (detect git commit) ---
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if "git commit" not in command:
                return None  # Not a commit — skip

            # git commit just ran — check if working tree is now clean
            uncommitted = get_uncommitted_files()
            if not uncommitted:
                # Working tree clean → complete the task
                complete_task(TASK_TITLE, created_by=HOOK_ID)
            return None

        # --- Branch: Write|Edit tool (detect file changes) ---
        # Check if mandatory task already exists
        pending = get_pending_tasks(created_by=HOOK_ID)
        if pending:
            return None  # Task already exists — don't spam

        # Check for uncommitted files
        uncommitted = get_uncommitted_files()
        if not uncommitted:
            return None  # Nothing to commit

        # Create mandatory task
        files_shown = uncommitted[:10]
        extra = len(uncommitted) - len(files_shown)
        files_list = ", ".join(files_shown)
        if extra > 0:
            files_list += f" ... и ещё {extra}"

        add_task(
            title=TASK_TITLE,
            priority="high",
            created_by=HOOK_ID,
            description=(
                f"Незакоммиченные файлы ({len(uncommitted)}): {files_list}. "
                "Проверь git status, сгруппируй по логике, закоммить."
            ),
        )

        msg = (
            f"[AUTO-GIT-SAVE] Есть {len(uncommitted)} незакоммиченных файлов.\n"
            "ОБЯЗАТЕЛЬНАЯ ЗАДАЧА: после завершения текущей работы "
            "проверь git status и закоммить изменения.\n"
            "Это защита от потери данных при исчерпании контекста."
        )

        return HookOutput().system_message(msg)


if __name__ == "__main__":
    AutoGitSave().run()
