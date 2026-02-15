#!/usr/bin/env python3
"""
Hook: decision-to-triad
Event: UserPromptSubmit
Matcher: (none — fires on every user prompt)
Purpose: Detect IDEAS and DECISIONS in chat conversation and route them
         through the Factory (Triad) for artifact creation.

         Uses two detection layers:
         Layer A: Phrase matching (multi-word patterns like "давай сделаем")
         Layer B: Fuzzy single-word matching via pymorphy3 + rapidfuzz
                  (catches typos "удалть" and inflections "удалим")

Timeout: 5s
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

# Lazy-load FuzzyMatcher (heavy imports: pymorphy3, rapidfuzz)
_fuzzy_matcher = None


def _get_fuzzy_matcher():
    """Lazy-init fuzzy matcher with action verbs."""
    global _fuzzy_matcher
    if _fuzzy_matcher is None:
        try:
            from shared.fuzzy_match import FuzzyMatcher
            _fuzzy_matcher = FuzzyMatcher(
                keywords=[
                    # Action verbs (will match all inflections + typos)
                    "удалить", "создать", "добавить", "реализовать",
                    "автоматизировать", "внедрить", "убрать", "очистить",
                    "предотвратить", "блокировать", "развернуть",
                    "переименовать", "переместить", "заменить",
                ],
                fuzzy_threshold=78,
            )
        except Exception:
            _fuzzy_matcher = False  # Mark as failed, don't retry
    return _fuzzy_matcher if _fuzzy_matcher is not False else None


class DecisionToTriad(BaseHook):
    """Detect decisions/ideas in chat and route through Factory."""

    # --- Layer A: Multi-word phrase patterns (exact substring match) ---

    DECISION_PHRASES_RU = [
        "давай сделаем", "давай реализуем", "давай создадим",
        "давай добавим", "давай внедрим", "давай автоматизируем",
        "нужно создать", "нужно добавить", "нужно реализовать",
        "нужно автоматизировать", "нужно внедрить",
        "нужно удал", "нужно очист", "нужно убрать",
        "удалить автоматически", "удалять автоматически",
        "очистить автоматически",
        "решили что", "решено", "принято решение",
        "хочу чтобы", "хочу автоматизировать",
        "пусть срабатывает", "пусть автоматически",
        "создай новый", "добавь новый", "реализуй новый",
        "нужен новый", "создать новый",
        "должно быть", "должны быть", "должен быть",
        "всегда должно", "всегда должны",
        "чтобы не повторялось",
    ]

    DECISION_PHRASES_EN = [
        "let's create", "let's implement", "let's add",
        "let's build", "let's automate",
        "we need to create", "we need to add",
        "we should create", "we should add",
        "i want to automate", "i want to create",
        "create a new", "add a new", "implement a new",
    ]

    TRIAD_PHRASES = [
        "хук для", "hook for", "новый хук", "новый hook",
        "create hook", "создай hook", "создай хук",
        "скилл для", "skill for", "новый скилл", "новый skill",
        "новый домен", "новая область", "new domain",
        "mcp tool", "mcp сервер", "mcp server",
        "автоматизировать событие", "автоматизировать процесс",
        "кешировать", "добавить в кеш",
        "паттерн для", "добавь паттерн",
        "триада", "triad", "фабрика", "factory",
        "чтобы больше не", "чтобы не повтор", "не допускать",
    ]

    ARCHITECTURE_PHRASES = [
        "новая фаза", "новую фазу", "new phase",
        "следующая фаза", "следующую фазу",
        "новый pipeline", "новый пайплайн",
        "новая стратегия", "новую стратегию",
        "добавить стратегию", "создать стратегию",
        "новый агент", "нового агента",
        "новый обработчик", "новый loader",
        "новый провайдер", "нового провайдера",
        "расширить фреймворк", "extend framework",
        "новый компонент", "новый модуль",
    ]

    SKIP_KEYWORDS = [
        "исправь", "поправь", "fix", "typo",
        "замени", "удали строку", "переименуй",
        "покажи", "прочитай", "открой",
        "запусти", "run", "test", "тест",
        "git status", "git log", "git diff",
        "коммит", "commit", "push",
        # Brainstorm — handled by research-task-detector
        "придумай", "предложи варианты",
        "давай обсудим варианты", "какой подход выбрать",
    ]

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt) < 10:
            return None

        prompt_lower = prompt.lower()

        # Skip routine/small tasks
        skip_score = sum(1 for kw in self.SKIP_KEYWORDS if kw in prompt_lower)
        if skip_score >= 2:
            return None

        # --- Layer A: Phrase matching (multi-word patterns) ---
        triad_score = sum(1 for kw in self.TRIAD_PHRASES if kw in prompt_lower)
        if triad_score >= 1:
            return self._factory_message(
                "TRIAD-COMPONENT-DETECTED",
                "Обнаружен запрос на создание компонента триады "
                "(hook / skill / MCP / домен).",
            )

        decision_score = sum(
            1 for kw in self.DECISION_PHRASES_RU if kw in prompt_lower
        ) + sum(
            1 for kw in self.DECISION_PHRASES_EN if kw in prompt_lower
        )

        arch_score = sum(
            1 for kw in self.ARCHITECTURE_PHRASES if kw in prompt_lower
        )

        # --- Layer B: Fuzzy single-word matching (typos + inflections) ---
        fuzzy_score = 0
        matcher = _get_fuzzy_matcher()
        if matcher is not None:
            fuzzy_matches = matcher.match_prompt(prompt)
            fuzzy_score = len(fuzzy_matches)
            # Fuzzy matches count as decision intent
            decision_score += fuzzy_score

        # --- Scoring logic ---
        if decision_score >= 1 and arch_score >= 1:
            return self._factory_message(
                "ARCHITECTURE-DECISION",
                "Обнаружено архитектурное решение "
                "(новый компонент / фаза / стратегия).",
            )

        if decision_score >= 2:
            return self._factory_message(
                "DECISION-DETECTED",
                "Обнаружена идея / решение в чате.",
            )

        if arch_score >= 2:
            return self._factory_message(
                "ARCHITECTURE-IDEA",
                "Обнаружена архитектурная идея.",
            )

        return None

    def _factory_message(self, tag: str, description: str) -> HookOutput:
        """Generate systemMessage routing to the Factory process."""
        return HookOutput().system_message(
            f"[{tag}] {description}\n"
            "\n"
            "Прогони через ФАБРИКУ ТРИАДЫ (skill `triad-factory`):\n"
            "\n"
            "ШАГ 1 — КЛАССИФИКАЦИЯ (5 вопросов):\n"
            "  Q1: Должно срабатывать АВТОМАТИЧЕСКИ на событие? → Hook\n"
            "  Q2: Есть ПРОЦЕДУРА/ЗНАНИЕ для описания? → Skill\n"
            "  Q3: Нужен ВНЕШНИЙ ИНСТРУМЕНТ (API, DB)? → MCP Tool\n"
            "  Q4: Нужно НАКАПЛИВАТЬ знания? → Cache\n"
            "  Q5: Нужно ПРИНУДИТЕЛЬНО выполнять? → Enforcer\n"
            "\n"
            "ШАГ 2 — ФОРМУЛА: определи комбинацию (Hook + Skill + MCP + ...)\n"
            "ШАГ 3 — ГЕНЕРАЦИЯ: создай артефакты по шаблонам\n"
            "ШАГ 4 — СВЯЗЫВАНИЕ: settings.json, _index.json, MEMORY.md\n"
            "ШАГ 5 — ВЕРИФИКАЦИЯ: тест каждого компонента\n"
            "\n"
            "ВАЖНО: Решение из чата ДОЛЖНО стать артефактом. "
            "Иначе — потеряно."
        )


if __name__ == "__main__":
    DecisionToTriad().run()
