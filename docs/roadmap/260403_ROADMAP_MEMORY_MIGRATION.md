# ROADMAP: Миграция Unified Memory System

**Дата:** 2026-04-03 (обновлено 2026-04-04 — P0.5 завершена с Russian stemming)
**Проект:** Перенос компонентов Unified Memory из `D:\1C-Enterprise_Framework` в `D:\1С-Framework\src\memory\`
**Статус:** В РАБОТЕ — P0 DONE, P0.5 DONE, P1 DONE

---

## 1. Сводка миграции

### 1.1 Общая статистика

| Метрика | Источник | Цель (текущая) | Цель (план) |
|---------|----------|----------------|-------------|
| Файлов | 198 | 12 | ~45-55 |
| MCP Tools | 72+ | 18 | 35-40 |
| Подсистемы | 5 (orchestrator, unified-mcp, vector, skill, ai) | 4 (orchestrator, vector, skill, ai) | 4 (расширенные) |
| Бэкенды | TimescaleDB + Neo4j + Qdrant + Redis + SQLite | SQLite + Qdrant + JSONL | SQLite + Qdrant + JSONL (без изменений) |
| Тесты | 20+ файлов | 1 файл (26 тестов) | 4+ файла (~80 тестов) |

### 1.2 Оценка трудозатрат

| Приоритет | Фаза | Часы (raw) | Экономия (reuse) | Часы (итог) | Обязательность |
|-----------|-------|------------|------------------|-------------|----------------|
| **P0** | Критический оркестратор | 40-50 | -13ч (Hybrid RRF, Qdrant, Config) | **27-37** | ✅ DONE |
| **P0.5** | Memory-First Hook + Stemming | 4-6 | 0 | **~5** | ✅ DONE |
| **P1** | Инфраструктура и пропагация | 35-45 | -12ч (CircuitBreaker, Backoff, NetworkX) | **23-33** | ОБЯЗАТЕЛЬНО |
| **P2** | Продвинутый поиск и сервисы | 40-50 | -16ч (BM25, Cache, Rerankers, Metrics) | **24-34** | ОБЯЗАТЕЛЬНО |
| **P3** | Realtime и адаптеры | 50-65 | -4ч (Logger) | **46-61** | Опционально |
| **P4** | MCP Tools расширение | 25-35 | 0 | **25-35** | Опционально |
| | **ИТОГО (raw)** | **194-251** | **-45ч** | **149-206** | |

> Экономия ~25% за счёт переиспользования 12 компонентов из `pdf_framework/` и `shared/`

### 1.3 Стек технологий: адаптация

| Компонент | Исходный стек | Целевой стек | Стратегия |
|-----------|---------------|--------------|-----------|
| Реляционные данные | TimescaleDB | SQLite | Перенос с упрощением схем |
| Векторное хранилище | Qdrant (768d) | Qdrant (1024d, E5) | Без изменений |
| Графовые данные | Neo4j | SQLite (adjacency list) | Упрощение до реляционной модели |
| Кэширование | Redis | in-memory LRU + SQLite | Упрощение для single-process |
| Очереди/События | Redis Streams | asyncio.Queue + SQLite WAL | Embedded решение |
| Логирование | Custom logger | Python logging + structlog | Стандартизация |

---

## 2. Архитектурная диаграмма (Целевое состояние)

```
D:\1С-Framework\src\memory\
|
+-- orchestrator/
|   +-- unified_id.py              [EXISTS]
|   +-- link_registry.py           [EXISTS]
|   +-- unified_search.py          [EXISTS -> ENHANCE]
|   +-- memory_orchestrator.py     [MIGRATE: P0]
|   +-- memory_router.py           [MIGRATE: P0]
|   +-- propagation_engine.py      [MIGRATE: P1]
|   +-- search/
|       +-- hybrid_search.py       [MIGRATE: P2]
|       +-- bsl_scorer.py          [MIGRATE: P2]
|       +-- result_merger.py       [MIGRATE: P2]
|
+-- ai_memory/
|   +-- server.py                  [EXISTS -> EXTEND]
|   +-- adapters/
|   |   +-- base.py                [MIGRATE: P1]
|   +-- services/
|       +-- audit_service.py       [MIGRATE: P1]
|       +-- versioning_service.py  [MIGRATE: P2]
|       +-- ttl_service.py         [MIGRATE: P2]
|
+-- vector_memory/
|   +-- server.py                  [EXISTS -> EXTEND]
|   +-- models.py                  [EXISTS]
|   +-- graph/
|   |   +-- algorithms.py          [MIGRATE: P2]
|   |   +-- relation_types.py      [MIGRATE: P2]
|   +-- services/
|       +-- forgetgate_service.py  [MIGRATE: P2]
|
+-- skill_learning/
|   +-- server.py                  [EXISTS -> EXTEND]
|   +-- merge_patterns.py          [MIGRATE: P1]
|
+-- infrastructure/
|   +-- cache.py                   [MIGRATE: P2]
|   +-- circuit_breaker.py         [MIGRATE: P1]
|   +-- event_bus.py               [MIGRATE: P3]
|   +-- event_store.py             [MIGRATE: P3]
|   +-- metrics.py                 [MIGRATE: P2]
|   +-- retry.py                   [MIGRATE: P0]
|   +-- timeout.py                 [MIGRATE: P0]
|
+-- tests/
    +-- integration/
        +-- test_memory_unified.py [EXISTS -> EXTEND]
        +-- test_propagation.py    [NEW: P1]
        +-- test_search.py         [NEW: P2]
        +-- test_services.py       [NEW: P2]
