# ROADMAP: Миграция Unified Memory System

**Дата:** 2026-04-03 (обновлено 2026-04-04 — GitHub research + infrastructure reuse)
**Проект:** Перенос компонентов Unified Memory из `D:\1C-Enterprise_Framework` в `D:\1С-Framework\src\memory\`
**Статус:** ПЛАНИРОВАНИЕ (v2 — с учётом best practices и переиспользования)

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
| **P0** | Критический оркестратор | 40-50 | -13ч (Hybrid RRF, Qdrant, Config) | **27-37** | ОБЯЗАТЕЛЬНО |
| **P1** | Инфраструктура и пропагация | 35-45 | -12ч (CircuitBreaker, Backoff, NetworkX) | **23-33** | ОБЯЗАТЕЛЬНО |
| **P2** | Продвинутый поиск и сервисы | 40-50 | -16ч (BM25, Cache, Rerankers, Metrics) | **24-34** | ОБЯЗАТЕЛЬНО |
| **P3** | Realtime и адаптеры | 50-65 | -4ч (Logger) | **46-61** | Опционально |
| **P4** | MCP Tools расширение | 25-35 | 0 | **25-35** | Опционально |
| | **ИТОГО (raw)** | **190-245** | **-45ч** | **145-200** | |

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

- [ ] Создать директорию `infrastructure/` и `__init__.py`
- [ ] Перенести `retry.py` -> `infrastructure/retry.py`
  - [ ] Адаптировать импорты, добавить типизацию
  - [ ] Покрыть тестами
- [ ] Перенести `timeout.py` -> `infrastructure/timeout.py`
  - [ ] Адаптировать импорты, добавить типизацию
  - [ ] Покрыть тестами
- [ ] Сравнить `unified_id.py` (источник vs цель)
  - [ ] Мерж если есть различия
  - [ ] Проверить обратную совместимость
- [ ] Сравнить `link_registry.py` (источник vs цель)
  - [ ] Мерж если есть различия, проверить схему SQLite
- [ ] Перенести `memory_orchestrator.py`
  - [ ] Заменить TimescaleDB коннекты на SQLite
  - [ ] Адаптировать 8 MCP tools к текущим сигнатурам:
    - [ ] `unified_search` — федеративный запрос к 3 серверам
    - [ ] `route_and_save` — роутинг по целевым системам
    - [ ] `get_full_context` — агрегация с graph traversal
    - [ ] `create_link`, `get_related` — через LinkRegistry
    - [ ] `propagate_update` — заглушка (для P1)
    - [ ] `get_system_stats`, `health_check`
- [ ] Перенести `memory_router.py`
  - [ ] Упростить правила для 3 бэкендов (code->ai_memory, pattern->vector, skill->skill_learning)
  - [ ] Убрать зависимости от Neo4j
- [ ] Интеграционные тесты
  - [ ] Тест маршрутизации по типам контента
  - [ ] Тест федеративного поиска
  - [ ] Тест создания связей
- [ ] Проверить обратную совместимость: существующие 18 tools и 26 тестов работают

---

### Фаза P1: Инфраструктура и пропагация (Core)

**Приоритет:** Высокий
**Зависимости:** P0
**Оценка:** 35-45 часов
**Цель:** Восстановить граф-пропагацию confidence и базовые сервисы (circuit breaker, audit).

#### Таблица миграции P1

| Файл источника | Файл цели | Изменения | Оценка (ч) |
|----------------|-----------|-----------|------------|
| `memory-orchestrator/propagation_engine.py` | `orchestrator/propagation_engine.py` | Замена Neo4j на SQLite adjacency, адаптация BFS | 15-18 |
| `unified-memory-mcp/services/circuit_breaker.py` | `infrastructure/circuit_breaker.py` | Упрощение, убираем Redis | 4-5 |
| `unified-memory-mcp/services/audit_service.py` | `ai_memory/services/audit_service.py` | Адаптация под SQLite | 4-5 |
| `unified-memory-mcp/adapters/base.py` | `ai_memory/adapters/base.py` | Абстрактный базовый класс | 3-4 |
| `vector-memory-mcp/merge_patterns` | `skill_learning/merge_patterns.py` | Перенос логики слияния | 4-5 |

#### Чеклист P1

- [ ] Перенести `propagation_engine.py`
  - [ ] Заменить Neo4j граф на SQLite adjacency list
    - [ ] Таблица `edges(id, source_id, target_id, relation_type, weight, created_at)`
    - [ ] Индексы на source_id, target_id
  - [ ] Адаптировать BFS алгоритм (Neo4j Cypher -> SQL рекурсия)
  - [ ] Сохранить time decay + distance decay формулы
  - [ ] Rate limiting через asyncio.Semaphore
  - [ ] Background workers через asyncio.create_task
  - [ ] Покрыть тестами (unit + integration)
- [ ] Перенести `circuit_breaker.py`
  - [ ] Убрать Redis зависимость, использовать in-memory state
  - [ ] Добавить конфигурацию порогов
  - [ ] Покрыть тестами
- [ ] Перенести `audit_service.py`
  - [ ] Таблица `audit_log(id, timestamp, action, entity_id, details_json)`
  - [ ] Индексы по дате
  - [ ] Покрыть тестами
- [ ] Создать `ai_memory/adapters/base.py`
  - [ ] Абстрактный класс MemoryAdapter (save, search, get, delete, update)
  - [ ] Покрыть тестами
- [ ] Перенести `merge_patterns.py` в skill_learning
  - [ ] Адаптировать под JSONL формат
  - [ ] Добавить conflict resolution
  - [ ] Зарегистрировать как новый MCP tool
  - [ ] Покрыть тестами
- [ ] Интеграционные тесты: пропагация, circuit breaker, audit

---

### Фаза P2: Продвинутый поиск и сервисы (Core)

**Приоритет:** Средний
**Зависимости:** P0, P1
**Оценка:** 40-50 часов
**Цель:** Восстановить гибридный поиск, versioning, TTL, forgetgate, metrics.

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
P0 (Orchestrator Core)
 ├── P1 (Infrastructure + Propagation)
 │    └── P2 (Search + Services)
 │         ├── P3 (Realtime + Adapters)  [optional]
 │         └── P4 (MCP Tools)            [optional]
 └── P4 может начаться параллельно с P2 для оберток P0-инструментов
```

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

