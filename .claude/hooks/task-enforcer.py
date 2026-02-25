#!/usr/bin/env python3
"""
Hook: task-enforcer
Event: Stop
Matcher: (none — fires on every stop attempt)
Purpose: Block Claude from stopping if mandatory hook tasks are pending.
         v2.1: Added sync_git_tasks_with_status() — auto-complete git tasks
         when git status is clean (fixes zombie tasks).
         Reads hook-todos.json directly (no shared/ imports for max reliability).
         Coexists with ralph_wiggum_stop.py (both run sequentially on Stop).
Timeout: 10s

Exit codes:
  0 = allow stop
  2 = block stop (mandatory tasks pending)

Ported from 1C-Enterprise_Framework stop/task-enforcer.py v2.1.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Resolve cache path: core_paths if available, else fallback
def _find_cache_dir() -> Path:
    try:
        import os as _os
        _this = _os.path.dirname(_os.path.abspath(__file__))
        _user = _os.path.join(_os.path.expanduser("~"), ".claude", "hooks")
        if _os.path.isdir(_os.path.join(_user, "shared")):
            sys.path.insert(0, _user)
        sys.path.insert(0, _this)
        from shared.core_paths import get_cache_dir
        return get_cache_dir()
    except (ImportError, Exception):
        return Path(__file__).resolve().parent.parent / "cache"


CACHE_DIR = _find_cache_dir()
TODOS_FILE = CACHE_DIR / "hook-todos.json"
PROJECT_ROOT = CACHE_DIR.parent.parent  # .claude/cache -> project root

# Hook IDs whose pending tasks block stop
MANDATORY_HOOKS = {
    "knowledge-cache-reminder-hook",
    "factory-enforcer-hook",
    "docs-change-tracker-hook",
    "auto-git-save-hook",
    "code-skill-enforcer",
    "code-verify-reminder",
}


def sync_git_tasks_with_status(data: dict) -> int:
    """Auto-complete pending git tasks when git status is clean.

    Ported from Enterprise task-enforcer.py v2.1.
    Prevents zombie git tasks from blocking stop indefinitely.

    Returns:
        Number of tasks auto-completed
    """
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, encoding="utf-8", timeout=3,
        )
        if result.returncode != 0:
            return 0
        # If there ARE uncommitted files — don't touch tasks
        if result.stdout.strip():
            return 0

        # Git is clean — complete all pending git tasks
        todos = data.get("todos", [])
        completed = 0
        now = datetime.now().isoformat()

        for todo in todos:
            if (todo.get("status") == "pending"
                    and todo.get("createdBy") == "auto-git-save-hook"):
                todo["status"] = "completed"
                todo["completedAt"] = now
                todo["note"] = "Auto-synced: git status clean at stop"
                completed += 1

        return completed
    except Exception:
        return 0  # Silent fail — don't block stop


def sync_stats(data: dict) -> bool:
    """Fix stats if they don't match actual todos. Returns True if fixed."""
    todos = data.get("todos", [])
    actual = {
        "total": len(todos),
        "pending": sum(1 for t in todos if t.get("status") == "pending"),
        "in_progress": sum(1 for t in todos if t.get("status") == "in_progress"),
        "completed": sum(1 for t in todos if t.get("status") == "completed"),
    }
    if data.get("stats", {}) != actual:
        data["stats"] = actual
        return True
    return False


def get_pending_mandatory_tasks() -> list:
    """Get pending tasks from mandatory hooks.

    v2.1: Runs sync_git_tasks_with_status() and sync_stats() before checking.
    Saves file if any changes were made.
    """
    if not TODOS_FILE.exists():
        return []

    try:
        with open(TODOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        needs_save = False

        # v2.1: Auto-sync git tasks with git status
        git_synced = sync_git_tasks_with_status(data)
        if git_synced > 0:
            needs_save = True

        # Auto-fix stats
        if sync_stats(data):
            needs_save = True

        # Save if changes were made
        if needs_save:
            try:
                data["timestamp"] = datetime.now().isoformat()
                with open(TODOS_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass  # Non-critical

        todos = data.get("todos", [])
        pending = []

        for todo in todos:
            if (todo.get("status") == "pending"
                    and todo.get("createdBy", "") in MANDATORY_HOOKS):
                pending.append({
                    "content": todo.get("content", ""),
                    "createdBy": todo.get("createdBy", ""),
                    "createdAt": todo.get("createdAt", ""),
                })

        return pending
    except (json.JSONDecodeError, OSError, KeyError):
        return []


def main():
    """Check for pending mandatory tasks. Block stop if found."""
    # Invocation timer
    try:
        from shared.invocation_logger import InvocationTimer
        timer = InvocationTimer("task-enforcer", event="Stop").start()
    except Exception:
        timer = None

    try:
        pending = get_pending_mandatory_tasks()

        if not pending:
            # No mandatory tasks pending — allow stop
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        # Build reason message listing pending tasks
        task_list = []
        for task in pending[:5]:  # Show max 5 tasks
            content = task["content"][:80]
            hook = task["createdBy"].replace("-hook", "")
            task_list.append(f"  - [{hook}] {content}")

        tasks_str = "\n".join(task_list)

        reason = (
            f"[TASK-ENFORCER] {len(pending)} mandatory task(s) pending!\n\n"
            f"{tasks_str}\n\n"
            "Execute these tasks before stopping:\n"
            "- Cache tasks: save research to skills cache\n"
            "- Factory tasks: update settings.json, registries, MEMORY.md\n"
            "- Docs tasks: update documentation and skills per docs-change-tracker\n"
            "- Git tasks: commit uncommitted changes (auto-git-save)\n"
            "- After completing ALL tasks, you may stop."
        )

        output = {"decision": "block", "reason": reason}
        out_bytes = json.dumps(output, ensure_ascii=False).encode("utf-8")
        sys.stdout.buffer.write(out_bytes + b"\n")
        sys.stdout.buffer.flush()
        if timer:
            timer.log(outcome="block")
        sys.exit(2)  # Block stop

    except Exception as e:
        # Graceful degradation: allow stop on any error
        if timer:
            timer.log(outcome="error", error=f"{type(e).__name__}: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
