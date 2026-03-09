#!/usr/bin/env python3
"""
Hook: z-ai-delegation-enforcer
Event: UserPromptSubmit
Matcher: (none - fires on every user prompt)
Purpose: Detects tasks delegatable to Z.AI via LLM Rotation,
         reminds to use delegation protocol for token economy.
Timeout: 3s
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# --- Delegation signal keywords ---

# Medium: docs, decomposition, tests, boilerplate
_MEDIUM_SIGNALS = [
    "documentation", "readme", "changelog",
    "decompos", "split into", "break down",
    "generate tests", "test cases", "write tests",
    "boilerplate", "template",
    # Russian
    "разбей", "декомпозиция", "разбить на",
    "сгенерируй", "напиши тесты", "создай тесты",
    "напиши readme", "changelog",
    "по шаблону", "бойлерплейт",
    "максимальн", "подробн",
]

# Hard: code generation, refactoring, analysis
_HARD_SIGNALS = [
    "write code", "implement", "create module",
    "refactor", "rewrite",
    "analysis report", "generate report",
    # Russian
    "напиши код", "реализуй", "создай модуль",
    "рефакторинг", "перепиши",
    "аналитический отчёт", "сгенерируй отчёт",
    "написать функцию", "написать класс",
]

# Never: architecture, security, debugging (skip delegation)
_NEVER_SIGNALS = [
    "architecture", "how to design", "security",
    "debug", "investigate", "why does",
    # Russian
    "архитектур", "как лучше сделать", "безопасност",
    "отладка", "отладить", "почему не работает",
    "расследовать", "причина ошибки",
]

# Min prompt length to consider (skip short prompts)
_MIN_PROMPT_LEN = 40


class ZAIDelegationEnforcer(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt.strip()
        if not prompt or len(prompt) < _MIN_PROMPT_LEN:
            return None

        prompt_lower = prompt.lower()

        # Never delegate - skip silently
        never_score = sum(1 for s in _NEVER_SIGNALS if s in prompt_lower)
        if never_score >= 1:
            return None

        # Hard signals
        hard_score = sum(1 for s in _HARD_SIGNALS if s in prompt_lower)
        if hard_score >= 1:
            return HookOutput().system_message(
                "[Z.AI DELEGATION: HARD] This task can be delegated to Z.AI.\n"
                "Protocol: Z.AI generates draft -> Opus THOROUGH review (mandatory).\n"
                "Use: mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)\n"
                "Review checklist: accuracy + completeness + format + logic + edge cases + security.\n"
                "If >50% rewrite needed -> do it yourself (Opus).\n"
                "Full protocol: Skill('z-ai-delegation')"
            )

        # Medium signals
        medium_score = sum(1 for s in _MEDIUM_SIGNALS if s in prompt_lower)
        if medium_score >= 2:
            return HookOutput().system_message(
                "[Z.AI DELEGATION: MEDIUM] This task should be delegated to Z.AI.\n"
                "Protocol: Z.AI generates draft -> Opus review (mandatory).\n"
                "Use: mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)\n"
                "Review checklist: accuracy + completeness + format.\n"
                "Full protocol: Skill('z-ai-delegation')"
            )

        return None


if __name__ == "__main__":
    ZAIDelegationEnforcer().run()
