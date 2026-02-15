#!/usr/bin/env python3
"""
Hook: task-enforcer
Event: Stop
Matcher: (none — fires on every stop attempt)
Purpose: Block Claude from stopping if mandatory hook tasks are pending.
         Reads hook-todos.json directly (no shared/ imports for max reliability).
         Coexists with ralph_wiggum_stop.py (both run sequentially on Stop).
Timeout: 5s

Exit codes:
  0 = allow stop
  2 = block stop (mandatory tasks pending)

Adapted from 1C-Enterprise_Framework stop/task-enforcer.py.
"""

import json
import sys
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

# Hook IDs whose pending tasks block stop
MANDATORY_HOOKS = {
    "knowledge-cache-reminder-hook",
    "factory-enforcer-hook",
}


def get_pending_mandatory_tasks() -> list:
    """Get pending tasks from mandatory hooks."""
    if not TODOS_FILE.exists():
        return []

    try:
        with open(TODOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

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
    try:
        pending = get_pending_mandatory_tasks()

        if not pending:
            # No mandatory tasks pending — allow stop
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
            "- After completing ALL tasks, you may stop."
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