```

---

## 3. Фазы миграции

### Фаза P0: Критический оркестратор (Core)

**Приоритет:** Критический
**Зависимости:** Нет
**Оценка:** 40-50 часов
**Цель:** Восстановить ядро оркестрации — маршрутизацию и координацию между тремя MCP-серверами.

**GitHub-паттерны для P0:**
- **MemCube abstraction** (MemOS) — единый dataclass-контейнер для всех подсистем
- **Auto-classify memory type** (Memori) — middleware interceptor в memory_router
- **Hybrid RRF search** (OpenCrabs) — переиспользовать `HybridSearchStrategy` из pdf_framework

**Переиспользование:** HybridSearchStrategy (-8ч), QdrantVectorStore (-3ч), Pydantic Settings (-2ч)

#### Таблица миграции P0

| Файл источника | Файл цели | Изменения | Оценка (ч) |
|----------------|-----------|-----------|------------|
| `memory-orchestrator/memory_orchestrator.py` | `orchestrator/memory_orchestrator.py` | Адаптация импортов, замена TimescaleDB на SQLite | 12-15 |
| `memory-orchestrator/memory_router.py` | `orchestrator/memory_router.py` | Упрощение роутинга для 3 бэкендов | 8-10 |
| `memory-orchestrator/unified_id.py` | `orchestrator/unified_id.py` | Сравнение, мерж если нужно | 2-3 |
| `memory-orchestrator/link_registry.py` | `orchestrator/link_registry.py` | Сравнение, мерж если нужно | 2-3 |
| `memory-orchestrator/unified_search.py` | `orchestrator/unified_search.py` | Замена stub на рабочую реализацию | 8-10 |
| `utils/retry.py` | `infrastructure/retry.py` | Извлечение, адаптация | 2-3 |
| `utils/timeout.py` | `infrastructure/timeout.py` | Извлечение, адаптация | 2-3 |

#### Чеклист P0

- [x] Создать директорию `infrastructure/` и `__init__.py`
- [x] Перенести `retry.py` -> `infrastructure/retry.py`
  - [x] Адаптировать импорты, добавить типизацию
  - [x] Покрыть тестами
- [x] Перенести `timeout.py` -> `infrastructure/timeout.py`
  - [x] Адаптировать импорты, добавить типизацию
  - [x] Покрыть тестами
- [x] Сравнить `unified_id.py` (источник vs цель)
  - [x] Мерж если есть различия
  - [x] Проверить обратную совместимость
- [x] Сравнить `link_registry.py` (источник vs цель)
  - [x] Мерж если есть различия, проверить схему SQLite
- [x] Перенести `memory_orchestrator.py`
  - [x] Заменить TimescaleDB коннекты на SQLite
  - [x] Адаптировать 8 MCP tools к текущим сигнатурам:
    - [x] `unified_search` — федеративный запрос к 3 серверам
    - [x] `route_and_save` — роутинг по целевым системам
    - [x] `get_full_context` — агрегация с graph traversal
    - [x] `create_link`, `get_related` — через LinkRegistry
    - [x] `propagate_update` — заглушка (для P1)
    - [x] `get_system_stats`, `health_check`
- [x] Перенести `memory_router.py`
  - [x] Упростить правила для 3 бэкендов (code->ai_memory, pattern->vector, skill->skill_learning)
  - [x] Убрать зависимости от Neo4j
- [x] MemCube abstraction (MemOS pattern) — `orchestrator/memcube.py`
  - [x] `MemoryCube` dataclass с полями identity/scoring/temporal/observations
  - [x] `ContentType` enum (fact/preference/rule/skill/code/observation)
  - [x] Конвертеры: `to_ai_memory_row()`, `to_vector_memory_payload()`, `to_skill_learning_record()`
- [x] Auto-classify middleware (Memori pattern) — `memory_router.py`
  - [x] `ContentClassifier` — regex-based middleware перед роутингом
  - [x] `ClassificationResult` dataclass (content_type, confidence, signals)
  - [x] Фаза 0 в `MemoryRouter.route()` — auto-detect fact/preference/rule/skill/code
  - [x] `classify_content()` — публичный API для внешнего использования
- [x] Hybrid RRF search (OpenCrabs/ClawMem pattern) — `unified_search.py`
  - [x] `RRFMerger` — Reciprocal Rank Fusion с source weights и k-parameter
  - [x] Нормализация RRF scores к [0, 1] шкале
  - [x] 60% RRF rank + 40% quality signal комбинирование
  - [x] `SearchOptions.rrf_enabled` / `rrf_k` / `rrf_source_weights` конфигурация
  - [x] Fallback на legacy `ScoreNormalizer` при `rrf_enabled=False`
- [x] Интеграционные тесты
  - [x] Тест маршрутизации по типам контента (24 теста)
  - [x] Тест федеративного поиска (26 тестов)
  - [x] Тест создания связей (18 тестов)
- [x] Проверить обратную совместимость: 68/68 тестов проходят

---

### Фаза P0.5: Memory-First Hook (Auto-Context) — DONE ✅

**Приоритет:** Критический
**Зависимости:** P0 (unified_search должен работать)
**Оценка:** 4-6 часов → **Факт: ~5 часов**
**Статус:** ЗАВЕРШЕНА (2026-04-04)
**Цель:** Обеспечить автоматический поиск в памяти **перед** каждым ответом Claude — любой вопрос/просьба опирается на сохранённый контекст из предыдущих сессий.

**Проблема:** MCP-серверы памяти — это инструменты, которые Claude вызывает **по своему решению**. Без этой фазы Claude может "забыть" проверить память и ответить с нуля.

**Решение (реализация):** UserPromptSubmit hook, который:
1. Получает текст запроса пользователя (stdin JSON)
2. Читает локальные memory-файлы из `MEMORY.md` индекса (без MCP/HTTP зависимостей)
3. Выполняет token-based поиск с weighted scoring (name×3, desc×2, body×1)
4. Возвращает топ-3 релевантных записей как `systemMessage`
5. Claude получает контекст памяти **до** начала обработки запроса

> **Отличие от плана:** Вместо вызова `unified_search` через HTTP/subprocess — прямое чтение
> локальных `.md` файлов памяти. Это устраняет зависимость от MCP-сервера, снижает latency
> и гарантирует работу даже при отключённых MCP-серверах. Federaged MCP search можно
> добавить как upgrade в будущем.

**Архитектура (реализованная):**

```
User prompt (stdin JSON)
  ↓
