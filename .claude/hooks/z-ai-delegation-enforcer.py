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

# Orchestrator: complex tasks needing decompose + batch delegate
_ORCHESTRATOR_SIGNALS = [
    "each file", "for every", "per file", "all files",
    "batch", "multiple files", "several files",
    # Russian
    "каждый файл", "для каждого", "все файлы",
    "пакетно", "несколько файлов", "по файлам",
    "каждая фаза", "каждый модуль",
]

# Medium: docs, decomposition, tests, boilerplate, configs
_MEDIUM_SIGNALS = [
    "documentation", "readme", "changelog",
    "decompos", "split into", "break down",
    "generate tests", "test cases", "write tests",
    "boilerplate", "template", "scaffold",
    "config", "setup", "migration script",
    "checklist", "summary", "table",
    "roadmap", "plan document",
    # Russian
    "разбей", "декомпозиция", "разбить на",
    "дорожн", "план реализаци", "план фаз",
    "создай документ", "напиши документ",
    "сгенерируй", "напиши тесты", "создай тесты",
    "напиши readme", "changelog",
    "по шаблону", "бойлерплейт",
    "максимальн", "подробн",
    "конфиг", "настрой", "миграц",
    "чеклист", "таблиц", "сводк",
    "добавь", "создай файл",
]

# Hard: code generation, refactoring, analysis
_HARD_SIGNALS = [
    "write code", "implement", "create module",
    "refactor", "rewrite", "add feature",
    "analysis report", "generate report",
    "new class", "new function", "new hook",
    "write service", "write handler",
    # Russian
    "напиши код", "реализуй", "создай модуль",
    "рефакторинг", "перепиши",
    "аналитический отчёт", "сгенерируй отчёт",
    "написать функцию", "написать класс",
    "новый класс", "новый хук", "новый сервис",
    "добавь функционал", "добавь фичу",
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

# Numeric patterns: "10 files", "5 modules", etc.
import re
_MULTI_FILE_RE = re.compile(r"\b([3-9]|[1-9]\d+)\s*(файл|file|модул|module|фаз|phase|часте|part)", re.IGNORECASE)

# Min prompt length to consider (skip short prompts)
_MIN_PROMPT_LEN = 20


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

        # Orchestrator mode: 3+ files or batch signals
        orchestrator_score = sum(1 for s in _ORCHESTRATOR_SIGNALS if s in prompt_lower)
        has_multi_file = bool(_MULTI_FILE_RE.search(prompt))
        medium_score = sum(1 for s in _MEDIUM_SIGNALS if s in prompt_lower)
        hard_score = sum(1 for s in _HARD_SIGNALS if s in prompt_lower)

        if orchestrator_score >= 1 or has_multi_file:
            level = "HARD" if hard_score >= 1 else "MEDIUM"
            return HookOutput().system_message(
                f"[Z.AI DELEGATION: ORCHESTRATOR ({level})] Complex task detected (3+ outputs).\n"
                "Protocol: DECOMPOSE -> PREPARE prompts -> DELEGATE to Z.AI -> REVIEW -> ASSEMBLE.\n"
                "Steps:\n"
                "1. Opus: decompose into subtasks, classify each (Soft/Medium/Hard/Never)\n"
                "2. Opus: build prompt per subtask (task+context+format+constraints)\n"
                "3. Z.AI: mcp__llm-rotation__llm_complete() per subtask\n"
                "4. Opus: review each result, fix inline\n"
                "5. Opus: assemble + Write() final files\n"
                "Full protocol: Skill('z-ai-delegation')"
            )

        # Hard signals (single task)
        if hard_score >= 1:
            return HookOutput().system_message(
                "[Z.AI DELEGATION: HARD] This task can be delegated to Z.AI.\n"
                "Protocol: Z.AI generates draft -> Opus THOROUGH review (mandatory).\n"
                "Use: mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)\n"
                "Review checklist: accuracy + completeness + format + logic + edge cases + security.\n"
                "If >50% rewrite needed -> do it yourself (Opus).\n"
                "Full protocol: Skill('z-ai-delegation')"
            )

        # Medium signals (single task) — threshold 1 for maximum delegation
        if medium_score >= 1:
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
