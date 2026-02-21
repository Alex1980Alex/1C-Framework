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
# Core path resolution: find base/ + shared/ in user-level or project-level
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# Lazy-load FuzzyMatcher (heavy imports: pymorphy3, rapidfuzz)
_fuzzy_research = None
_fuzzy_arch = None


def _get_fuzzy_research():
    """Fuzzy matcher for research verbs."""
    global _fuzzy_research
    if _fuzzy_research is None:
        try:
            from shared.fuzzy_match import FuzzyMatcher
            _fuzzy_research = FuzzyMatcher(
                keywords=[
                    "улучшить", "оптимизировать", "ускорить",
                    "исправить", "решить", "обойти",
                    "исследовать", "проанализировать", "сравнить",
                    "объяснить", "описать", "настроить",
                ],
                fuzzy_threshold=78,
            )
        except Exception:
            _fuzzy_research = False
    return _fuzzy_research if _fuzzy_research is not False else None


def _get_fuzzy_arch():
    """Fuzzy matcher for architecture verbs."""
    global _fuzzy_arch
    if _fuzzy_arch is None:
        try:
            from shared.fuzzy_match import FuzzyMatcher
            _fuzzy_arch = FuzzyMatcher(
                keywords=[
                    "улучшить", "оптимизировать", "ускорить",
                    "рефакторить", "масштабировать", "расширить",
                ],
                fuzzy_threshold=78,
            )
        except Exception:
            _fuzzy_arch = False
    return _fuzzy_arch if _fuzzy_arch is not False else None


_fuzzy_brainstorm = None


def _get_fuzzy_brainstorm():
    """Fuzzy matcher for brainstorm verbs."""
    global _fuzzy_brainstorm
    if _fuzzy_brainstorm is None:
        try:
            from shared.fuzzy_match import FuzzyMatcher
            _fuzzy_brainstorm = FuzzyMatcher(
                keywords=[
                    "придумать", "предложить", "спроектировать",
                    "разработать", "выбрать", "обсудить",
                ],
                fuzzy_threshold=78,
            )
        except Exception:
            _fuzzy_brainstorm = False
    return _fuzzy_brainstorm if _fuzzy_brainstorm is not False else None


