# CLAUDE.md — PDF Vector & Graph Framework

> AI agent instructions are in [AGENTS.md](AGENTS.md). This file is project context for humans and AI.

## Project Overview

Framework for PDF document processing: semantic search (RAG), knowledge graphs, hybrid retrieval. Production-ready with REST API, CLI, MCP server, Streamlit UI.

## Tech Stack

- **Python 3.11+**, async-first
- **LangChain / LangGraph** — agents, tools, chains, orchestration
- **Qdrant / ChromaDB / FAISS** — vector stores
- **Neo4j / NetworkX** — graph stores
- **FastAPI** — REST API
- **MCP** — Model Context Protocol server
- **Typer** — CLI

## Project Structure

```
src/
  pdf_framework/        # Core library
    loaders/            # PDF loading (pymupdf, pdfplumber)
    processing/         # Splitting, cleaning, metadata
    embeddings/         # Embedding providers
    vector_store/       # Vector DB (base + providers)
    graph_store/        # Graph DB (base + providers)
    search/             # Hybrid search, strategies, reranking
    agents/             # LangGraph agents (RAG, analytical, research)
    indexing/           # Indexing pipelines, hybrid loader
    tools/              # LangChain tools
    chains/             # LangChain chains
    schemas/            # Pydantic data models
    config/             # Settings modules
    evaluation/         # RAGAS, benchmarks
    guardrails/         # Input/output validation
    observability/      # Logging, tracing
    analytics/          # Cost tracking, audits
    feedback/           # User feedback
    multitenancy/       # Multi-tenant support
    optimization/       # Performance tuning
    knowledge_base/     # Knowledge base management
    callbacks/          # Event callbacks
    utils/              # Utilities
  api/                  # REST API (FastAPI)
  cli/                  # CLI (Typer)
  mcp_server/           # MCP server for Claude Code
  ui/                   # Streamlit web UI
  workers/              # Background task workers
```

## Development Rules

- Store implementations extend abstract base classes in `*/base.py`
- Pydantic models from `schemas/` as data contracts
- Async-first: all I/O operations are `async`
- Configuration via `pydantic-settings` (`.env` file)
- Provider pattern: swap Vector/Graph/Embedding providers without changing logic

## Output Rules

- File references in responses must be clickable markdown: `[file.py](.claude/hooks/file.py)` or `[file.py:42](.claude/hooks/file.py#L42)`

## BSL Development (1C Enterprise)

