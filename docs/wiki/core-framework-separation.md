---
confidence: 0.85
created_at: 2026-04-20 10:00:00+00:00
related:
- '[[_index]]'
- '[[overview]]'
- '[[triad-architecture]]'
- '[[patterns]]'
- '[[bsl-integration]]'
sources:
- '[CLAUDE.md](../../CLAUDE.md)'
- '[01.2 Архитектура](../framework documentation/01_ОБЗОР/01.2_Архитектура.md)'
status: active
tags:
- architecture
- structure
- conventions
- boundaries
title: Core / Framework Separation
unified_id: 019e1e30-10a9-7781-950e-c396bbd3d66b
updated_at: 2026-05-14 23:30:00+00:00
---

# Core / Framework Separation

Архитектурная граница между **переиспользуемым ядром** (`src/pdf_framework/`) и **application-кодом** (REST API / CLI / MCP / UI / workers). Цель — `pdf_framework` устанавливается как библиотека через `pip install pdf-framework`, application слои живут отдельно и потребляют ядро через публичный API.

## Слои

### Core: `src/pdf_framework/`

Reusable library. **Не знает** про FastAPI, Typer, Gradio, MCP. Содержит только провайдеры, стратегии, чейны, схемы:

```
src/pdf_framework/
  loaders/        ← PDF loading (provider pattern: pymupdf, pdfplumber, docling)
  processing/     ← Splitting, cleaning, metadata enrichment
  embeddings/     ← Embedding providers (TEI, local, OpenAI, Jina, BGE, GIGA)
  vector_store/   ← Qdrant / ChromaDB / FAISS (single ABC)
  graph_store/    ← NetworkX / Neo4j (single ABC)
  search/         ← 14 стратегий + reranking
  agents/         ← 10 RAG-агентов (LangGraph)
  indexing/       ← Pipelines, hybrid loader, wiki exporter
  tools/          ← LangChain tools
  chains/         ← LangChain chains
  schemas/        ← Pydantic data contracts
  config/         ← pydantic-settings
  evaluation/     ← RAGAS, AutoRAG, benchmarks
  guardrails/     ← I/O validation
  observability/  ← Tracing, logging, metrics
  ...
```

Правила core:
- **Async-first**: все I/O async
- **Provider pattern**: каждое хранилище / embedding / loader наследует `*/base.py` ABC
- **Pydantic v2 schemas**: контракты данных в `schemas/`
- **Configuration через `pydantic-settings`** + `.env`
- **No application concerns**: no FastAPI routes, no Typer commands, no UI rendering

### App: entrypoints

Конкретные точки входа, потребляющие core:

| Слой | Где | Технология | Назначение |
|---|---|---|---|
| REST API | `src/api/` | FastAPI | 40+ endpoints, 18 групп роутеров, JWT auth, multitenancy middleware |
| CLI | `src/cli/` | Typer | 11+ команд (`python -m src.cli`) |
| MCP Server | `src/mcp_server/` | FastMCP | 15 tools для Claude Code |
| Web UI | `src/ui/` | Gradio | 5 страниц (Chat, Search, Documents, Graph, Settings) |
| Workers | `src/workers/` | ARQ | Background jobs (длинные индексации, evaluation runs) |

Правила app:
- App импортирует core, **core не импортирует app** (направленность зависимости)
- Каждый app-слой — отдельный модуль, удаление его не ломает остальные
- Application configuration (host/port/CORS) живёт в app-слое, не в core

### Adjacent: BSL и инструменты

Не «core», не «app» — параллельные подсистемы:

- `src/bsl/` — Python-инструменты для 1С (semantic_search, mcp_server, mcp_integration, sonar, finetuning)
- `src/memory/` — unified memory system (ai_memory, vector_memory, skill_learning, orchestrator)
- `src/shared/` — пересекающиеся утилиты (llm_rotation сервис)
- `tools/` — Node.js / Python-инструменты (auto-documenter, bsl-debugger, ast-grep-mcp)

См. [[bsl-integration]] для деталей 1С-слоя.

## Direction of dependencies

```
app/ ──→ pdf_framework/         (allowed: app may consume core)
app/ ──→ schemas/                (allowed: shared data contracts)

pdf_framework/ ──×── api/        (forbidden: core never imports FastAPI)
pdf_framework/ ──×── cli/        (forbidden: core never imports Typer)
pdf_framework/ ──×── ui/         (forbidden)
pdf_framework/ ──×── mcp_server/ (forbidden)

bsl/ ──→ pdf_framework/          (allowed: BSL tooling uses core embeddings/search)
bsl/ ──×── api/                  (avoid: BSL is its own subsystem)

memory/ ──→ pdf_framework/       (allowed via shared schemas)
memory/ ──→ shared/              (allowed)
```

Регрессии в этой направленности — флажок для review.

## Public surface (что экспортируется)

`pdf_framework/__init__.py` экспортирует основные классы (`Settings`, `QuickRAG`, провайдеры) через `__all__`. Application слои импортируют через namespace `from src.pdf_framework import ...`.

`schemas/` целиком публичный — это контракт между core и app, изменение схемы = breaking change.

## Расширение

Добавить новый provider (например, Pinecone):
1. Реализовать `BasePineconeStore(BaseVectorStore)` в `vector_store/providers/pinecone.py`
2. Зарегистрировать в `vector_store/__init__.get_vector_store()` (provider registry)
3. Никаких изменений в `api/` или `cli/` — switchover через `VECTOR_STORE__PROVIDER=pinecone` в `.env`

Добавить новый CLI subcommand:
1. Добавить функцию в `cli/main.py` (или подмодуль)
2. **НЕ** трогать `pdf_framework/` — функциональность уже в core, CLI только wrapper

См. [[patterns]] для конкретных реализаций (Provider Pattern, Factory, Strategy).
