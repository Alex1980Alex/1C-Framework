#!/usr/bin/env python3
"""SessionStart hook: on Saturdays, nudge about deferred known-issue fixes (ADR-055 layer 2).

Local best-effort reminder — fires only if a session is opened on Saturday and
there are non-expired known-issue suppressions still pending a real fix.
Opt-out via env KNOWN_ISSUE_NUDGE_DISABLE=1.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWN_ISSUES = PROJECT_ROOT / "data" / "reports" / "tools" / "known_issues.json"
STATE = PROJECT_ROOT / ".claude" / "cache" / "known-issue-saturday-nudge-state.json"


def _load_known_issues() -> dict:
    try:
        with open(KNOWN_ISSUES, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _review_expired(review_by, now: datetime) -> bool:
    if not review_by:
        return True
    try:
        return datetime.fromisoformat(review_by).date() < now.date()
    except (TypeError, ValueError):
        return True


def active_nudges(known: dict, now: datetime) -> list[str]:
    if now.weekday() != 5:
        return []
    result = []
    for name, entry in known.items():
        if not _review_expired(entry.get("review_by"), now):
            result.append(name)
    return sorted(result)


def _already_nudged_today(now: datetime) -> bool:
    try:
        with open(STATE, encoding="utf-8") as f:
            st = json.load(f)
        return st.get("last_nudge_date") == now.date().isoformat()
    except Exception:
        return False


def _mark_nudged(now: datetime) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"last_nudge_date": now.date().isoformat()}, f)
        os.replace(tmp, STATE)
    except OSError:
        pass


class KnownIssueSaturdayNudge(BaseHook):
    HOOK_NAME = "KnownIssueSaturdayNudge"

    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("KNOWN_ISSUE_NUDGE_DISABLE") == "1":
            return None

        now = datetime.now()
        tools = active_nudges(_load_known_issues(), now)
        if not tools:
            return None

        if _already_nudged_today(now):
            return None

        _mark_nudged(now)

        names = ", ".join(f"`{t}`" for t in tools)
        return HookOutput().system_message(
            f"[SATURDAY-NUDGE] ⏰ Суббота — отложенные known-issue фиксы ждут: {names}. "
            "См. roadmap 260718 секцию NEXT (F1/F2/F3) + data/reports/tools/known_issues.json. "
            "Займись фиксом ЛИБО продли review_by."
        )


if __name__ == "__main__":
    KnownIssueSaturdayNudge().run()
