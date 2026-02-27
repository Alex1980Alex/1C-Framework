#!/usr/bin/env python3
"""
Hook: skill-eval-enforcer (shell-output version)
Event: UserPromptSubmit
Matcher: (none — fires on every user prompt)
Purpose: Force Claude to evaluate and activate relevant skills before responding.
Timeout: 3s

KEY DIFFERENCE from skill-eval-enforcer.py:
  - Old: HookOutput.system_message() → JSON {"systemMessage": "..."} → <system-reminder> tag
  - New: print() → plain text stdout → direct context injection

Research basis (Scott Spence, 650+ trials):
  - JSON systemMessage: 55% activation (NO improvement vs baseline!)
  - Shell echo stdout:   100% activation
  - Source: https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals

Position: AFTER skill-router.py in the hook chain (reads its recommendations).
"""

import json
import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    prompt = data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    prompt_stripped = prompt.strip()

    # Skip IDE events (VS Code injects file open/selection metadata)
    if prompt_stripped.startswith(("<ide_", "<ide_opened_file", "<ide_selection")):
        sys.exit(0)

    # Skip very short prompts (trivial tasks)
    if len(prompt_stripped) < 15:
        sys.exit(0)

    # Skip slash commands (handled by Claude Code)
    if prompt_stripped.startswith("/"):
        sys.exit(0)

    # --- Phase 11.2: Check if skill-router already output specific recommendations ---
    # If router fired with concrete Skill() calls, skip generic enforcement (reduces noise)
    try:
        sys.path.insert(0, _HOOK_DIR)
        from shared.session_state import SessionState
        if SessionState.was_router_fired_recently(seconds=10):
            # Router already gave specific "ACTIVATE SKILLS: Skill('X')" instruction
            # No need for generic "MANDATORY SKILL EVALUATION" on top of it
            sys.exit(0)
    except Exception:
        pass  # Fallback: output generic instruction

    # Generic instruction (ONLY when skill-router didn't match any bundles)
    # Plain text stdout = 100% injection rate (vs 55% for JSON systemMessage)
    print(
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
    _timer = None
    try:
        from shared.invocation_logger import InvocationTimer
        _timer = InvocationTimer("skill-eval-enforcer-shell", event="UserPromptSubmit").start()
    except Exception:
        pass

    try:
        main()
        if _timer:
            _timer.log(outcome="message")
    except SystemExit:
        # main() calls sys.exit(0) for skipped prompts
        if _timer:
            _timer.log(outcome="allow")
        raise
    except Exception:
        if _timer:
            _timer.log(outcome="error")
        sys.exit(0)  # Graceful degradation: never block
