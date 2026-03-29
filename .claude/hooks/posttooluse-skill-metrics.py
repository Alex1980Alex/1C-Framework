#!/usr/bin/env python3
"""
Hook: posttooluse-skill-metrics
Event: PostToolUse
Matcher: Skill
Purpose: Confirm skill activation after Skill tool completes.
         Logs confirmed activation with tool_response analysis.
         Uses hookSpecificOutput for feedback if skill fails to load.
Timeout: 3s
"""

import json
import os
import sys
from datetime import datetime

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


def _log_confirmed(skill_name: str, session_id: str, loaded: bool) -> None:
    """Append confirmed skill activation to data/skill-usage.log."""
    try:
        project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
        log_path = os.path.join(project_dir, "data", "skill-usage.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "confirmed" if loaded else "failed"
        line = f"{ts} | skill={skill_name} | session={session_id[:16] if session_id else 'unknown'} | posttooluse={status}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _log_accuracy_confirmed(prompt_id: str, skill_name: str, loaded: bool) -> None:
    """Write confirmed event to data/skill-accuracy.jsonl."""
    try:
        project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
        log_path = os.path.join(project_dir, "data", "skill-accuracy.jsonl")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(),
            "type": "confirmed" if loaded else "failed",
            "prompt_id": prompt_id,
            "skill": skill_name,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


class PostToolUseSkillMetrics(BaseHook):
    """PostToolUse hook for Skill: confirms activation and logs outcome."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Skill":
            return None

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

        if not skill_name:
            return None

        # Analyze tool_response to confirm skill loaded
        # Claude Code sends 'tool_response' (not 'tool_result')
        tool_response = inp.raw.get("tool_response", inp.tool_result)
        if isinstance(tool_response, dict):
            response_text = json.dumps(tool_response)
        else:
            response_text = str(tool_response) if tool_response else ""

        # Skill loaded if response contains "Launching skill:" or is non-empty
        loaded = bool(response_text and ("Launching skill:" in response_text or len(response_text) > 20))

        # Log confirmed activation
        _log_confirmed(skill_name, inp.session_id, loaded)

        # Accuracy tracking
        try:
            from shared.session_state import get_prompt_id
            prompt_id = get_prompt_id()
            if prompt_id:
                _log_accuracy_confirmed(prompt_id, skill_name, loaded)
        except Exception:
            pass

        # Feedback: warn if skill didn't load properly
        if not loaded:
            return HookOutput().hook_context(
                f"[skill-metrics] Skill '{skill_name}' may not have loaded properly — "
                f"tool_response was empty or very short ({len(response_text)} chars). "
                f"Consider retrying or checking skill name."
            )

        return None


if __name__ == "__main__":
    PostToolUseSkillMetrics().run()
