---
confidence: 0.9
created_at: 2026-04-20 10:00:00+00:00
related:
- '[[_index]]'
- '[[SCHEMA]]'
- '[[triad-architecture]]'
- '[[ralph-wiggum]]'
- '[[hooks-reference]]'
- '[[skills-reference]]'
- '[[patterns]]'
- '[[bsl-integration]]'
- '[[core-framework-separation]]'
sources:
- '[CLAUDE.md](../../CLAUDE.md)'
- '[01.1 Введение](../framework documentation/01_ОБЗОР/01.1_Введение.md)'
- '[01.2 Архитектура](../framework documentation/01_ОБЗОР/01.2_Архитектура.md)'
- '[01.3 Технологический стек](../framework documentation/01_ОБЗОР/01.3_Технологический_стек.md)'
status: active
tags:
- meta
- overview
- architecture
- entrypoints
title: Framework Overview
unified_id: 019e1e30-10a7-7db1-9226-669a6066e1cf
updated_at: 2026-05-14 12:00:00+00:00
---

# Framework Overview

PDF Vector & Graph Framework — async-first Python 3.11+ платформа для интеллектуальной обработки PDF: семантический и графовый RAG поверх Qdrant + NetworkX/Neo4j, оркестрация через LangGraph, 6 entrypoints (Web UI, REST, CLI, MCP, Python, OpenAI-compatible). Эта страница — wiki-уровень навигации; deep-tech описания живут в [`docs/framework documentation/01_ОБЗОР/`](../framework%20documentation/01_ОБЗОР/).

## Архитектура — 6 слоёв

```
INTERFACES (вход)
  Web UI │ REST API │ CLI │ MCP │ Python │ OpenAI-compat
            ▼
RAG-АГЕНТЫ (LangGraph)
  Self-RAG │ Adaptive │ Deep Research │ Plan-Execute │ Multi-Agent
            ▼
ПОИСК (SearchManager, 14 стратегий)        ГРАФ (LightRAG/GraphRAG)
  Vector │ BM25 │ Hybrid │ Section-First   Entities │ Relations │ Communities
            ▼                                     ▼
ОБРАБОТКА (Hybrid Loader → Pipeline → Chunks)
            ▼
ХРАНЕНИЕ
  Qdrant (4096d Qwen3) │ SQLite FTS5 (BM25) │ NetworkX/Neo4j │ SQLite (parent/cache/feedback)
            ▼
ОЦЕНКА
  RAG Triad │ RAGAS │ AutoRAG │ Regression
```

Каноническая глубокая версия — [01.2 Архитектура](../framework%20documentation/01_ОБЗОР/01.2_Архитектура.md).

## Entrypoints

| Интерфейс | Технология | Порт | Канон |
|---|---|---|---|
| Web UI | Gradio | 7860 | 5 вкладок (Chat / Search / Documents / Graph / Settings) |
| REST API | FastAPI | 8000 | 40+ endpoints, 18 групп роутеров |
| OpenAI-compat | FastAPI | 8000 | `/v1/chat/completions` для OpenAI SDK |
| CLI | Typer | — | 11+ команд (`python -m src.cli`) |
| MCP Server | FastMCP | — | 15 tools для Claude Code |
| Python API | QuickRAG | — | RAG в 3 строки кода |

## Потоки данных

**Индексация:** PDF → Hybrid Loader (PyMuPDF4LLM + fitz tables + Docling + Vision OCR) → Pipeline (split + metadata + contextual retrieval) → TEI Qwen3-Embedding-8B (4096d) → {Qdrant dense, FTS5 BM25, NetworkX/Neo4j entities, Parent Store}.

**Поиск:** Запрос → Turbo Classifier (rule-based 0 ms) → {simple: BM25 5 ms; moderate: Hybrid + Reranker; complex: Adaptive RAG → Decomposition → Multi-step → Synthesis}.

**RAG:** Self-RAG → SearchManager → grading (asyncio.gather) → optional rewrite → Claude Opus генерация → hallucination check → grounded? → ответ / regeneration.

## Tech stack (production, Phase 8+9.1 — 2026-04-30)

