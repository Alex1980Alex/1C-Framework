#!/usr/bin/env python3
"""
Hook: skill-quality-monitor
Event: UserPromptSubmit
Matcher: (none - fires on every user prompt)
Purpose: LOGGING ONLY. Tracks skill router quality metrics:
         - Which skills were recommended (from skill-router.log)
         - Whether user called Skill() manually (from session state)
         - Router confidence level
         Writes to data/skill-quality-metrics.jsonl
         NO blocking. NO systemMessage. Graceful degradation.
Timeout: 2s
"""

import json
import os
import sys
from datetime import datetime

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

_PROJECT_DIR = os.path.dirname(os.path.dirname(_HOOK_DIR))
_METRICS_PATH = os.path.join(_PROJECT_DIR, "data", "skill-quality-metrics.jsonl")


class SkillQualityMonitor(BaseHook):
    """Passive quality monitor - logs skill routing accuracy signals."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt) < 5:
            return None

        # Collect metrics from session state (populated by skill-router + observer)
        entry = {
            "ts": datetime.now().isoformat(),
            "session_id": inp.session_id[:16] if inp.session_id else "",
            "prompt_len": len(prompt),
            "prompt_snippet": prompt[:80].replace("\n", " "),
        }

        try:
            from shared.session_state import SessionState
            # Skills recommended by router this session
            recommended = SessionState.get_already_recommended()
            # Skills actually activated via Skill() tool
            activated = SessionState.get_already_activated()
            # Prompt ID from last router recommendation
            prompt_id = SessionState.get_prompt_id()

            entry["recommended"] = list(recommended) if recommended else []
            entry["activated"] = list(activated) if activated else []
            entry["prompt_id"] = prompt_id or ""

            # Detect manual activation: user called Skill() for a skill
            # that router did NOT recommend = router missed it
            if activated and recommended:
                manual = [s for s in activated if s not in recommended]
                entry["manual_activations"] = manual
            else:
                entry["manual_activations"] = []

        except Exception:
            entry["recommended"] = []
            entry["activated"] = []
            entry["manual_activations"] = []
            entry["prompt_id"] = ""

        # Write to JSONL (append-only, never blocks)
        try:
            os.makedirs(os.path.dirname(_METRICS_PATH), exist_ok=True)
            with open(_METRICS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

        # NEVER return output - this is a passive logger
        return None


if __name__ == "__main__":
    SkillQualityMonitor().run()
