# P0 — Фундамент

**Effort:** 6-10 дней | **Impact:** HIGH | **Phases:** 44-46
**Зависимости:** Нет (первый приоритет)

---

## F1 — CI/CD Pipeline (Phase 44)

**Текущее:** `.github/workflows/ci.yml` существует (4 jobs: lint, typecheck, docstrings, test). Qdrant service container. Trigger: push/PR to main/master.
**Gap:** Нет pre-commit, нет badge в README, нет caching зависимостей, нет separate staging.

### F1.1 Pre-commit hooks

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| F1.1.1 | Создать `.pre-commit-config.yaml` | `.pre-commit-config.yaml` | ~30 | `pre-commit run --all-files` |
| F1.1.2 | Hook: ruff (lint + format) | В config | — | ruff check src/ |
| F1.1.3 | Hook: mypy type check | В config | — | mypy src/ |
| F1.1.4 | Hook: trailing whitespace + EOF | В config | — | Автоматический |
| F1.1.5 | Hook: check-yaml, check-json | В config | — | Валидация конфигов |
| F1.1.6 | Hook: no-commit-to-branch (main) | В config | — | Блокирует прямые пуши в main |
| F1.1.7 | Установить pre-commit | `pip install pre-commit && pre-commit install` | — | `.git/hooks/pre-commit` существует |
| F1.1.8 | Добавить `pre-commit` в dev dependencies | `pyproject.toml` | +1 | `pip install .[dev]` включает pre-commit |

**Acceptance:** `pre-commit run --all-files` проходит без ошибок.

**Файл `.pre-commit-config.yaml`:**
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: no-commit-to-branch
        args: ['--branch', 'main']
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, fastapi]
        args: [--ignore-missing-imports]
