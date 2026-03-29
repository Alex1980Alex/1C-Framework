#!/usr/bin/env python3
"""
Hook: posttooluse-quality-feedback
Event: PostToolUse
Matcher: Write|Edit
Purpose: Run ruff check on *.py files after Write/Edit and report errors
         back to Claude via hookSpecificOutput. Only fires for Python files.
Timeout: 5s
"""

import json
import os
import subprocess
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


def _run_ruff(file_path: str) -> list[dict] | None:
    """Run ruff check on a file. Returns list of issues or None on error."""
    project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
    venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    venv_ruff = os.path.join(project_dir, ".venv", "Scripts", "ruff.exe")

    # Prefer ruff executable, fallback to python -m ruff
    if os.path.isfile(venv_ruff):
        cmd = [venv_ruff, "check", "--output-format=json", file_path]
    elif os.path.isfile(venv_python):
        cmd = [venv_python, "-m", "ruff", "check", "--output-format=json", file_path]
    else:
        return None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_dir,
        )
        # ruff exits 0 if no issues, 1 if issues found, 2 on error
        if result.returncode == 2:
            return None
        if result.stdout.strip():
            issues = json.loads(result.stdout)
            return issues if isinstance(issues, list) else None
        return []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


class PostToolUseQualityFeedback(BaseHook):
    """PostToolUse hook for Write|Edit: run ruff on *.py files."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_input = inp.tool_input
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, AttributeError):
                return None

        if not isinstance(tool_input, dict):
            return None

        file_path = tool_input.get("file_path", "")
        if not file_path:
            return None

        # Only Python files
        if not file_path.replace("\\", "/").endswith(".py"):
            return None

        # Skip non-project files
        normalized = file_path.replace("\\", "/")
        skip = (
            ".claude/cache/", ".claude/hooks/",
            "__pycache__", ".venv/", "node_modules/",
            "build/", "dist/",
        )
        if any(s in normalized for s in skip):
            return None

        # File must exist (Write creates it, Edit modifies)
        if not os.path.isfile(file_path):
            return None

        issues = _run_ruff(file_path)
        if issues is None:
            return None  # ruff unavailable or errored

        if not issues:
            return None  # No issues found

        # Build feedback message
        error_count = 0
        warning_count = 0
        lines = []
        for issue in issues[:10]:  # Max 10 issues to avoid feedback bloat
            loc = f"{issue.get('location', {}).get('row', '?')}"
            code = issue.get("code", "")
            msg = issue.get("message", "")
            severity = "E" if code.startswith("E") or code.startswith("F") else "W"
            if severity == "E":
                error_count += 1
            else:
                warning_count += 1
            lines.append(f"  L{loc} [{code}] {msg}")

        summary = f"[quality-feedback] ruff found {error_count} errors, {warning_count} warnings in {os.path.basename(file_path)}:\n"
        summary += "\n".join(lines)
        if len(issues) > 10:
            summary += f"\n  ... and {len(issues) - 10} more issues"

        return HookOutput().hook_context(summary)


if __name__ == "__main__":
    PostToolUseQualityFeedback().run()
