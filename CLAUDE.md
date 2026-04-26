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
- **Qdrant коллекции**: `bsl_code_v2` (768d nomic), `ai_memory` (768d), `learned_patterns` (768d), `skill_library` (768d nomic, 75 skills), `experience_bank` (768d nomic)
- **BSL hook**: `bsl-tool-router.py` — routes BSL/1C queries to bsl-development skill
- **1С Pipeline** (slash-команды): `/analyze-1c-task` → `/implement-1c-task` → `/write-1c-tests` → `/run-1c-tests` (цепочный прогон VA BDD с resume, pre-scenario TestDB check, `.run-state.json`). Skills: `va-bdd-testing` v1.1 (Stage 4a). Runner: `tools/vanessa/run-bdd.ps1 -OutputJson -RunId`. Подробности: [17.5 Команды 1С Pipeline](docs/framework%20documentation/17_ТЕСТИРОВАНИЕ_1С/17.5_КОМАНДЫ_ПАЙПЛАЙНА.md)
- **Hooks Infrastructure**: `.claude/hooks/docs-change-enforcer.py` → `SKIP_PATTERNS` для инфра-файлов (`.gitmodules`/`.gitignore`/`.gitattributes`, `tools/`, `scripts/`, `tests/`, `features/`, `.run-state.json`, `pyproject.toml`, `.mcp.json`, `src/projects/`, `src/bsl/`, `tmp/`, `.obsidian/`, `.canvas`). При добавлении нового типа инфра-файла — добавить в `SKIP_PATTERNS`, иначе `UNMAPPED` блокировка. **Existence filter** (added 2026-04-15): `get_session_files()` отбрасывает файлы, которых уже нет в working tree (удалены в пределах 6-часового окна `git log`), чтобы стрей-артефакты не блокировали завершение сессии. `code-skill-patterns.json` — конфиг `code-skill-enforcer`, правила `{pattern, skill, label, domain}`; `skill` должен существовать в каталоге `.claude/skills/`, иначе phantom-блокировка. **Phase 5 path migration follow-up (2026-04-26)**: hardcoded `D:\1С-Framework` пути в `settings.json` (PreToolUse `ensure-docker-qdrant` hook) выровнены на `C:/1С-Framework`. **code-verify-reminder Stop-fallback (commit `98d5ea22`)**: дублирующая регистрация хука как PostToolUse + Stop для обхода Windows регрессии #6305 (PostToolUse не срабатывает) — Stop выступает страховочным closer'ом
- **Phase 8 — Qwen3 миграция (2026-04-26)**: roadmap `docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md`. Backup snapshots всех 11 коллекций (E5 baseline) в `docker_qdrant_snapshots` volume + копия `E:/Transfer folder/qdrant/1c-pre-qwen3-2026-04-26/`, manifest `docs/roadmap/260426_PHASE_8_PRE_QWEN3_BACKUP_MANIFEST.json`. Скрипты для шагов 8.1–8.4 (uninstall CPU torch → cu128 install → Qwen3 download → benchmark): `scripts/phase8_run.ps1` + `scripts/bench_qwen3_embedding.py`. Запускать **вне** активной Claude Code сессии (нужно остановить MCP-серверы)

## Research

При вопросах про 1С: документация 8.3.27 — первоисточник. Внешние источники (its.1c.ru, infostart.ru) — только дополнение. Каждый факт с атрибуцией. Протокол: skill `1c-doc-research`.

При вопросах про RAG/ML/Python: протокол в skill `tech-research`.
