#!/usr/bin/env python3
"""
Code Verify Reminder — mandatory task after code changes.

Event: PostToolUse
Matcher: Write|Edit (create task) + Skill (auto-complete on code-verify)
Timeout: 3s

MANDATORY: creates task in hook-todos.json → task-enforcer blocks stop.
Auto-completes when skill code-verify is activated.

Cycle:
  Edit .py → add_task() → task-enforcer blocks stop → Claude runs code-verify
  → Skill(code-verify) fires → complete_task_by_hook() → stop allowed

Author: Claude Code
Version: 2.1.0
Created: 2026-02-25
"""

import os
import sys

# Path resolution (same pattern as all other hooks)
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# Optional imports (graceful degradation)
try:
    from shared.task_master import add_task, complete_task_by_hook
except ImportError:
    add_task = None
    complete_task_by_hook = None


CODE_EXTENSIONS = {".py", ".ts", ".js", ".go", ".rs", ".java", ".jsx", ".tsx"}
SKIP_DIRS = {"docs/", "data/", ".claude/cache/", "node_modules/", "__pycache__/"}

HOOK_ID = "code-verify-reminder"
TASK_TITLE = "Запустить code-verify для изменённого кода"


class CodeVerifyReminder(BaseHook):
    """Mandatory code verification after code changes.

    - PostToolUse Write|Edit: creates mandatory task
    - PostToolUse Skill: auto-completes task when code-verify is used
    """

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_name = inp.tool_name

        # --- PostToolUse Skill: auto-complete task on code-verify ---
        if tool_name == "Skill":
            return self._handle_skill(inp)

        # --- PostToolUse Write|Edit: create mandatory task ---
        return self._handle_code_change(inp)

    # Skills that satisfy code verification requirement:
    # - code-verify: primary (dedicated verification skill)
    # - learning-loop: fallback (SEARCH→FETCH→EXECUTE→VERIFY→CREATE when skill missing)
    VERIFY_SKILLS = {"code-verify", "learning-loop"}

    def _handle_skill(self, inp: HookInput) -> HookOutput | None:
        """Auto-complete pending code-verify task when verification skill is activated."""
        skill = inp.tool_input.get("skill", "") if isinstance(inp.tool_input, dict) else ""
        if skill not in self.VERIFY_SKILLS:
            return None

        if complete_task_by_hook is None:
            return None

        try:
            result = complete_task_by_hook(HOOK_ID)
            count = result.get("completed_count", 0)
            if count > 0:
                return HookOutput().system_message(
                    f"[CODE-VERIFY] Task completed ({count}). "
                    "Верификация запущена — задача закрыта."
                )
        except Exception:
            pass  # Graceful degradation

        return None

    def _handle_code_change(self, inp: HookInput) -> HookOutput | None:
        """Create mandatory task when code file is changed."""
        file_path = inp.tool_input.get("file_path", "")

        # Skip non-code files
        if not any(file_path.endswith(ext) for ext in CODE_EXTENSIONS):
            return None

        # Normalize path separators
        normalized = file_path.replace("\\", "/")

        # Skip excluded directories
        if any(skip in normalized for skip in SKIP_DIRS):
            return None

        if add_task is None:
            # Fallback: advisory systemMessage if task_master unavailable
            return HookOutput().system_message(
                "[CODE-VERIFY] Код изменён. Запусти code-verify после завершения."
            )

        try:
            filename = os.path.basename(file_path)
            added = add_task(
                title=TASK_TITLE,
                priority="high",
                created_by=HOOK_ID,
                description=(
                    f"Код изменён: {filename}\n"
                    "Запусти skill code-verify (режим: quality-review или knowledge-compliance).\n"
                    "Задача авто-завершится при активации скилла code-verify."
                ),
            )
        except Exception:
            added = False

        if added:
            return HookOutput().system_message(
                "[CODE-VERIFY] Mandatory task создана. "
                "После завершения изменений запусти: Skill(code-verify). "
                "Если скилл недоступен — используй Skill(learning-loop). "
                "Task-enforcer заблокирует stop до выполнения."
            )

        # Task already exists (duplicate pending) — silent
        return None


if __name__ == "__main__":
    CodeVerifyReminder().run()
