#!/usr/bin/env python3
"""
Hook: bulk-action-guard
Event: PostToolUse
Matcher: Bash
Purpose: Detect bulk/destructive operations (rm multiple files, drop tables, etc.)
         and inject Q5 enforcer reminder.

         Catches ACTIONS, not WORDS. When Claude executes `rm -f` on 5+ files
         or runs destructive commands, this hook injects a system message
         asking: "Do you need an enforcer hook to prevent this from recurring?"

         This is Layer 2 of intent detection — complements keyword-based
         Layer 1 (decision-to-triad.py) by catching the actual execution.

Timeout: 3s
"""

import re
import sys
import os

# Core path resolution: find base/ + shared/ in user-level or project-level
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# Patterns that indicate bulk/destructive operations
_BULK_RM_PATTERN = re.compile(
    r"rm\s+(-[rfv]+\s+)*"  # rm with flags
    r"("
    r'("[^"]+"\s*){3,}'    # 3+ quoted paths
    r"|"
    r"(\S+\s+){3,}"        # 3+ unquoted paths
    r"|"
    r"\S+\*"               # glob pattern (e.g., test_*.py)
    r")"
)

_DESTRUCTIVE_PATTERNS = [
    r"rm\s+-rf?\s+",         # rm -r, rm -rf
    r"git\s+push\s+--force",
    r"git\s+reset\s+--hard",
    r"drop\s+table",
    r"delete\s+from\s+\w+\s*;",  # SQL DELETE without WHERE
    r"truncate\s+table",
]

_DESTRUCTIVE_RE = re.compile(
    "|".join(f"({p})" for p in _DESTRUCTIVE_PATTERNS),
    re.IGNORECASE,
)


def _count_rm_targets(command: str) -> int:
    """Count how many file targets an rm command has."""
    # Find all rm invocations
    rm_matches = re.finditer(r"rm\s+(?:-[rfvI]+\s+)*(.+?)(?:\s*&&|\s*;|\s*$)", command)
    total = 0
    for m in rm_matches:
        targets_str = m.group(1).strip()
        # Count quoted paths
        quoted = re.findall(r'"[^"]+"', targets_str)
        if quoted:
            total += len(quoted)
        else:
            # Count space-separated paths (exclude flags)
            parts = [p for p in targets_str.split() if not p.startswith("-")]
            total += len(parts)
        # Glob patterns count as bulk
        if "*" in targets_str:
            total += 5  # Treat glob as 5+ files
    return total


class BulkActionGuard(BaseHook):
    """Detect bulk/destructive operations and inject Q5 reminder."""

    BULK_THRESHOLD = 5  # 5+ files in rm = bulk operation

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Bash":
            return None

        command = inp.tool_input.get("command", "")
        if not command:
            return None

        # Check 1: Bulk rm (5+ files or glob)
        rm_count = _count_rm_targets(command)
        if rm_count >= self.BULK_THRESHOLD:
            return HookOutput().system_message(
                f"[BULK-ACTION-GUARD] Bulk delete detected: ~{rm_count} targets.\n"
                "\n"
                "Q5 CHECK: Нужен ли enforcer-хук чтобы предотвратить "
                "повторное накопление этих файлов?\n"
                "\n"
                "Паттерн CLEANUP = CLEANUP + GUARD:\n"
                "  1. Удалил мусор ✓\n"
                "  2. Создай hook чтобы мусор не появлялся снова\n"
                "\n"
                "Если это одноразовая операция — игнорируй.\n"
                "Если рекуррентная проблема — создай PreToolUse/Write guard."
            )

        # Check 2: Destructive patterns (rm -rf, force push, DROP TABLE)
        if _DESTRUCTIVE_RE.search(command):
            return HookOutput().system_message(
                "[BULK-ACTION-GUARD] Destructive command detected.\n"
                "Убедись что это безопасно и необратимые последствия учтены."
            )

        return None


if __name__ == "__main__":
    BulkActionGuard().run()
