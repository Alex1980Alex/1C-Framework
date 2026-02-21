#!/usr/bin/env python3
"""
Hook: docs-change-tracker
Event: PostToolUse
Matcher: Write|Edit
Purpose: When source code files change, remind Claude to update
         the corresponding user documentation AND skills.
         Maps: src/ code area → docs/framework documentation/ + .claude/skills/

         Pattern: "Код изменился → фича изменилась → обнови доки и скиллы"

Timeout: 5s
"""

import sys
import os

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput
from shared.task_master import add_task, get_pending_tasks, complete_task

HOOK_ID = "docs-change-tracker-hook"

# ═══════════════════════════════════════════════════════════════════════
# MAPPING: code path → (documentation files, skill names, update hints)
#
# Each entry: (code_path_pattern, docs_list, skills_list, hints)
#   - code_path_pattern: prefix matched against changed file path
#   - docs_list: files in docs/framework documentation/ to update
#   - skills_list: SKILL.md files to update
#   - hints: what to check/update
# ═══════════════════════════════════════════════════════════════════════

_FD = "docs/framework documentation"  # base path alias

_CODE_TO_DOCS_SKILLS = [
    # ─── SEARCH ───────────────────────────────────────────────────────
    (
        "src/pdf_framework/search/strategies/",
        [
            f"{_FD}/04_ПОИСК/04.1_Обзор_стратегий.md",
            f"{_FD}/04_ПОИСК/04.7_Расширенный_поиск.md",
        ],
        ["search-pipeline-debug"],
        "- Проверь таблицу стратегий (добавлена/изменена стратегия?)\n"
        "- Обнови параметры, .env переменные если изменились\n"
        "- Обнови секцию Файлы в скилле",
    ),
    (
        "src/pdf_framework/search/reranking/",
        [f"{_FD}/04_ПОИСК/04.6_Фильтрация_и_Reranking.md"],
        ["search-pipeline-debug"],
        "- Обнови таблицу reranker-ов\n"
        "- Проверь конфиг reranking в скилле",
    ),
    (
        "src/pdf_framework/search/bm25",
        [f"{_FD}/04_ПОИСК/04.4_BM25.md"],
        ["search-pipeline-debug"],
        "- Обнови описание BM25 (FTS5, lemmatization)\n"
        "- Проверь .env переменные BM25",
    ),
    (
        "src/pdf_framework/search/semantic_cache",
        [f"{_FD}/07_КЭШИРОВАНИЕ/07.1_Семантический_кэш.md"],
        ["framework-caching"],
        "- Обнови API/параметры семантического кеша\n"
        "- Проверь threshold, TTL",
    ),
    (
        "src/pdf_framework/search/manager",
        [f"{_FD}/04_ПОИСК/04.1_Обзор_стратегий.md"],
        ["search-pipeline-debug"],
        "- Search manager изменён — проверь routing стратегий\n"
        "- Обнови flow поиска если изменился",
    ),
    # ─── AGENTS ───────────────────────────────────────────────────────
    (
        "src/pdf_framework/agents/rag/",
        [
            f"{_FD}/05_RAG_АГЕНТЫ/05.1_Self_RAG.md",
            f"{_FD}/05_RAG_АГЕНТЫ/05.4_Conversational_RAG.md",
        ],
        ["agent-orchestration"],
        "- Обнови описание RAG/Self-RAG агента\n"
        "- Проверь nodes, middleware, grading если изменились",
    ),
    (
        "src/pdf_framework/agents/routing/",
        [f"{_FD}/05_RAG_АГЕНТЫ/05.2_Adaptive_RAG.md"],
        ["agent-orchestration"],
        "- Обнови описание Adaptive RAG / routing\n"
        "- Проверь классификатор запросов",
    ),
    (
        "src/pdf_framework/agents/research",
        [f"{_FD}/05_RAG_АГЕНТЫ/05.3_Deep_Research.md"],
        ["agent-orchestration"],
        "- Обнови описание Deep Research агента\n"
        "- Проверь planner, synthesizer",
    ),
    (
        "src/pdf_framework/agents/plan_execute/",
        [f"{_FD}/05_RAG_АГЕНТЫ/05.5_Специализированные_агенты.md"],
        ["agent-orchestration"],
        "- Обнови описание Plan-Execute агента\n"
        "- Проверь steps, tools, execution flow",
    ),
    (
        "src/pdf_framework/agents/multi/",
        [f"{_FD}/05_RAG_АГЕНТЫ/05.5_Специализированные_агенты.md"],
        ["agent-orchestration"],
        "- Обнови описание Multi-Agent оркестратора",
    ),
    (
        "src/pdf_framework/agents/analytical/",
        [f"{_FD}/05_RAG_АГЕНТЫ/05.5_Специализированные_агенты.md"],
        ["agent-orchestration"],
        "- Обнови описание Analytical агента",
    ),
    (
        "src/pdf_framework/agents/memory/",
        [f"{_FD}/05_RAG_АГЕНТЫ/05.4_Conversational_RAG.md"],
        ["agent-orchestration"],
        "- Обнови описание Chat Mode / ConversationMemory\n"
        "- Проверь backends (SQLite, Memory)",
    ),
    # ─── INDEXING / PROCESSING ────────────────────────────────────────
    (
        "src/pdf_framework/loaders/",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.1_Загрузка_PDF.md"],
        ["indexing-pipeline"],
        "- Обнови описание Hybrid Loader (4 уровня)\n"
        "- Проверь fallback strategy",
    ),
    (
        "src/pdf_framework/processing/splitters/",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.2_Опции_индексации.md"],
        ["indexing-pipeline"],
        "- Обнови описание сплиттеров\n"
        "- Проверь chunk_size, overlap параметры",
    ),
    (
        "src/pdf_framework/processing/extractors/",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.3_Граф_знаний.md"],
        ["graph-operations"],
        "- Обнови описание entity extraction\n"
        "- Проверь LLM prompt, entity types",
    ),
    (
        "src/pdf_framework/indexing/delta_indexer",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.4_Инкрементальная_индексация.md"],
        ["indexing-pipeline"],
        "- Обнови описание Delta Indexing (SHA-256)\n"
        "- Проверь API endpoints delta",
    ),
    (
        "src/pdf_framework/indexing/visual_indexer",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.5_Изображения_и_таблицы.md"],
        ["indexing-pipeline", "embedding-models"],
        "- Обнови описание Visual Indexing (ColPali)\n"
        "- Проверь DPI, модели, pipeline",
    ),
    (
        "src/pdf_framework/processing/versioning",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.4_Инкрементальная_индексация.md"],
        ["indexing-pipeline"],
        "- Обнови описание Document Versioning\n"
        "- Проверь rollback, checkpoint",
    ),
    (
        "src/pdf_framework/processing/image_",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.5_Изображения_и_таблицы.md"],
        ["indexing-pipeline"],
        "- Обнови описание Image Extraction\n"
        "- Проверь Vision API описатель",
    ),
    (
        "src/pdf_framework/processing/page_renderer",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.5_Изображения_и_таблицы.md"],
        ["indexing-pipeline"],
        "- Обнови описание Page Renderer (PDF → Image)\n"
        "- Проверь DPI параметры",
    ),
    (
        "src/pdf_framework/processing/context_generator",
        [f"{_FD}/07_КЭШИРОВАНИЕ/07.3_LLM_кэш.md"],
        ["framework-caching"],
        "- Обнови описание Contextual Retrieval Cache\n"
        "- Проверь SQLite cache, hash-based",
    ),
    # ─── GRAPH STORE ──────────────────────────────────────────────────
    (
        "src/pdf_framework/graph_store/",
        [f"{_FD}/03_ИНДЕКСАЦИЯ/03.3_Граф_знаний.md"],
        ["graph-operations"],
        "- Обнови описание Graph Store\n"
        "- Проверь providers (NetworkX, Neo4j)\n"
        "- Проверь entity embeddings, incremental update",
    ),
    # ─── EMBEDDINGS ───────────────────────────────────────────────────
    (
        "src/pdf_framework/embeddings/",
        [f"{_FD}/02_БЫСТРЫЙ_СТАРТ/02.2_Конфигурация.md"],
        ["embedding-models"],
        "- Обнови таблицу моделей (dims, скорость)\n"
        "- Проверь prefix requirements, backends\n"
        "- Обнови .env переменные EMBEDDING__*",
    ),
    # ─── CONFIG ───────────────────────────────────────────────────────
    (
        "src/pdf_framework/config/",
        [f"{_FD}/02_БЫСТРЫЙ_СТАРТ/02.2_Конфигурация.md"],
        ["framework-config"],
        "- Обнови таблицу .env переменных\n"
        "- Проверь новые/удалённые настройки\n"
        "- Обнови defaults если изменились",
    ),
    # ─── INTERFACES: API ──────────────────────────────────────────────
    (
        "src/api/routes/",
        [f"{_FD}/06_ИНТЕРФЕЙСЫ/06.2_REST_API.md"],
        ["framework-api"],
        "- Обнови таблицу endpoints\n"
        "- Проверь новые/изменённые роуты\n"
        "- Обнови curl примеры если изменился формат",
    ),
    (
        "src/api/middleware/",
        [
            f"{_FD}/09_АДМИНИСТРИРОВАНИЕ/09.3_Rate_Limiting.md",
            f"{_FD}/10_УСТРАНЕНИЕ_НЕПОЛАДОК/10.1_Частые_ошибки.md",
        ],
        ["deployment", "framework-troubleshooting"],
        "- Обнови описание middleware (rate limit, guardrails)\n"
        "- Проверь .env параметры",
    ),
    (
        "src/api/dependencies/auth",
        [f"{_FD}/09_АДМИНИСТРИРОВАНИЕ/09.2_Авторизация.md"],
        ["deployment"],
        "- Обнови описание авторизации (JWT, RBAC)\n"
        "- Проверь roles, permissions",
    ),
    (
        "src/api/app.py",
        [f"{_FD}/06_ИНТЕРФЕЙСЫ/06.2_REST_API.md"],
        ["framework-api", "deployment"],
        "- Проверь подключённые роутеры\n"
        "- Обнови middleware/CORS если изменились",
    ),
    # ─── INTERFACES: CLI ──────────────────────────────────────────────
    (
        "src/cli/",
        [f"{_FD}/06_ИНТЕРФЕЙСЫ/06.3_CLI.md"],
        ["framework-cli"],
        "- Обнови таблицу CLI команд\n"
        "- Проверь аргументы, флаги, примеры",
    ),
    # ─── INTERFACES: MCP ──────────────────────────────────────────────
    (
        "src/mcp_server/",
        [f"{_FD}/06_ИНТЕРФЕЙСЫ/06.4_MCP_Server.md"],
        ["framework-mcp-ui"],
        "- Обнови таблицу MCP tools\n"
        "- Проверь параметры, enum стратегий\n"
        "- Обнови описание tool если изменился",
    ),
    # ─── INTERFACES: UI ───────────────────────────────────────────────
    (
        "src/ui/",
        [f"{_FD}/06_ИНТЕРФЕЙСЫ/06.1_Web_UI.md"],
        ["framework-mcp-ui"],
        "- Обнови описание Web UI (Gradio)\n"
        "- Проверь вкладки, функционал страниц",
    ),
    # ─── CACHING ──────────────────────────────────────────────────────
    (
        "src/pdf_framework/callbacks/",
        [f"{_FD}/07_КЭШИРОВАНИЕ/07.3_LLM_кэш.md"],
        ["framework-caching"],
        "- Обнови описание LLM кеша\n"
        "- Проверь hash-based key generation",
    ),
    # ─── EVALUATION ───────────────────────────────────────────────────
    (
        "src/pdf_framework/evaluation/",
        [
            f"{_FD}/08_ОЦЕНКА_КАЧЕСТВА/08.1_RAG_Triad.md",
            f"{_FD}/08_ОЦЕНКА_КАЧЕСТВА/08.2_RAGAS.md",
        ],
        ["evaluation-benchmark"],
        "- Обнови метрики, конфиг оценки\n"
        "- Проверь API endpoints eval",
    ),
    (
        "src/pdf_framework/feedback/",
        [f"{_FD}/08_ОЦЕНКА_КАЧЕСТВА/08.4_Обратная_связь.md"],
        ["evaluation-benchmark"],
        "- Обнови описание Feedback Loop\n"
        "- Проверь FeedbackCollector, StrategyTuner",
    ),
    (
        "src/pdf_framework/optimization/",
        [f"{_FD}/08_ОЦЕНКА_КАЧЕСТВА/08.3_AutoRAG.md"],
        ["evaluation-benchmark", "prompt-engineering"],
        "- Обнови описание AutoRAG / DSPy MIPROv2\n"
        "- Проверь параметры оптимизации",
    ),
    # ─── ADMINISTRATION ───────────────────────────────────────────────
    (
        "src/pdf_framework/multitenancy/",
        [f"{_FD}/09_АДМИНИСТРИРОВАНИЕ/09.1_Мультитенантность.md"],
        ["deployment"],
        "- Обнови описание мультитенантности\n"
        "- Проверь tenant isolation, quotas",
    ),
    (
        "src/pdf_framework/observability/",
        [f"{_FD}/09_АДМИНИСТРИРОВАНИЕ/09.4_Мониторинг.md"],
        ["deployment"],
        "- Обнови описание мониторинга (Langfuse, Prometheus)\n"
        "- Проверь трейсы, метрики",
    ),
    (
        "src/pdf_framework/guardrails/",
        [f"{_FD}/10_УСТРАНЕНИЕ_НЕПОЛАДОК/10.1_Частые_ошибки.md"],
        ["framework-troubleshooting"],
        "- Обнови описание Guardrails (PII, injection, content)\n"
        "- Проверь паттерны, .env переменные",
    ),
    # ─── WORKERS ──────────────────────────────────────────────────────
    (
        "src/workers/",
        [f"{_FD}/09_АДМИНИСТРИРОВАНИЕ/09.5_Docker.md"],
        ["deployment"],
        "- Обнови описание Workers/ARQ Queue\n"
        "- Проверь task types, Redis config",
    ),
    # ─── DOCKER ───────────────────────────────────────────────────────
    (
        "docker/",
        [f"{_FD}/09_АДМИНИСТРИРОВАНИЕ/09.5_Docker.md"],
        ["deployment"],
        "- Обнови описание Docker Compose\n"
        "- Проверь сервисы, порты, volumes",
    ),
    # ─── VECTOR STORE ─────────────────────────────────────────────────
    (
        "src/pdf_framework/vector_store/",
        [f"{_FD}/04_ПОИСК/04.2_Hybrid_Search.md"],
        ["qdrant-operations"],
        "- Обнови описание vector store (Qdrant)\n"
        "- Проверь named vectors, sparse, collections",
    ),
    # ─── HOOKS & SKILLS (meta) ────────────────────────────────────────
    (
        ".claude/hooks/",
        [f"{_FD}/01_ОБЗОР/01.2_Архитектура.md"],
        ["hooks-skills-mcp-triad"],
        "- Обнови описание hook в архитектуре\n"
        "- Проверь event/matcher/назначение",
    ),
    (
        ".claude/skills/",
        [f"{_FD}/01_ОБЗОР/01.2_Архитектура.md"],
        ["hooks-skills-mcp-triad"],
        "- Обнови описание skill в архитектуре\n"
        "- Проверь trigger/тип/описание\n"
        "- Обнови skill-router-config.json если нужно",
    ),
    # ─── .ENV / PYPROJECT ─────────────────────────────────────────────
    (
        ".env.example",
        [f"{_FD}/02_БЫСТРЫЙ_СТАРТ/02.2_Конфигурация.md"],
        ["framework-config"],
        "- .env.example изменён — синхронизируй документацию\n"
        "- Проверь все переменные в скилле framework-config",
    ),
    (
        "pyproject.toml",
        [
            f"{_FD}/02_БЫСТРЫЙ_СТАРТ/02.1_Установка.md",
            f"{_FD}/01_ОБЗОР/01.3_Технологический_стек.md",
        ],
        ["framework-quickstart"],
        "- Обнови зависимости в документации\n"
        "- Проверь версии, новые пакеты",
    ),
]

