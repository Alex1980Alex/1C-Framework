#!/usr/bin/env python3
"""
Hook: logging-status-banner
Event: SessionStart
Matcher: (none)
Purpose: One-shot confirmation that the universal MCP/slash-command logging
         pipeline is active in this session. Lets the user verify after a
         Claude Code restart that hooks added in a prior session actually
         loaded.

Output: a short systemMessage on each SessionStart with:
    - log file path
    - presence of mcp-invocation-logger.py and slash-command-tracker.py on disk
    - count of slash_run + mcp_call entries in the last 24h (so a restart with
      no traffic still surfaces "logging is wired but no recent activity")

Failure mode: if anything goes wrong (file missing, permission, etc.), the
hook degrades to no-op — it must never block a SessionStart.

Timeout: 3s
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(_HOOK_DIR).parent.parent
LOG_FILE = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
MCP_HOOK = Path(_HOOK_DIR) / "mcp-invocation-logger.py"
SLASH_HOOK = Path(_HOOK_DIR) / "slash-command-tracker.py"
RECENT_WINDOW_HOURS = 24


class LoggingStatusBanner(BaseHook):
    HOOK_NAME = "LoggingStatusBanner"

    def execute(self, inp: HookInput) -> HookOutput | None:
        # No event check — settings.json registers this hook only on SessionStart.
        # base/protocol.py:53 detected_event returns "Unknown" for SessionStart
        # payloads (only session_id is present), so an event check would
        # incorrectly skip every legitimate fire.
        mcp_present = MCP_HOOK.is_file()
        slash_present = SLASH_HOOK.is_file()
        slash_n, mcp_n = _recent_counts()

        status = "ACTIVE" if mcp_present and slash_present else "PARTIAL"
        msg = (
            f"[mcp/slash logging: {status}] "
            f"log={LOG_FILE.name} | "
            f"mcp-logger={'ok' if mcp_present else 'MISSING'} | "
            f"slash-tracker={'ok' if slash_present else 'MISSING'} | "
            f"last {RECENT_WINDOW_HOURS}h: slash_run={slash_n} mcp_call={mcp_n}"
        )
        return HookOutput().system_message(msg)


def _recent_counts() -> tuple[int, int]:
    """Count slash_run and mcp_call entries in the last RECENT_WINDOW_HOURS."""
    if not LOG_FILE.is_file():
        return 0, 0
    cutoff = datetime.now() - timedelta(hours=RECENT_WINDOW_HOURS)
    slash_n = mcp_n = 0
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry.get("ts", ""))
                    if ts < cutoff:
                        continue
                    cat = entry.get("category", "")
                    if cat == "slash_run":
                        slash_n += 1
                    elif cat == "mcp_call":
                        mcp_n += 1
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
    except OSError:
        pass
    return slash_n, mcp_n


if __name__ == "__main__":
    LoggingStatusBanner().run()
