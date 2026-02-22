#!/usr/bin/env python3
"""
Hook: git-commit-enforcer
Event: Stop
Matcher: (none — fires on every stop attempt)
Purpose: Block Claude from stopping if there are uncommitted changes
         to tracked files in watched paths.
         Checks git status (modified/added/deleted, ignores untracked).
         Forces commit before ending session.
Timeout: 5s

Exit codes:
  0 = allow stop (working tree clean or no watched changes)
  2 = block stop (uncommitted changes found)

Pattern: Enforcer (поведенческий подпаттерн триады — Цикл принуждения).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Core path resolution for shared modules
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

# Project root (hooks/ -> .claude/ -> project/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Enforce for all project-critical paths
WATCHED_PATHS = [
    "src/",
    "docs/",
    "tests/",
    ".claude/skills/",
    ".claude/hooks/",
]

# Git status codes that indicate changes (including untracked)
CHANGE_STATUSES = {"M", "A", "D", "R", "C", "U", "T"}


def get_uncommitted_changes() -> list[str]:
    """Get list of uncommitted changes (modified/added/deleted, not untracked).

    Returns list of formatted strings: "  M  path/to/file"
    """
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []

        changes = []
        for line in result.stdout.strip().splitlines():
            if not line or len(line) < 4:
                continue

            index_status = line[0]   # staged
            work_status = line[1]    # unstaged
            # Use line[2:].lstrip() to handle both "M  path" and " M path"
            # line[3:] would strip leading "." from ".claude/" paths
            filepath = line[2:].lstrip().strip('"')

            # Include untracked files (new files should be committed too)
            is_untracked = index_status == "?" and work_status == "?"

            # At least one status must indicate a real change
            has_change = (
                is_untracked
                or index_status in CHANGE_STATUSES
                or work_status in CHANGE_STATUSES
            )
            if not has_change:
                continue

            # Filter by watched paths (if configured)
            if WATCHED_PATHS:
                # Normalize: git may use forward slashes
                fp_normalized = filepath.replace("\\", "/")
                if not any(fp_normalized.startswith(p) for p in WATCHED_PATHS):
                    continue

            status_display = line[:2].strip() or "M"
            changes.append(f"  {status_display:>2}  {filepath}")

        return changes
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def main():
    """Check for uncommitted changes. Block stop if found."""
    try:
        # Read stdin (required by Claude Code hook protocol)
        try:
            sys.stdin.buffer.read()
        except Exception:
            pass

        changes = get_uncommitted_changes()

        if not changes:
            # Working tree clean (or no changes in watched paths) — allow stop
            sys.exit(0)

        # Build reason message
        shown = changes[:15]
        extra = len(changes) - len(shown)
        files_str = "\n".join(shown)
        if extra > 0:
            files_str += f"\n  ... и ещё {extra} файл(ов)"

        watched = ", ".join(WATCHED_PATHS) if WATCHED_PATHS else "все файлы"

        reason = (
            f"[GIT-COMMIT-ENFORCER] Обнаружены незакоммиченные изменения "
            f"({len(changes)} файлов в {watched})!\n\n"
            f"{files_str}\n\n"
            "Создай коммит перед завершением сессии:\n"
            "1. Проверь изменения: git diff --stat\n"
            "2. Добавь файлы: git add <файлы>\n"
            "3. Закоммить: git commit -m \"описание изменений\"\n\n"
            "После коммита можешь завершить."
        )

        output = {"decision": "block", "reason": reason}
        out_bytes = json.dumps(output, ensure_ascii=False).encode("utf-8")
        sys.stdout.buffer.write(out_bytes + b"\n")
        sys.stdout.buffer.flush()
        sys.exit(2)  # Block stop

    except Exception:
        # Graceful degradation: allow stop on any error
        sys.exit(0)


if __name__ == "__main__":
    main()
