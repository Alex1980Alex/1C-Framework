#!/usr/bin/env python3
"""
Hook: ralph-activator
Event: UserPromptSubmit
Matcher: (none — fires on every user prompt)
Purpose: Auto-activate Ralph Wiggum autonomous loop when detecting
         complex multi-step tasks (factory, research, phase, multi-step).
         Never activates for simple tasks (fix typo, git status, etc.).

         Detection uses negative-first approach:
         1. Check SIMPLE_SIGNALS → skip Ralph
         2. Check FACTORY/RESEARCH/PHASE/MULTI_STEP signals → activate

         Creates .ralph_active + .ralph_criteria.json for the stop hook.

Timeout: 5s
"""

import re
import sys
import os

# Core path resolution: find base/ + shared/ in user-level or project-level
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# Lazy-load FuzzyMatcher
_fuzzy_complex = None


def _get_fuzzy_complex():
    """Fuzzy matcher for complex-task verbs."""
    global _fuzzy_complex
    if _fuzzy_complex is None:
        try:
            from shared.fuzzy_match import FuzzyMatcher
            _fuzzy_complex = FuzzyMatcher(
                keywords=[
                    "исследовать", "проанализировать", "реализовать",
                    "автоматизировать", "интегрировать", "рефакторить",
                    "мигрировать", "оптимизировать",
                ],
                fuzzy_threshold=78,
            )
        except Exception:
            _fuzzy_complex = False
    return _fuzzy_complex if _fuzzy_complex is not False else None


