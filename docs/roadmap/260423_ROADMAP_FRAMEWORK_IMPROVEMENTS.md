# 260423 Roadmap — Исправления и улучшения PDF Vector & Graph Framework

**Дата:** 2026-04-23
**Статус:** draft (готов к review)
**Версия:** 1.0
**Автор:** Claude Opus 4.7 (1M context) через skill `architecture-research` (6 фаз)
**Исследование:**
- [framework-gaps-analysis-2026-04.md](../../.claude/skills/architecture-research/cache/framework-gaps-analysis-2026-04.md) — факты о слабых местах кодовой базы
- [production-rag-patterns-2026.md](../../.claude/skills/architecture-research/cache/production-rag-patterns-2026.md) — best practices с GitHub (60+ источников)

---

## TL;DR

Дорожная карта сгруппирована в **3 трека**, распределённых по **3 горизонтам** (2 недели / 1-2 мес / 2-3 мес). Итого **21 работа** + условные `brownfield-revisit` пункты:

| Трек | Что это | Кол-во | Прим. effort | Основание |
|------|---------|--------|--------------|-----------|
| **A. Исправления** | Production-blocking TODO и tech-debt из codebase-scan | 7 | 9-14 дней | `framework-gaps-analysis-2026-04.md` |
| **B. Улучшения** | Best practices 2026 (Contextual RAG, GEPA, OTel, Send API, Matryoshka) | 7 | 11-18 дней | `production-rag-patterns-2026.md` |
| **C. Закрытие** | Отложенные roadmap-пункты (Phase 67, ADR-008, Memory P5, Iter 4-5) | 7 | 8-12 дней | MEMORY.md + ROADMAP_*.md index |

**Итого:** 28-44 дня FTE (~6-9 недель при 1 разработчике), укладывается в квартал при декомпозиции по трекам.

**Гипотеза ROI (TOP-5):**
1. A1. Доделать JWT в `tenants.py` — **блокирует multi-tenant в prod** (2h, Critical)
2. B1. Contextual Retrieval chunking — **-67% retrieval failures** (paper-proven)
3. B2. GEPA (замена MIPROv2) — **+26% accuracy на DSPy**
4. B3. OpenLLMetry + Langfuse — **закрывает 50% dark-zone observability** и даёт prompt registry
5. C1. Smoke-gate eval (ADR-008 verdict) — **разблокирует CI + завершает Hermes Phase 2**

---

## 1. Контекст: зачем новый roadmap

### Что уже сделано (2026-02 .. 2026-04)

По состоянию на 2026-04-23 в `docs/roadmap/` **60+ документов**, из них крупные COMPLETE:

- **Hermes (LLM Wiki)** — Phases 0-6 + TODO-1..3 DONE (2026-04-21)
- **LLM Rotation v2.0** — 5 итераций (CB, backoff, health check, multi-level, adaptive) DONE
- **BSL Intelligence V4** — Phases 58-66 DONE, Phase 67 DEFERRED
- **SDD / OpenSpec** — Phases 1-5 DONE, `brownfield-validate` в проде
- **Memory Migration** — P0-P4 DONE (UnifiedID, LinkRegistry, EventBus, ConflictResolver, PropagationEngine, MemoryCube, HybridSearchService), P5 in progress
- **Serena Audit Hybrid** — Phases 0-7 DONE (Extract-only); Serena будет удалён после Phases 8-10
- **Skill-First Enforcement** — 95/113 задач DONE (M1-M5 done, M6-M7 todo)
- **Delegation Learning** — Iter 1-3 DONE (включая LinUCB Bandit в проде), Iter 4-5 TODO

### Что НЕ закрыто (из MEMORY + свежие коммиты)