| Метрика | Текущее | Целевое |
|---------|---------|---------|
| MCP Tools | 18 | 28-32 |
| Тесты | 26 | 60+ |
| Federated search | Stub | Рабочая реализация |
| Маршрутизация контента | Нет | route_and_save по типу |
| Confidence propagation | Нет | BFS с time/distance decay |
| Audit trail | Нет | Полный лог действий |
| Circuit breaker | Нет | Защита от cascading failures |
| Hybrid search | Нет | Semantic + FTS5 fusion |
| Pattern merge | Нет | Слияние дубликатов |
| Versioning + rollback | Нет | Undo/redo для записей |

### По завершении P3-P4 (Full):

| Метрика | Целевое |
|---------|---------|
| MCP Tools | 35-40 |
| Тесты | 80+ |
| Event Bus | Внутрипроцессный pub/sub |
| Surprise detection | Anomaly scoring |
| Cache warmup | Предзагрузка из SQLite |
| Docs RAG adapter | SQLite + Qdrant integration |

---

## 8. Связанные документы

- [PHASE_49_UNIFIED_MEMORY.md](MIGRATION_1C_ENTERPRISE_FRAMEWORK/PHASE_49_UNIFIED_MEMORY.md) — исходный план миграции (Phase 49, DONE)
- [TECHNOLOGY_COMPARISON.md](MIGRATION_1C_ENTERPRISE_FRAMEWORK/TECHNOLOGY_COMPARISON.md) — сравнение технологий
- [INDEX.md](MIGRATION_1C_ENTERPRISE_FRAMEWORK/INDEX.md) — карта всех фаз миграции
- `src/memory/` — текущая реализация
- `.claude/skills/memory-unified/SKILL.md` — skill документация
- `tests/integration/test_memory_unified.py` — существующие тесты
