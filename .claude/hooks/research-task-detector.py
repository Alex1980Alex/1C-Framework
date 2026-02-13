#!/usr/bin/env python3
"""
Hook: research-task-detector
Event: UserPromptSubmit
Matcher: (none — fires on every user prompt)
Purpose: Detect research questions and route to domain-specific skills:
         - 1C questions -> 1c-doc-research skill
         - Tech/RAG/ML questions -> tech-research skill
         - PDF indexing -> pdf-knowledge skill
         Skip small tasks (typo fixes, single-line changes).
Timeout: 5s

Adapted from 1C-Enterprise_Framework 1c-task-detector.py.
"""

import sys
import os

# Add hooks directory to path for base/ and shared/ imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput


class ResearchTaskDetector(BaseHook):
    """Detect research questions and route to appropriate skills."""

    # --- Research question keywords (Russian) ---
    RESEARCH_KEYWORDS_RU = [
        "расскажи про", "как работает", "что такое",
        "документация по", "объясни", "найди информацию",
        "исследуй", "сделай обзор", "проанализируй", "сравни",
        "best practices", "лучшие практики",
        "как устроен", "для чего нужен", "зачем нужен",
        "как создать", "как настроить",
    ]

    # --- Research question keywords (English) ---
    RESEARCH_KEYWORDS_EN = [
        "how does", "what is", "explain",
        "research", "compare", "overview of",
        "documentation for", "describe", "tell me about",
    ]

    # --- 1C-specific terms (strong research signal) ---
    C1_TERMS = [
        "справочник", "документ", "регистр",
        "перечисление", "обработка", "отчет", "отчёт",
        "план видов", "bsl", "1с", "1c",
        "конфигурация", "конфигуратор", "платформа",
        "табличная часть", "реквизит", "форма",
        "подсистема", "модуль", "проведение",
        "ws-ссылк", "web-сервис", "http-сервис",
        "регламентное задание", "общий модуль",
    ]

    # --- PDF / indexing keywords ---
    PDF_KEYWORDS = [
        "проиндексируй", "загрузи pdf", "индексация",
        "index pdf", "reindex", "переиндексируй",
        "загрузи документ", "добавь в индекс",
    ]

    # --- Tech/RAG/ML terms (route to tech-research) ---
    TECH_TERMS = [
        "rag", "embeddings", "embedding", "vector search", "vector db",
        "reranking", "reranker", "chunking", "bm25", "sparse vector",
        "langchain", "langgraph", "qdrant", "chromadb", "faiss",
        "sentence-transformers", "colbert", "raptor", "hyde",
        "hybrid search", "semantic search", "knowledge graph",
        "graphrag", "mcp", "tool use", "agent",
        "llm", "claude api", "anthropic", "openai",
        "onnx", "openvino", "transformer",
        "fastapi", "pydantic", "asyncio",
        "tokenizer", "fine-tuning", "few-shot",
        "retrieval", "generation", "pipeline",
    ]

    # --- Small task detection (skip routing) ---
    SMALL_TASK_KEYWORDS = [
        "исправь", "поправь", "замени слово",
        "добавь комментарий", "fix typo", "fix line",
        "одну строку", "переименуй", "удали строку",
    ]

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt) < 5:
            return None

        prompt_lower = prompt.lower()

        # Skip small tasks
        small_score = sum(1 for kw in self.SMALL_TASK_KEYWORDS if kw in prompt_lower)
        if small_score >= 2:
            return None

        # --- Detect PDF indexing ---
        pdf_score = sum(1 for kw in self.PDF_KEYWORDS if kw in prompt_lower)
        if pdf_score >= 1:
            return HookOutput().system_message(
                "[PDF-TASK-DETECTED] Обнаружена задача работы с PDF.\n"
                "Используй skill `pdf-knowledge` для MCP-инструментов.\n"
                "Доступные инструменты: index_pdf, search_documents, "
                "ask_question, graph_query, analyze, research."
            )

        # --- Score domains ---
        research_score = sum(
            1 for kw in self.RESEARCH_KEYWORDS_RU if kw in prompt_lower
        )
        research_score += sum(
            1 for kw in self.RESEARCH_KEYWORDS_EN if kw in prompt_lower
        )
        c1_score = sum(1 for kw in self.C1_TERMS if kw in prompt_lower)
        tech_score = sum(1 for kw in self.TECH_TERMS if kw in prompt_lower)

        # --- Route: 1C domain (research + 1C terms) ---
        if research_score >= 1 and c1_score >= 1:
            return HookOutput().system_message(
                "[1C-RESEARCH-DETECTED] Обнаружен вопрос по платформе 1С.\n"
                "ОБЯЗАТЕЛЬНО используй skill `1c-doc-research` — "
                "приоритет документации 1С:Предприятие 8.3.27.\n"
                "Фаза 0: проверь кеш "
                "(.claude/skills/1c-doc-research/cache/_index.json)\n"
                "Фаза 1: POST http://127.0.0.1:8000/search/ask "
                "strategy=hybrid k=10 rerank=true\n"
                "Фаза 5: ОБЯЗАТЕЛЬНО сохрани результат в кеш."
            )

        # --- Route: Tech domain (research + tech terms) ---
        if research_score >= 1 and tech_score >= 1:
            return HookOutput().system_message(
                "[TECH-RESEARCH-DETECTED] Обнаружен вопрос по технологиям "
                "RAG/ML/Python.\n"
                "Используй skill `tech-research` — "
                "приоритет official documentation.\n"
                "Фаза 0: проверь кеш "
                "(.claude/skills/tech-research/cache/_index.json)\n"
                "Фаза 1: WebSearch по official docs библиотеки\n"
                "Фаза 5: ОБЯЗАТЕЛЬНО сохрани результат в кеш."
            )

        # --- Route: Tech without research keyword (direct mention) ---
        if tech_score >= 2:
            return HookOutput().system_message(
                "[TECH-DETECTED] Обнаружены технические термины "
                "(RAG/ML/Python).\n"
                "При необходимости исследования используй skill "
                "`tech-research`.\n"
                "Кеш: .claude/skills/tech-research/cache/_index.json"
            )

        # --- Route: Generic research (2+ keywords, no domain) ---
        if research_score >= 2:
            return HookOutput().system_message(
                "[RESEARCH-DETECTED] Обнаружен исследовательский вопрос.\n"
                "Определи домен и используй соответствующий skill:\n"
                "- 1С-платформа → `1c-doc-research`\n"
                "- RAG/ML/Python → `tech-research`\n"
                "Начни с проверки кеша соответствующего skill."
            )

        return None  # Pass through


if __name__ == "__main__":
    ResearchTaskDetector().run()