- **BSL код**: `src/bsl/` (semantic_search, mcp_server, mcp_integration, sonar, finetuning)
- **Инструменты**: `tools/auto-documenter/` (Node.js), `tools/bsl-debugger/` (Node.js), `tools/bsl-debug-server/` (Python — live RDBG wrapper, **HMR-enabled через `mcp_hmr_proc.py`**), `tools/ast-grep-mcp/`, `tools/bsl-semantic-diff/`
- **MCP серверы**: bsl-semantic-search, bsl-platform-context, auto-documenter, bsl-debugger, **`1c-debug` + `1c-debug-hmr`** (live BSL отладка через RDBG, HMR-вариант reload'ит при edit без потери session — `.active.json` persistence + unified `ping()` dispatch, добавлен 2026-05-10; см. [`docs/framework documentation/36_AUTONOMOUS_DEBUG_CONTROL/36.7_HMR_Subprocess_Wrapper.md`](docs/framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/36.7_HMR_Subprocess_Wrapper.md) + skill [`1c-debug-hmr`](.claude/skills/1c-debug-hmr/SKILL.md)), ast-grep-mcp, bsl-semantic-diff
- **Memory**: `src/memory/` (ai_memory, vector_memory, skill_learning, orchestrator, infrastructure). P0-P4 DONE, P5 in progress. Hook: `session-memory-save.py` (Stop, auto-saves session to SQLite). Skill: `memory-unified`
- **LLM Rotation**: `src/shared/llm_rotation/` (5 провайдеров, fallback)
- **Субагенты**: `.claude/agents/` (learning-loop — 5-phase self-learning pipeline, monitor)
- **Паттерны**: `docs/architecture/PATTERNS.md` (15 arch + 13 automation), skill `framework-patterns`
- **Профили**: `.mcp/pdf.json`, `.mcp/bsl.json`, `.mcp/full.json`, `.mcp/lazy-mcp.json`
- **Lazy MCP**: `infra/lazy-mcp/` (proxy, 11 категорий, 27 on-demand серверов)
- **Qdrant коллекции (после Phase 8 + 9.1, 2026-04-30; config defaults aligned 2026-05-01 §2.1)**: 10 коллекций × **Qwen3-Embedding-8B 4096d** через TEI Docker (`pdf-rag-tei`). Production retrieval: `bsl_code_v4_late` (24 455, Late Chunking), `bsl_code_v4` (24 455 std), `framework_code_v1` (21 277+, auto-reindex on commit), `graph_embeddings` (6 694), `wiki_pages_v1` (3 073), `pdf_documents` (830), `skill_library` (80, Phase 9.1), `learned_patterns` (44), `experience_embeddings`/`conversation_memory` (0, ready for auto-populate). Code-side defaults: `EmbeddingSettings.provider="tei"`, `model="Qwen/Qwen3-Embedding-8B"`, `dimensions=4096`; `VectorStoreSettings.dimensions=4096`; regression: `tests/unit/test_config.py::test_phase8_invariants`. Подробности: [chapter 31 Qwen3 Retrieval Production](docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md). Legacy `bsl_code_v2` (768d nomic), `_e5_legacy`, `bsl_code_v3` (1024d E5), `visual_grounding` (768d nomic) — **dropped 2026-04-30**, см. roadmap §27/§32.5
- **BSL hook**: `bsl-tool-router.py` — routes BSL/1C queries to bsl-development skill
- **1С Pipeline** (slash-команды): `/analyze-1c-task` → `/implement-1c-task` → `/write-1c-tests` → `/run-1c-tests` (цепочный прогон VA BDD с resume, pre-scenario TestDB check, `.run-state.json`). Skills: `va-bdd-testing` v1.1 (Stage 4a). Runner: `tools/vanessa/run-bdd.ps1 -OutputJson -RunId`. Подробности: [17.5 Команды 1С Pipeline](docs/framework%20documentation/17_ТЕСТИРОВАНИЕ_1С/17.5_КОМАНДЫ_ПАЙПЛАЙНА.md)
- **Hooks Infrastructure**: `.claude/hooks/docs-change-enforcer.py` → `SKIP_PATTERNS` для инфра-файлов (`.gitmodules`/`.gitignore`/`.gitattributes`, `tools/`, `scripts/`, `tests/`, `features/`, `.run-state.json`, `pyproject.toml`, `.mcp.json`, `configuration/`, `ИБTransportManagementDevelop/`, `src/bsl/`, `tmp/`, `.obsidian/`, `.canvas`, `external/`, `createinfobase` (1cv8.exe CREATEINFOBASE log в корне репо — содержит DB credentials, должен быть и в `.gitignore`)). При добавлении нового типа инфра-файла — добавить в `SKIP_PATTERNS`, иначе `UNMAPPED` блокировка. **Existence filter** (added 2026-04-15): `get_session_files()` отбрасывает файлы, которых уже нет в working tree (удалены в пределах 6-часового окна `git log`), чтобы стрей-артефакты не блокировали завершение сессии. `code-skill-patterns.json` — конфиг `code-skill-enforcer`, правила `{pattern, skill, label, domain}`; `skill` должен существовать в каталоге `.claude/skills/`, иначе phantom-блокировка. **Phase 5 path migration follow-up (2026-04-26)**: hardcoded `D:\1С-Framework` пути в `settings.json` (PreToolUse `ensure-docker-qdrant` hook) выровнены на `C:/1С-Framework`. **code-verify-reminder Stop-fallback (commit `98d5ea22`)**: дублирующая регистрация хука как PostToolUse + Stop для обхода Windows регрессии #6305 (PostToolUse не срабатывает) — Stop выступает страховочным closer'ом. **Parallel auto-save 2026-05-01**: `docs-change-enforcer.py` модифицирован параллельной сессией в серии auto-save commits (`84f5790b`+); содержание изменения pending review. **Mapping override block (2026-05-09, roadmap §3.1/§3.7/§3.3 closure follow-up)**: `CODE_TO_DOMAIN` table расширена specific overrides ПЕРЕД general prefixes (first-match wins): `callbacks/{langfuse,metrics,logging}/`, `config/observability.py`, `utils/retry.py`, `api/auth/` теперь корректно мапятся на `09_АДМИНИСТРИРОВАНИЕ` (observability/security в 09.2/09.4) вместо false-positive `07_КЭШИРОВАНИЕ`/`02_БЫСТРЫЙ_СТАРТ`/`01_ОБЗОР`. При добавлении новых specific overrides — поместить ДО соответствующего general prefix (e.g., `callbacks/foo/` ДО `callbacks/`). General prefixes остаются как fallback для не-overriden путей
- **Phase 8 — Qwen3 миграция (2026-04-26 → 2026-04-30, ✅ COMPLETE)**: roadmap `docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md` (1767 строк, §0 status dashboard в шапке). Финальная картина: **10 коллекций × 4096d Qwen3, 80 908 точек**, production retrieval recall@10 = 0.567 (+26% vs E5 baseline). Полная operational documentation: [`docs/framework documentation/31_QWEN3_RETRIEVAL_PRODUCTION/`](docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/) (5 подфайлов: обзор, архитектура, pipeline, auto-reindex on commit, миграция и итоги). Auto-reindex on git commit активен (`git config core.hooksPath scripts/git_hooks`). Phase 9.1 memory hooks alignment fixed silent dim mismatch bug (commit ac91c4b7) — `skill_library` теперь 80 pts × 4096d. Phase 9.2+ план — roadmap §32 (reranker, hybrid sparse+dense, auto-populate memory, LoRA DEFERRED)
- **Shared slash-command detector (2026-05-07)**: [`shared/slash_detect.py`](.claude/hooks/shared/slash_detect.py) — единая `detect_slash_command(prompt) -> str` для двух UPS-хуков ([slash-command-tracker.py](.claude/hooks/slash-command-tracker.py) и [implement-1c-task-preflight.py](.claude/hooks/implement-1c-task-preflight.py)), оба теперь импортируют общий парсер вместо локальных копий. Внутри: `<command-name>NAME</command-name>` тэг (post-expansion, win) → raw `/cmd` префикс с очисткой backtick-noise (Claude Code v2.1.126+ оборачивает CLI как `` `/cmd args ``, regression точка восстановлена в commit `fbdf1b720`). История drift'а: один раз backtick-handling уже терялся при UPE→UPS rewrite — единый источник правды убирает риск повтора. Future preflight-хуки для `/run-1c-tests` / `/write-1c-tests` импортируют тот же модуль
- **`/analyze-1c-task` preflight hook (2026-05-11, roadmap 260510 Phase 3 §5.1)**: [`.claude/hooks/analyze-1c-task-preflight.py`](.claude/hooks/analyze-1c-task-preflight.py) — UserPromptSubmit, content-фильтр на `/analyze-1c-task` (та же двухступенчатая детекция через `shared.slash_detect`). Probe debug-hmr через **shared helper** [`.claude/hooks/shared/debug_hmr_health.py`](.claude/hooks/shared/debug_hmr_health.py) (функция `probe_debug_hmr_ready()` — единая точка истины для обоих preflight-хуков). Распознаёт флаг `--trace` в prompt и выдаёт contextual systemMessage: «Phase 2.5 Runtime Trace будет запущена / доступна / SKIP». Не блокирует — Phase 2.5 opt-in. Лог: `data/hook-invocations.jsonl` category=`preflight`, outcome содержит `mode={Mode};exit={code};debug_hmr={0|1};trace_flag={0|1}`. Hook зарегистрирован в `.claude/settings.json` UserPromptSubmit chain после `implement-1c-task-preflight.py`, timeout 30s. Закрывает Phase 3 §5.1 [roadmap 260510](docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md)
- **`/implement-1c-task` preflight hook (2026-05-07, debug-hmr integration 2026-05-11)**: [`.claude/hooks/implement-1c-task-preflight.py`](.claude/hooks/implement-1c-task-preflight.py) — UserPromptSubmit, content-фильтр на slash-команду `/implement-1c-task` (двухступенчатая детекция: `<command-name>`-тег / raw `/cmd` с backtick-noise обходом, как у `slash-command-tracker.py`). Запускает [`scripts/smoke_test_implement_1c_task.py`](scripts/smoke_test_implement_1c_task.py) через `subprocess.run(..., timeout=25)`, парсит `--json`, эмитит `systemMessage` с режимом pipeline (Full / **Full (no-BP)** / Code-only / Read-only verify / Read-only research / unusable), списком unreachable серверов и отдельной строкой «Debug environment: ready/not-ready» (BP-verification Этапа 5.x). Не блокирует — пользователь может принудительно запустить даже при unusable. Лог в `data/hook-invocations.jsonl` с `category="preflight"`, `outcome="mode=<Mode>;exit=<code>;debug_hmr=<0|1>"` (поле `debug_hmr` добавлено 2026-05-11 — корреляция: `jq 'select(.category=="preflight") | .outcome' data/hook-invocations.jsonl` показывает доступность BP-verification по runs), `run_id` подхватывается через `shared.run_context.get_run_id(session_id)` (slash-command-tracker регистрируется выше в UPS-цепочке и наполняет `.current-runs.json` к моменту preflight). Hook timeout в settings.json = 30s (covers 3x stdio MCP handshakes @ 6s + TCP/HTTP probes + slack). Smoke-test расширен 2026-05-11 опциональным probe `1c-debug-hmr` (handshake через `initialize` JSON-RPC) — поле `mcp_health.debug_hmr` в `--json` output, недоступность НЕ блокирует pipeline (orthogonal axis). Roadmap: [`260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md`](docs/roadmap/260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md) Phase 5.2 + [`260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md`](docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md) Phase 1 (§3.1)
- **`/implement-1c-task` smoke-stop alert (2026-05-08, tie-breaker fix 2026-05-09)**: [`.claude/hooks/implement-1c-task-smoke-stop-alert.py`](.claude/hooks/implement-1c-task-smoke-stop-alert.py) — Stop, читает tail `data/hook-invocations.jsonl` (512 KB, ~24ч окно), ищет: (1) preflight с `exit≥1` и (2) `slash_run start` для `slash:implement-1c-task` — если оба найдены, эмитит informational `systemMessage` со ссылкой на `scripts/smoke_test_implement_1c_task.py` и `16.6_EDT_MCP_setup.md`. Per-session cooldown через cookie-файл `.claude/cache/smoke-stop-alert-sessions.json` (boot до 50 sessions). Selection of worst preflight: severity priority (`exit_code` higher wins), tie-break — более свежий `ts` (precedence-bug в исходном tie-breaker'е был исправлен через quality-review reviewer'ом — операторное precedence `ts > prev_ts or datetime.min` всегда давало truthy → разделено на отдельный `prev_ts = … or datetime.min`). Не блокирует. В `settings.json` зарегистрирован после `slash-command-tracker` (чтобы тот успел залогать end-события) и перед enforcer'ами. Закрывает Phase 5.4 [`260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md`](docs/roadmap/260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md). Pattern — Enforcer informational variant (только `system_message`, без `block`)
- **Universal MCP & slash-command logging (2026-05-04)**: единый аудит-лог `data/hook-invocations.jsonl` теперь содержит три категории записей через поле `category` (расширение [`shared/invocation_logger.py`](.claude/hooks/shared/invocation_logger.py) — поля `category`, `run_id`). [`mcp-invocation-logger.py`](.claude/hooks/mcp-invocation-logger.py) на regex-matcher `mcp__.*` ловит **любой** MCP-сервер (текущий и будущий — `bsl-semantic-search`, `1c-mcp-crud`, `edt-mcp`, `memory-orchestrator`, `pdf-vector-graph`, `bsl-platform-context`, `bsl-debugger`, `ast-grep-mcp`, …) с `category="mcp_call"`, без per-server обвязки. [`slash-command-tracker.py`](.claude/hooks/slash-command-tracker.py) (**UserPromptSubmit** + Stop; UPE сохранён как forward-compat fallback. Изначально полагался на `UserPromptExpansion` ([official Claude Code 2.x event](https://code.claude.com/docs/en/hooks)) с готовым `command_name` payload, но эмпирически 2026-05-05 (сессия `10108f33-d062-4580-a1c5-3d425f707193`) подтверждено: на Windows UPE платформой **не эмитится** для `/cmd` — ноль hook entries при валидной регистрации в `settings.json`. Перешли на UPS + парсинг `prompt`: сначала ищем `<command-name>NAME</command-name>` (post-expansion), затем стрипаем leading backtick/quote (Claude Code v2.1.126+ оборачивает real CLI как `` `/cmd args ``, см. commit `fbdf1b720` и регрессию 2026-05-05) и матчим `^\s*/NAME` (raw CLI). UPE-обработчик оставлен с guard'ом `get_run` чтобы не было дубль run_id если платформа починит событие) генерит UUID `run_id` для каждого `/cmd`, складывает в [`data/.current-runs.json`](data/.current-runs.json) через [`shared/run_context.py`](.claude/hooks/shared/run_context.py), и MCP-логгер прицепляет этот `run_id` к каждой записи MCP-вызова. **Паттерн для будущих MCP-серверов**: новые серверы покрываются автоматически — никаких правок в settings.json не нужно, regex `mcp__.*` уже ловит всё. Если нужен спец-обработчик (как у `mcp__llm-rotation__llm_complete`) — добавлять отдельным matcher'ом, общий логгер продолжит работать параллельно. Корреляция: `jq 'select(.run_id=="<UUID>")' data/hook-invocations.jsonl` показывает полную трассу slash-run → все MCP-вызовы → Stop. Pre/Post pair (один и тот же tool с двумя записями) даёт runtime: `ts(post) - ts(pre)`

## Research

При вопросах про 1С: документация 8.3.27 — первоисточник. Внешние источники (its.1c.ru, infostart.ru) — только дополнение. Каждый факт с атрибуцией. Протокол: skill `1c-doc-research`.

При вопросах про RAG/ML/Python: протокол в skill `tech-research`.
