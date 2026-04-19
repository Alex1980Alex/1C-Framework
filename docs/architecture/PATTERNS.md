---
status: active
tags: [architecture, patterns, automation]
related: [[overview]], [[triad-architecture]], [[ralph-wiggum]], [[hooks-reference]], [[skills-reference]], [[bsl-integration]], [[core-framework-separation]]
---

# Каталог паттернов фреймворка

> Полный каталог архитектурных паттернов и паттернов автоматизации PDF Vector & Graph Framework.

---

## 1. Архитектурные паттерны (src/pdf_framework/)

### 1.1 Provider Pattern
**Где используется:** `vector_store/`, `graph_store/`, `embeddings/`, `loaders/` (4 домена)
**Ключевые классы:** `BaseVectorStore`, `BaseGraphStore`, `BaseEmbeddingEngine`, `BaseLoader`
**Как работает:** Каждый домен изолирован: абстрактный интерфейс в `base.py` и конкретные реализации в `providers/`. Фабричные функции скрывают детали инстанцирования от клиента.
**Пример:**
```python
store = get_vector_store(settings)      # → QdrantVectorStore / ChromaVectorStore
engine = get_embedding_engine(settings) # → LocalEmbeddingEngine / JinaEmbeddingEngine
```

### 1.2 Strategy Pattern
**Где используется:** `search/strategies/` (14 стратегий)
**Ключевые классы:** `SearchManager`, `VectorSearchStrategy`, `HybridSearchStrategy`, `AdaptiveSearchStrategy`
**Как работает:** `SearchManager` хранит реестр стратегий и делегирует вызов выбранной. Новые алгоритмы добавляются без изменения менеджера.
**Стратегии:** Vector, Hybrid, BM25, GraphRAG (local/global/light/auto), AutoMerge, Adaptive, RAPTOR, Web, Visual, TwoStage, Semantic
**Пример:**
```python
manager = SearchManager()
manager.register_strategy("hybrid", HybridSearchStrategy())
results = await manager.search("query", strategy="hybrid")
```

### 1.3 DI Container
**Где используется:** `api/dependencies/components.py`
**Ключевые классы:** `Components`
**Как работает:** Синглтон `Components` создаёт и связывает stores, engines и strategies. Функция `get_components()` возвращает готовый контейнер с инжектированными зависимостями.
**Пример:**
```python
c = await get_components()  # Components singleton
results = await c.search_manager.search("запрос", strategy="auto")
```

### 1.4 Abstract Base Class (ABC)
**Где используется:** `vector_store/base.py`, `graph_store/base.py`, `embeddings/engine.py`, `loaders/base.py`
**Ключевые классы:** `BaseVectorStore`, `BaseGraphStore`, `BaseEmbeddingEngine`, `BaseLoader`
**Как работает:** Четыре контракта определяют обязательные методы: `add_documents`, `search`, `delete` и др. Провайдеры наследуют ABC и реализуют все абстрактные методы.
**Пример:**
```python
class QdrantVectorStore(BaseVectorStore):
    async def add_documents(self, docs): ...
    async def search(self, query, k=5): ...
```

### 1.5 Registry
**Где используется:** `search/manager.py`, `loaders/templates/base.py`, `knowledge_base/document_registry.py`
**Ключевые классы:** `SearchManager` (стратегии), `TEMPLATE_REGISTRY` (шаблоны парсинга), `DocumentRegistry` (документы)
**Как работает:** Каждый реестр — `dict[str, type]` с методами `register`/`get`. Позволяет динамически подключать новые компоненты.
**Пример:**
```python
TEMPLATE_REGISTRY["research_paper"] = ResearchPaperTemplate
tpl = get_template("research_paper")
```

### 1.6 Factory
**Где используется:** `processing/pipeline.py`, `search/manager.py`, `agents/rag/agent.py`
**Ключевые классы:** `_create_splitter()`, `_create_reranker()`, `create_rag_agent()`, `get_loader()`
**Как работает:** Фабричные функции принимают конфигурацию и возвращают нужный объект, инкапсулируя логику выбора и инициализации.
**Пример:**
```python
splitter = _create_splitter(settings)   # → SemanticTextSplitter / RecursiveTextSplitter
reranker = _create_reranker(settings)   # → LLMReranker / CrossEncoderReranker
```

