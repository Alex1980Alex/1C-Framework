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
- **Инструменты**: `tools/auto-documenter/` (Node.js), `tools/bsl-debugger/` (Node.js), `tools/ast-grep-mcp/`, `tools/bsl-semantic-diff/`
- **MCP серверы**: bsl-semantic-search, bsl-platform-context, auto-documenter, bsl-debugger, ast-grep-mcp, bsl-semantic-diff
- **Memory**: `src/memory/` (ai_memory, vector_memory, skill_learning, orchestrator, infrastructure). P0-P4 DONE, P5 in progress. Hook: `session-memory-save.py` (Stop, auto-saves session to SQLite). Skill: `memory-unified`
- **LLM Rotation**: `src/shared/llm_rotation/` (5 провайдеров, fallback)
- **Субагенты**: `.claude/agents/` (learning-loop — 5-phase self-learning pipeline, monitor)
- **Паттерны**: `docs/architecture/PATTERNS.md` (15 arch + 13 automation), skill `framework-patterns`
- **Профили**: `.mcp/pdf.json`, `.mcp/bsl.json`, `.mcp/full.json`, `.mcp/lazy-mcp.json`
- **Lazy MCP**: `infra/lazy-mcp/` (proxy, 11 категорий, 27 on-demand серверов)
- **Qdrant коллекции (после Phase 8 + 9.1, 2026-04-30; config defaults aligned 2026-05-01 §2.1)**: 10 коллекций × **Qwen3-Embedding-8B 4096d** через TEI Docker (`pdf-rag-tei`). Production retrieval: `bsl_code_v4_late` (24 455, Late Chunking), `bsl_code_v4` (24 455 std), `framework_code_v1` (21 277+, auto-reindex on commit), `graph_embeddings` (6 694), `wiki_pages_v1` (3 073), `pdf_documents` (830), `skill_library` (80, Phase 9.1), `learned_patterns` (44), `experience_embeddings`/`conversation_memory` (0, ready for auto-populate). Code-side defaults: `EmbeddingSettings.provider="tei"`, `model="Qwen/Qwen3-Embedding-8B"`, `dimensions=4096`; `VectorStoreSettings.dimensions=4096`; regression: `tests/unit/test_config.py::test_phase8_invariants`. Подробности: [chapter 31 Qwen3 Retrieval Production](docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md). Legacy `bsl_code_v2` (768d nomic), `_e5_legacy`, `bsl_code_v3` (1024d E5), `visual_grounding` (768d nomic) — **dropped 2026-04-30**, см. roadmap §27/§32.5
- **BSL hook**: `bsl-tool-router.py` — routes BSL/1C queries to bsl-development skill
- **1С Pipeline** (slash-команды): `/analyze-1c-task` → `/implement-1c-task` → `/write-1c-tests` → `/run-1c-tests` (цепочный прогон VA BDD с resume, pre-scenario TestDB check, `.run-state.json`). Skills: `va-bdd-testing` v1.1 (Stage 4a). Runner: `tools/vanessa/run-bdd.ps1 -OutputJson -RunId`. Подробности: [17.5 Команды 1С Pipeline](docs/framework%20documentation/17_ТЕСТИРОВАНИЕ_1С/17.5_КОМАНДЫ_ПАЙПЛАЙНА.md)
- **Hooks Infrastructure**: `.claude/hooks/docs-change-enforcer.py` → `SKIP_PATTERNS` для инфра-файлов (`.gitmodules`/`.gitignore`/`.gitattributes`, `tools/`, `scripts/`, `tests/`, `features/`, `.run-state.json`, `pyproject.toml`, `.mcp.json`, `src/projects/`, `src/bsl/`, `tmp/`, `.obsidian/`, `.canvas`). При добавлении нового типа инфра-файла — добавить в `SKIP_PATTERNS`, иначе `UNMAPPED` блокировка. **Existence filter** (added 2026-04-15): `get_session_files()` отбрасывает файлы, которых уже нет в working tree (удалены в пределах 6-часового окна `git log`), чтобы стрей-артефакты не блокировали завершение сессии. `code-skill-patterns.json` — конфиг `code-skill-enforcer`, правила `{pattern, skill, label, domain}`; `skill` должен существовать в каталоге `.claude/skills/`, иначе phantom-блокировка. **Phase 5 path migration follow-up (2026-04-26)**: hardcoded `D:\1С-Framework` пути в `settings.json` (PreToolUse `ensure-docker-qdrant` hook) выровнены на `C:/1С-Framework`. **code-verify-reminder Stop-fallback (commit `98d5ea22`)**: дублирующая регистрация хука как PostToolUse + Stop для обхода Windows регрессии #6305 (PostToolUse не срабатывает) — Stop выступает страховочным closer'ом. **Parallel auto-save 2026-05-01**: `docs-change-enforcer.py` модифицирован параллельной сессией в серии auto-save commits (`84f5790b`+); содержание изменения pending review
- **Phase 8 — Qwen3 миграция (2026-04-26 → 2026-04-30, ✅ COMPLETE)**: roadmap `docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md` (1767 строк, §0 status dashboard в шапке). Финальная картина: **10 коллекций × 4096d Qwen3, 80 908 точек**, production retrieval recall@10 = 0.567 (+26% vs E5 baseline). Полная operational documentation: [`docs/framework documentation/31_QWEN3_RETRIEVAL_PRODUCTION/`](docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/) (5 подфайлов: обзор, архитектура, pipeline, auto-reindex on commit, миграция и итоги). Auto-reindex on git commit активен (`git config core.hooksPath scripts/git_hooks`). Phase 9.1 memory hooks alignment fixed silent dim mismatch bug (commit ac91c4b7) — `skill_library` теперь 80 pts × 4096d. Phase 9.2+ план — roadmap §32 (reranker, hybrid sparse+dense, auto-populate memory, LoRA DEFERRED)

## Research

При вопросах про 1С: документация 8.3.27 — первоисточник. Внешние источники (its.1c.ru, infostart.ru) — только дополнение. Каждый факт с атрибуцией. Протокол: skill `1c-doc-research`.

При вопросах про RAG/ML/Python: протокол в skill `tech-research`.
