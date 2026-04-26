#!/usr/bin/env python3
"""
Hook: task-protocol-enforcer
Event: PreToolUse
Matcher: Write|Edit
Purpose: Block Write/Edit until skills are checked (phase must be "skill_checked").
Timeout: 3s

Part of Task Protocol enforcement system.
Ensures Claude follows: classify → (decompose) → skill search → execute → verify.
Only phase="skill_checked" allows Write/Edit. Skill() call sets this phase.

Exempt files (always allowed):
- .claude/ directory (hooks, skills, settings)
- docs/ directory
- data/ directory
- Config files (.json, .toml, .yml, .yaml, .env, .cfg, .ini)
- Non-code files (.md, .txt, .csv, .log)
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base.protocol import BaseHook, HookInput, HookOutput  # noqa: E402
from typing import Optional  # noqa: E402


# Directories exempt from protocol enforcement
_EXEMPT_DIRS = (
    ".claude/",
    ".claude\\",
    "docs/",
    "docs\\",
    "data/",
    "data\\",
    ".github/",
    ".github\\",
)

# File extensions exempt from protocol enforcement
_EXEMPT_EXTENSIONS = (
    ".json", ".toml", ".yml", ".yaml", ".env", ".cfg", ".ini",  # config
    ".md", ".txt", ".csv", ".log", ".rst",  # non-code
    ".gitignore", ".dockerignore",  # dotfiles
)


def _is_exempt(file_path: str) -> bool:
    """Check if file is exempt from task protocol enforcement."""
    if not file_path:
        return True  # No file path = allow (safety)

    # Normalize path separators
    normalized = file_path.replace("\\", "/")

    # Strip project root prefix if present
    for prefix in ("D:/1С-Framework/", "D:\\1С-Framework\\"):
        if normalized.startswith(prefix.replace("\\", "/")):
            normalized = normalized[len(prefix):]
            break

    # Check exempt directories
    for exempt_dir in _EXEMPT_DIRS:
        exempt_normalized = exempt_dir.replace("\\", "/")
        if normalized.startswith(exempt_normalized):
            return True

    # Check exempt extensions
    _, ext = os.path.splitext(normalized)
    if ext.lower() in _EXEMPT_EXTENSIONS:
        return True

    # Check basename for dotfiles
    basename = os.path.basename(normalized)
    if basename.startswith("."):
        return True

    return False


def _extract_file_path(tool_input: dict) -> str:
    """Extract file path from Write or Edit tool input."""
    return (
        tool_input.get("file_path", "")
        or tool_input.get("filePath", "")
        or tool_input.get("path", "")
        or ""
    )


class TaskProtocolEnforcer(BaseHook):
    """PreToolUse:Write|Edit → blocks unless phase is 'skill_checked'."""

    def execute(self, inp: HookInput) -> Optional[HookOutput]:
        # Only act on Write/Edit
        if inp.tool_name not in ("Write", "Edit"):
            return None

        # Check file exemption
        file_path = _extract_file_path(inp.tool_input)
        if _is_exempt(file_path):
            return None

        # Check task protocol state
        try:
            from shared.session_state import SessionState
            protocol = SessionState.get_task_protocol()
        except Exception:
            return None  # Graceful degradation: allow on error

        phase = protocol.get("phase", "idle")

        # Only skill_checked allows Write/Edit
        if phase == "skill_checked":
            return None

        # Build context-aware block message
        if phase == "idle":
            hint = (
                "1. CLASSIFY complexity (trivial/medium/complex)\n"
                "2. Search skills → activate via Skill()\n"
                "3. IF NOT trivial: TaskCreate subtasks\n"
                "4. Then retry Write/Edit."
            )
        elif phase == "classified":
            hint = (
                "Skills not checked yet!\n"
                "1. Search available skills for this task\n"
                "2. Activate via Skill() — or Skill('learning-loop') if none found\n"
                "3. Then retry Write/Edit."
            )
        elif phase == "decomposed":
            hint = (
                "Decomposed but skills not checked!\n"
                "1. Search skills for current subtask\n"
                "2. Activate via Skill() — or Skill('learning-loop') if none found\n"
                "3. Then retry Write/Edit."
            )
        else:
            hint = "Activate a skill via Skill() before writing code."

        return HookOutput().block(
            f"TASK PROTOCOL: Check skills before writing code.\n"
            f"{hint}\n"
            f"Full algorithm: Skill('task-protocol')"
        )


if __name__ == "__main__":
    TaskProtocolEnforcer().run()