| Источник | Отложенное | Status |
|----------|-----------|--------|
| `PHASE_67.md` | claude-hud, codebase-memory-mcp, parry, sonar-bsl, bsl-language-server integration | DEFERRED |
| `ADR-008` | DSPy migration verdict: metrics "pending" | blocked by eval |
| `GAP_P5_HOOK_OBSERVABILITY.md` | Phases 5-8 (Stream-aware logging, Cross-hook tracing, Unified metrics schema) | schedule unknown |
| `260320_ROADMAP_DELEGATION_LEARNING.md` | Iter 4-5 | TODO |
| `.pre-commit-config.yaml:70` | `hermes-eval-smoke` gate без fallback | опасно для CI |
| `260414_Serena Audit.md` v4.1 | Phases 8-10 (context/mode system, Tier 4 tools, dashboard) | 5-7 дней, не начаты |
| GAP Roadmap (Phases 44-61) | F3 Langfuse, A4 Propositions, S3 Incremental Graph | частично |

### Почему стоит делать roadmap сейчас

1. **Фронт задач ясен** — codebase scan дал 16 конкретных находок с file:line.
2. **Best practices 2026 обогнали код** — Contextual Retrieval (Anthropic), GEPA (ECIR 2026), Send API (LangGraph) опубликованы после планирования предыдущих roadmap'ов.
3. **Смерть по наследству** — 60+ старых roadmap'ов без единого индекса в MEMORY — новичок (или я сам через месяц) не поймёт что открыто. Нужен сводный документ.

---

## 2. Методология синтеза

Проведено через skill `architecture-research` (6 фаз):

| Фаза | Действие | Артефакт |
|------|----------|----------|
| 0 | Проверка кеша | `_index.json` (13 тем существовало) |
| 1 | Локальная база знаний (GAP_ROADMAP, Serena, Hermes, BSL V4 Phase 67) | Контекст собран |
| 2 | Web-research GitHub 2026 (60+ источников) | `production-rag-patterns-2026.md` |
| 2b | Codebase-scan TODO/FIXME/skip | `framework-gaps-analysis-2026-04.md` |
| 3 | Синтез — эта дорожная карта | ← этот документ |
| 4 | Атрибуция | `[code]`, `[web]`, `[exp]` в каждом пункте |
| 5 | Кеш-файлы сохранены | 2 файла (cache + gaps), индекс обновлён |
| 6 | ADR — см. секцию 10 (выводы) | кандидат: ADR-008 verdict, ADR-009 observability stack |

**Атрибуция** в каждом пункте:
- `[code]` — найдено в `src/` (TODO / pattern / missing)
- `[web]` — из 2026 best practices
- `[exp]` — из MEMORY.md и прошлых roadmap'ов
- `[own]` — экспертная оценка приоритета

---

## 3. Трек A — Исправления (production-blocking tech-debt)

### A1. JWT парсинг в `tenants.py` — блокирует multi-tenant auth
- **Найдено:** `src/api/routes/tenants.py:34,45` — TODO в `get_current_tenant` и `require_admin`. Любой request без валидации может получить admin-роль. [code]
- **Риск:** HIGH — security, multi-tenant изоляция не работает.
- **Действие:** реализовать `jwt.decode(token, key, algorithms=["HS256"])` через уже существующий `src/api/auth/jwt_handler.py` (Hermes Phase 12.3, 159 LoC, готов). Добавить audit-лог отказов. Pytest на 401/403.
- **Effort:** 2-4 ч. **Impact:** Critical. **Dep:** нет.

### A2. Dual-write в `feedback.py` без conflict resolver
- **Найдено:** `src/api/routes/feedback.py:4` — комментарий "Dual-write: old FeedbackCollector (sync) + new FeedbackStore (async)". Нет синхронизации. [code]
- **Риск:** HIGH — потеря данных, race conditions.
- **Действие:** либо выпилить sync-путь (если async покрывает), либо подключить существующий `ConflictResolver` из `src/memory/infrastructure/conflict_resolver.py` (260 LoC, стратегии resolution уже готовы) [exp].
- **Effort:** 3-5 ч. **Impact:** HIGH.

