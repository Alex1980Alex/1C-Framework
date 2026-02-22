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

    # Plain text output (NOT JSON systemMessage!)
    # This is the key: plain text stdout = 100% activation rate
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
    try:
        main()
    except Exception:
        sys.exit(0)  # Graceful degradation: never block
