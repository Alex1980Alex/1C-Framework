#!/usr/bin/env python3
"""
Hook: skill-usage-metrics
Event: PostToolUse
Matcher: Skill
Purpose: Logs which skills are loaded via the Skill tool.
         Appends to data/skill-usage.log for monitoring and dead skill detection.
Timeout: 3s
"""

import json
import os
import sys
from datetime import datetime

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


def _log_skill_usage(skill_name: str, session_id: str) -> None:
    """Append skill usage to data/skill-usage.log."""
    try:
        project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
        log_path = os.path.join(project_dir, "data", "skill-usage.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | skill={skill_name} | session={session_id[:16] if session_id else 'unknown'}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # Logging must never block


class SkillUsageMetrics(BaseHook):
    """Logs Skill tool invocations for usage analytics."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Skill":
            return None

        # Extract skill name from tool_input
        tool_input = inp.tool_input
        skill_name = ""

        if isinstance(tool_input, dict):
            skill_name = tool_input.get("skill", "")
        elif isinstance(tool_input, str):
            try:
                parsed = json.loads(tool_input)
                skill_name = parsed.get("skill", "")
            except (json.JSONDecodeError, AttributeError):
                skill_name = tool_input

        if skill_name:
            _log_skill_usage(skill_name, inp.session_id)

        # Pure logging — no system message, no blocking
        return None


if __name__ == "__main__":
    SkillUsageMetrics().run()
