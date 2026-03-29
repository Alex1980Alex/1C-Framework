#!/usr/bin/env python3
"""
Hook: skill-eval-enforcer (shell-output version)
Event: UserPromptSubmit
Matcher: (none — fires on every user prompt)
Purpose: Task Protocol enforcement + skill evaluation on every user prompt.
Timeout: 3s

Responsibilities:
  1. Reset task protocol state on each new prompt
  2. Auto-classify prompt complexity (trivial/medium/complex)
  3. Set SessionState.set_task_classified() for trivial prompts (auto-allow)
  4. Output Task Protocol instruction (replaces generic skill eval)

Research basis (Scott Spence, 650+ trials):
  - JSON systemMessage: 55% activation (NO improvement vs baseline!)
  - Shell echo stdout:   100% activation
  - Source: https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals

Position: AFTER skill-router.py in the hook chain (reads its recommendations).
"""

import json
import os
import re
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

# Multi-file indicators that force non-trivial classification
_MULTI_FILE_MARKERS = re.compile(
    r"и также|а также|плюс|additionally|across|multiple files|"
    r"refactor|все файлы|each file|several|несколько файлов|"
    r"во всех|all files|every file",
    re.IGNORECASE,
)


def _classify_complexity(prompt: str) -> str:
    """Auto-classify prompt complexity.

    Returns: 'trivial', 'medium', or 'complex'.
    """
    word_count = len(prompt.split())

    # Multi-file markers always force non-trivial
    if _MULTI_FILE_MARKERS.search(prompt):
        return "complex" if word_count > 100 else "medium"

    if word_count < 30:
        return "trivial"
    elif word_count < 100:
        return "medium"
    else:
        return "complex"


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

    # --- Task Protocol: reset and auto-classify on each new prompt ---
    complexity = _classify_complexity(prompt_stripped)
    try:
        from shared.session_state import SessionState

        # Reset protocol state for new prompt
        SessionState.reset_task_protocol()

        # Auto-classify: trivial prompts get immediate "classified" phase
        # This prevents false blocking by task-protocol-enforcer
        SessionState.set_task_classified(complexity)
    except Exception:
        pass  # Graceful degradation

    # --- Phase 11.2: Check if skill-router already output specific recommendations ---
    # If router fired with concrete Skill() calls, skip generic enforcement (reduces noise)
    try:
        from shared.session_state import SessionState
        if SessionState.was_router_fired_recently(seconds=10):
            # Router already gave specific "ACTIVATE SKILLS: Skill('X')" instruction
            # No need for generic instruction on top of it
            sys.exit(0)
    except Exception:
        pass  # Fallback: output instruction

    # Task Protocol instruction (replaces generic MANDATORY SKILL EVALUATION)
    # Plain text stdout = 100% injection rate (vs 55% for JSON systemMessage)
    print(
        "INSTRUCTION: TASK PROTOCOL (MANDATORY)\n"
        "1. CLASSIFY: trivial (<1 file) | medium (1-3 files) | complex (4+)\n"
        "   Auto-classified as: {complexity}\n"
        "2. IF NOT trivial: DECOMPOSE via TaskCreate\n"
        "3. SKILL CHECK (ALL tasks including trivial!):\n"
        "   Search skills -> activate via Skill() or Skill('learning-loop')\n"
        "   Write/Edit is BLOCKED until Skill() is called.\n"
        "4. Execute -> TaskUpdate completed\n"
        "5. VERIFY: Skill('code-verify') after code changes\n"
        "CRITICAL: Skill() call is REQUIRED before any Write/Edit.".format(
            complexity=complexity
        )
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