UserPromptSubmit hook (memory-first-hook.py)
  ↓
load_all_memories() — чтение .md файлов из MEMORY_DIR
  ├── Парсинг YAML frontmatter (name, description, type)
  ├── Fallback: glob *.md если MEMORY.md пуст
  └── Tokenization + Russian stemming
  ↓
search_memories(prompt, memories) — weighted token overlap
  ├── name tokens × 3 (strongest signal)
  ├── description tokens × 2
  └── body tokens × 1
  ↓
score = 0.7 × query_coverage + 0.3 × memory_density
  ↓
systemMessage: "[MEMORY CONTEXT] Found {n} relevant memories..."
  ↓
Claude отвечает С УЧЁТОМ памяти
```

**Формат systemMessage:**

```
[MEMORY CONTEXT] Found {n} relevant memories for your query:
1. [{type}] {title} — {snippet} (confidence: {score})
2. [{type}] {title} — {snippet} (confidence: {score})
3. [{type}] {title} — {snippet} (confidence: {score})
Use this context to inform your response. If memory conflicts with current code, trust current code.
```

**Оптимизации (реализованные):**
- **Минимальная длина запроса:** skip для prompt < 20 chars (приветствия, /commands)
- **Cooldown:** не чаще 1 раза в 30 секунд (файл `cache/memory-first-cooldown.json`)
- **Threshold:** score < 0.3 → не включать (низкорелевантный шум)
- **Timeout:** max 2 секунды (threading-based, Windows-compatible)
- **Skip patterns:** `/command`, однословные запросы
- **Russian stemming:** суффиксный стриппер для русских словоформ (29 суффиксов, 3/2/1-char)
- **Graceful degradation:** при любой ошибке → `{"continue": true}`, лог в `cache/hooks-error.log`

**Russian Stemming (v1.1):**

| Словоформа | Стем | Суффикс |
|-----------|------|---------|
| агенты | агент | -ы |
| агентов | агент | -ов |
| агентам | агент | -ам |
| агентами | агент | -ами |
| документации | документаци | -и |
| документацию | документаци | -ю |
| конфигурации | конфигураци | -и |

> Английские токены не стеммируются (работают хорошо без стемминга).
> Минимальная длина стема: 3 символа. Только кириллические токены обрабатываются.

#### Чеклист P0.5

- [x] Создать `.claude/hooks/memory-first-hook.py`
  - [x] Парсинг stdin (UserPromptSubmit JSON формат)
  - [x] Чтение локальных memory-файлов (MEMORY.md индекс + frontmatter парсинг)
  - [x] Token-based поиск с weighted scoring
  - [x] Форматирование systemMessage
  - [x] Timeout 2s (threading) + graceful fallback
  - [x] Skip для коротких/служебных запросов
  - [x] Russian stemming (суффиксный стриппер, 29 суффиксов)
- [x] Зарегистрировать hook в `settings.json`
  - [x] `event: UserPromptSubmit`
  - [x] `command: python D:/1C-Enterprise_Framework/.claude/hooks/memory-first-hook.py`
- [x] Добавить инструкцию в CLAUDE.md:
  - [x] Секция "Memory Context (Auto-Injected by memory-first-hook)"
  - [x] "Trust code over memory", "Use as hints", "Check recency"
- [x] Тесты (`scripts/claude-backend/tests/test_memory_first_hook.py`): **41 тестов PASS**
  - [x] TestShouldSkip (8 тестов) — skip logic
  - [x] TestParseFrontmatter (4 теста) — YAML парсинг
  - [x] TestStemToken (9 тестов) — Russian stemming
  - [x] TestTokenize (7 тестов) — tokenization + stemming integration
  - [x] TestScoreMemory (6 тестов) — weighted scoring + Russian wordforms
  - [x] TestFormatMemoryContext (3 теста) — output formatting
  - [x] TestHookIntegration (4 теста) — subprocess end-to-end
- [x] Интеграционный тест: полный цикл (prompt → hook → memory → systemMessage)

#### Известные ограничения (для будущих фаз)

| Ограничение | Влияние | Решение |
|-------------|---------|---------|
| Только локальные .md файлы | Не ищет в MCP-серверах (vector, skill_learning) | Upgrade: добавить HTTP fallback к unified_search |
| Стемминг без морфологии | "конфигурация" → "конфигураци" (не идеально) | Pymorphy2 или snowball-stemmer |
| Кириллица/латиница не транслитерируются | "GLM" (lat) ≠ "ГЛМ" (cyr) | Добавить transliteration mapping |
| Нет semantic similarity | Только token overlap, не понимает синонимы | Upgrade: embedding-based search через Qdrant |

---

### Фаза P1: Инфраструктура и пропагация (Core)

**Приоритет:** Высокий
**Зависимости:** P0
**Оценка:** 35-45 часов
**Цель:** Восстановить граф-пропагацию confidence и базовые сервисы (circuit breaker, audit).

**GitHub-паттерны для P1:**
- **RFI scoring** (OpenMemory) — заменить linear decay на Recency x Frequency x Importance
- **Temporal fact invalidation** (Graphiti) — valid_from/valid_to в LearnedPattern
- **Structured observations** (Engram) — what/why/where/learned формат для save

**Переиспользование:** CircuitBreaker (-4ч), BackoffStrategy (-2ч), NetworkXStore (-6ч)

#### Таблица миграции P1

| Файл источника | Файл цели | Изменения | Оценка (ч) |
|----------------|-----------|-----------|------------|
| `memory-orchestrator/propagation_engine.py` | `orchestrator/propagation_engine.py` | Замена Neo4j на SQLite adjacency, адаптация BFS | 15-18 |
| `unified-memory-mcp/services/circuit_breaker.py` | `infrastructure/circuit_breaker.py` | Упрощение, убираем Redis | 4-5 |
| `unified-memory-mcp/services/audit_service.py` | `ai_memory/services/audit_service.py` | Адаптация под SQLite | 4-5 |
| `unified-memory-mcp/adapters/base.py` | `ai_memory/adapters/base.py` | Абстрактный базовый класс | 3-4 |
| `vector-memory-mcp/merge_patterns` | `skill_learning/merge_patterns.py` | Перенос логики слияния | 4-5 |

#### Чеклист P1

- [x] Перенести `propagation_engine.py`
  - [x] Заменить Neo4j граф на SQLite adjacency list
    - [x] ~~Таблица `edges` — уже в LinkRegistry~~
    - [x] ~~Индексы на source_id, target_id — уже в LinkRegistry~~
    - [x] Адаптировать BFS алгоритм (Neo4j Cypher -> SQL через LinkRegistry)
    - [x] Сохранить time decay + distance decay формулы
    - [x] Rate limiting через config (depth, entities, delta threshold)
    - [x] Background workers через asyncio.create_task
    - [x] Покрыть тестами (8 тестов)
- [x] Перенести `circuit_breaker.py`
  - [x] Убрать Redis зависимость, использовать in-memory state
  - [x] CircuitBreakerRegistry для multi-circuit management
  - [x] Покрыть тестами (12 тестов)
- [x] Перенести `audit_service.py`
  - [x] JSONL persistence (append-only) + in-memory buffer
  - [x] Immediate persist for destructive actions (DELETE, ROLLBACK)
  - [x] Deduplication in get_errors/query
  - [x] Покрыть тестами (9 тестов)
- [x] Создать `ai_memory/adapters/base.py`
  - [x] BaseMemoryAdapter ABC (save, search, get, delete, update, health_check)
  - [x] SaveRequest, SearchResult, BackendStats dataclasses
  - [x] Покрыть тестами (6 тестов)
- [x] Перенести `merge_patterns.py` в skill_learning
  - [x] PatternRecord dataclass with JSONL IO
  - [x] Conflict resolution (4 strategies: higher_confidence, newer, older, merge_all)
  - [x] Tag merging (union) + application count aggregation
  - [x] Backup before write + dry_run mode
  - [x] Покрыть тестами (7 тестов)
- [x] Интеграционные тесты: 39/39 tests pass
  - [x] Existing P0 tests: 68/68 pass (no regression)
  - [x] MemoryOrchestrator: propagate_update uses real PropagationEngine

---

### Фаза P2: Продвинутый поиск и сервисы (Core)

**Приоритет:** Средний
**Зависимости:** P0, P1
**Оценка:** 40-50 часов
**Цель:** Восстановить гибридный поиск, versioning, TTL, forgetgate, metrics.

**GitHub-паттерны для P2:**
- **ECL+memify** (Cognee) — self-improving graph: prune stale links, strengthen frequent edges
- **Two-tier memory** (Letta/MemGPT) — core (hot) + archival (cold) separation
- **Multi-signal retrieval** (ClawMem) — BM25+vector+graph+rerank через RRF

**Переиспользование:** BM25Store (-3ч), SemanticSearchCache (-4ч), Rerankers (-5ч), EvalMetrics (-3ч), FrameworkLogger (-1ч)

#### Таблица миграции P2

| Файл источника | Файл цели | Изменения | Оценка (ч) |
|----------------|-----------|-----------|------------|
| `search/hybrid_search.py` | `orchestrator/search/hybrid_search.py` | FTS5 вместо TimescaleDB | 8-10 |
| `search/bsl_scorer.py` | `orchestrator/search/bsl_scorer.py` | Прямой перенос | 3-4 |
| `search/result_merger.py` | `orchestrator/search/result_merger.py` | RRF алгоритм, прямой перенос | 3-4 |
| `services/versioning_service.py` | `ai_memory/services/versioning_service.py` | SQLite таблица versions | 5-6 |
| `services/ttl_service.py` | `ai_memory/services/ttl_service.py` | SQLite + asyncio cleanup | 4-5 |
| `services/forgetgate_service.py` | `vector_memory/services/forgetgate_service.py` | Адаптация под Qdrant payload | 5-6 |
| `graph/algorithms.py` | `vector_memory/graph/algorithms.py` | Без Neo4j, чистый Python/networkx | 6-8 |
| `graph/relation_types.py` | `vector_memory/graph/relation_types.py` | Прямой перенос | 1-2 |
| `utils/metrics.py` | `infrastructure/metrics.py` | In-memory counters без Prometheus | 3-4 |
| `services/cache.py` (Redis) | `infrastructure/cache.py` (LRU) | Полная переработка | 4-5 |

#### Чеклист P2

- [ ] Создать директории `orchestrator/search/`, `vector_memory/graph/`
- [ ] Перенести `hybrid_search.py`
  - [ ] SQLite FTS5 вместо TimescaleDB полнотекстового поиска
  - [ ] Гибридная формула скоринга (semantic + keyword)
- [ ] Перенести `bsl_scorer.py` + `result_merger.py`
- [ ] Перенести `versioning_service.py`
  - [ ] Таблица `versions(id, entity_id, version, data_json, created_at)`
  - [ ] Diff + rollback функциональность
- [ ] Перенести `ttl_service.py`
  - [ ] Таблица `ttl_registry(id, entity_id, expires_at)`
  - [ ] Background cleanup через asyncio
- [ ] Перенести `forgetgate_service.py`
  - [ ] Алгоритм "забывания" адаптирован под Qdrant payload
  - [ ] Surprise detection (отклонение от паттернов)
- [ ] Перенести `graph/algorithms.py`
  - [ ] SQLite + networkx (или чистый Python)
  - [ ] Shortest path, centrality metrics
- [ ] Перенести `cache.py` (LRU на OrderedDict, TTL, max size)
- [ ] Перенести `metrics.py` (in-memory counters, JSON export)
- [ ] Обновить `unified_search.py` для использования hybrid_search
- [ ] Интеграционные тесты: hybrid search, versioning+rollback, TTL expiry, forgetgate

---

### Фаза P3: Realtime и продвинутые адаптеры (Optional)

**Приоритет:** Низкий
**Зависимости:** P0, P1, P2
**Оценка:** 50-65 часов
**Цель:** Восстановить event bus, адаптировать docs_rag адаптер, добавить research/surprise/warmup tools.

#### 3.1 Realtime компоненты

| Модуль источника | Решение | Обоснование |
|------------------|---------|-------------|
| `event_bus.py` (Redis Pub/Sub) | Переписать на asyncio.Queue | Внутрипроцессная шина достаточна |
| `event_store.py` (TimescaleDB) | SQLite таблица `events` | JSONL hot buffer + SQLite cold |
| `subscriptions.py` (Redis) | In-memory dict | Подписчики в рамках одного процесса |
| `conflict_resolver.py` | Прямой перенос | Чистая логика, без внешних зависимостей |
| `websocket_server.py` | **НЕ ПЕРЕНОСИТЬ** | Нет клиентов |

Архитектура EventBus на asyncio:

```
EventBus (singleton)
  +-- _subscribers: dict[str, list[asyncio.Queue]]
  +-- _event_store: EventStore
  +-- publish(event) -> None
        +-- Запись в EventStore (SQLite + JSONL)
        +-- Рассылка в очереди подписчиков
