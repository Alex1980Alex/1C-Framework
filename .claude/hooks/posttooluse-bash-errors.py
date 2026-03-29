#!/usr/bin/env python3
"""
Hook: posttooluse-bash-errors
Event: PostToolUse
Matcher: Bash
Purpose: Parse Bash tool_response for common error patterns (pytest failures,
         git conflicts, pip errors, ruff errors). Return structured feedback
         via hookSpecificOutput with actionable suggestions.
Timeout: 3s
"""

import json
import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# Error patterns: (regex_fragment, error_type, extract_hint)
ERROR_PATTERNS = [
    # pytest
    ("FAILED ", "pytest_failure", "test"),
    ("AssertionError", "assertion_error", "test"),
    ("pytest: error:", "pytest_error", "config"),
    # git
    ("CONFLICT (content)", "git_conflict", "merge"),
    ("merge conflict", "git_conflict", "merge"),
    ("fatal: not a git repository", "git_error", "path"),
    ("error: failed to push", "git_push_error", "remote"),
    # pip/uv
    ("ERROR: Could not find a version",
     "pip_version_error", "package"),
    ("ERROR: No matching distribution",
     "pip_dist_error", "package"),
    ("ResolutionImpossible", "pip_resolve_error", "deps"),
    # ruff/linting
    ("Found ", " errors", "lint_errors", "code"),
    # mypy/pyright
    ("error:", "type_error", "type"),
    # general
    ("Permission denied", "permission_error", "perms"),
    ("No such file or directory",
     "file_not_found", "path"),
    ("CommandNotFoundException", "command_not_found", "install"),
    ("is not recognized as an internal",
     "command_not_found_win", "path"),
]

# Patterns that should NOT trigger (false positives)
SKIP_PATTERNS = [
    "echo ",
    "printf ",
    "cat <<",
    "grep -c",
]


class PostToolUseBashErrors(BaseHook):
    """PostToolUse hook for Bash: detect errors in command output."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Bash":
            return None

        tool_response = inp.raw.get("tool_response", "")
        if not tool_response:
            return None

        # Normalize response
        if isinstance(tool_response, list):
            text = ""
            for block in tool_response:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
        elif isinstance(tool_response, str):
            text = tool_response
        else:
            text = str(tool_response)

        if not text or len(text) < 20:
            return None

        # Skip commands that just print status
        tool_input = inp.tool_input
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, AttributeError):
                return None

        if not isinstance(tool_input, dict):
            return None

        command = tool_input.get("command", "")
        if not command:
            return None

        # Skip echo/printf commands (likely status messages)
        cmd_start = command.strip()[:20].lower()
        for skip in SKIP_PATTERNS:
            if cmd_start.startswith(skip):
                return None

        # Detect errors
        text_lower = text.lower()
        detected = []
        for pattern, error_type, hint in ERROR_PATTERNS:
            if pattern.lower() in text_lower:
                detected.append((error_type, hint))

        if not detected:
            return None

        # Deduplicate error types
        seen = set()
        unique = []
        for etype, hint in detected:
            if etype not in seen:
                seen.add(etype)
                unique.append((etype, hint))

        # Build feedback
        types_str = ", ".join(t for t, _ in unique)
        hints_str = "; ".join(h for _, h in unique)

        message = (
            f"[bash-errors] Detected {len(unique)} error type(s) "
            f"in Bash output: {types_str}.\n"
            f"Suggested focus areas: {hints_str}.\n"
            f"Review the command output above for details."
        )

        return HookOutput().hook_context(message)


if __name__ == "__main__":
    PostToolUseBashErrors().run()
