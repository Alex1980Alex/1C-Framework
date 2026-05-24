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
- **Memory**: `src/memory/` (ai_memory, vector_memory, skill_learning, orchestrator, infrastructure). P0-P4 DONE, P5 in progress. Hook: `session-memory-save.py` (Stop, auto-saves session to SQLite). Skill: `memory-unified`. **L5 drafts pipeline (2026-05-14)**: `session-memory-save.py:try_promote_patterns()` после save вызывает `python -m scripts.export_graph_to_wiki promote-patterns` (subprocess timeout 4s, swallow errors, opt-out `SESSION_MEMORY_NO_PROMOTE=1`); закрывает L2→L5 promotion gap, документированный в [roadmap 260514](docs/roadmap/260514_ROADMAP_WIKI_PROMOTION_GAP.md). Field-name drift `usage_count`→`application_count` исправлен в `src/memory/librarian/wiki_promoter.py`; canonical field пишется `src/memory/vector_memory/server.py:391 handle_apply_pattern` (bayesian update `confidence += 0.02 if success else -0.01`, clamp [0,1]; `application_count += 1`). Pipeline-activation подтверждена smoke-тестом end-to-end (synthetic bump → CLI создал draft + log entry → state revert).
- **LLM Rotation**: `src/shared/llm_rotation/` (5 провайдеров, fallback)
- **Субагенты**: `.claude/agents/` (learning-loop — 5-phase self-learning pipeline, monitor)
- **Паттерны**: `docs/architecture/PATTERNS.md` (15 arch + 13 automation), skill `framework-patterns`
- **Профили**: `.mcp/pdf.json`, `.mcp/bsl.json`, `.mcp/full.json`, `.mcp/lazy-mcp.json`
- **Lazy MCP**: `infra/lazy-mcp/` (proxy, 11 категорий, 27 on-demand серверов)
- **Qdrant коллекции (после Phase 8 + 9.1, 2026-04-30; config defaults aligned 2026-05-01 §2.1)**: 10 коллекций × **Qwen3-Embedding-8B 4096d** через TEI Docker (`pdf-rag-tei`). Production retrieval: `bsl_code_v4_late` (alias → `bsl_code_v4_late_hybrid` 37 668 pts, named `{dense:4096d, bm25:sparse IDF}` since 2026-05-22; prev physical `_v2` retained as backup; default query mode = pure BM25 после realistic golden eval — см. [chapter 31.7](docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.7_BSL_Hybrid_Sparse_BM25.md) + memory `feedback_bsl_sparse_bm25_dominance`), `bsl_code_v4` (24 455 std), `framework_code_v1` (21 277+, auto-reindex on commit), `graph_embeddings` (6 694), `wiki_pages_v1` (3 073), `pdf_documents` (830), `skill_library` (80, Phase 9.1), `learned_patterns` (44), `experience_embeddings`/`conversation_memory` (0, ready for auto-populate). Code-side defaults: `EmbeddingSettings.provider="tei"`, `model="Qwen/Qwen3-Embedding-8B"`, `dimensions=4096`; `VectorStoreSettings.dimensions=4096`; regression: `tests/unit/test_config.py::test_phase8_invariants`. Подробности: [chapter 31 Qwen3 Retrieval Production](docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md). Legacy `bsl_code_v2` (768d nomic), `_e5_legacy`, `bsl_code_v3` (1024d E5), `visual_grounding` (768d nomic) — **dropped 2026-04-30**, см. roadmap §27/§32.5
- **BSL hook**: `bsl-tool-router.py` — routes BSL/1C queries to bsl-development skill
- **Auto-reports (2026-05-22, chapter [`28_1_AUTO_REPORTS`](docs/framework%20documentation/28_1_AUTO_REPORTS/))**: после каждого `category=run_end` в [`data/indexing-progress.jsonl`](data/indexing-progress.jsonl) Stop-хук [`post-indexing-analyzer.py`](.claude/hooks/post-indexing-analyzer.py) детачит [`scripts/analyze_run.py`](scripts/analyze_run.py) — пишет deep отчёт в `data/reports/{indexing,graph}/` (Markdown + JSON sidecar + `_latest_<subject>.md`). Indexing: alias-resolved Qdrant introspection (`framework_code_v1` → `*_mrl_1024`), quantization detect, L2 norm + self-recall@1 probes, diff vs prev. Graph (3 sub-источника): `sqlite` (`cache/bsl_call_graph.db` — 33k symbols/80k calls/2k modules, dangling-call detector), `neo4j` (default `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` env vars), `qdrant_graph` (collection `graph_embeddings`, entity-vs-relation split). Cold-start: на первом запуске seed'ит existing run_ids без анализа (защита от dump'а истории). FIFO dedup state в `.claude/cache/post-indexing-analyzer-state.json` (cap 500), atomic write через `os.replace`. Cap 5 spawn'ов/Stop. Skill: [`post-indexing-analysis`](.claude/skills/post-indexing-analysis/SKILL.md). Smoke: [`tests/integration/test_analyze_run.py`](tests/integration/test_analyze_run.py) (3 теста, Qdrant-independent). Mapping в [`docs-change-enforcer.py`](.claude/hooks/docs-change-enforcer.py) CODE_TO_DOMAIN: `scripts/analyzers/`, `scripts/analyze_run.py`, `.claude/hooks/post-indexing-analyzer.py` → `28_1_AUTO_REPORTS` / `post-indexing-analysis`. Ручной запуск: `python scripts/analyze_run.py --mode {indexing|graph} --run-id <id>` или для графа `--source {sqlite|neo4j|qdrant_graph}`.
- **1С Pipeline** (slash-команды): `/analyze-1c-task` → `/implement-1c-task` → `/write-1c-tests` → `/run-1c-tests` (цепочный прогон VA BDD с resume, pre-scenario TestDB check, `.run-state.json`). Skills: `va-bdd-testing` v1.1 (Stage 4a). Runner: `tools/vanessa/run-bdd.ps1 -OutputJson -RunId`. Подробности: [17.5 Команды 1С Pipeline](docs/framework%20documentation/17_ТЕСТИРОВАНИЕ_1С/17.5_КОМАНДЫ_ПАЙПЛАЙНА.md)
- **Hooks Infrastructure**: `.claude/hooks/docs-change-enforcer.py` → `SKIP_PATTERNS` для инфра-файлов (`.gitmodules`/`.gitignore`/`.gitattributes`, `tools/`, `scripts/`, `tests/`, `features/`, `.run-state.json`, `pyproject.toml`, `.mcp.json`, `src/projects/`, `src/bsl/`). При добавлении нового типа инфра-файла — добавить в `SKIP_PATTERNS`, иначе `UNMAPPED` блокировка. **Existence filter** (added 2026-04-15): `get_session_files()` отбрасывает файлы, которых уже нет в working tree (удалены в пределах 6-часового окна `git log`), чтобы стрей-артефакты не блокировали завершение сессии. `code-skill-patterns.json` — конфиг `code-skill-enforcer`, правила `{pattern, skill, label, domain}`; `skill` должен существовать в каталоге `.claude/skills/`, иначе phantom-блокировка
- **PR-automation (`post-task-push-pr.py` P0-P3 batch, landed via roadmap 260522)**: PostToolUse:TaskUpdate хук — на `TaskUpdate(status=completed)` собирает per-task ветку, push на origin, открывает / переиспользует PR, опционально ждёт checks и мержит. 18 items из [40.4 Дорожная карта](docs/framework%20documentation/40_PR_AUTOMATION/40.4_Дорожная_карта.md): label-driven activation, conflict-aware push, existing-PR reuse, pre-commit pre-push gate, SMTP уведомления, merge wait-for-checks, auto-rebase, dry-run, per-task SHA tracking, CODEOWNERS reviewer assignment, cross-PR blocked-by labels, cherry-pick branch model через git worktree (P3.2), post-merge auto-revert script ([`scripts/pr_check_post_merge.py`](scripts/pr_check_post_merge.py) P3.4), GitHub merge queue alternative `AUTO_PR_MERGE_QUEUE=1` (P3.3). Companion helpers: [`shared/pr_helpers.py`](.claude/hooks/shared/pr_helpers.py) (git/gh primitives + `cherry_pick_range_to_branch`), [`shared/pr_notifier.py`](.claude/hooks/shared/pr_notifier.py) (SMTP), dashboard [`scripts/pr_automation_dashboard.py`](scripts/pr_automation_dashboard.py) (P1.5), orphan cleanup [`scripts/cleanup_orphan_branches.py`](scripts/cleanup_orphan_branches.py) (P2.4), GitHub webhook receiver [`src/api/routes/github_webhooks.py`](src/api/routes/github_webhooks.py) (P3.1), Mergify template [`.mergify.yml`](.mergify.yml) (P3.3). **Master switch:** `AUTO_PR_ENABLED=1` (default `0` после миграции). Base ветка: `AUTO_PR_BASE=master` (после reconciliation 2026-05-23, roadmap 260523 §11; dev-master deleted). Полный env reference + smoke checks + operator wiring guide — [40.4 §«Реализация 2026-05-22 — P3»](docs/framework%20documentation/40_PR_AUTOMATION/40.4_Дорожная_карта.md) и [40.5 Pipeline Workflow](docs/framework%20documentation/40_PR_AUTOMATION/40.5_Pipeline_Workflow.md). **Зависимость:** хук требует modernized `base/protocol.py` (`hook_event_name` приоритет, `transcript_path` fallback) — портирован в этой же миграции
- **`base/protocol.py` modernization (landed 2026-05-22 в составе PR-automation migration)**: `HookInput.detected_event` теперь читает `hook_event_name` payload-поле как авторитативный источник (Claude Code 2.x), `transcript` падает на `transcript_path` (snake_case современный) с легаси-фоллбэком на `transcript`. Без этой модернизации все PostToolUse-хуки misclassify-ят modern Claude Code события как "Unknown" и не срабатывают. Обратная совместимость со старым payload-форматом сохранена
- **F821 hotfix stubs (2026-05-24, hotfix/ci-green-master / PR #10)**: pre-existing F821 errors в `.claude/hooks/` после PR #2 merge — helper functions удалены, calls остались. На `session-memory-save.py` восстановлены 3 stub: `save_to_wiki_log`, `try_promote_patterns`, `_emit_langfuse_span` (все return None/False, no-op). На `memory-first-hook.py` добавлен `HOOK_NAME` constant (`"memory-first-hook"`). Полная реализация (Langfuse spans, L5 wiki promote) deferred до master CI stabilization. Stubs предотвращают `NameError` при runtime, ratchet down ruff F821 errors в `.claude/hooks/` с 16 до 9. См. PR #10 commits `a54b3ebe3`, `ab44af483`
- **§14 Pre-Work dispatcher (PR #9, 2026-05-23)**: новый UPS hook [`shared/prework_dispatcher.py`](.claude/hooks/shared/prework_dispatcher.py) реализует ADR-D1 (asyncio.gather parallel orchestrator из [roadmap 260523 §17.1](docs/roadmap/260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md)) + aggregator [`shared/prework_aggregator.py`](.claude/hooks/shared/prework_aggregator.py) (top-K + ~500 tokens cap, ADR-D2 MVP) + first worker [`prework-architecture.py`](.claude/hooks/prework-architecture.py) (rapidfuzz match на `architecture-research/cache/_index.json`). Worker contract: stdin `{prompt}` → stdout `{items: [{title, body, score}]}`. Регистрация в `settings.json` UPS chain после `memory-first-hook` (timeout 5s). Smoke: real prompt → top-3 cached topics с score 1.0/1.0/0.889. Per-worker timeout via `asyncio.wait_for`, orphan subprocess killed на `TimeoutError`. Reversibility: single rollback = remove dispatcher entry. Future workers (P1, separate PRs): prework-similar-code (Qdrant `framework_code_v1`), prework-github-bp (cache-first WebSearch), prework-stackoverflow (UPS + PostToolUse:Bash reactive). Code-verify PASS via subagent aa124b154f2739a13. Memory entry `feedback_prework_dispatcher_works` будет saved после prod observation 24h

## Research

При вопросах про 1С: документация 8.3.27 — первоисточник. Внешние источники (its.1c.ru, infostart.ru) — только дополнение. Каждый факт с атрибуцией. Протокол: skill `1c-doc-research`.

При вопросах про RAG/ML/Python: протокол в skill `tech-research`.