```

**Оценка realtime:** 19 часов

#### 3.2 Адаптеры

| Адаптер | Технология | Решение | Причина |
|---------|-----------|---------|---------|
| `base` | ABC | Перенести | Основа интерфейса |
| `vector_memory` | Qdrant | Перенести | Базовый адаптер |
| `docs_rag` | RAG | Адаптировать | Полезный функционал, переписать на SQLite+Qdrant |
| `qdrant_official` | Qdrant SDK | НЕ переносить | Дублирует vector_memory |
| `ai_memory` | Neo4j+Qdrant | НЕ переносить | Neo4j исключен |
| `memory_ai` | TimescaleDB | НЕ переносить | TimescaleDB исключен |
| `memory_ai_direct` | TimescaleDB | НЕ переносить | Дублирует memory_ai |
| `anthropic` | Anthropic API | НЕ переносить | Deprecated |

**Оценка docs_rag адаптера:** 16 часов

#### 3.3 Дополнительные инструменты

| Tool | Назначение | Оценка (ч) |
|------|-----------|------------|
| `research` | Глубокий анализ связей и аномалий | 6 |
| `id_management` | UUIDv7, резолвинг конфликтов | 3 |
| `surprise` | Unexpectedness score для новых паттернов | 4 |
| `warmup` | Предзагрузка часто используемых данных в LRU | 3 |
| Тесты | Все вышеперечисленное | 5 |

**Итого P3: 50-65 часов**

#### Чеклист P3

- [ ] EventBus на asyncio.Queue (wildcard подписки, backpressure)
- [ ] EventStore на SQLite (JSONL hot buffer, SQLite cold)
- [ ] SubscriptionManager (in-memory dict, heartbeat)
- [ ] ConflictResolver (last-write-wins, source-priority, merge-fields)
- [ ] 8 MCP endpoints для realtime (subscribe, publish, replay, history...)
- [ ] docs_rag адаптер (SQLite chunks + Qdrant embeddings)
- [ ] research, id_management, surprise, warmup tools
- [ ] Интеграция EventBus в MemoryOrchestrator
- [ ] Тесты (unit + integration + нагрузочный)

---

### Фаза P4: MCP Tools расширение (Optional)

**Приоритет:** Низкий
**Зависимости:** P0-P2 (P3 для realtime tools)
**Оценка:** 25-35 часов
**Цель:** Оформить оставшуюся функциональность как MCP endpoints.

#### Реестр инструментов

Из 45+ tools unified-memory-mcp, часть уже покрыта в P0-P2. Ниже — оставшиеся для регистрации:

| Tool | Покрыт фазой | Требует нового кода? |
|------|--------------|---------------------|
| `search`, `advanced_search` | P0 (unified_search) | Нет, обертка |
| `save` | P0 (route_and_save) | Нет, обертка |
| `analyze` | P3 (research) | Да, аналитика |
| `context` | P0 (get_full_context) | Нет, обертка |
| `graph_analysis` | P2 (algorithms) | MCP endpoint |
| `learning_stats` | EXISTS (skill-learning) | Расширить |
| `history` | P3 (event_store) | MCP endpoint |
| `audit` | P1 (audit_service) | MCP endpoint |
| `circuit` | P1 (circuit_breaker) | MCP endpoint |
| `health` | P0 (health_check) | Расширить |
| `metrics` | P2 (metrics) | MCP endpoint |
| `id_management` | P3 | MCP endpoint |
| `ttl` | P2 (ttl_service) | MCP endpoint |
| `versioning` | P2 (versioning_service) | MCP endpoint |
| `forgetgate` | P2 (forgetgate_service) | MCP endpoint |
| `surprise` | P3 | MCP endpoint |
| `warmup` | P3 | MCP endpoint |

#### Чеклист P4

- [ ] Зарегистрировать MCP endpoints для сервисов из P1-P2:
  - [ ] `memory_audit_log` — обертка над audit_service
  - [ ] `memory_circuit_status` — статус circuit breaker
  - [ ] `memory_metrics` — агрегированные метрики
  - [ ] `memory_ttl_set` / `memory_ttl_check` — управление TTL
  - [ ] `memory_version_history` / `memory_rollback` — версионирование
  - [ ] `memory_forget` — селективное удаление через forgetgate
  - [ ] `memory_graph_analyze` — граф-аналитика
- [ ] Расширить `learning_stats` для всех подсистем
- [ ] Расширить `health_check` для всех подсистем
- [ ] Обновить `.mcp.json` с новыми серверами
- [ ] Обновить skill `memory-unified/SKILL.md`
- [ ] Документация: описание каждого нового tool

---

## 4. Граф зависимостей фаз

```
P0 (Orchestrator Core)          ✅ DONE
 ├── P0.5 (Memory-First Hook)   ✅ DONE (local .md + Russian stemming)
 ├── P1 (Infrastructure + Propagation)  ✅ DONE
 │    └── P2 (Search + Services)  ← NEXT
 │         ├── P3 (Realtime + Adapters)  [optional]
 │         └── P4 (MCP Tools)            [optional]
 └── P4 может начаться параллельно с P2 для оберток P0-инструментов
