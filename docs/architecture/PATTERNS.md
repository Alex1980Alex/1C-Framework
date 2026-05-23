---
status: active
tags: [architecture, patterns, automation, index]
related: ["[[overview]]", "[[triad-architecture]]", "[[ralph-wiggum]]", "[[hooks-reference]]", "[[skills-reference]]", "[[bsl-integration]]", "[[core-framework-separation]]"]
---

# Каталог паттернов фреймворка

> Index-страница: 15 архитектурных + 13 автоматизационных паттернов. Каждый паттерн вынесен в отдельную wiki-страницу в [docs/wiki/patterns/](../wiki/patterns/) для точечной ссылаемости.

---

## 1. Архитектурные паттерны (`src/pdf_framework/`)

| # | Паттерн | Wiki-страница |
|---|---------|---------------|
| 1.1 | Provider Pattern | [[provider-pattern]] |
| 1.2 | Strategy Pattern | [[strategy-pattern]] |
| 1.3 | DI Container | [[di-container]] |
| 1.4 | Abstract Base Class (ABC) | [[abstract-base-class]] |
| 1.5 | Registry | [[registry]] |
| 1.6 | Factory | [[factory]] |
| 1.7 | Template Method | [[template-method]] |
| 1.8 | Composite | [[composite]] |
| 1.9 | Router / Classifier | [[router-classifier]] |
| 1.10 | Pipeline | [[pipeline]] |
| 1.11 | State Machine | [[state-machine]] |
| 1.12 | Singleton | [[singleton]] |
| 1.13 | Adapter | [[adapter]] |
| 1.14 | Observer | [[observer]] |
| 1.15 | Change Detector | [[change-detector]] |

---

## 2. Паттерны автоматизации (`.claude/hooks/`)

| # | Паттерн | Wiki-страница |
|---|---------|---------------|
| 2.1 | BaseHook Protocol | [[base-hook-protocol]] |
| 2.2 | SessionState | [[session-state]] |
| 2.3 | Config-Driven Routing | [[config-driven-routing]] |
| 2.4 | Fuzzy Intent Detection | [[fuzzy-intent-detection]] |
| 2.5 | Multi-Level Enforcement | [[multi-level-enforcement]] |
| 2.6 | Guard Gate | [[guard-gate]] |
| 2.7 | Silent Observer | [[silent-observer]] |
| 2.8 | Error Classifier | [[error-classifier]] |
| 2.9 | Stop Gate | [[stop-gate]] |
| 2.10 | Circuit Breaker | [[circuit-breaker]] |
| 2.11 | Task Master | [[task-master]] |
| 2.12 | Invocation Logger | [[invocation-logger]] |
| 2.13 | 3-Tier Pipeline | [[three-tier-pipeline]] |

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