### A3. Унификация retry / circuit breaker / rate limiter
- **Найдено:** 3 разных реализации — `src/shared/llm_rotation/rate_limiter.py`, `src/pdf_framework/utils/retry.py`, `src/memory/infrastructure/circuit_breaker.py`. Нет единой политики. [code]
- **Действие:** выделить `src/shared/resilience/` модуль, переключить LLM Rotation + vector store + MCP clients через единый `SharedRetryPolicy`. Не ломать API (facade pattern).
- **Effort:** 2-3 дня. **Impact:** MED. **Dep:** нет.

### A4. Sync-in-async мосты в vector stores
- **Найдено:** `parent_store.py:102` (×7 методов) и `bm25_store.py:318` (×5 методов) делают `await asyncio.to_thread(_sync_...)`. При параллельной работе — thread pool thrashing (default executor = 5 threads) [code].
- **Действие:** либо полный async (рекомендуется для bm25 — есть `rank_bm25` не async, но можно обернуть через `aiofiles` + numpy vectorize), либо выделенный `ThreadPoolExecutor(max_workers=16)` на уровне store.
- **Effort:** 1-2 дня. **Impact:** MED.

### A5. Stub embedding в `summary_index.py`
- **Найдено:** `src/pdf_framework/processing/summary_index.py:280` — TODO "Use actual embedding engine from components". 80 строк hardcoded mock [code].
- **Действие:** DI через `EmbeddingProvider` (уже есть в `src/pdf_framework/embeddings/`). Unit-тест на корректность dim 768.
- **Effort:** 2 ч. **Impact:** MED (document pre-routing не работает).

### A6. Missing test coverage в критичных модулях
- **Найдено:** zero-coverage: `src/pdf_framework/loaders/providers/docling_loader.py` (438 LoC), `src/bsl/sonar/` (cli, config_manager), `src/memory/orchestrator/propagation_engine.py` (557 LoC, только integration). Оценка coverage: 60-65% [code].
- **Действие:** pytest unit-тесты на публичные интерфейсы (min 60% на каждый модуль). Подключить `pytest-cov` с gate в CI (`--cov-fail-under=70`).
- **Effort:** 3-5 дней. **Impact:** MED. **Dep:** C6 (CI gates).

### A7. RAPTOR tree traversal + LLM re-ranking в BSL
- **Найдено:** `src/pdf_framework/search/strategies/raptor_search.py:163` — только flat leaf queries. `src/bsl/semantic_search/services/search.py:245,261` — LLM re-ranking не реализован, стадии 2-4 — заглушки [code].
- **Действие:** BFS-traversal для RAPTOR (алгоритм есть в paper). LLM reranker — подключить `cross-encoder/ms-marco-MiniLM` или через llm-rotation (Z.AI кешируемый). Benchmark до/после на dev-set.
- **Effort:** 2-3 дня. **Impact:** MED. **Dep:** C2 (eval dataset).

---

## 4. Трек B — Улучшения (best practices 2026)

### B1. Contextual Retrieval chunking (Anthropic) — HIGHEST ROI
- **Основание:** Anthropic paper: Contextual Embeddings -35%, +BM25 -49%, +Rerank -67% retrieval failures. У нас hybrid+rerank есть, contextual chunking нет [web].
- **Действие:** новый splitter `ContextualSplitter` в `src/pdf_framework/processing/` — для каждого чанка LLM генерирует 50-100-токен префикс с контекстом документа, embed prefix+chunk. Использовать prompt caching (Claude) для снижения стоимости.
- **Плюсы:** paper-proven, no infra change, drop-in для существующего pipeline.
- **Минусы:** +latency на индексацию, +токены (компенсируется prompt caching ~90%).
- **Effort:** 2-3 дня. **Impact:** HIGH. **Dep:** C2 (eval dataset для проверки).

