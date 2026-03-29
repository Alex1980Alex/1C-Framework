#!/usr/bin/env python3
"""
Hook: posttooluse-docs-tracker
Event: PostToolUse
Matcher: Write|Edit
Purpose: Instant feedback after Write/Edit about docs that need updating.
         Uses hookSpecificOutput to deliver reminder to Claude immediately.
Timeout: 3s
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


# Map of code paths to documentation areas
DOC_MAPPINGS = {
    "src/pdf_framework/": "PDF Framework core (src/pdf_framework/)",
    "src/api/": "REST API (src/api/)",
    "src/cli/": "CLI commands (src/cli/)",
    "src/mcp_server/": "MCP server (src/mcp_server/)",
    "src/ui/": "UI pages (src/ui/)",
    "src/bsl/": "BSL development (src/bsl/)",
    "src/shared/": "Shared modules (src/shared/)",
    "src/workers/": "Background workers (src/workers/)",
    ".claude/hooks/": "Hooks infrastructure (.claude/hooks/)",
    ".claude/skills/": "Skills (.claude/skills/)",
}

# Paths that don't need docs tracking
SKIP_PATTERNS = [
    "docs/",
    ".claude/cache/",
    "__pycache__",
    ".claude/data/",
    "data/",
    ".venv/",
    "node_modules/",
    ".git/",
    ".claude/settings",
    ".claude/hooks/base/",
    ".claude/hooks/shared/",
]

# Extensions that don't need docs
SKIP_EXTENSIONS = {
    ".log", ".tmp", ".bak", ".pyc", ".json", ".toml", ".yml", ".yaml",
    ".env", ".cfg", ".ini", ".lock", ".db", ".sqlite",
}


class PostToolUseDocsTracker(BaseHook):
    """PostToolUse hook for Write|Edit: instant docs change reminder."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_input = inp.tool_input
        if isinstance(tool_input, str):
            import json
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, AttributeError):
                return None

        if not isinstance(tool_input, dict):
            return None

        file_path = tool_input.get("file_path", "")
        if not file_path:
            return None

        # Normalize path
        file_path = file_path.replace("\\", "/")

        # Skip non-code paths
        for pattern in SKIP_PATTERNS:
            if pattern in file_path:
                return None

        # Skip non-code extensions
        _, ext = os.path.splitext(file_path)
        if ext.lower() in SKIP_EXTENSIONS:
            return None

        # Skip .claude/ internal files (but allow hooks and skills)
        if file_path.startswith(".claude/"):
            if not any(file_path.startswith(p) for p in (".claude/hooks/", ".claude/skills/")):
                return None

        # Find matching doc areas
        matched_areas = []
        for code_prefix, doc_area in DOC_MAPPINGS.items():
            if code_prefix in file_path:
                matched_areas.append(doc_area)

        if not matched_areas:
            return None

        # Build feedback message
        areas_text = "; ".join(matched_areas)
        message = (
            f"[docs-tracker] {file_path} was modified. "
            f"Related docs may need updating: {areas_text}. "
            f"If this is a public API/behavior change, update documentation accordingly."
        )

        return HookOutput().hook_context(message)


if __name__ == "__main__":
    PostToolUseDocsTracker().run()
