#!/usr/bin/env python3
"""
Hook: knowledge-cache-reminder
Event: PostToolUse
Matcher: WebSearch|WebFetch
Purpose: After web search/fetch, remind Claude to save research findings
         to the appropriate knowledge cache:
         - 1C results -> 1c-doc-research/cache/ (Phase 5)
         - Tech results -> tech-research/cache/ (Phase 5)
         Creates mandatory task in hook-todos.json.
Timeout: 5s

Adapted from 1C-Enterprise_Framework documentation-blocker.py.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.task_master import add_task, has_recent_completion, get_pending_tasks

HOOK_ID = "knowledge-cache-reminder-hook"


class KnowledgeCacheReminder(BaseHook):
    """Remind to cache research findings after web searches."""

    # Signals that 1C/documentation research was performed
    C1_SIGNALS = [
        "1с", "1c", "платформа", "конфигуратор",
        "справочник", "документ", "регистр",
        "перечисление", "обработка", "модуль",
        "табличная часть", "реквизит", "проведение",
        "its.1c.ru", "infostart.ru", "bsl",
    ]

    # Signals that tech/RAG/ML research was performed
    TECH_SIGNALS = [
        "rag", "retrieval", "embedding", "vector",
        "reranking", "reranker", "chunking", "bm25",
        "langchain", "langgraph", "qdrant", "chromadb",
        "sentence-transformers", "colbert", "faiss",
        "transformer", "llm", "claude", "anthropic",
        "huggingface", "arxiv", "benchmark",
        "fastapi", "pydantic", "pip install",
        "github.com", "readthedocs", "pypi.org",
    ]

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_name = inp.tool_name
        tool_result = inp.tool_result

        # Only process WebSearch and WebFetch results
        if tool_name not in ("WebSearch", "WebFetch"):
            return None

        # Ignore empty or very short results
        if not tool_result or len(str(tool_result)) < 200:
            return None

        # Cooldown: don't spam if we just completed a cache task
        if has_recent_completion(HOOK_ID, cooldown_minutes=10):
            return None

        result_lower = str(tool_result).lower()

        # Score both domains
        c1_score = sum(1 for s in self.C1_SIGNALS if s in result_lower)
        tech_score = sum(1 for s in self.TECH_SIGNALS if s in result_lower)

        # --- 1C research (priority — domain-specific) ---
        if c1_score >= 2:
            pending = get_pending_tasks(created_by=HOOK_ID)
            if not pending:
                add_task(
                    title="Сохранить результаты исследования в кеш знаний (1С)",
                    description=(
                        "Фаза 5 skill 1c-doc-research: создать topic-файл в "
                        ".claude/skills/1c-doc-research/cache/<тема>.md "
                        "и обновить _index.json"
                    ),
                    priority="high",
                    created_by=HOOK_ID,
                )

            return HookOutput().system_message(
                "[CACHE-REMINDER] Обнаружены результаты исследования "
                "по 1С/документации.\n"
                "ОБЯЗАТЕЛЬНО выполни Фазу 5 skill `1c-doc-research`:\n"
                "1. Создай topic-файл в "
                ".claude/skills/1c-doc-research/cache/<тема>.md\n"
                "2. Заполни по шаблону cache/_topic_template.md "
                "(8 категорий знаний)\n"
                "3. Обнови _index.json (keywords, last_verified)"
            )

        # --- Tech research ---
        if tech_score >= 2:
            pending = get_pending_tasks(created_by=HOOK_ID)
            if not pending:
                add_task(
                    title="Сохранить результаты исследования в кеш знаний (Tech)",
                    description=(
                        "Фаза 5 skill tech-research: создать topic-файл в "
                        ".claude/skills/tech-research/cache/<тема>.md "
                        "и обновить _index.json"
                    ),
                    priority="high",
                    created_by=HOOK_ID,
                )

            return HookOutput().system_message(
                "[CACHE-REMINDER] Обнаружены результаты исследования "
                "по технологиям RAG/ML/Python.\n"
                "ОБЯЗАТЕЛЬНО выполни Фазу 5 skill `tech-research`:\n"
                "1. Создай topic-файл в "
                ".claude/skills/tech-research/cache/<тема>.md\n"
                "2. Заполни по шаблону cache/_topic_template.md "
                "(7 категорий знаний)\n"
                "3. Обнови _index.json (keywords, domain, last_verified)"
            )

        # Light hint for borderline cases
        total_score = c1_score + tech_score
        if total_score >= 1 or len(str(tool_result)) > 1000:
            return HookOutput().system_message(
                "[CACHE-HINT] Найдена информация через "
                f"{tool_name}.\n"
                "Если это полезное знание — рассмотри сохранение в кеш:\n"
                "- 1С → 1c-doc-research/cache/\n"
                "- Tech → tech-research/cache/"
            )

        return None


if __name__ == "__main__":
    KnowledgeCacheReminder().run()