class RalphActivator(BaseHook):
    """Auto-activate Ralph Wiggum for complex multi-step tasks."""

    # --- Tier 0: Simple task signals (NEVER activate Ralph) ---
    SIMPLE_SIGNALS = [
        "исправь", "поправь", "fix", "typo",
        "покажи", "прочитай", "открой", "выведи",
        "git status", "git log", "git diff", "git stash",
        "коммит", "commit", "push",
        "запусти", "run", "test", "тест",
        "удали строку", "переименуй", "замени слово",
        "одну строку", "add comment", "добавь комментарий",
        "что это", "where is", "как называется",
        "объясни", "расскажи",
    ]

    # --- Tier 2.5: Brainstorm signals (max 10 iterations) ---
    BRAINSTORM_SIGNALS = [
        "придумай", "предложи", "спроектируй",
        "какой подход выбрать", "давай обсудим",
        "предложи архитектуру", "предложи решение",
        "как лучше сделать", "какой вариант лучше",
        "как улучшить", "как оптимизировать",
    ]
    BRAINSTORM_CRITERIA = [
        "comparison table created",
        "recommendation given",
    ]
    BRAINSTORM_MAX = 10

    # --- Tier 2: Research signals (5-7 steps, max 8 iterations) ---
    RESEARCH_SIGNALS = [
        "исследуй", "сделай обзор", "проанализируй",
        "сравни подходы", "compare approaches",
        "best practices", "лучшие практики",
        "какие есть варианты", "what options",
        "overview of", "обзор по",
    ]
    RESEARCH_CRITERIA = ["cache saved", "_index.json updated"]
    RESEARCH_MAX = 8

    # --- Tier 3: Factory signals (6-8 steps, max 12 iterations) ---
    FACTORY_SIGNALS = [
        "новый хук", "new hook", "создай hook", "создай хук",
        "хук для", "hook for",
        "новый скилл", "new skill", "скилл для", "skill for",
        "mcp tool", "mcp сервер", "mcp server",
        "автоматизировать событие", "автоматизировать процесс",
        "нужен enforcer", "нужен guard",
        "триада", "triad", "фабрика", "factory",
        "новый домен", "new domain",
    ]
    FACTORY_CRITERIA = [
        "settings.json updated",
        "MEMORY.md updated",
        "test passed",
    ]
    FACTORY_MAX = 12

    # --- Tier 4: Phase/architecture signals (5-15 steps, max 15) ---
    PHASE_SIGNALS = [
        "новая фаза", "новую фазу", "new phase",
        "следующая фаза", "следующую фазу",
        "реализуй phase", "implement phase",
        "новый pipeline", "новый пайплайн",
        "новая стратегия", "новую стратегию",
        "новый агент", "нового агента",
        "новый провайдер", "нового провайдера",
        "новый loader", "новый обработчик",
        "расширить фреймворк", "extend framework",
        "новый компонент", "новый модуль",
    ]
    PHASE_CRITERIA = [
        "all files created",
        "tests pass",
        "MEMORY.md updated",
    ]
    PHASE_MAX = 15

    # --- Tier 5: Multi-step markers ---
    MULTI_STEP_PHRASES = [
        "а также", "и ещё", "and also", "additionally",
        "после этого", "затем", "потом", "then",
        "во-первых", "во-вторых",
    ]
    MULTI_STEP_MAX = 10

    # Regex for numbered lists: "1. ... 2. ... 3. ..."
    _NUMBERED_LIST_RE = re.compile(r"(?:^|\n)\s*\d+[.)]\s", re.MULTILINE)

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt) < 15:
            return None

        # Don't re-activate if already active (but auto-deactivate if stale)
        from shared.ralph_state import is_active, is_stale, deactivate
        if is_active():
            if is_stale():
                deactivate()  # Stale from crashed/timed-out session
            else:
                return None

        prompt_lower = prompt.lower()

        # --- Negative filter: simple tasks ---
        simple_score = sum(
            1 for kw in self.SIMPLE_SIGNALS if kw in prompt_lower
        )
        if simple_score >= 2:
            return None

        # --- Tier 3: Factory (highest priority after simple filter) ---
        factory_score = sum(
            1 for kw in self.FACTORY_SIGNALS if kw in prompt_lower
        )
        if factory_score >= 1:
            return self._activate(
                "factory", prompt, self.FACTORY_CRITERIA, self.FACTORY_MAX
            )

        # --- Tier 4: Phase/architecture ---
        phase_score = sum(
            1 for kw in self.PHASE_SIGNALS if kw in prompt_lower
        )
        if phase_score >= 1:
            return self._activate(
                "phase", prompt, self.PHASE_CRITERIA, self.PHASE_MAX
            )

        # --- Tier 2.5: Brainstorm ---
        brainstorm_score = sum(
            1 for kw in self.BRAINSTORM_SIGNALS if kw in prompt_lower
        )
        if brainstorm_score >= 1:
            return self._activate(
                "brainstorm", prompt,
                self.BRAINSTORM_CRITERIA, self.BRAINSTORM_MAX,
            )

        # --- Tier 2: Research ---
        research_score = sum(
            1 for kw in self.RESEARCH_SIGNALS if kw in prompt_lower
        )
        if research_score >= 1:
            return self._activate(
                "research", prompt, self.RESEARCH_CRITERIA, self.RESEARCH_MAX
            )

        # --- Tier 5: Multi-step (numbered lists, sequential markers) ---
        multi_score = sum(
            1 for kw in self.MULTI_STEP_PHRASES if kw in prompt_lower
        )
        numbered_items = len(self._NUMBERED_LIST_RE.findall(prompt))
        if numbered_items >= 3 or multi_score >= 2:
            return self._activate(
                "multi_step", prompt,
                ["all listed items completed"],
                self.MULTI_STEP_MAX,
            )

        # --- Fuzzy fallback for complex verbs ---
        fuzzy = _get_fuzzy_complex()
        if fuzzy is not None and fuzzy.match_count(prompt) >= 2:
            return self._activate(
                "multi_step", prompt,
                ["all tasks completed"],
                self.MULTI_STEP_MAX,
            )

        return None

    def _activate(
        self,
        task_type: str,
        prompt: str,
        criteria: list[str],
        max_iterations: int,
    ) -> HookOutput:
        """Activate Ralph mode and inject system message."""
        from shared.ralph_state import activate
        activate(task_type, prompt, criteria, max_iterations)

        criteria_text = "\n".join(f"  - {c}" for c in criteria)
        return HookOutput().system_message(
            f"[RALPH-ACTIVATED] Autonomous mode ON "
            f"(type={task_type}, max {max_iterations} iterations).\n"
            "\n"
            "Ralph Wiggum автономный цикл активирован.\n"
            "Claude НЕ остановится пока все критерии не выполнены:\n"
            f"{criteria_text}\n"
            "\n"
            "Когда ВСЕ критерии выполнены, включи маркер: RALPH_DONE\n"
            "Если задача невыполнима — тоже включи RALPH_DONE с объяснением."
        )


if __name__ == "__main__":
    RalphActivator().run()