### 1.7 Template Method
**Где используется:** `loaders/templates/base.py`
**Ключевые классы:** `ParseTemplate`, `GenericTemplate`, `ResearchPaperTemplate`, `UserManualTemplate`
**Как работает:** Базовый класс определяет скелет парсинга, а подклассы переопределяют хуки `element_priorities`, `skip_elements`, `chunk_size_overrides`.
**Пример:**
```python
class ResearchPaperTemplate(ParseTemplate):
    element_priorities = {"abstract": 10, "methodology": 8}
    skip_elements = ["acknowledgements"]
```

### 1.8 Composite
**Где используется:** `search/strategies/hybrid_search.py`
**Ключевые классы:** `HybridSearchStrategy`
**Как работает:** Компонует Vector + Graph + BM25, объединяя результаты через Reciprocal Rank Fusion (RRF). Стратегия сама является `BaseSearchStrategy`.
**Пример:**
```python
hybrid = HybridSearchStrategy(vector=vs, graph=gs, bm25=bs)
results = await hybrid.search("запрос")  # RRF fusion
```

### 1.9 Router / Classifier
**Где используется:** `search/routing/`
**Ключевые классы:** `QueryClassifier`, `StrategyRouter`, `SubQuestionDecomposer`
**Как работает:** Классификатор определяет тип запроса, роутер выбирает стратегию, декомпозер разбивает сложные вопросы на подзапросы.
**Пример:**
```python
classification = QueryClassifier.classify("сравни A и B")
decision = StrategyRouter.route(classification)  # → "hybrid"
```

### 1.10 Pipeline
**Где используется:** `processing/pipeline.py`, `search/pipelines/`
**Ключевые классы:** `ProcessingPipeline`, `TwoStagePipeline`, `SectionFirstPipeline`
**Как работает:** Конвейер последовательно пропускает данные через этапы: split → page_assign → dedup → enrich. Каждый этап — независимый трансформер.

### 1.11 State Machine
**Где используется:** `agents/rag/state.py`, `agents/rag/agent.py` (LangGraph)
**Ключевые классы:** `RAGState`
**Как работает:** Граф состояний LangGraph: `analyze → search → grade → rewrite → generate`. Переходы зависят от оценки релевантности (Self-RAG).

### 1.12 Singleton
**Где используется:** `config/_base.py`, `api/dependencies/components.py`
**Ключевые классы:** `get_settings()`, `get_components()`
**Как работает:** Глобальные точки доступа гарантируют единственный экземпляр конфигурации и контейнера компонентов в рамках процесса.

### 1.13 Adapter
**Где используется:** `loaders/router.py`, `multitenancy/tenant_store.py`
**Ключевые классы:** `SmartLoaderRouter`, `TenantVectorStoreManager`
**Как работает:** `SmartLoaderRouter` адаптирует разные загрузчики под единый интерфейс. `TenantVectorStoreManager` изолирует данные тенантов в одном хранилище.

### 1.14 Observer
**Где используется:** `feedback/collector.py`, `analytics/tracker.py`, `analytics/cost.py`
**Ключевые классы:** `FeedbackCollector`, `QueryTracker`, `CostTracker`
**Как работает:** Трекеры подписываются на события поиска и собирают метрики: запросы, стоимость, обратную связь — без влияния на основной поток.

### 1.15 Change Detector
**Где используется:** `graph_store/change_detector.py`
**Ключевые классы:** `GraphChangeDetector`, `IncrementalGraphUpdater`
**Как работает:** Детектор сравнивает версии документов и находит дельту. Инкрементальный обновлитель применяет только изменения к графу без полной перестройки.

---

## 2. Паттерны автоматизации (.claude/hooks/)

