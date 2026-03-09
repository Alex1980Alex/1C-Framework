#!/usr/bin/env python3
"""
Hook: code-review-enforcer
Event: PostToolUse
Matcher: Write|Edit
Purpose: Mandatory Opus self-review after ANY code write/edit.
         Basic review for all code, Thorough for Hard tasks.
         Does NOT fire for docs/config/markdown files.
Timeout: 3s
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# Code file extensions that require review
_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".bsl", ".os",
    ".java", ".go", ".rs", ".rb", ".php",
    ".c", ".cpp", ".h", ".hpp",
    ".sh", ".bash", ".ps1",
}

# Skip patterns (not real code changes)
_SKIP_PATTERNS = [
    r"\.claude/cache/",
    r"\.claude/data/",
    r"__pycache__",
    r"\.pyc$",
    r"node_modules/",
    r"\.git/",
    r"data/.*\.json$",
    r"data/.*\.db$",
    r"\.env",
]

# Hard task indicators in file path
_HARD_PATH_PATTERNS = [
    r"src/",
    r"tools/",
    r"infra/",
    r"scripts/",
]


class CodeReviewEnforcer(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        file_path = inp.tool_input.get("file_path", "")
        if not file_path:
            return None

        # Normalize path
        normalized = file_path.replace("\\", "/")

        # Skip non-code files
        ext = os.path.splitext(normalized)[1].lower()
        if ext not in _CODE_EXTENSIONS:
            return None

        # Skip cache/data/config paths
        for pattern in _SKIP_PATTERNS:
            if re.search(pattern, normalized):
                return None

        # Determine review level
        is_hard = any(re.search(p, normalized) for p in _HARD_PATH_PATTERNS)

        # Extract filename for readable message
        filename = os.path.basename(normalized)

        if is_hard:
            return HookOutput().system_message(
                f"[CODE-REVIEW: THOROUGH] You wrote/edited `{filename}` (production code).\n"
                "MANDATORY: Perform thorough self-review before moving on:\n"
                "- [ ] Logic correctness (conditions, loops, returns)\n"
                "- [ ] Edge cases (None, empty, 0, boundary values)\n"
                "- [ ] Security (injection, secrets, input validation)\n"
                "- [ ] Project patterns (async-first, provider pattern)\n"
                "- [ ] Error handling (no silent except)\n"
                "Output brief review summary (3-5 lines)."
            )

        return HookOutput().system_message(
            f"[CODE-REVIEW: BASIC] You wrote/edited `{filename}`.\n"
            "MANDATORY: Quick self-review before moving on:\n"
            "- [ ] Logic correct? Edge cases handled?\n"
            "- [ ] Naming consistent? No copy-paste errors?\n"
            "Output 1-2 line review confirmation."
        )


if __name__ == "__main__":
    CodeReviewEnforcer().run()