# Skip patterns — avoid recursion and noise
_SKIP_PATTERNS = [
    "/cache/",
    "/__pycache__/",
    "_index.json",
    "_topic_template.md",
    "/docs/framework documentation/",  # don't trigger on doc edits themselves
    "/docs/roadmap/",
    "/docs/analysis/",
    "/memory/",
    "auto-git-save-state",
    "hook-todos",
]


class DocsChangeTracker(BaseHook):
    """When code changes, remind to update corresponding docs + skills."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name not in ("Write", "Edit"):
            return None

        tool_input = inp.tool_input
        file_path = ""
        if isinstance(tool_input, dict):
            file_path = tool_input.get("file_path", "")
        elif isinstance(tool_input, str):
            file_path = tool_input

        if not file_path:
            return None

        path_norm = file_path.replace("\\", "/").lower()

        # FIRST: check if this edit completes any pending tasks
        # (e.g., Claude editing a doc/skill file that was requested)
        completed = self._try_complete_tasks(path_norm)
        if completed > 0:
            # Claude is doing the requested update — don't create new tasks
            return None

        # Skip docs/noise (avoid creating NEW tasks for doc edits)
        for skip in _SKIP_PATTERNS:
            if skip.lower() in path_norm:
                return None

        # Find ALL matching mappings (a file may match multiple)
        matches = []
        for pattern, doc_files, skill_names, hints in _CODE_TO_DOCS_SKILLS:
            if pattern.replace("\\", "/").lower() in path_norm:
                matches.append((doc_files, skill_names, hints))

        if not matches:
            return None

        return self._remind(file_path, matches)

    def _try_complete_tasks(self, path_norm: str) -> int:
        """Auto-complete pending tasks when their target doc/skill is actually edited.

        Mechanism: task description contains paths of docs and skill names.
        When Claude edits one of those files — task is done.
        """
        is_doc = "docs/framework documentation/" in path_norm
        is_skill = ".claude/skills/" in path_norm

        if not is_doc and not is_skill:
            return 0

        pending = get_pending_tasks(created_by=HOOK_ID)
        if not pending:
            return 0

        completed = 0
        for task in pending:
            desc_lower = task.get("description", "").replace("\\", "/").lower()

            # Doc edit: check if the relative doc path is mentioned in the task
            if is_doc:
                idx = path_norm.find("docs/framework documentation/")
                if idx >= 0:
                    rel_path = path_norm[idx:]
                    if rel_path in desc_lower:
                        complete_task(task["content"], created_by=HOOK_ID)
                        completed += 1
                        continue

            # Skill edit: check if the skill name is mentioned in the task
            if is_skill:
                parts = path_norm.split(".claude/skills/")
                if len(parts) > 1:
                    skill_name = parts[1].split("/")[0]
                    if skill_name and skill_name in desc_lower:
                        complete_task(task["content"], created_by=HOOK_ID)
                        completed += 1
                        continue

        return completed

    def _remind(self, changed_file, matches):
        """Create task and return systemMessage with all affected docs+skills."""
        pending = get_pending_tasks(created_by=HOOK_ID)
        if len(pending) >= 20:
            return None

        basename = os.path.basename(changed_file)

        # Collect unique docs and skills
        all_docs = []
        all_skills = []
        all_hints = []
        for doc_files, skill_names, hints in matches:
            for d in doc_files:
                if d not in all_docs:
                    all_docs.append(d)
            for s in skill_names:
                if s not in all_skills:
                    all_skills.append(s)
            all_hints.append(hints)

        # Build message parts
        docs_str = "\n".join(f"  📄 {d}" for d in all_docs)
        skills_str = "\n".join(
            f"  🔧 .claude/skills/{s}/SKILL.md" for s in all_skills
        )
        hints_str = "\n".join(all_hints)

        add_task(
            title=f"Обновить доки/скиллы (изменён {basename})",
            description=(
                f"Файл {basename} изменён.\n"
                f"Документация: {', '.join(all_docs)}\n"
                f"Скиллы: {', '.join(all_skills)}\n"
                f"{hints_str}"
            ),
            priority="normal",
            created_by=HOOK_ID,
        )

        msg = (
            f"[DOCS-TRACKER] Изменён файл: {basename}\n\n"
            f"Обнови ДОКУМЕНТАЦИЮ:\n{docs_str}\n\n"
            f"Обнови СКИЛЛЫ:\n{skills_str}\n\n"
            f"Что проверить:\n{hints_str}"
        )

        return HookOutput().system_message(msg)


if __name__ == "__main__":
    DocsChangeTracker().run()