### B2. GEPA (замена MIPROv2 для DSPy grader/rewriter/hallucination-checker)
- **Основание:** ECIR 2026, `dspy.GEPA` — 93% MATH vs 67% ChainOfThought, превосходит TextGrad, `optimize_anything` API [web].
- **Действие:** добавить `src/pdf_framework/prompts/optimizers/gepa_adapter.py`. Параллельно с MIPROv2 в A/B. Переключить после 2-недельного теста, если +5% и более на RAGAS.
- **Эффект:** завершает Hermes TODO-1 вместо deferred ADR-008.
- **Effort:** 2-3 дня. **Impact:** HIGH. **Dep:** A6 (тесты), C1 (eval).

### B3. OpenLLMetry + Langfuse self-hosted (замена ad-hoc `observability/`)
- **Основание:** 50% модулей без structured logging [code]. OTel gen_ai.* convention + Langfuse (MIT) — 2-line init, vendor-agnostic, prompt registry bonus [web].
- **Действие:**
  1. `pip install traceloop-sdk` + `Traceloop.init(...)` в FastAPI startup
  2. Docker-compose: `langfuse/langfuse:latest` + Postgres + Clickhouse
  3. `BaggageSpanProcessor` для tenant/user/task attribution (fix ручной analytics/)
  4. Мигрировать custom `src/pdf_framework/observability/` на OTel spans
- **Effort:** 3-5 дней. **Impact:** HIGH. **Dep:** A1 (tenant для baggage).

### B4. LangGraph Send API (map-reduce для multi-PDF / multi-query)
- **Основание:** Dynamic worker fan-out, `max_concurrency`, 3-10× latency на batch [web].
- **Действие:** в `src/pdf_framework/indexing/` + `agents/research/` заменить последовательный loop на `Send(indexer_node, pdf_path)` × N. Deferred synchronization barrier для aggregation.
- **Effort:** 2 дня. **Impact:** HIGH (latency), MED (complexity).

### B5. Matryoshka embeddings (Jina v4 или Voyage voyage-3-large)
- **Основание:** 4× storage cut, quality-preserving, Qdrant native `prefetch` → top-k → rescore [web]. Наш nomic-embed-text — НЕ MRL.
- **Действие:** A/B в dev-collection. Миграционный скрипт для bsl_code_v3 + wiki_pages_v1 (с параллельным bm25 для смены без downtime).
- **Effort:** 3-5 дней (включая reindex). **Impact:** MED-HIGH (cost + quality).
- **Замечание:** нужно свериться с лицензией Voyage (commercial API) — возможно ограничиться Jina v4 (Apache 2.0).

### B6. MCP Inspector smoke-gate для OAuth
- **Основание:** glama.ai MCP Inspector тестирует tools/resources/prompts/elicitation/sampling + OAuth 2.1 DCR [web]. У нас OAuth 2.1 есть (Hermes Phase 6, `src/shared/mcp_oauth/`) но нет автомат.smoke-теста.
- **Действие:** CI-job: `npx @modelcontextprotocol/inspector --run-smoke` против поднятого `pdf-vector-graph` MCP. Блокирует PR при regression.
- **Effort:** 0.5 дня. **Impact:** MED.

### B7. DeepEval pytest-gating (замена "ручного" RAGAS)
- **Основание:** 14+ self-explaining metrics как `@pytest.fixture`, блокирует PR при регрессии [web]. Дополняет MLflow Unified Scorers.
- **Действие:** в `tests/eval/` — deepeval тесты на golden-questions из `data/eval/`. Добавить в CI matrix.
- **Effort:** 2 дня. **Impact:** MED. **Dep:** A6, C1.

---

## 5. Трек C — Закрытие отложенных roadmap'ов