_SUBAGENT_CACHE_WARNING = (
    "\n\n"
    "⚠ ВАЖНО: PostToolUse hooks НЕ видят tool calls внутри Task-субагентов.\n"
    "Если WebSearch/WebFetch делегирован субагенту — knowledge-cache-reminder "
    "НЕ сработает.\n"
    "После завершения субагентов — ОБЯЗАТЕЛЬНО выполни Фазу 5 "
    "(сохранение в кеш) ВРУЧНУЮ:\n"
    "1. Создай topic-файл в cache/<тема>.md по шаблону _topic_template.md\n"
    "2. Обнови _index.json (keywords, domain, last_verified)"
)


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
        "почему не работает", "в чём проблема",
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

    # --- Architecture discussion terms (route to architecture-research) ---
    ARCHITECTURE_TERMS = [
        "архитектурное решение", "архитектурный подход",
        "как лучше сделать", "как лучше реализовать",
        "какой подход", "выбор подхода", "выбор архитектуры",
        "предлагаю реализовать", "предлагаю добавить",
        "новый функционал", "добавить функционал",
        "как реализовать", "давай обсудим",
        "best practices", "лучшие практики",
        "сравни подходы", "какие есть варианты",
        "оптимальный способ", "правильный подход",
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

    # --- Brainstorm signals (generate new ideas, not find existing) ---
    BRAINSTORM_KEYWORDS_RU = [
        "придумай", "предложи", "спроектируй", "разработай",
        "какой подход выбрать", "как лучше сделать",
        "какой вариант лучше", "давай обсудим варианты",
        "давай подумаем", "что думаешь о",
        "как бы ты", "нестандартный подход",
        "предложи архитектуру", "предложи решение",
    ]

    BRAINSTORM_KEYWORDS_EN = [
        "suggest", "design", "propose", "come up with",
        "which approach", "what's the best way",
        "how should we", "let's discuss",
        "alternative approach", "creative solution",
    ]

    # --- Hybrid signals (research + brainstorm combined) ---
    HYBRID_KEYWORDS = [
        "исследуй и предложи", "найди подходы и выбери",
        "найди и предложи", "сравни подходы и выбери",
        "как улучшить", "как оптимизировать", "как ускорить",
        "как исправить", "как решить", "как обойти",
        "можно ли улучшить", "можно ли оптимизировать",
        "как сделать лучше", "что можно улучшить",
        "слабые места", "узкое место",
        "research and suggest", "find and propose",
        "compare and choose",
    ]

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt) < 5:
            return None

        # TIER 2A: Skip IDE events (VS Code metadata, not user intent)
        prompt_stripped = prompt.strip()
        if prompt_stripped.startswith(("<ide_", "<ide_opened_file", "<ide_selection")):
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
        # Layer A: Phrase matching
        research_score = sum(
            1 for kw in self.RESEARCH_KEYWORDS_RU if kw in prompt_lower
        )
        research_score += sum(
            1 for kw in self.RESEARCH_KEYWORDS_EN if kw in prompt_lower
        )
        c1_score = sum(1 for kw in self.C1_TERMS if kw in prompt_lower)
        tech_score = sum(1 for kw in self.TECH_TERMS if kw in prompt_lower)
        arch_score = sum(
            1 for kw in self.ARCHITECTURE_TERMS if kw in prompt_lower
        )

        # Score brainstorm and hybrid
        brainstorm_score = sum(
            1 for kw in self.BRAINSTORM_KEYWORDS_RU if kw in prompt_lower
        )
        brainstorm_score += sum(
            1 for kw in self.BRAINSTORM_KEYWORDS_EN if kw in prompt_lower
        )
        hybrid_score = sum(
            1 for kw in self.HYBRID_KEYWORDS if kw in prompt_lower
        )

        # Layer B: Fuzzy single-word matching (typos + inflections)
        fuzzy_r = _get_fuzzy_research()
        if fuzzy_r is not None:
            research_score += fuzzy_r.match_count(prompt)
        fuzzy_a = _get_fuzzy_arch()
        if fuzzy_a is not None:
            arch_score += fuzzy_a.match_count(prompt)
        fuzzy_b = _get_fuzzy_brainstorm()
        if fuzzy_b is not None:
            brainstorm_score += fuzzy_b.match_count(prompt)

        # --- Route: Hybrid (explicit markers, highest priority) ---
        if hybrid_score >= 1:
            domain = self._detect_domain(c1_score, tech_score, arch_score)
            return HookOutput().system_message(
                "[HYBRID-TASK-DETECTED] Задача типа Hybrid "
                "(исследование + генерация).\n"
                "Используй skill `task-evaluation` — Hybrid Workflow:\n"
                f"ЧАСТЬ 1 (Research): skill `{domain}` — фазы 0-5\n"
                "ЧАСТЬ 2 (Brainstorm): skill `task-evaluation` — фазы 1-5\n"
                "  Фаза 1: Формулировка проблемы\n"
                "  Фаза 2: Генерация 3-5 подходов\n"
                "  Фаза 3: Evaluation matrix (таблица сравнения)\n"
                "  Фаза 4: Рекомендация с обоснованием\n"
                "  Фаза 5: Сохранить решение как ADR"
                + _SUBAGENT_CACHE_WARNING
            )

        # --- Route: Pure Brainstorm (no research needed) ---
        if brainstorm_score >= 1 and research_score == 0:
            return HookOutput().system_message(
                "[BRAINSTORM-DETECTED] Задача на генерацию идей.\n"
                "Используй skill `task-evaluation` — Brainstorm Workflow:\n"
                "Фаза 1: Формулировка проблемы "
                "(что решаем, критерии, ограничения)\n"
                "Фаза 2: Генерация 3-5 подходов (разные философии!)\n"
                "Фаза 3: Evaluation matrix "
                "(Подход | Pros | Cons | Риск | Трудозатраты)\n"
                "Фаза 4: Рекомендация с обоснованием\n"
                "Фаза 5: Сохранить решение в "
                "architecture-research/adr/"
            )

        # --- Route: Brainstorm + Research signals = Hybrid ---
        if brainstorm_score >= 1 and research_score >= 1:
            domain = self._detect_domain(c1_score, tech_score, arch_score)
            return HookOutput().system_message(
                "[HYBRID-TASK-DETECTED] Обнаружены сигналы "
                "research + brainstorm.\n"
                "Используй skill `task-evaluation` — Hybrid Workflow:\n"
                f"ЧАСТЬ 1 (Research): skill `{domain}` — фазы 0-5\n"
                "ЧАСТЬ 2 (Brainstorm): task-evaluation — фазы 1-5"
                + _SUBAGENT_CACHE_WARNING
            )

        # --- Route: Architecture discussion ---
        if arch_score >= 1 and (research_score >= 1 or tech_score >= 1):
            return HookOutput().system_message(
                "[ARCHITECTURE-RESEARCH-DETECTED] Обнаружено обсуждение "
                "архитектуры / нового функционала.\n"
                "ОБЯЗАТЕЛЬНО используй skill `architecture-research`:\n"
                "Фаза 0: проверь кеш "
                "(.claude/skills/architecture-research/cache/_index.json)\n"
                "Фаза 1: ОБЯЗАТЕЛЬНО проверь docs/documentation/ — "
                "Glob + Read по теме\n"
                "Фаза 2: WebSearch best practices + GitHub repos\n"
                "Фаза 3: Синтез — предложение с обоснованием\n"
                "Фаза 4: Атрибуция: [docs], [web], [exp]\n"
                "Фаза 5: Сохрани в кеш "
                "architecture-research/cache/<тема>.md"
                + _SUBAGENT_CACHE_WARNING
            )

        # Architecture alone (2+ keywords = confident)
        if arch_score >= 2:
            return HookOutput().system_message(
                "[ARCHITECTURE-DETECTED] Обнаружена архитектурная дискуссия.\n"
                "Используй skill `architecture-research`:\n"
                "1. Проверь docs/documentation/ по теме\n"
                "2. WebSearch best practices\n"
                "3. Предложи решение с атрибуцией"
            )

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
                + _SUBAGENT_CACHE_WARNING
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
                + _SUBAGENT_CACHE_WARNING
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
                "- Архитектура фреймворка → `architecture-research`\n"
                "- 1С-платформа → `1c-doc-research`\n"
                "- RAG/ML/Python → `tech-research`\n"
                "Начни с проверки кеша соответствующего skill."
                + _SUBAGENT_CACHE_WARNING
            )

        return None  # Pass through

    def _detect_domain(
        self, c1_score: int, tech_score: int, arch_score: int,
    ) -> str:
        """Determine domain skill for hybrid routing."""
        if c1_score >= 1:
            return "1c-doc-research"
        if tech_score >= 1:
            return "tech-research"
        return "architecture-research"


if __name__ == "__main__":
    ResearchTaskDetector().run()