| Слой | Что |
|---|---|
| Main LLM | Claude Opus 4.6 |
| Fast LLM / grading / hallucination | Claude Sonnet 4.5 |
| Embedding | **Qwen3-Embedding-8B 4096d** через TEI Docker (`pdf-rag-tei`) — production default, MTEB-Code 80.68, 32K context |
| Vector store | Qdrant v1.17.1 — 10 коллекций × 4096d cosine, 80 908 точек |
| Graph store | NetworkX (primary) / Neo4j (optional) |
| BM25 | SQLite FTS5 + pymorphy3 (русская лемматизация) |
| Agent framework | LangGraph + LangChain |
| Web framework | FastAPI |
| UI | Gradio |
| CLI | Typer |
| MCP | FastMCP |

Полная таблица провайдеров (Jina, BGE-M3, GIGA, ColPali, ChromaDB, pgvector) — [01.3 Технологический стек](../framework%20documentation/01_ОБЗОР/01.3_Технологический_стек.md).

## Память — 5 слоёв

Каноническая схема — [[SCHEMA]] (5-layer retrieval, frontmatter, naming rules, promotion lifecycle):

| Layer | Storage | Weight |
|---|---|---|
| L1 episodic | SQLite `memory_ai.db` | 0.30 |
| L2 semantic | Qdrant `learned_patterns` (4096d) | 0.35 |
| L3 wiki canonical | `docs/wiki/entities/` + hub pages | 0.20 |
| L4 user memory | `MEMORY.md` | 0.15 |
| L5 wiki drafts | `docs/wiki/drafts/` | 0.20 (active session) |

`MemoryCube.to_wiki_page()` / `from_wiki_page()` round-trip между L2 и L3/L5. memory-first-hook v3 делает 4-layer RRF над L1+L2+L4+L3.

## Автоматизация — триада Hooks + Skills + MCP

См. [[triad-architecture]] и skill `hooks-skills-mcp-triad`:

| Слой | Кол-во | Роль |
|---|---|---|
| Hooks | 48 | КОГДА (event-driven: routing, enforcement, docs-tracking, MCP/slash audit) |
| Skills | 86 | КАК / ЧТО (5 domain + 8 infra + 17 framework + 10 LangChain + 9 CC + 1 sandbox + 9 1С + ...) |
| Skill Router | 16 bundles | 3-layer scoring (keyword + fuzzy + TF-IDF, v9) |
| MCP tools | 15 | ЧЕМ (search, index, graph, analyze, research, debug) |

Self-correction loop — [[ralph-wiggum]] (11 точек интеграции). 1С Pipeline (`/analyze-1c-task` → `/implement-1c-task` → `/write-1c-tests` → `/run-1c-tests`) — [[bsl-integration]].

## Снимок масштаба

| Параметр | Значение |
|---|---|
| Фаз реализовано | 75+ (Phases 1-30, 44-78+) |
| Python файлов | 444+ |
| LOC | 87 000+ |
| Стратегий поиска | 14 |
| RAG-агентов | 10 |
| Qdrant коллекций | 10 × 4096d Qwen3 = 80 908 точек |
| Wiki entities | 2 822 |
| Wiki patterns | 28 |
| ADR | 7 |

## Навигация

**Wiki:**

- [[_index]] — карта всех hub-страниц
- [[SCHEMA]] — wiki-формат, frontmatter, naming, promotion lifecycle
- [[triad-architecture]] — Hooks + Skills + MCP детально
- [[ralph-wiggum]] — автономный цикл и self-correction
- [[hooks-reference]] · [[skills-reference]] · [[patterns]]
- [[bsl-integration]] — 1С Enterprise pipeline
- [[core-framework-separation]] — где живут hooks/skills/code

**Deep docs (вне wiki):**

- [01.1 Введение](../framework%20documentation/01_ОБЗОР/01.1_Введение.md) · [01.2 Архитектура](../framework%20documentation/01_ОБЗОР/01.2_Архитектура.md) · [01.3 Технологический стек](../framework%20documentation/01_ОБЗОР/01.3_Технологический_стек.md)
- [Chapter 31 — Qwen3 Retrieval Production](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md) (Phase 8+9.1 production state)
- [CLAUDE.md](../../CLAUDE.md) — project root context для AI-агентов
