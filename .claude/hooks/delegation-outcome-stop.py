#!/usr/bin/env python3
"""
Hook: delegation-outcome-stop
Event: Stop
Purpose: Appends session delegation summary to JSONL at session end
Timeout: 3s

Non-blocking: advisory only, never prevents stop.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

try:
    from shared.session_state import SessionState
except ImportError:
    SessionState = None

OUTCOMES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "delegation-outcomes.jsonl"


class DelegationOutcomeStop(BaseHook):
    """Append session delegation summary at stop."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if not OUTCOMES_FILE.exists():
            return None

        session_id = ""
        if SessionState:
            try:
                session_id = SessionState.get_session_id()
            except Exception:
                pass

        if not session_id:
            return None

        # Read outcomes for this session
        outcomes = []
        try:
            with open(OUTCOMES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("session_id") == session_id and "type" not in entry:
                        outcomes.append(entry)
        except Exception:
            return None

        if not outcomes:
            return None

        total = len(outcomes)
        delegated = sum(1 for o in outcomes if o.get("delegated"))
        total_lines = sum(o.get("estimated_lines", 0) for o in outcomes)

        summary = {
            "type": "session_summary",
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "total_writes": total,
            "delegated_count": delegated,
            "undelegated_count": total - delegated,
            "delegation_rate": round(delegated / total, 2) if total > 0 else 0,
            "total_lines": total_lines,
            "classifications": {},
        }

        for o in outcomes:
            cls = o.get("classification", "Unknown")
            summary["classifications"][cls] = summary["classifications"].get(cls, 0) + 1

        try:
            with open(OUTCOMES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        except Exception:
            pass

        return None


if __name__ == "__main__":
    DelegationOutcomeStop().run()