### C1. Разблокировать ADR-008 (DSPy verdict) + safe smoke-gate
- **Проблема:** `docs/architecture/ADR-008-dspy-migration-verdict.md` — все metrics "pending". `.pre-commit-config.yaml:70` — `hermes-eval-smoke` hook без fallback, сломает CI.
- **Действие:**
  1. Завершить `src/pdf_framework/optimization/dspy_optimizer.py:105` TODO (wire FeedbackStore → dataset)
  2. Запустить `python scripts/eval_hermes_phase2.py --baseline langchain`
  3. Записать метрики в ADR-008, вынести verdict `accepted` / `rejected` / `conditional`
  4. В pre-commit: `if not os.path.exists("scripts/eval_hermes_phase2.py"): skip` + `|| true` fallback
- **Effort:** 1 день. **Impact:** HIGH (unblock CI, завершает Hermes Phase 2).

### C2. Golden-eval dataset для RAG
- **Проблема:** Phase 58 (BSL eval dataset, 100 queries) DONE, но для основного RAG-pipeline нет dataset. DSPy optimizer не работает без данных [code].
- **Действие:** 100 queries × 3 категории (factual / analytical / cross-document) + expected answers. Сохранить в `data/eval/rag/`. Использовать для B1 / B2 / B7 бенчмарка.
- **Effort:** 2-3 дня (включая curation). **Impact:** HIGH (unblocker).

### C3. Memory P5 — hook observability (Phases 5-8)
- **Проблема:** `GAP_P5_HOOK_OBSERVABILITY.md` Phases 1-4 DONE, 5-8 без timeline. Hooks работают, но cross-hook tracing отсутствует.
- **Действие:** после B3 (OTel baseline) — добавить OTel tracing во все hooks через `shared/hook_tracing.py`. Unified metrics schema. Dashboard в Langfuse.
- **Effort:** 2-3 дня. **Impact:** MED. **Dep:** B3.

### C4. Delegation Learning Iter 4-5
- **Проблема:** Iter 1-3 DONE (LinUCB bandit в проде). Iter 4 (multi-provider matrix) + Iter 5 (cost-aware routing) TODO. Roadmap: `260320_ROADMAP_DELEGATION_LEARNING.md`.
- **Действие:** расширить feature vector контекстом (task_type × provider_fit × current_cost_budget). A/B тест на текущем корпусе 544+ outcomes.
- **Effort:** 2-3 дня. **Impact:** MED (token economy).

### C5. Serena Audit Phases 8-10 (context/mode system, Tier 4 tools, dashboard)
- **Проблема:** Phases 0-7 DONE (Extract-only). 8-10 opt-in, 5-7 дней.
- **Действие:** подождать реального сигнала боли. Если в ближайший месяц нет запроса на context/mode — ставим on-hold. Если есть — phases 8-10 идут единым спринтом.
- **Effort:** 5-7 дней (если пойдёт). **Impact:** MED. **Приоритет:** pending-demand.

### C6. CI pipeline modernization (частичное закрытие F1 GAP_P0)
- **Проблема:** pre-commit hooks есть (.pre-commit-config.yaml), но единого CI workflow (GitHub Actions) нет для Python-фреймворка. Mixed-manual гейты.
- **Действие:**
  1. `.github/workflows/ci.yml` — matrix {3.11, 3.12} × {unit, integration, eval}
  2. Gate: coverage ≥ 70% (A6), mypy strict, ruff
  3. Pre-merge: B6 MCP Inspector smoke + B7 DeepEval eval
  4. Release: на tag `v*` — build + publish to private PyPI
- **Effort:** 2-3 дня. **Impact:** HIGH. **Dep:** A6.

### C7. Phase 67 (External BSL Tools Integration)
- **Проблема:** DEFERRED в BSL V4, 4 кандидата (claude-hud, codebase-memory-mcp, parry, sonar-bsl). Subset из них нужен.
- **Действие:** mini-evaluation каждого за 0.5 дня → keep/drop. **Вероятно оставить только:** `sonar-bsl-plugin` (252 stars, 100+ rules для 1С) + `bsl-language-server` standalone (уже используем в Serena Audit Variant A).
- **Effort:** 2-3 дня (если 2 кандидата). **Impact:** LOW-MED.