```

---

### F1.2 CI Improvements

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| F1.2.1 | Добавить pip caching | `.github/workflows/ci.yml` | +5 | Cache hit в логах GH Actions |
| F1.2.2 | Добавить coverage upload (Codecov) | `.github/workflows/ci.yml` | +10 | Badge в README |
| F1.2.3 | Добавить badge: CI status | `README.md` | +2 | Badge отображается |
| F1.2.4 | Добавить badge: coverage % | `README.md` | +1 | Badge отображается |
| F1.2.5 | Добавить pre-commit CI check | `.github/workflows/ci.yml` | +15 | Job `pre-commit` passes |
| F1.2.6 | Pinning Python version matrix (3.11, 3.12) | `.github/workflows/ci.yml` | +8 | Test job runs on both versions |

**Acceptance:** CI pipeline <5 мин, badges зелёные в README.

---

### F1.3 Makefile targets

| # | Подзадача | Файл | Строк |
|---|-----------|------|-------|
| F1.3.1 | `make ci` — полная CI проверка локально | `Makefile` | +3 |
| F1.3.2 | `make pre-commit` — запуск pre-commit hooks | `Makefile` | +2 |
| F1.3.3 | `make requirements` — генерация requirements.txt из pyproject.toml | `Makefile` | +2 |

**Acceptance:** `make ci` эквивалентен полному CI pipeline.

---

## F2 — Test Suite (Phase 45)

**Текущее:** 60 test files в `tests/`, pytest + pytest-asyncio + pytest-cov. conftest.py с 3 fixtures. Структура unit/integration/e2e существует но unit/ пуста.
**Gap:** Unit тесты не написаны. Нет fixtures для Qdrant mock. Нет маркеров `@pytest.mark.slow`. Нет test для hooks.

### F2.1 Test infrastructure

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| F2.1.1 | Добавить pytest markers (slow, integration, e2e) | `pyproject.toml` | +6 | `pytest --markers` показывает 3 custom |
| F2.1.2 | Добавить marker `@pytest.mark.slow` к тестам >5s | Разные test_*.py | ~20 правок | `pytest -m "not slow"` быстрый |
| F2.1.3 | Fixture: mock Qdrant client | `tests/conftest.py` | +40 | Тесты не требуют Docker |
| F2.1.4 | Fixture: mock Anthropic client | `tests/conftest.py` | +30 | Тесты не вызывают API |
| F2.1.5 | Fixture: sample ProcessedDocument | `tests/conftest.py` | +25 | Переиспользуется в unit |
| F2.1.6 | Fixture: temp data directory | `tests/conftest.py` | +10 | Каждый тест в изоляции |
| F2.1.7 | Fixture: settings override (in-memory stores) | `tests/conftest.py` | +20 | Тесты не зависят от .env |

**Acceptance:** `pytest tests/ -v -m "not slow"` <30 sec, без Docker/API.

---

### F2.2 Unit tests — Config

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.2.1 | Test Settings загрузка из .env | `tests/unit/test_config.py` | ~40 | config/_base.py |
| F2.2.2 | Test EmbeddingSettings валидация | `tests/unit/test_config.py` | ~30 | config/embedding.py |
| F2.2.3 | Test VectorStoreSettings (qdrant vs chroma) | `tests/unit/test_config.py` | ~30 | config/vector_store.py |
| F2.2.4 | Test SearchSettings defaults | `tests/unit/test_config.py` | ~20 | config/search.py |

---

### F2.3 Unit tests — Search

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.3.1 | Test SearchManager.register_strategy | `tests/unit/search/test_manager.py` | ~40 | search/manager.py |
| F2.3.2 | Test SearchManager.search routing | `tests/unit/search/test_manager.py` | ~50 | search/manager.py |
| F2.3.3 | Test BM25Store add/search | `tests/unit/search/test_bm25.py` | ~60 | search/bm25_store.py |
| F2.3.4 | Test BM25Store FTS5 schema migration | `tests/unit/search/test_bm25.py` | ~40 | search/bm25_store.py |
| F2.3.5 | Test TwoStagePipeline classify_query | `tests/unit/search/test_pipeline.py` | ~50 | search/pipelines/two_stage.py |
| F2.3.6 | Test SectionFirstPipeline dominant section | `tests/unit/search/test_pipeline.py` | ~40 | search/pipelines/section_first.py |
| F2.3.7 | Test RRF fusion formula | `tests/unit/search/test_fusion.py` | ~30 | search/strategies/ |

---

### F2.4 Unit tests — Embeddings

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.4.1 | Test LocalEmbeddingProvider init + prefix | `tests/unit/embeddings/test_local.py` | ~40 | embeddings/providers/local.py |
| F2.4.2 | Test embed_batch chunking (batch_size) | `tests/unit/embeddings/test_local.py` | ~30 | embeddings/providers/local.py |
| F2.4.3 | Test SQLite embedding cache hit/miss | `tests/unit/embeddings/test_cache.py` | ~50 | embeddings/cache/sqlite_cache.py |

---

### F2.5 Unit tests — Loaders

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.5.1 | Test HybridLoader level selection | `tests/unit/loaders/test_hybrid.py` | ~60 | loaders/providers/hybrid_loader.py |
| F2.5.2 | Test page_offsets correctness | `tests/unit/loaders/test_hybrid.py` | ~40 | loaders/providers/hybrid_loader.py |
| F2.5.3 | Test coverage verification | `tests/unit/loaders/test_hybrid.py` | ~30 | loaders/providers/hybrid_loader.py |

---

### F2.6 Unit tests — Processing

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.6.1 | Test RecursiveSplitter chunk sizes | `tests/unit/processing/test_splitters.py` | ~40 | processing/splitters/recursive.py |
| F2.6.2 | Test SemanticSplitter boundary detection | `tests/unit/processing/test_splitters.py` | ~50 | processing/splitters/semantic.py |
| F2.6.3 | Test Pipeline._assign_page_numbers | `tests/unit/processing/test_pipeline.py` | ~40 | processing/pipeline.py |
| F2.6.4 | Test deterministic ID generation | `tests/unit/processing/test_ids.py` | ~30 | utils/id_generator.py |

---

### F2.7 Unit tests — Vector Store

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.7.1 | Test Qdrant _to_qdrant_id determinism | `tests/unit/vector_store/test_qdrant.py` | ~30 | vector_store/providers/qdrant.py |
| F2.7.2 | Test Qdrant hybrid_search RRF merge | `tests/unit/vector_store/test_qdrant.py` | ~50 | vector_store/providers/qdrant.py |
| F2.7.3 | Test Qdrant MMR with named vectors | `tests/unit/vector_store/test_qdrant.py` | ~40 | vector_store/providers/qdrant.py |

---

### F2.8 Unit tests — Graph Store

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.8.1 | Test NetworkXGraphStore add/get entity | `tests/unit/graph_store/test_networkx.py` | ~40 | graph_store/providers/networkx_store.py |
| F2.8.2 | Test deduplication in GraphBuilder | `tests/unit/graph_store/test_builder.py` | ~50 | graph_store/construction/builder.py |
| F2.8.3 | Test JSON persistence (save/load) | `tests/unit/graph_store/test_networkx.py` | ~40 | graph_store/providers/networkx_store.py |

---

### F2.9 Unit tests — Agents

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.9.1 | Test RAG agent node: grader | `tests/unit/agents/test_rag_nodes.py` | ~50 | agents/rag/nodes/ |
| F2.9.2 | Test RAG agent node: rewriter | `tests/unit/agents/test_rag_nodes.py` | ~40 | agents/rag/nodes/ |
| F2.9.3 | Test StreamingRAGRunner event types | `tests/unit/agents/test_streaming.py` | ~40 | agents/rag/streaming.py |

---

### F2.10 Unit tests — API

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.10.1 | Test health endpoints (live, ready) | `tests/unit/api/test_health.py` | ~30 | api/routes/health.py |
| F2.10.2 | Test JWT create + verify | `tests/unit/api/test_auth.py` | ~40 | api/auth/jwt_handler.py |
| F2.10.3 | Test RBAC permission check | `tests/unit/api/test_auth.py` | ~40 | api/auth/rbac.py |
| F2.10.4 | Test rate limiter (token bucket) | `tests/unit/api/test_rate_limit.py` | ~40 | api/middleware/rate_limit.py |

---

### F2.11 Integration tests

| # | Подзадача | Файл | Строк | Покрытие |
|---|-----------|------|-------|----------|
| F2.11.1 | Test full indexing pipeline (PDF → chunks → Qdrant) | `tests/integration/test_indexing.py` | ~80 | Весь indexing flow |
| F2.11.2 | Test full search pipeline (query → results) | `tests/integration/test_search.py` | ~60 | Весь search flow |
| F2.11.3 | Test API endpoints via TestClient | `tests/integration/test_api.py` | ~80 | FastAPI routes |

**Acceptance:** Coverage > 60% (с `pytest-cov`). `make test-fast` < 1 мин.

---

## F3 — Observability: Langfuse (Phase 46)

**Текущее:** `tracer.py` — JsonFileTracer (JSONL), LangSmithTracer (stub), NoOpTracer. MetricsCollector (in-memory). HTML dashboard. Analytics (SQLite). TokenTracker middleware.
**Gap:** Нет Langfuse/OpenTelemetry. Нет distributed tracing. Нет trace visualization.

### F3.1 Langfuse SDK integration

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| F3.1.1 | Добавить `langfuse` в dependencies | `pyproject.toml` | +1 | `pip install .[observability]` |
| F3.1.2 | Создать `LangfuseTracer(BaseTracer)` | `src/pdf_framework/observability/langfuse_tracer.py` | ~80 | Unit test |
| F3.1.3 | Реализовать `span()` → Langfuse generation | Тот же файл | ~40 | Trace видна в Langfuse UI |
| F3.1.4 | Реализовать `record_query()` → Langfuse score | Тот же файл | ~30 | Score записана |
| F3.1.5 | Env vars: `LANGFUSE_PUBLIC_KEY`, `SECRET_KEY`, `HOST` | `src/pdf_framework/config/observability.py` | +6 | Config загружается |
| F3.1.6 | Factory: `create_tracer(type)` → выбор реализации | `src/pdf_framework/observability/__init__.py` | ~20 | Конфиг `tracer=langfuse` |

**Acceptance:** Traces видны в Langfuse dashboard с latency, tokens, scores.

---

### F3.2 LangChain callback handler

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| F3.2.1 | Создать `LangfuseCallbackHandler` | `src/pdf_framework/observability/langfuse_callback.py` | ~60 | Unit test |
| F3.2.2 | Интеграция с RAG agent (`with_middleware`) | `src/pdf_framework/agents/rag/agent.py` | +5 | Trace включает все LLM calls |
| F3.2.3 | Интеграция с grader, rewriter, hallucination_checker | 3 файла по +3 строки | +9 | Каждый LLM call трейсится |
| F3.2.4 | Передача user_id из API request → trace | `src/api/routes/search.py`, `chat.py` | +4 | User attribution в traces |

**Acceptance:** Каждый RAG запрос создаёт полный trace tree: query → retrieval → grading → generation.

---

### F3.3 Metrics export

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| F3.3.1 | Добавить `prometheus-client` в dependencies | `pyproject.toml` | +1 | Import работает |
| F3.3.2 | Создать Prometheus counters/histograms | `src/pdf_framework/observability/prometheus_metrics.py` | ~50 | Unit test |
| F3.3.3 | Endpoint `GET /metrics/prometheus` | `src/api/routes/metrics.py` | +15 | curl возвращает Prometheus format |
| F3.3.4 | Instrument: query_latency_seconds (histogram) | Тот же файл | +5 | Гистограмма записывается |
| F3.3.5 | Instrument: query_total (counter by strategy) | Тот же файл | +5 | Счётчик увеличивается |
| F3.3.6 | Instrument: cache_hit_total (counter) | Тот же файл | +5 | Счётчик увеличивается |
| F3.3.7 | Instrument: token_usage_total (counter by model) | Тот же файл | +5 | Счётчик увеличивается |

**Acceptance:** `curl /metrics/prometheus` возвращает валидный Prometheus exposition format.

---

### F3.4 Dashboard & alerting config

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| F3.4.1 | Создать Grafana dashboard JSON | `docker/grafana/dashboards/rag-overview.json` | ~200 | Import в Grafana |
| F3.4.2 | Panels: latency p95, cache hit rate, queries/min | В dashboard JSON | — | Визуализация работает |
| F3.4.3 | Panels: token usage, cost per day, errors | В dashboard JSON | — | Визуализация работает |
| F3.4.4 | Создать `docker/prometheus.yml` (отсутствует!) | `docker/prometheus.yml` | ~20 | Prometheus scrapes API |
| F3.4.5 | Alert rule: p95 latency > 5s | `docker/prometheus/alerts.yml` | ~15 | Alert fires в тестовом режиме |

**Acceptance:** Grafana dashboard отображает real-time метрики. Prometheus собирает данные каждые 15s.

---

## Чеклист завершения P0

- [ ] `.pre-commit-config.yaml` создан и проходит
- [ ] CI pipeline: 5 jobs (lint, type, docstrings, pre-commit, test)
- [ ] pytest markers: slow, integration, e2e
- [ ] Unit tests: > 30 новых файлов
- [ ] Coverage > 60%
- [ ] `make test-fast` < 1 мин
- [ ] Langfuse tracer подключён
- [ ] Prometheus endpoint `/metrics/prometheus` работает
- [ ] Grafana dashboard импортирован
- [ ] `docker/prometheus.yml` создан
- [ ] README badges: CI status + coverage