```

> **P0.5 — ключевая фаза для UX:** именно она превращает memory из "инструмента по запросу" в "автоматический контекст каждой сессии". Без неё Claude может не обращаться к памяти. С ней — каждый ответ опирается на накопленные знания.
>
> **Промежуточный итог P0.5:** Реализация использует прямое чтение локальных `.md` файлов
> вместо HTTP-вызова unified_search. Это оказалось быстрее и надёжнее (нет зависимости от MCP-сервера).
> Russian stemming решает проблему словоформ (агенты/агентов/агентам → агент).
> 41 тест покрывает все компоненты. Upgrade до federated MCP search — опционален для P2+.

---

## 5. Что НЕ переносить

| Компонент | Причина | Альтернатива в целевом стеке |
|-----------|---------|------------------------------|
| **TimescaleDB** hypertable | Нет инфраструктуры, SQLite достаточен для масштаба | SQLite WAL mode |
| **Neo4j** native графы | Нет Docker-сервиса, SQLite adjacency list покрывает потребности | SQLite adjacency + networkx |
| **Redis** кэш/очереди | Избыточен для single-process, нет Redis сервера | in-memory LRU (OrderedDict) |
| **Prometheus** exporter | Нет Prometheus инфраструктуры | JSON metrics export в лог |
| **WebSocket** server | Нет внешних клиентов, MCP использует stdio | asyncio.Queue для внутренних событий |
| **Anthropic Memory API** adapter | Deprecated, нет requirements | Не нужен |
| **3 дублирующих адаптера** (memory_ai, memory_ai_direct, qdrant_official) | Дублируют vector_memory и ai_memory | Единый адаптер на подсистему |
| **Pipeline/Aggregator** tools (14 из 22 realtime) | Избыточны для MCP, нет WS клиентов | 8 базовых realtime tools |
| **monitoring_server.py** (HTTP) | Нет внешнего мониторинга | Логирование в stderr |

---

## 6. Риски и митигации

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Обратная несовместимость existing 18 tools | Средняя | Высокое | Каждая фаза начинается с прогона 26 existing тестов |
| SQLite adjacency медленнее Neo4j на больших графах | Низкая | Среднее | Индексы + LIMIT + кэширование BFS результатов |
| In-memory LRU теряется при перезапуске | Средняя | Низкое | Warm-up из SQLite при старте, persistence опционально |
| Propagation engine: deadlock при рекурсии | Низкая | Высокое | asyncio.Semaphore + max_depth ограничение |
| JSONL файлы skill_learning растут бесконечно | Средняя | Среднее | Ротация по размеру (10MB), архивация |
| Конфликт Qdrant коллекций (learned_patterns 768d -> 1024d) | Нет | Нет | Уже решено в текущей реализации (1024d E5) |

---

## 7. Метрики успеха

### По завершении P0-P2 (Core):

| Метрика | Текущее | Целевое | Benchmark (GitHub) |
|---------|---------|---------|-------------------|
| MCP Tools | 18 | 28-32 | — |
| Тесты | 26 | 60+ | — |
| Federated search | Stub | Hybrid RRF (reuse pdf_framework) | OpenCrabs: FTS5+vector RRF |
| Scoring | Linear decay | RFI (Recency x Frequency x Importance) | OpenMemory: RFI composite |
| Маршрутизация | Нет | Auto-classify + route_and_save | Memori: middleware interceptor |
| Confidence propagation | Нет | BFS + temporal invalidation | Graphiti: valid_from/valid_to |
| **Memory-First Hook** | ✅ Auto-context (local .md + stemming) | **Upgrade: federated MCP search** | Engram: auto-recall |
| Audit trail | Нет | Полный лог действий | — |
| Circuit breaker | Нет | Reuse из llm_rotation | — |
| Hybrid search | Нет | 4-signal (BM25+vector+graph+rerank) | ClawMem: multi-signal |
| Pattern merge | Нет | Слияние дубликатов | — |
| Versioning + rollback | Нет | Undo/redo для записей | — |
| Memory abstraction | 3 раздельных store | MemoryCube unified dataclass | MemOS: MemCube |
| Self-improving graph | Нет | memify (prune stale + strengthen) | Cognee: ECL+memify |
| Structured save | Нет | what/why/where/learned формат | Engram: observations |

### По завершении P3-P4 (Full):

| Метрика | Целевое | Benchmark (GitHub) |
|---------|---------|-------------------|
| MCP Tools | 35-40 | — |
| Тесты | 80+ | — |
| Event Bus | Внутрипроцессный pub/sub | — |
| Surprise detection | Anomaly scoring | — |
| Cache warmup | Предзагрузка из SQLite | — |
| Docs RAG adapter | SQLite + Qdrant integration | — |
| Prompt optimization | Memory improves agent prompts | LangMem: prompt optimizers |
| Two-tier memory | Core (hot) + Archival (cold) | Letta: core+archival |

### Целевые бенчмарки (LoCoMo dataset):

| System | Accuracy | Tokens/Query | Наш ориентир |
|--------|----------|-------------|-------------|
| Memori | 81.95% | 1,294 | Минимум 75% accuracy |
| Mem0 | Top tier | N/A | Референс по архитектуре |
| MemOS | +43.7% vs OpenAI | N/A | Паттерн MemCube |
| Наша цель (P2) | >75% | <2,000 | RFI + Hybrid RRF + Reranking |

---

## 8. GitHub Best Practices: ТОП-17 проектов (референсы)

| # | Проект (owner/repo) | Stars | Категория | Ключевые паттерны для нас |
|---|---|---|---|---|
| 1 | mem0ai/mem0 | ~51,500 | Universal Memory | hybrid triple-store (vector+KV+graph), auto fact extraction, 26% выше accuracy vs OpenAI Memory |
| 2 | MemoriLabs/Memori | ~12,400 | SQL-native Memory | middleware interceptor, auto-classify turns (facts/preferences/rules), confidence decay, 82% accuracy LoCoMo |
| 3 | memodb-io/memobase | active | Profile Memory | profile-centric (не conversation), event timelines, batch buffer, <100ms |
| 4 | letta-ai/letta (MemGPT) | very high | Stateful Agent | two-tier memory (core+archival), self-editing memory, agent serialization |
| 5 | NousResearch/hermes-agent | ~8,700 | Learning Agent | auto skill creation, MEMORY.md+USER.md, FTS SQLite |
| 6 | topoteretes/cognee | ~12,000 | Knowledge Graph | ECL pipeline, memify (prune stale, strengthen frequent), 14 retrieval modes |
| 7 | getzep/graphiti | notable | Temporal KG | valid_from/valid_to, hybrid retrieval, incremental graph updates |
| 8 | getzep/zep | notable | Context Engine | relationship-aware retrieval, sub-200ms latency |
| 9 | MemTensor/MemOS | ~7,300 | Memory OS | MemCube abstraction, 3 memory types, +43.7% vs OpenAI Memory |
| 10 | modelcontextprotocol/servers/memory | MCP official | MCP Memory | knowledge graph via MCP, JSONL persistence |
| 11 | Gentleman-Programming/engram | active | MCP Memory | SQLite+FTS5, Go binary, deferred tools, git sync |
| 12 | edg-l/engram-mcp | active | MCP Memory | confidence decay, dedup, relationship graphs, ONNX embeddings |
| 13 | adolfousier/opencrabs | active | Self-improving | daily log compaction, FTS5+vector RRF, curated MEMORY.md |
| 14 | CaviraOSS/OpenMemory | ~3,100 | Multi-sector | 5 секторов памяти, RFI scoring (Recency x Frequency x Importance), sparse graph |
| 15 | langchain-ai/langmem | active | LangChain Memory | memory managers, prompt optimization from memory |
| 16 | coolmanns/openclaw-memory-architecture | active | Reference Arch | 12 memory layers, activation/decay с 30d half-life |
| 17 | yoloshii/ClawMem | active | Multi-signal | BM25+vector+RRF+cross-encoder, composite scoring, self-evolving notes |

---

## 9. ТОП-10 архитектурных паттернов для адаптации

| # | Паттерн | Источник (проект) | Текущий GAP | Рекомендация для нашей системы | Фаза |
|---|---|---|---|---|---|
| 1 | RFI scoring (Recency x Frequency x Importance) | OpenMemory | Наш linear decay примитивен | Заменить exponential decay на RFI composite score в vector-memory | P1 |
| 2 | Temporal fact invalidation (valid_from/valid_to) | Graphiti | Нет validity windows | Добавить `valid_from`/`valid_to` в LearnedPattern model + auto-invalidation | P1 |
| 3 | MemCube abstraction (content+metadata, composable) | MemOS | 3 раздельных store без единого объекта | Создать `MemoryCube` dataclass — единый контейнер для всех подсистем | P0 |
| 4 | ECL+memify (self-improving graph) | Cognee | Граф статичен — связи не усиливаются | Добавить prune stale links + strengthen frequently-traversed edges | P2 |
| 5 | Hybrid RRF search (reuse) | OpenCrabs, ClawMem | Есть в pdf_framework, **отсутствует** в memory | Переиспользовать `HybridSearchStrategy` из `search/` | P0 |
| 6 | Structured observations (what/why/learned) | Engram | Save неструктурирован | title/type/content + what/why/where/learned формат в skill-learning | P1 |
| 7 | Prompt optimization from memory | LangMem | Уникальная фича, нет аналога | Experimental: память улучшает промпты агента | P4 |
| 8 | Auto-classify memory type | Memori | Нет автоклассификации | Middleware interceptor в memory_router: auto-detect fact/preference/rule/skill | P0 |
| 9 | Two-tier memory (core+archival) | Letta/MemGPT | Flat memory без приоритизации | Core (hot, in-memory) + Archival (cold, Qdrant) tier separation | P2 |
| 10 | Multi-signal retrieval (BM25+vector+graph+rerank) | ClawMem | Компоненты есть, нет объединения | Объединить 4 сигнала в federated search через RRF | P2 |

---

## 10. Переиспользование из текущей инфраструктуры

Вместо написания с нуля, следующие компоненты переиспользуются напрямую:

| # | Компонент | Путь в проекте | Что даёт | Заменяет (не нужно писать) | Экономия (ч) |
|---|---|---|---|---|---|
| 1 | HybridSearchStrategy | `src/pdf_framework/search/hybrid_search.py` | RRF fusion (vector+graph+BM25) | hybrid_search для memory | 8-10 |
| 2 | QdrantVectorStore | `src/pdf_framework/vector_store/providers/qdrant.py` | Async client, batch upsert, UUID IDs | Новый Qdrant adapter | 5-8 |
| 3 | SemanticSearchCache | `src/pdf_framework/search/semantic_cache.py` | SQLite+numpy cache, TTL, hit stats | cache.py для memory | 4-5 |
| 4 | CircuitBreaker | `src/shared/llm_rotation/circuit_breaker.py` | 3-state CB (Closed/Open/HalfOpen) | circuit_breaker для memory | 4-5 |
| 5 | BackoffStrategy | `src/shared/llm_rotation/backoff.py` | Exponential+jitter+cap | retry для memory | 2-3 |
| 6 | NetworkXStore | `src/pdf_framework/graph_store/providers/networkx_store.py` | In-memory graph | Graph algorithms для memory | 6-8 |
| 7 | BM25Store (FTS5) | `src/pdf_framework/search/bm25_store.py` | SQLite FTS5 full-text search | Полнотекстовый поиск по памяти | 3-4 |
| 8 | EvalMetrics | `src/pdf_framework/evaluation/metrics.py` | NDCG, MRR, precision@k, recall@k | Метрики качества retrieval | 3-4 |
| 9 | BaseVectorStore | `src/pdf_framework/vector_store/base.py` | Abstract interface | Абстракция для memory backends | 2-3 |
| 10 | Rerankers | `src/pdf_framework/search/reranking/` | CrossEncoder, LLM, ColBERT | Ранжирование memory результатов | 5-6 |
| 11 | Pydantic Settings | `src/pdf_framework/config/_base.py` | Nested .env config | Конфигурация memory module | 1-2 |
| 12 | FrameworkLogger | `src/pdf_framework/callbacks/logging/` | Structured JSON logging | Observability для memory | 1-2 |

**Общая экономия: 45-60 часов** (из 190-245ч raw = ~25% экономии)

### Стратегия переиспользования

Вместо copy-paste — **импорт и адаптация**:

```python
# P0: Federated search с RRF из pdf_framework
from src.pdf_framework.search.strategies.hybrid_search import HybridSearchStrategy
from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore
from src.pdf_framework.search.semantic_cache import SemanticSearchCache

# P1: Resilience из llm_rotation
from src.shared.llm_rotation.circuit_breaker import CircuitBreaker
from src.shared.llm_rotation.backoff import BackoffStrategy

# P2: Graph + evaluation
from src.pdf_framework.graph_store.providers.networkx_store import NetworkXStore
from src.pdf_framework.evaluation.metrics import ndcg_at_k, mrr
```

---

## 11. Связанные документы

- [PHASE_49_UNIFIED_MEMORY.md](MIGRATION_1C_ENTERPRISE_FRAMEWORK/PHASE_49_UNIFIED_MEMORY.md) — исходный план миграции (Phase 49, DONE)
- [TECHNOLOGY_COMPARISON.md](MIGRATION_1C_ENTERPRISE_FRAMEWORK/TECHNOLOGY_COMPARISON.md) — сравнение технологий
- [INDEX.md](MIGRATION_1C_ENTERPRISE_FRAMEWORK/INDEX.md) — карта всех фаз миграции
- `src/memory/` — текущая реализация
- `.claude/skills/memory-unified/SKILL.md` — skill документация
- `tests/integration/test_memory_unified.py` — существующие тесты
