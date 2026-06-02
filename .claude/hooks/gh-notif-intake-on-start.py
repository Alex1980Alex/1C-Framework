#!/usr/bin/env python3
"""
Hook: gh-notif-intake-on-start
Event: SessionStart
Purpose: Summarize unread GitHub notifications via gh api → systemMessage.
  Closes Phase 2 item #3 — email-side intake (using gh notifications API,
  not Gmail MCP since hooks run as subprocesses and cannot call MCP tools).
Opt-out: GH_NOTIF_INTAKE_DISABLE=1
Timeout: 5s
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.gh_notif_classifier import classify, summarize

TIMEOUT_S = 4


def _fetch_notifications() -> list[dict]:
    try:
        r = subprocess.run(
            [
                "gh",
                "api",
                "notifications",
                "--jq",
                "[.[] | {subject: .subject.title, type: .subject.type, reason}]",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return []


def _format_summary(notifs: list[dict]) -> str:
    if not notifs:
        return "[GH-NOTIF] 0 unread GitHub notifications"
    stats = summarize(notifs)
    parts = [f"[GH-NOTIF] {stats['total']} unread"]
    by_cat = stats["by_category"]
    cat_str = ", ".join(f"{c}={n}" for c, n in sorted(by_cat.items(), key=lambda x: -x[1]))
    parts.append(f"({cat_str})")
    return " ".join(parts)


class GhNotifIntake(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("GH_NOTIF_INTAKE_DISABLE") == "1":
            return None
        notifs = _fetch_notifications()
        if not notifs:
            return None
        msg = _format_summary(notifs)
        # Top-3 priority subjects inline for fast triage
        seen = []
        for n in notifs[:3]:
            cat, prio = classify(n.get("subject", ""), n.get("reason", ""))
            seen.append(f"  • [{prio} {cat}] {(n.get('subject') or '')[:70]}")
        if seen:
            msg = msg + "\n" + "\n".join(seen)
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    GhNotifIntake().run()
