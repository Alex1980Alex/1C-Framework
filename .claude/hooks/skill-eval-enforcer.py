#!/usr/bin/env python3
"""
Hook: skill-eval-enforcer
Event: UserPromptSubmit
Matcher: (none — fires on every user prompt)
Purpose: Force Claude to evaluate and activate relevant skills before responding.
         Without this hook, skill-router recommendations are ignored ~95% of the time.
         With forced evaluation: 95%+ activation rate (based on Scott Spence testing).
Timeout: 3s

Based on: umputun forced-eval pattern + Scott Spence empirical data (650+ trials).
Position: AFTER skill-router.py in the hook chain (reads its recommendations).

References:
  - https://gist.github.com/umputun/570c77f8d5f3ab621498e1449d2b98b6
  - https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


class SkillEvalEnforcer(BaseHook):
    """Mandatory skill evaluation instruction on every user prompt.

    Forces Claude to:
    1. Evaluate [SKILL-ROUTER] recommendations from the previous hook
    2. Activate ALL relevant skills via Skill() tool
    3. Only then proceed with the actual response

    Filters out:
    - IDE events (<ide_opened_file>, <ide_selection>) — no user intent
    - Very short prompts (< 15 chars) — likely trivial
    - Slash commands (/help, /commit, etc.) — handled differently
    """

    # Minimum prompt length to trigger evaluation
    MIN_PROMPT_LENGTH = 15

    # Prefixes that indicate IDE metadata, not user input
    IDE_PREFIXES = ("<ide_", "<ide_opened_file", "<ide_selection")

    # Slash commands handled by Claude Code directly
    SLASH_COMMAND_PREFIX = "/"

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt:
            return None

        prompt_stripped = prompt.strip()

        # Skip IDE events (VS Code injects file open/selection metadata)
        if any(prompt_stripped.startswith(p) for p in self.IDE_PREFIXES):
            return None

        # Skip very short prompts (trivial tasks)
        if len(prompt_stripped) < self.MIN_PROMPT_LENGTH:
            return None

        # Skip slash commands (handled by Claude Code)
        if prompt_stripped.startswith(self.SLASH_COMMAND_PREFIX):
            return None

        return HookOutput().system_message(
            "INSTRUCTION: MANDATORY SKILL EVALUATION\n"
            "Before responding to this prompt, you MUST evaluate skill relevance:\n"
            "1. Check [SKILL-ROUTER] recommendations above (if any)\n"
            "2. Check <available_skills> in system context\n"
            "3. IF any skills are relevant to this prompt:\n"
            "   - State which skills and why (1 line each)\n"
            "   - Activate ALL relevant skills via Skill() tool\n"
            "   - Then proceed with implementation using skill knowledge\n"
            "4. IF no skills are relevant: Proceed directly (no statement needed)\n"
            "CRITICAL: Mentioning a skill without activating it via Skill() is useless.\n"
            "Multiple skills can and should be activated when applicable."
        )


if __name__ == "__main__":
    SkillEvalEnforcer().run()