### 2.1 BaseHook Protocol
**Где используется:** все хуки в `.claude/hooks/`
**Ключевые классы:** `BaseHook`, `HookInput`, `HookOutput`, `HookEvent`
**Как работает:** Каждый хук читает JSON из stdin (`HookInput`), обрабатывает и пишет JSON в stdout (`HookOutput`). При ошибке — graceful degradation (sys.exit(0)). Кодировка строго UTF-8.

### 2.2 SessionState
**Где используется:** `.claude/hooks/shared/session_state.py`
**Как работает:** Singleton-файл `session-skills.json` координирует состояние между 15+ хуками. Хуки читают/пишут активные навыки, флаги делегирования и фазы task protocol.

### 2.3 Config-Driven Routing
**Где используется:** `.claude/hooks/skill-router.py`
**Как работает:** Трёхуровневый роутинг: Layer A — точное совпадение фразы, Layer B — fuzzy matching (pymorphy3 + rapidfuzz), Layer C — TF-IDF семантический скоринг. Конфиг `skill-router-config.json` определяет бандлы и веса.

### 2.4 Fuzzy Intent Detection
**Где используется:** `.claude/hooks/shared/fuzzy_match.py`
**Как работает:** Трёхшаговое сопоставление: exact lemma → fuzzy original → fuzzy lemma. Pymorphy3 для лемматизации ("удалим" → "удалить"), rapidfuzz для опечаток. Порог 78%.

### 2.5 Multi-Level Enforcement
**Где используется:** `.claude/hooks/code-skill-enforcer.py`
**Как работает:** 6 уровней проверки: B (directory rules) → A (content patterns) → A.1 (research protocol) → C (bash commands) → D (research cache) → E (post-verification) → F (LEARN phase). Блокирует Write/Edit без активации нужного скилла.

### 2.6 Guard Gate
**Где используется:** `.claude/hooks/z-ai-write-guard.py`, `.claude/hooks/approval-gate.py`
**Как работает:** PreToolUse хуки перехватывают операции записи и блокируют при нарушении политик. `z-ai-write-guard` требует Z.AI делегирование для >15 строк кода. `approval-gate` требует одобренный OpenSpec.

### 2.7 Silent Observer
**Где используется:** `.claude/hooks/task-protocol-observer.py`
**Как работает:** PostToolUse хук молча обновляет состояние в SessionState после каждого вызова инструмента (TaskCreate → decomposed, Skill → skill_checked, llm_complete → delegated).

### 2.8 Error Classifier
**Где используется:** `.claude/hooks/posttooluse-bash-errors.py`
**Как работает:** Классифицирует ошибки bash-команд по типам (pytest_failure, git_conflict, pip_error) и возвращает `hookSpecificOutput` с рекомендацией.

### 2.9 Stop Gate
**Где используется:** `.claude/hooks/ralph_wiggum_stop.py`, `.claude/hooks/git-commit-enforcer.py`
**Как работает:** Stop хуки проверяют финальное состояние. `ralph_wiggum_stop` — проверяет критерии завершения автоцикла. `git-commit-enforcer` — требует чистый working tree в watched paths.

### 2.10 Circuit Breaker
**Где используется:** `.claude/hooks/shared/circuit_breaker.py`
**Как работает:** Три состояния: CLOSED → OPEN (при 5 ошибках) → HALF_OPEN (через 300s) → CLOSED (при 2 успехах). Декоратор `@with_circuit_breaker("hook-name")` оборачивает хуки.

### 2.11 Task Master
**Где используется:** `.claude/hooks/shared/task_master.py`
**Как работает:** Управляет mandatory tasks в `.claude/cache/hook-todos.json`: add_task → update_task_metadata → complete_task_by_hook. Используется auto-git-save и другими хуками.

### 2.12 Invocation Logger
**Где используется:** `.claude/hooks/shared/invocation_logger.py`
**Как работает:** Append-only JSONL лог всех вызовов хуков. Каждая запись: timestamp, hook, event, tool, elapsed_ms, outcome. Ротация при 10MB.

