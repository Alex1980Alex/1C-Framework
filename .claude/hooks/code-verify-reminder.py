#!/usr/bin/env python3
"""
Code Verify Reminder — advisory reminder after code changes.

Event: PostToolUse
Matcher: Write|Edit
Timeout: 3s
Purpose: After code file changes, remind about code-verify skill.

NON-BLOCKING: advisory only, never creates mandatory tasks.
Uses 15-minute cooldown to avoid spam.

Author: Claude Code
Version: 1.0.0
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
    from shared.task_master import has_recent_completion
except ImportError:
    has_recent_completion = None


CODE_EXTENSIONS = {".py", ".ts", ".js", ".go", ".rs", ".java", ".jsx", ".tsx"}
SKIP_DIRS = {"docs/", "data/", ".claude/cache/", "node_modules/", "__pycache__/"}


class CodeVerifyReminder(BaseHook):
    """Advisory reminder to run code-verify after code changes."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        file_path = inp.tool_input.get("file_path", "")

        # Skip non-code files
        if not any(file_path.endswith(ext) for ext in CODE_EXTENSIONS):
            return None

        # Normalize path separators
        normalized = file_path.replace("\\", "/")

        # Skip excluded directories
        if any(skip in normalized for skip in SKIP_DIRS):
            return None

        # Cooldown check (15 minutes)
        if has_recent_completion is not None:
            try:
                if has_recent_completion("code-verify-reminder", cooldown_minutes=15):
                    return None
            except Exception:
                pass  # Graceful degradation

        return HookOutput().system_message(
            "[CODE-VERIFY] Код изменён. После завершения изменений — "
            "запусти code-verify (режим: quality-review или knowledge-compliance). "
            "Skill: code-verify"
        )


if __name__ == "__main__":
    CodeVerifyReminder().run()
