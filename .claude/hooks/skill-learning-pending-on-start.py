#!/usr/bin/env python3
"""
Hook: skill-learning-pending-on-start
Event: SessionStart
Purpose: Surface the skill-learning pending quarantine at session start
  (roadmap 260611 P2.1) — [SKILL-LEARNING] pending=N (oldest Xd): top-3 names.
  Reminds about moderation (confirm_pattern / reject_pattern) so pending
  candidates don't rot unseen between sessions.
Opt-out: SKILL_LEARNING_PENDING_DISABLE=1
Timeout: 3s (pure local JSONL read, no network)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PENDING_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "skill_learning" / "pending_patterns.jsonl"
)
TOP_N = 3


def _read_pending() -> list[dict]:
    if not PENDING_FILE.exists():
        return []
    items = []
    try:
        with open(PENDING_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return items


def _oldest_age_days(items: list[dict]) -> int | None:
    oldest: datetime | None = None
    for it in items:
        raw = it.get("created_at")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if oldest is None or dt < oldest:
            oldest = dt
    if oldest is None:
        return None
    return max(0, (datetime.now() - oldest).days)


class SkillLearningPendingBanner(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("SKILL_LEARNING_PENDING_DISABLE") == "1":
            return None
        items = _read_pending()
        if not items:
            return None
        age = _oldest_age_days(items)
        age_str = f" (oldest {age}d)" if age is not None else ""
        names = ", ".join(
            (it.get("name") or it.get("pattern_id", "?"))[:50] for it in items[:TOP_N]
        )
        msg = (
            f"[SKILL-LEARNING] pending={len(items)}{age_str}: {names}\n"
            "  Модерация: mcp__skill-learning__get_pending_patterns → "
            "confirm_pattern / reject_pattern"
        )
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    SkillLearningPendingBanner().run()