### 2.13 3-Tier Pipeline
**Где используется:** весь lifecycle хуков Claude Code
**Как работает:**
1. `UserPromptSubmit` — роутинг (skill-router, research-task-detector)
2. `PreToolUse` — enforcement (code-skill-enforcer, z-ai-write-guard, approval-gate)
3. `PostToolUse` — observation (task-protocol-observer, delegation-tracker, auto-git-save)
4. `Stop` — финальные проверки (ralph_wiggum_stop, git-commit-enforcer)

---

## 3. Связи между паттернами

```
┌─────────────────────────────────────────────────────────────────┐
│                    АРХИТЕКТУРНЫЙ СЛОЙ                            │
│                                                                 │
│  Provider ──────► DI Container ──────► Strategy Registration    │
│  (4 домена)      (Components)          (SearchManager)          │
│       │                │                      │                  │
│       ▼                ▼                      ▼                  │
│  [ABC контракты]  [Singleton]         [Registry + Composite]    │
│                                                                 │
│  QueryClassifier ──► StrategyRouter ──► SubQuestionDecomposer   │
│       │                    │                                    │
│       ▼                    ▼                                    │
│  [State Machine: analyze → search → grade → rewrite → generate] │
│                                                                 │
│  ProcessingPipeline ──► ChangeDetector ──► IncrementalUpdater   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    СЛОЙ АВТОМАТИЗАЦИИ                            │
│                                                                 │
│  BaseHook Protocol ◄──── SessionState (singleton JSON)          │
│       │                    │                                    │
│       ▼                    ▼                                    │
│  SkillRouter ──► CodeSkillEnforcer ──► TaskProtocolObserver     │
│  (Layer A/B/C)   (6 levels)            (silent)                 │
│       │                │                    │                    │
│       ▼                ▼                    ▼                    │
│  CircuitBreaker   GuardGate          InvocationLogger           │
│  (state machine)  (PreToolUse)       (append-only JSONL)        │
│                                                                 │
│  UserPromptSubmit ──► PreToolUse ──► PostToolUse ──► Stop       │
│  (routing)           (enforce)       (observe)        (gate)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Когда какой паттерн использовать

| Задача | Паттерн | Пример |
|--------|---------|--------|
| Добавить новое векторное хранилище | Provider + ABC | `MilvusVectorStore(BaseVectorStore)` |
| Добавить алгоритм поиска | Strategy + Registry | `register_strategy("colbert", ColbertStrategy())` |
| Связать компоненты приложения | DI Container | `get_components().search_manager` |
| Поддержать формат документа | Template Method | `InvoiceTemplate(ParseTemplate)` с хуками |
| Объединить несколько поисков | Composite | `HybridStrategy = Vector + BM25 + Graph` |
| Маршрутизировать запросы | Router/Classifier | `QueryClassifier → StrategyRouter` |
| Обработать документ по шагам | Pipeline | `ProcessingPipeline(split → dedup → enrich)` |
| Управлять сложным агентом | State Machine | LangGraph `analyze → search → generate` |
| Глобальная конфигурация | Singleton | `get_settings().embedding` |
| Унифицировать разные API | Adapter | `SmartLoaderRouter.load("file.docx")` |
| Собирать метрики | Observer | `CostTracker.on_api_call(cost=0.02)` |
| Обновить граф без перестройки | Change Detector | `IncrementalGraphUpdater.apply(delta)` |
| Перехватить опасное действие | Guard Gate | `z-ai-write-guard → block` |
| Защитить от каскадных ошибок | Circuit Breaker | `CLOSED → OPEN` при 5 ошибках |
| Определить намерение пользователя | Fuzzy Intent | `pymorphy3 + rapidfuzz ≥ 78%` |
| Координировать состояние хуков | SessionState | `session-skills.json` |
| Логировать все вызовы | Invocation Logger | append-only JSONL audit trail |
| Разбить сложный запрос | SubQuestionDecomposer | "сравни A, B, C" → 3 подзапроса |
