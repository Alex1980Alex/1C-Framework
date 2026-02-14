#!/usr/bin/env python3
"""
Hook: decision-to-triad
Event: UserPromptSubmit
Matcher: (none — fires on every user prompt)
Purpose: Detect IDEAS and DECISIONS in chat conversation and route them
         through the Factory (Triad) for artifact creation.

         This is the META-HOOK — it catches the conversation itself as an event.
         When user discusses an idea ("давай сделаем", "нужно создать"),
         this hook injects the Factory process (Q1-Q5 classification)
         so the decision becomes an artifact, not just a chat message.

         Different from research-task-detector.py which catches QUESTIONS
         ("что такое", "как работает"). This hook catches ACTION/DECISION intent.

Timeout: 5s
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput


class DecisionToTriad(BaseHook):
    """Detect decisions/ideas in chat and route through Factory."""

    # --- Decision/action intent keywords (Russian) ---
    DECISION_KEYWORDS_RU = [
        "давай сделаем", "давай реализуем", "давай создадим",
        "давай добавим", "давай внедрим", "давай автоматизируем",
        "нужно создать", "нужно добавить", "нужно реализовать",
        "нужно автоматизировать", "нужно внедрить",
        "решили что", "решено", "принято решение",
        "хочу чтобы", "хочу автоматизировать",
        "пусть срабатывает", "пусть автоматически",
        "создай новый", "добавь новый", "реализуй новый",
        "нужен новый", "создать новый",
    ]

    # --- Decision/action intent keywords (English) ---
    DECISION_KEYWORDS_EN = [
        "let's create", "let's implement", "let's add",
        "let's build", "let's automate",
        "we need to create", "we need to add",
        "we should create", "we should add",
        "i want to automate", "i want to create",
        "create a new", "add a new", "implement a new",
    ]

    # --- Triad-specific terms (strong signal for Factory routing) ---
    TRIAD_TERMS = [
        "хук для", "hook for", "новый хук", "новый hook",
        "create hook", "создай hook", "создай хук",
        "скилл для", "skill for", "новый скилл", "новый skill",
        "новый домен", "новая область", "new domain",
        "mcp tool", "mcp сервер", "mcp server",
        "автоматизировать событие", "автоматизировать процесс",
        "кешировать", "добавить в кеш",
        "паттерн для", "добавь паттерн",
        "триада", "triad", "фабрика", "factory",
    ]

    # --- Architecture/design terms (signal for Factory) ---
    # Include inflected forms (accusative/genitive) for Russian
    ARCHITECTURE_TERMS = [
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

    # --- Skip small/routine tasks (no Factory needed) ---
    SKIP_KEYWORDS = [
        "исправь", "поправь", "fix", "typo",
        "замени", "удали строку", "переименуй",
        "покажи", "прочитай", "открой",
        "запусти", "run", "test", "тест",
        "git status", "git log", "git diff",
        "коммит", "commit", "push",
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

        # --- Strong signal: triad-specific terms ---
        triad_score = sum(1 for kw in self.TRIAD_TERMS if kw in prompt_lower)
        if triad_score >= 1:
            return self._factory_message(
                "TRIAD-COMPONENT-DETECTED",
                "Обнаружен запрос на создание компонента триады "
                "(hook / skill / MCP / домен).",
            )

        # --- Score decision intent ---
        decision_score_ru = sum(
            1 for kw in self.DECISION_KEYWORDS_RU if kw in prompt_lower
        )
        decision_score_en = sum(
            1 for kw in self.DECISION_KEYWORDS_EN if kw in prompt_lower
        )
        decision_score = decision_score_ru + decision_score_en

        arch_score = sum(
            1 for kw in self.ARCHITECTURE_TERMS if kw in prompt_lower
        )

        # --- Strong decision + architecture = full Factory ---
        if decision_score >= 1 and arch_score >= 1:
            return self._factory_message(
                "ARCHITECTURE-DECISION",
                "Обнаружено архитектурное решение "
                "(новый компонент / фаза / стратегия).",
            )

        # --- Decision intent alone (2+ keywords = confident) ---
        if decision_score >= 2:
            return self._factory_message(
                "DECISION-DETECTED",
                "Обнаружена идея / решение в чате.",
            )

        # --- Architecture terms alone (2+ = confident) ---
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
            "Прогони через ФАБРИКУ ТРИАДЫ (skill `hooks-skills-mcp-triad`):\n"
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