---

## 6. Evaluation matrix

```
Легенда: I=Impact (1-5), E=Effort (1-5, меньше лучше), D=Deps, T=Track
```

| # | Название | I | E | D | T | Горизонт | Risk |
|---|----------|---|---|---|---|----------|------|
| A1 | JWT в tenants.py | 5 | 1 | — | A | QW | security |
| A2 | Dual-write feedback | 4 | 2 | — | A | QW | data-loss |
| A5 | Stub embedding summary_index | 3 | 1 | — | A | QW | quality |
| C1 | ADR-008 verdict + smoke-gate fix | 5 | 2 | — | C | QW | CI block |
| B6 | MCP Inspector smoke | 3 | 1 | — | B | QW | low |
| A3 | Retry/CB unification | 3 | 3 | — | A | MT | regression |
| A4 | Sync-in-async рефакторинг | 3 | 3 | — | A | MT | regression |
| A6 | Test coverage | 4 | 4 | — | A | MT | effort |
| A7 | RAPTOR + LLM rerank | 3 | 3 | C2 | A | MT | quality |
| B1 | Contextual Retrieval | 5 | 3 | C2 | B | MT | low |
| B2 | GEPA replace MIPROv2 | 4 | 3 | A6,C1 | B | MT | metric-drift |
| B3 | OpenLLMetry + Langfuse | 5 | 4 | A1 | B | MT | infra |
| B4 | LangGraph Send API | 4 | 2 | — | B | MT | low |
| B7 | DeepEval gating | 3 | 2 | A6,C1 | B | MT | flaky |
| C2 | RAG eval dataset | 5 | 3 | — | C | MT | curation |
| C4 | Delegation Iter 4-5 | 3 | 3 | — | C | MT | low |
| C6 | CI pipeline (GH Actions) | 5 | 3 | A6 | C | MT | infra |
| B5 | Matryoshka embeddings | 4 | 4 | — | B | ST | migration |
| C3 | Memory P5 observability | 3 | 3 | B3 | C | ST | dep |
| C5 | Serena Phases 8-10 | 3 | 4 | — | C | ST | demand |
| C7 | Phase 67 external tools | 2 | 3 | — | C | ST | value |

Горизонты: **QW** = Quick Wins (≤ 2 недели), **MT** = Mid-Term (1-2 месяца), **ST** = Strategic (2-3 месяца).

---

## 7. Roadmap по горизонтам

### Горизонт 1 — Quick Wins (Неделя 1-2, ~5-7 дней FTE)

Цель: закрыть **security + CI unblock + quick infra**.

| Последовательность | Задача | Дн. |
|-----|--------|-----|
| 1.1 | **A1** JWT в tenants.py | 0.5 |
| 1.2 | **A2** Dual-write feedback (через ConflictResolver) | 0.5 |
| 1.3 | **A5** Stub embedding summary_index | 0.25 |
| 1.4 | **C1** ADR-008 verdict + smoke-gate safe-fallback | 1.0 |
| 1.5 | **B6** MCP Inspector smoke в CI | 0.5 |
| 1.6 | **buffer** для review / hotfix | 1-2 |

**Deliverables:** multi-tenant безопасно, CI не ломается, DSPy verdict записан.

### Горизонт 2 — Mid-Term (Месяц 1-2, ~18-22 дня FTE)

Цель: **качество поиска + observability + eval инфраструктура**.

```
Неделя 3:   C2 (eval dataset)  │  A6 (test coverage — параллельно)
Неделя 4:   B1 (Contextual)    │  B4 (Send API)
Неделя 5:   B3 (OTel + Langfuse) + A3 (retry unify)
Неделя 6:   B2 (GEPA A/B) + B7 (DeepEval gate)
Неделя 7:   A4 (sync-in-async) + A7 (RAPTOR + rerank)
Неделя 8:   C6 (CI pipeline) + C4 (Delegation 4-5) + buffer
```

