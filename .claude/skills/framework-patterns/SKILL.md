---
name: framework-patterns
description: "Каталог архитектурных паттернов и паттернов автоматизации фреймворка. Триггеры: 'паттерн', 'pattern', 'архитектура фреймворка', 'как устроен', 'какие паттерны'. НЕ для создания паттернов — используй architecture-research."
---

# Framework Patterns — Каталог паттернов фреймворка

> Каталог архитектурных паттернов и паттернов автоматизации фреймворка. Триггеры: 'паттерн', 'pattern', 'архитектура фреймворка', 'как устроен', 'какие паттерны'. НЕ для создания паттернов — используй architecture-research.

## Обзор

Скилл для навигации по архитектурным паттернам (`Strategy`, `Provider`, `DI`, `Factory`, etc.) и паттернам автоматизации (`BaseHook`, `Enforcer`, `Router`, `Observer`, etc.) фреймворка PDF Vector & Graph. Помогает быстро найти нужный паттерн, понять его роль и увидеть ключевые классы. Полный каталог: `docs/architecture/PATTERNS.md`.

## Быстрый справочник

### Архитектурные паттерны (src/pdf_framework/)

| Паттерн | Где | Ключевые классы | Когда использовать |
|---------|-----|-----------------|-------------------|
| **Provider** | `vector_store/`, `graph_store/`, `embeddings/`, `loaders/` | `BaseVectorStore`, `BaseEmbeddingEngine` | Добавить новое хранилище/загрузчик |
| **Strategy** | `search/strategies/` (14 шт) | `SearchManager`, `VectorSearchStrategy` | Добавить алгоритм поиска |
| **DI Container** | `api/dependencies/components.py` | `Components`, `get_components()` | Связать компоненты приложения |
| **Registry** | `search/manager.py`, `loaders/templates/base.py` | `SearchManager`, `TEMPLATE_REGISTRY` | Динамическая регистрация компонентов |
| **Factory** | `processing/pipeline.py`, `search/manager.py` | `_create_splitter()`, `_create_reranker()` | Создание объекта по конфигурации |
| **Template Method** | `loaders/templates/base.py` | `ParseTemplate` | Скелет алгоритма с вариациями |
| **Composite** | `search/strategies/hybrid_search.py` | `HybridSearchStrategy` | Объединить несколько стратегий (RRF) |
| **Router/Classifier** | `search/routing/` | `QueryClassifier`, `StrategyRouter` | Автовыбор стратегии по запросу |
| **Pipeline** | `processing/pipeline.py`, `search/pipelines/` | `ProcessingPipeline`, `TwoStagePipeline` | Последовательная обработка данных |
| **State Machine** | `agents/rag/state.py` | `RAGState` (LangGraph) | Многошаговые агенты с ветвлением |
| **Singleton** | `config/_base.py`, `components.py` | `get_settings()`, `get_components()` | Глобальная конфигурация |
| **Adapter** | `loaders/router.py`, `multitenancy/` | `SmartLoaderRouter` | Унификация разных API |
| **Observer** | `feedback/`, `analytics/` | `FeedbackCollector`, `CostTracker` | Сбор метрик без влияния на поток |
| **Change Detector** | `graph_store/change_detector.py` | `GraphChangeDetector` | Инкрементальное обновление графа |

### Паттерны автоматизации (.claude/hooks/)

| Паттерн | Где | Ключевые файлы | Когда использовать |
|---------|-----|----------------|-------------------|
| **BaseHook Protocol** | `hooks/base/` | `base.py`, `protocol.py` | Создание нового хука |
| **SessionState** | `hooks/shared/session_state.py` | `session-skills.json` | Координация между хуками |
| **Config-Driven Routing** | `hooks/skill-router.py` | `skill-router-config.json` | Маршрутизация промптов к скиллам |
| **Multi-Level Enforcement** | `hooks/code-skill-enforcer.py` | `code-skill-patterns.json` | Принудительное соблюдение стандартов |
| **Guard Gate** | `hooks/z-ai-write-guard.py` | `hooks/approval-gate.py` | Блокировка критических операций |
| **Stop Gate** | `hooks/ralph_wiggum_stop.py` | `hooks/git-commit-enforcer.py` | Проверка критериев завершения |
| **Circuit Breaker** | `hooks/shared/circuit_breaker.py` | — | Защита от каскадных сбоев |
| **3-Tier Pipeline** | Весь lifecycle | UserPromptSubmit→PreToolUse→PostToolUse→Stop | Перехват на всех этапах |

## Как добавить новый паттерн

### Архитектурный паттерн (src/)

1. Создай `base.py` с ABC и абстрактными методами
2. Реализуй в `providers/` (наследуя ABC)
3. Создай фабричную функцию `get_*()` в `__init__.py`
4. Зарегистрируй в `Components` (DI Container)
5. Обнови `docs/architecture/PATTERNS.md`

### Паттерн автоматизации (.claude/)

1. Наследуй `BaseHook` из `hooks/base/base.py`
2. Выбери event: UserPromptSubmit / PreToolUse / PostToolUse / Stop
3. Реализуй `execute()` с graceful degradation
4. Зарегистрируй в `settings.json` (hooks section)
5. Обнови `docs/architecture/PATTERNS.md`

## Диагностика

| Проблема | Причина | Решение |
|----------|---------|---------|
| Стратегия не вызывается | Не зарегистрирована в `SearchManager` | `register_strategy()` в `Components.__init__()` |
| Хук молчит | Неправильный event или timeout | Проверь `settings.json` hooks section |
| Provider возвращает None | DI-контейнер не инициализирован | `await get_components()` при старте |
| Circuit Breaker в OPEN | Накопленные ошибки >= 5 | Проверь лог, дождись HALF_OPEN (300s) |
| Pipeline падает на середине | Исключение в стадии не обработано | Graceful degradation + logging |

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| `if type == "vector": ...` в бизнес-логике | Хардкод, невозможно расширить | Strategy + Router через `QueryClassifier` |
| Прямой `import QdrantVectorStore` | Жёсткая связанность | Provider: `get_vector_store(settings)` |
| Копипаст хука с минимальными правками | Дублирование, рассинхрон | Наследуй `BaseHook` + параметризация |
| Singleton на каждый класс | Глобальное состояние → баги | Только для `settings` и `components` |
| Игнорирование ошибок в хуке | Ошибка проглатывается | Логируй + используй Circuit Breaker |
