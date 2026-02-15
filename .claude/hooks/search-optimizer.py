#!/usr/bin/env python3
"""
Hook: search-optimizer
Event: PreToolUse
Matcher: Bash
Purpose: When Claude makes Bash calls to the search API (localhost:8000/search),
         suggest optimal parameters (strategy=hybrid, rerank=true, k=10).
         Does NOT block — only provides suggestions via systemMessage.
Timeout: 3s

Adapted from 1C-Enterprise_Framework multi-pipeline-blocker.py (advisory mode).
"""

import sys
import os

# Core path resolution: find base/ + shared/ in user-level or project-level
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


class SearchOptimizer(BaseHook):
    """Validate search API calls have optimal parameters."""

    SEARCH_ENDPOINTS = [
        "/search/ask",
        "/search/",
        "localhost:8000/search",
        "127.0.0.1:8000/search",
    ]

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Bash":
            return None

        command = inp.tool_input.get("command", "")
        if not command:
            return None

        # Check if this is a search API call
        is_search = any(ep in command for ep in self.SEARCH_ENDPOINTS)
        if not is_search:
            return None

        suggestions = []

        # Check strategy parameter
        if "strategy" not in command:
            suggestions.append(
                'strategy="hybrid" (не указана, по умолчанию может быть suboptimal)'
            )

        # Check rerank for /search/ask
        if "/search/ask" in command and "rerank" not in command:
            suggestions.append(
                "rerank=true (не указан, улучшает качество ответа)"
            )

        # Check k parameter
        if '"k"' not in command and "'k'" not in command and '"k":' not in command:
            suggestions.append(
                "k=10 (не указан, по умолчанию может вернуть мало результатов)"
            )

        if suggestions:
            msg = (
                "[SEARCH-OPTIMIZER] Обнаружен вызов Search API.\n"
                "Рекомендуемые параметры:\n"
                + "\n".join(f"  - {s}" for s in suggestions)
            )
            return HookOutput().system_message(msg)

        return None  # All parameters present, pass through


if __name__ == "__main__":
    SearchOptimizer().run()
