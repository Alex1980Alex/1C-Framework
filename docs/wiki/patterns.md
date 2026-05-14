---
confidence: 0.85
created_at: 2026-04-20 10:00:00+00:00
related:
- '[[_index]]'
- '[[overview]]'
- '[[triad-architecture]]'
- '[[ralph-wiggum]]'
- '[[hooks-reference]]'
- '[[bsl-integration]]'
- '[[core-framework-separation]]'
- '[[SCHEMA]]'
sources:
- '[docs/architecture/PATTERNS.md](../architecture/PATTERNS.md)'
- '[.claude/skills/framework-patterns/SKILL.md](../../.claude/skills/framework-patterns/SKILL.md)'
status: active
tags:
- meta
- index
- patterns
- architecture
- automation
title: Patterns Index
unified_id: 019e1e30-10a6-70c2-bb80-e259a9413623
updated_at: 2026-05-14 23:30:00+00:00
---

# Patterns Index

Wiki-уровневый каталог 28 паттернов фреймворка: 15 архитектурных (`src/pdf_framework/`) + 13 паттернов автоматизации (`.claude/hooks/`). Каждый паттерн вынесен в отдельную страницу в [`docs/wiki/patterns/`](patterns/) для точечной ссылаемости из других wiki-страниц и из BSL/Python кода через double-bracket syntax (Obsidian-совместимый).

Каноническая deep-документация со схемами + кодом — [`docs/architecture/PATTERNS.md`](../architecture/PATTERNS.md). Skill — [`framework-patterns`](../../.claude/skills/framework-patterns/SKILL.md).

## 1. Архитектурные паттерны (15)

Используются ядром фреймворка — провайдеры, стратегии, чейны, агенты. Все имеют ABC + 2-3 реализации.

| # | Паттерн | Wiki | Где живёт | Пример |
|---|---|---|---|---|
| 1.1 | Provider Pattern | [[provider-pattern]] | `vector_store/`, `graph_store/`, `embeddings/` | Qdrant / ChromaDB / FAISS — single ABC, swap через `.env` |
| 1.2 | Strategy Pattern | [[strategy-pattern]] | `search/strategies/` | 14 стратегий (BM25, Vector, Hybrid, Section-First, GraphRAG, …) |
| 1.3 | DI Container | [[di-container]] | `api/dependencies/` | FastAPI `Depends()` — Components, Auth |
| 1.4 | Abstract Base Class | [[abstract-base-class]] | `*/base.py` повсюду | `BaseVectorStore`, `BaseGraphStore`, `BaseEmbedder` |
| 1.5 | Registry | [[registry]] | Plugin discovery | Search strategy registry, agent registry |
| 1.6 | Factory | [[factory]] | `get_*_store()` функции | `get_vector_store()` читает settings → возвращает provider |
| 1.7 | Template Method | [[template-method]] | Loader/Splitter cycles | `BaseLoader.load()` → подклассы переопределяют `_extract()` |
| 1.8 | Composite | [[composite]] | Hybrid Loader | PyMuPDF + fitz tables + Docling + Vision OCR в одной обёртке |
| 1.9 | Router / Classifier | [[router-classifier]] | Turbo Classifier, Adaptive RAG | Rule-based + LLM-based маршрутизация запроса |
| 1.10 | Pipeline | [[pipeline]] | Indexing, Search | Loader → Splitter → Embedder → Store |
| 1.11 | State Machine | [[state-machine]] | LangGraph, Ralph | Узлы и переходы в RAG-агентах |
| 1.12 | Singleton | [[singleton]] | Connection pools | Qdrant client, Neo4j driver |
| 1.13 | Adapter | [[adapter]] | OpenAI-compatible API | FastAPI route translates OpenAI schema → internal call |
| 1.14 | Observer | [[observer]] | EventBus, callbacks | `IncrementalGraphUpdater` подписка через event bus |
| 1.15 | Change Detector | [[change-detector]] | File watcher, reverse sync | mtime/sha1 diff → re-index только delta |

## 2. Паттерны автоматизации (13)

Используются хуками Claude Code и enforcer'ами. Многие специфичны для этого проекта, реализуют 3-уровневую защиту (создание → напоминание → блокировка).

| # | Паттерн | Wiki | Где живёт | Пример |
|---|---|---|---|---|
| 2.1 | BaseHook Protocol | [[base-hook-protocol]] | `.claude/hooks/base.py` | Все хуки наследуют `BaseHook.execute(input) → output` |
| 2.2 | SessionState | [[session-state]] | `.claude/cache/`, `data/` | JSON-persisted per-session counters / cookies |
| 2.3 | Three-Tier Pipeline | [[three-tier-pipeline]] | `code-skill-enforcer` | Levels A-G: pattern → skill → research → verify |
| 2.4 | Multi-Level Enforcement | [[multi-level-enforcement]] | task-enforcer + git-commit-enforcer + docs-change-enforcer | 3 Stop-хука цепочкой |
| 2.5 | Stop Gate | [[stop-gate]] | All `Stop` hooks | Exit code 2 + блокировка через `systemMessage` |
| 2.6 | Guard Gate | [[guard-gate]] | `bulk-action-guard`, `root-clutter-guard` | PreToolUse: блок до выполнения tool |
| 2.7 | Silent Observer | [[silent-observer]] | `posttooluse-*-tracker.py` | Запись метрик без `systemMessage` |
| 2.8 | Invocation Logger | [[invocation-logger]] | `mcp-invocation-logger.py` | Унифицированный лог `data/hook-invocations.jsonl` |
| 2.9 | Config-Driven Routing | [[config-driven-routing]] | `skill-router-config.json` | Bundles + scoring (keyword + fuzzy + TF-IDF) |
| 2.10 | Router-Classifier | [[router-classifier]] | UPS hooks | Rule-based детекция намерения по prompt |
| 2.11 | Fuzzy Intent Detection | [[fuzzy-intent-detection]] | Skill Router Layer B | RapidFuzz token-set ratio для опечаток |
| 2.12 | Task Master | [[task-master]] | `shared/task_master.py` | Pending tasks API: add/complete/get/sync |
| 2.13 | Error Classifier | [[error-classifier]] | `llm_rotation/` | Классификация Anthropic API ошибок → retry/fallback |

## Вспомогательные паттерны

Не входят в основную таблицу, но реализованы в `patterns/`:

- [[circuit-breaker]] — `llm_rotation/` устранение каскадного отказа провайдеров

## Использование из кода

Чтобы сослаться на паттерн из BSL- или Python-кода:

```python
# Source: [[provider-pattern]]
class QdrantStore(BaseVectorStore):
    """Provider реализация для Qdrant. См. [[provider-pattern]]."""
```

В docstring указывается источник через double-bracket-обёрнутый pattern slug (например, `Source:` плюс slug в двойных квадратных скобках). Любой из форматов `Source: ...` или `См. ...` ловится `framework-patterns` skill'ом для cross-reference аудита. Конкретный пример см. в [[provider-pattern]] и других страницах [`docs/wiki/patterns/`](patterns/).

## Развитие

Новые паттерны добавляются в `docs/wiki/patterns/<slug>.md` + регистрация в этой таблице + (опционально) deep-описание в `docs/architecture/PATTERNS.md`. Bidirectional links: страница паттерна обязана включать `[[patterns]]` в `related`.
