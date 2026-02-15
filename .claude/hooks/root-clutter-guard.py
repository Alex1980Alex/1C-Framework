"""Root Clutter Guard — blocks ad-hoc test/debug files from being created in project root.

Trigger: PreToolUse → Write
Action: Block writes matching ad-hoc patterns in project root, suggest proper location.

Patterns blocked:
  test_*.py, search_*.py, check_*.py, verify_*.py, reindex_*.py
  temp_*.json, *_result*.json, *_result*.txt, *_debug*.py
  quick_*.py, rebuild_*.py, enrich_*.py

Allowed root files (whitelist):
  README.md, CLAUDE.md, pyproject.toml, requirements.lock, .gitignore, .env*
  run.bat, run_ui.bat, setup.bat, activate.bat, activate.sh, conftest.py
"""

import os
import re
import sys
from pathlib import PurePosixPath, PureWindowsPath

# Core path resolution: find base/ + shared/ in user-level or project-level
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# Ad-hoc file patterns (regex on filename only)
_AD_HOC_PATTERNS = [
    r"^test_.*\.(py|txt|json)$",
    r"^search_.*\.py$",
    r"^check_.*\.py$",
    r"^verify_.*\.py$",
    r"^reindex_.*\.py$",
    r"^temp_.*\.(json|py|txt)$",
    r".*_result.*\.(json|txt)$",
    r".*_debug.*\.py$",
    r"^quick_.*\.py$",
    r"^rebuild_.*\.py$",
    r"^enrich_.*\.py$",
    r"^pdf_search\.py$",
]

_AD_HOC_RE = re.compile("|".join(f"({p})" for p in _AD_HOC_PATTERNS))

# Project root (2 levels up from .claude/hooks/)
_PROJECT_ROOT = str(PureWindowsPath(__file__).parent.parent.parent).replace("\\", "/")


class RootClutterGuard(BaseHook):
    """Block ad-hoc test/debug files from polluting project root."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Write":
            return None

        file_path = inp.tool_input.get("file_path", "")
        if not file_path:
            return None

        # Normalize path (case-insensitive on Windows: D: vs d:)
        normalized = file_path.replace("\\", "/")

        # Check if file is in project root (not in any subdirectory)
        parent = normalized.rsplit("/", 1)[0] if "/" in normalized else ""
        if parent.rstrip("/").lower() != _PROJECT_ROOT.rstrip("/").lower():
            return None  # Not in root — allow

        # Extract filename
        filename = normalized.rsplit("/", 1)[-1] if "/" in normalized else normalized

        # Check against ad-hoc patterns
        if not _AD_HOC_RE.match(filename):
            return None  # Not an ad-hoc file — allow

        # Suggest proper location
        if filename.startswith("test_"):
            suggestion = f"tests/{filename}"
        else:
            suggestion = f"scripts/{filename}"

        return HookOutput().block(
            f"[ROOT-CLUTTER-GUARD] Blocked: '{filename}' in project root.\n"
            f"Ad-hoc scripts pollute the root directory.\n"
            f"Write to '{suggestion}' instead, or use a proper test in tests/."
        )


if __name__ == "__main__":
    RootClutterGuard().run()
