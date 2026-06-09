#!/usr/bin/env python3
"""pattern-reinforce-stop — §22 P1 reinforcement bridge (Stop hook).

Roadmap 260609 P0.1: replaces the reinforce call that previously lived at the
tail of session-memory-save.py, where two defects kept it from ever running in
production:
  1. it sat AFTER the `already_saved` daily-dedup early-return, so every Stop
     except the first-of-day skipped it;
  2. session-memory-save's 5s budget was spent on git collection before the
     Qdrant roundtrips even started, so the first-of-day run was killed
     mid-flight before the final log_event.

This hook does ONE thing within its own budget: detect session success
(commit OR completed task) and call reinforce_session() for patterns the
surfacing hook recorded via record_surfaced().

Key properties:
  - session_id comes from the Stop payload (same source memory-first-hook used
    to name the surfaced-patterns file) with session-skills.json as fallback;
  - early-exit BEFORE any Qdrant/src import when there is nothing surfaced;
  - candidate cap aligned with the hook budget (REINFORCE_CAP, default 10);
  - failures are logged as `session_error` to confidence-lifecycle.log — never
    a silent `except: pass`.

Event: Stop. Advisory: always exit 0. Opt-out: P1_REINFORCE_DISABLE=1.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SESSION_STATE_FILE = PROJECT_ROOT / ".claude" / "data" / "session-skills.json"
HOOK_TODOS_FILE = PROJECT_ROOT / ".claude" / "cache" / "hook-todos.json"

# Candidate cap per run, aligned with the hook timeout (each reinforce is up
# to one Qdrant retrieve + set_payload, 2s client timeout each worst-case).
REINFORCE_CAP = int(os.environ.get("REINFORCE_CAP", "10"))


def _read_json(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _detect_success() -> bool:
    """Cheap success heuristic: a commit in the last 8h OR a completed task.

    Mirrors shared.pattern_reinforce.detect_session_success(ctx) but collects
    only the two inputs it actually uses (no diff/status scans).
    """
    todos = _read_json(HOOK_TODOS_FILE)
    task_list = todos if isinstance(todos, list) else todos.get("tasks", [])
    for t in task_list:
        if isinstance(t, dict) and t.get("status") == "completed" and t.get("title"):
            return True

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=8 hours ago", "--format=%h"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
    except Exception:
        pass
    return False


class PatternReinforceStop(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.getenv("P1_REINFORCE_DISABLE") == "1":
            return None

        session_id = inp.session_id or _read_json(SESSION_STATE_FILE).get("session_id", "")
        if not session_id:
            return None

        from shared.pattern_reinforce import load_surfaced, reinforce_session

        # Early exit before any src/Qdrant import: nothing surfaced => nothing
        # to reinforce, and the sentinel does not need a mark for a no-op.
        if not load_surfaced(session_id):
            return None

        result = reinforce_session(session_id, _detect_success(), cap=REINFORCE_CAP)

        status = result.get("status", "?")
        if status == "ok":
            msg = (
                f"[REINFORCE] session={session_id[:8]} success={result.get('success')} "
                f"applied={result.get('applied', 0)} skipped={result.get('skipped', 0)} "
                f"errors={result.get('errors', 0)}"
            )
            return HookOutput(system_message=msg)
        if status == "error":
            # reinforce_session already wrote session_error to the lifecycle log.
            sys.stderr.write(f"[REINFORCE] error: {result.get('error', '')[:160]}\n")
        return None


if __name__ == "__main__":
    PatternReinforceStop().run()
