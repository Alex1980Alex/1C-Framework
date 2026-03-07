#!/usr/bin/env python3
"""
Hook: memory-sync
Event: Stop
Matcher: (none — fires on every stop attempt)
Purpose: Remind to sync memory systems if memory-related files were changed.
         Checks if any src/memory/ files were modified during the session.
Timeout: 5s

Exit codes:
  0 = allow stop (always — advisory only, no blocking)

Pattern: Advisory (systemMessage reminder, non-blocking).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Core path resolution
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

MEMORY_PATHS = [
    "src/memory/",
]


def get_memory_changes() -> list[str]:
    """Get uncommitted changes in memory-related paths."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []

        changes = []
        for line in result.stdout.strip().splitlines():
            if len(line) < 4:
                continue
            status = line[0:2].strip()
            filepath = line[3:].strip().strip('"')
            if any(filepath.startswith(p) for p in MEMORY_PATHS):
                changes.append(f"  {status}  {filepath}")
        return changes
    except Exception:
        return []


def main():
    # Read hook input from stdin
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        _hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        _hook_input = {}

    changes = get_memory_changes()

    output = {}

    if changes:
        files_list = "\n".join(changes)
        output["systemMessage"] = (
            f"[MEMORY-SYNC] Memory system files were modified in this session:\n"
            f"{files_list}\n\n"
            f"Consider:\n"
            f"- Committing memory system changes\n"
            f"- Verifying MCP servers start correctly: memory-ai, vector-memory, skill-learning\n"
            f"- Running integration tests: pytest tests/integration/test_memory_unified.py"
        )

    # Always allow stop (advisory only)
    json.dump(output, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