**Deliverables:**
- Retrieval failure rate -50…-65% (B1 + B2)
- Observability complete: dashboard с tenant/user cost attribution (B3)
- Coverage ≥ 70% с CI gate (A6 + C6)
- DSPy GEPA в проде (B2)

### Горизонт 3 — Strategic (Месяц 2-3, ~8-12 дней FTE)

Цель: **storage-optimization + долги**.

| # | Когда | Trigger |
|---|-------|---------|
| **B5** Matryoshka migration | Неделя 9-10 | Storage > 100GB или cost > $X/mo |
| **C3** Memory P5 observability | Неделя 11 | После B3 baseline |
| **C5** Serena Phases 8-10 | on-demand | запрос на context/mode system |
| **C7** Phase 67 external tools | Неделя 12 | evaluator report → keep/drop |

---

## 8. Зависимости (DAG)

```
         ┌── A1 (JWT) ──────┐
         ├── A2 (dual-write)│
         ├── A5 (stub emb) ─┤
QW ──────┤                  ├── C1 (ADR-008) ──┐
         │                  │                  │
         └── B6 (inspector)─┘                  │
                                               │
MT ── A6 (coverage) ── C6 (CI)                 │
                   │                           │
                   └──> A3 (retry unify)       │
                        A4 (sync-async)        │
                                               │
      C2 (eval dataset) ──┬──> B1 (Contextual)│
                           ├──> B2 (GEPA) ────┤
                           ├──> B7 (DeepEval) ┘
                           ├──> A7 (RAPTOR)
                           └──> B3 metrics

      A1 ──> B3 (OTel tenant baggage) ──> C3 (Memory P5)

      B4 (Send) ── independent
      C4 (Delegation) ── independent
      B5 (MRL) ── independent
      C5, C7 ── on-demand
```

**Критический путь:** C2 → B1 → B2 → CI gate (C6 + B7). Если разблокировать C2 быстро, то B1/B2 идут параллельно.

---

## 9. Риски и митигации

| # | Риск | Митигация |
|---|------|-----------|
| R1 | B1 (Contextual Retrieval) повысит стоимость индексации | Prompt caching Claude -90% cost, ограничить для popular docs |
| R2 | B2 GEPA метрики flaky на малом dataset | Минимум 100 queries в C2, 3 прогона с CI |
| R3 | B3 Langfuse self-hosted — дополнительная инфра | Docker compose, опциональный flag `TRACING_ENABLED=false` |
| R4 | A3 retry unification ломает provider fallback | Feature flag `USE_UNIFIED_RETRY`, canary per-component |
| R5 | B5 Matryoshka migration — длительная reindex | Параллельная коллекция, downtime-free cutover |
| R6 | C6 CI gate блокирует merges по flaky тестам | `@pytest.mark.flaky(retries=3)`, quarantine queue |
| R7 | A7 LLM rerank — rate limits на Z.AI | CircuitBreaker + per-request timeout 5s, fallback к BM25-only |
| R8 | Весь roadmap может устареть | Ревью в середине каждого горизонта (неделя 4, 8) |

---

## 10. Открытые вопросы для решения перед стартом

1. **Бюджет API на contextual chunking (B1)** — оценка $0.01 / doc × 10K docs = $100 разовый + $0.001 / новый doc. Подтвердить у владельца бюджета.
2. **Matryoshka модель (B5)** — Jina v4 (Apache 2.0) vs Voyage (commercial). Выбор: Jina если нет требований к GPT-лицензии.
3. **Langfuse cloud vs self-hosted (B3)** — self-hosted MIT, но +ops. Cloud = $0-29/mo до 100K events. Рекомендация: self-hosted (уже есть infra).
4. **A3 retry unification** — делать ли сейчас (рискованно) или отложить до C6 CI (тесты подстрахуют)? Рекомендация: после A6 + C6, **не в первой неделе**.
5. **C5 Serena 8-10** — делать превентивно или ждать triggering use-case? Рекомендация: ждать.

---

## 11. Критерии успеха

**По горизонту 1 (QW):**
- [ ] `curl /admin/...` без JWT → 401 (A1)
- [ ] `pytest tests/eval/smoke_test.py` не падает в pre-commit (C1)
- [ ] `npx inspector smoke` зелёный в CI (B6)

**По горизонту 2 (MT):**
- [ ] Retrieval precision@10 на golden eval: baseline → +30% (B1 + B2)
- [ ] Langfuse dashboard: span coverage ≥ 90% LLM calls (B3)
- [ ] Coverage report: ≥ 70% на `src/pdf_framework` (A6)
- [ ] PR блокируется при regression > 5% на RAGAS faithfulness (B7)

**По горизонту 3 (ST):**
- [ ] Storage Qdrant: -60…-75% после Matryoshka (B5)
- [ ] Hook tracing: сквозная цепочка UserPromptSubmit → PostToolUse → Stop в одном trace (C3)

---

## 12. Следующие шаги (actionable)

**Сегодня / завтра:**
1. Review этого roadmap — принять / отклонить / переприоритизировать.
2. Запустить **A1** (JWT) как pilot — 2 часа, unblocks multi-tenant.
3. Создать `data/eval/rag/` со скелетом для **C2** — даже 20 queries разблокируют старт.

**На неделе:**
1. Закрыть Quick Wins (5-7 дней работы).
2. Решить open questions 1-3 из секции 10.
3. Завести Issue/OpenSpec change для каждого крупного пункта (C2, B1, B3).

**До конца месяца:**
1. C2 (eval dataset) + A6 (coverage) как фундамент для всего остального.
2. Старт B1 (Contextual) и B4 (Send API) — независимые, быстрые wins.

---

## 13. Справочные материалы

### Кеш исследований
- [framework-gaps-analysis-2026-04.md](../../.claude/skills/architecture-research/cache/framework-gaps-analysis-2026-04.md)
- [production-rag-patterns-2026.md](../../.claude/skills/architecture-research/cache/production-rag-patterns-2026.md)
- [ai-agent-memory-systems-2026.md](../../.claude/skills/architecture-research/cache/ai-agent-memory-systems-2026.md) (для справки по memory landscape)

### Связанные roadmap'ы
- [GAP_ROADMAP.md](GAP_ROADMAP.md) — 187 задач, Phase 44-61 (частично закрыт)
- [260413_Hermes Agent...md](260413_Hermes%20Agent%20и%20LLM%20Wiki%20Карпати%20персистентные%20системы%20знаний.md) — Phases 0-6 DONE
- [260320_ROADMAP_DELEGATION_LEARNING.md](260320_ROADMAP_DELEGATION_LEARNING.md) — Iter 1-3 DONE
- [260414_Serena Audit...md](260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md) — Phases 0-7 DONE
- [ROADMAP_BSL_INTELLIGENCE_V4/PHASE_67.md](ROADMAP_BSL_INTELLIGENCE_V4/PHASE_67.md) — DEFERRED

### Ключевые источники best practices
- https://www.anthropic.com/news/contextual-retrieval — Contextual RAG (B1)
- https://github.com/gepa-ai/gepa — GEPA (B2)
- https://langfuse.com/integrations/native/opentelemetry — Langfuse + OTel (B3)
- https://docs.langchain.com/oss/python/langgraph/workflows-agents — Send API (B4)
- https://qdrant.tech/blog/qdrant-1.16.x/ — Tiered Multi-tenancy + MRL (B5)
- https://glama.ai/mcp/inspector — MCP Inspector (B6)
- https://deepeval.com/ — DeepEval gating (B7)

---

## Changelog

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0 | 2026-04-23 | Первичная дорожная карта на базе gaps-analysis + best-practices-2026 |
