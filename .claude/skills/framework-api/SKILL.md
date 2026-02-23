---
name: framework-api
description: "REST API endpoints PDF Framework. Триггеры: 'REST API', 'endpoint', 'curl', 'HTTP', 'API запрос', 'OpenAI compatible', 'websocket', 'Swagger', '/search/', '/documents/'. НЕ для CLI — используй framework-cli."
---

# Framework REST API — все endpoints

## Когда использовать
- "какие endpoints есть", "как отправить API запрос", "curl пример"
- "POST /search/", "OpenAI compatible", "websocket"
- Любые вопросы об HTTP API

## Запуск

```bash
python -m src.cli.main server --port 8000
# → http://localhost:8000
# → Swagger UI: http://localhost:8000/docs
```

---

## Quick Reference

| Задача | Method | Endpoint |
|--------|--------|----------|
| Поиск | `POST` | `/search/` |
| RAG вопрос | `POST` | `/search/ask` |
| RAG streaming | `POST` | `/search/ask/stream` |
| Индексация PDF | `POST` | `/documents/index` |
| Список документов | `GET` | `/documents/` |
| Health check | `GET` | `/health` |
| OpenAI chat | `POST` | `/v1/chat/completions` |

---

## Все endpoints по категориям

### Health

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/health` | Полный health check (vector_store, graph, llm, disk) |
| `GET` | `/health/ready` | K8s readiness probe (200/503) |
| `GET` | `/health/live` | K8s liveness probe (200) |

### Поиск

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/search/` | Поиск по документам (14+ стратегий) |
| `POST` | `/search/ask` | RAG question-answering (SSE streaming) |
| `POST` | `/search/suggest` | Предложения запросов |
| `POST` | `/search/analyze` | Analytical RAG — evidence + comparison (Phase 33) |
| `POST` | `/search/research` | Deep Research v2 — plan-execute-verify (Phase 36) |
| `POST` | `/search/multi-agent` | Multi-agent orchestration (Phase 39) |
| `POST` | `/search/visual` | ColPali visual search по страницам PDF (Phase 55) |
| `POST` | `/search/plan-execute` | Plan-Execute agent — DAG план (Phase 57) |

```bash
# Поиск
curl -X POST http://localhost:8000/search/ \
    -H "Content-Type: application/json" \
    -d '{"query": "конфигуратор", "strategy": "hybrid", "k": 5, "rerank": true}'

# RAG вопрос-ответ
curl -X POST http://localhost:8000/search/ask \
    -H "Content-Type: application/json" \
    -d '{"query": "Что такое конфигуратор?", "strategy": "hybrid"}'

# RAG с streaming (SSE)
curl -X POST http://localhost:8000/search/ask/stream \
    -H "Content-Type: application/json" \
    -d '{"query": "Опишите архитектуру"}'
```

### Документы

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/documents/upload` | Upload PDF файла |
| `POST` | `/documents/index` | Индексация PDF |
| `POST` | `/documents/index/stream` | Streaming индексация (NDJSON прогресс) |
| `POST` | `/documents/index/batch/stream` | Batch indexing нескольких PDF (Phase 32) |
| `POST` | `/documents/index/delta` | Инкрементальная индексация (Phase 18) |
| `GET` | `/documents/index/delta/stats` | Статистика delta |
| `POST` | `/documents/index/delta/clear` | Очистка delta cache |
| `POST` | `/documents/index-async` | Async indexing через ARQ queue (Phase 59) |
| `GET` | `/documents/` | Список документов |
| `GET` | `/documents/files` | Список загруженных PDF |
| `GET` | `/documents/registry` | Реестр документов с метаданными (Phase 32) |
| `PATCH` | `/documents/registry/{id}` | Обновление метаданных |
| `GET` | `/documents/stats` | Статистика индекса |
| `DELETE` | `/documents/{id}` | Удаление (каскадное) |
| `DELETE` | `/documents/clear` | Полная очистка vector store |
| `POST` | `/documents/rebuild-bm25` | Пересборка BM25 FTS5 |
| `POST` | `/documents/rebuild-sparse` | Пересборка Qdrant sparse BM25 |

```bash
# Индексация
curl -X POST http://localhost:8000/documents/index \
    -F "file=@document.pdf" -F 'options={"graph": true}'

# Список
curl http://localhost:8000/documents/

# Удаление (каскадное)
curl -X DELETE http://localhost:8000/documents/{document_id}

# Пересборка BM25
curl -X POST http://localhost:8000/documents/rebuild-bm25
```

### Граф знаний

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/graph/stats` | Статистика (entities, edges, communities) |
| `GET` | `/graph/entities` | Поиск/список entities |
| `DELETE` | `/graph/clear` | Очистка графа |
| `POST` | `/graph/build-communities` | Leiden community detection + LLM summarization |
| `POST` | `/graph/build-entity-embeddings` | LightRAG entity embeddings (Phase 38) |

### Chat

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/chat/message` | Сообщение в чат (SSE streaming) |
| `GET` | `/chat/history/{thread_id}` | История разговора |
| `GET` | `/chat/threads` | Список всех тредов |
| `DELETE` | `/chat/threads/{thread_id}` | Удаление треда |

### ToC (Оглавление)

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/toc/{doc_id}` | Оглавление документа |
| `GET` | `/toc/{doc_id}/section/{num}` | Конкретный раздел |
| `POST` | `/toc/{doc_id}/generate-summaries` | LLM-суммаризации секций (Phase 30) |

### Cache

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/cache/stats` | Статистика кэша |
| `POST` | `/cache/clear` | Очистка кэша |

### Feedback

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/feedback/submit` | Оценка результата (Phase 22) |
| `GET` | `/feedback/stats` | Статистика обратной связи |

### Metrics

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/metrics` | JSON: system + hook + skill + enforcement метрики |
| `GET` | `/metrics/html` | Unified HTML dashboard (cache, hooks, skills, errors) |
| `POST` | `/metrics/reset` | Reset daily counters |
| `GET` | `/metrics/prometheus` | Prometheus exposition format |

**`GET /metrics` JSON response** включает:
- `embedding_cache`, `llm_cache`, `document_cache` — cache stats
- `hook_metrics` — per-hook: count, avg_ms, p95_ms, blocks, errors (24h)
- `skill_metrics` — activation_rate, `by_source` (prompt-detection/post-tool-use), per_skill recommended/activated/rate/sources
- `accuracy` — prompt-level recommend→activate match_rate
- `enforcement` — total_blocks, block_rate, per_hook outcome breakdown
- `errors` — recent error log entries

**`GET /metrics/html`** — unified dashboard с секциями:
1. Key Metrics (queries, latency, cache, error rate)
2. Cache Statistics (embedding, LLM, document)
3. Search Strategy Usage
4. **Hook Invocations (24h)** — таблица: hook, count, avg_ms, p95, blocks, errors
5. **Skill Activations (24h)** — activation rate cards + Prompt Detection/PostToolUse cards + per-skill table with Source column
6. **Enforcement & Errors** — blocks/rate cards + recent errors table
7. **Try It** — interactive query box: Search (POST /search/) и Ask RAG (POST /search/ask) с выбором strategy/k

### Auth

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/auth/token` | Получить JWT токен |
| `POST` | `/auth/validate` | Валидировать JWT токен |

### Tenants (Phase 60)

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/tenants/` | Создать тенант |
| `GET` | `/tenants/` | Список тенантов |
| `GET` | `/tenants/{id}` | Информация о тенанте |
| `PATCH` | `/tenants/{id}` | Обновить тенант |
| `DELETE` | `/tenants/{id}` | Удалить тенант |
| `GET` | `/tenants/{id}/stats` | Usage statistics |
| `GET` | `/tenants/{id}/quotas` | Квоты тенанта |

### Collections (Phase 32)

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/collections/` | Создать коллекцию |
| `GET` | `/collections/` | Список коллекций |
| `GET` | `/collections/{id}` | Информация о коллекции |
| `PATCH` | `/collections/{id}` | Обновить коллекцию |
| `POST` | `/collections/{id}/documents` | Добавить документы |
| `DELETE` | `/collections/{id}/documents/{doc_id}` | Удалить документ из коллекции |

### Analytics (Phase 40)

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/analytics/summary` | Сводная аналитика |
| `GET` | `/analytics/queries` | Аналитика запросов |
| `GET` | `/analytics/queries/recent` | Последние запросы |
| `GET` | `/analytics/costs` | Отслеживание затрат |
| `GET` | `/analytics/audit` | Аудит-логи |

### Optimization (Phase 34)

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/optimization/stats` | Статистика DSPy оптимизации |
| `POST` | `/optimization/optimize` | Запустить MIPROv2 |
| `GET` | `/optimization/dataset` | Просмотр eval dataset |
| `POST` | `/optimization/dataset/add` | Добавить Q&A пары |

### Jobs (Phase 59)

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/jobs/enqueue` | Поставить задачу в очередь |
| `GET` | `/jobs/` | Список задач |
| `GET` | `/jobs/{id}` | Статус задачи |
| `POST` | `/jobs/{id}/cancel` | Отменить задачу |
| `GET` | `/jobs/{id}/progress` | Streaming прогресса (SSE) |

### WebSocket (Phase 49)

| Method | Endpoint | Описание |
|--------|----------|----------|
| `WS` | `/ws/search` | WebSocket streaming поиска |

---

## OpenAI-Compatible API

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/v1/chat/completions` | Chat с RAG (streaming) |
| `POST` | `/v1/embeddings` | Embedding generation |
| `GET` | `/v1/models` | Список доступных моделей |

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "pdf-rag", "messages": [{"role": "user", "content": "Что такое конфигуратор?"}]}'
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
response = client.chat.completions.create(
    model="pdf-rag",
    messages=[{"role": "user", "content": "Что такое конфигуратор?"}],
    stream=True,
)
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

Поддерживаемые параметры: `model` ("pdf-rag"), `messages`, `stream`. `temperature` и `max_tokens` игнорируются.

---

## Авторизация API

```bash
# Запрос с JWT токеном
curl -X POST http://localhost:8000/search/ \
    -H "Authorization: Bearer <jwt-token>" \
    -H "Content-Type: application/json" \
    -d '{"query": "конфигуратор"}'

# Tenant через заголовок
curl -X POST http://localhost:8000/search/ \
    -H "X-Tenant-ID: company-a" \
    -d '{"query": "конфигуратор"}'
```

---

## Связанные скиллы

- `framework-cli` — CLI альтернатива API
- `framework-config` — .env для API, Auth, Rate Limiting
- `deployment` — Docker, health checks, production запуск


## Незадокументированные REST API Endpoints

| Method | Endpoint | Source |
|--------|----------|--------|
| `GET` | `/analytics/audit/stats` | `src\api\routes\analytics.py` |
| `GET` | `/analytics/audit/user/{user_id}` | `src\api\routes\analytics.py` |
| `GET` | `/chat/stats/{thread_id}` | `src\api\routes\chat.py` |
| `GET` | `/collections/{collection_id}` | `src\api\routes\collections.py` |
| `PATCH` | `/collections/{collection_id}` | `src\api\routes\collections.py` |
| `DELETE` | `/collections/{collection_id}` | `src\api\routes\collections.py` |
| `POST` | `/collections/{collection_id}/documents` | `src\api\routes\collections.py` |
| `DELETE` | `/collections/{collection_id}/documents/{document_id}` | `src\api\routes\collections.py` |
| `GET` | `/collections/{collection_id}/documents` | `src\api\routes\collections.py` |
| `POST` | `/completions/chat/completions` | `src\api\routes\completions.py` |
| `GET` | `/completions/models` | `src\api\routes\completions.py` |
| `GET` | `/completions/models/{model_id}` | `src\api\routes\completions.py` |
| `POST` | `/completions/embeddings` | `src\api\routes\completions.py` |
| `PATCH` | `/documents/registry/{document_id}` | `src\api\routes\documents.py` |
| `GET` | `/feedback/examples/positive` | `src\api\routes\feedback.py` |
| `POST` | `/feedback/tune` | `src\api\routes\feedback.py` |
| `POST` | `/feedback/clear` | `src\api\routes\feedback.py` |
| `GET` | `/graph/entity-embeddings/stats` | `src\api\routes\graph.py` |
| `GET` | `/graph/neighbors/{entity_id}` | `src\api\routes\graph.py` |
| `POST` | `/graph/incremental-update` | `src\api\routes\graph.py` |
| `GET` | `/graph/incremental/detect-changes` | `src\api\routes\graph.py` |
| `GET` | `/jobs/{job_id}` | `src\api\routes\jobs.py` |
| `DELETE` | `/jobs/{job_id}` | `src\api\routes\jobs.py` |
| `GET` | `/jobs/{job_id}/stream` | `src\api\routes\jobs.py` |
| `GET` | `/metrics/html` | `src\api\routes\metrics.py` |
| `POST` | `/metrics/reset` | `src\api\routes\metrics.py` |
| `GET` | `/metrics/prometheus` | `src\api\routes\metrics.py` |
| `POST` | `/openai_compat/chat/completions` | `src\api\routes\openai_compat.py` |
| `POST` | `/openai_compat/embeddings` | `src\api\routes\openai_compat.py` |
| `GET` | `/openai_compat/models` | `src\api\routes\openai_compat.py` |
| `GET` | `/optimization/last-result` | `src\api\routes\optimization.py` |
| `GET` | `/tenants/{tenant_id}` | `src\api\routes\tenants.py` |
| `GET` | `/tenants/{tenant_id}/stats` | `src\api\routes\tenants.py` |
| `GET` | `/tenants/{tenant_id}/usage` | `src\api\routes\tenants.py` |
| `PUT` | `/tenants/{tenant_id}` | `src\api\routes\tenants.py` |
| `DELETE` | `/tenants/{tenant_id}` | `src\api\routes\tenants.py` |
| `GET` | `/toc/{document_id}` | `src\api\routes\toc.py` |
| `GET` | `/toc/{document_id}/section/{section_number:path}` | `src\api\routes\toc.py` |
| `POST` | `/toc/{document_id}/generate-summaries` | `src\api\routes\toc.py` |
| `WEBSOCKET` | `/websocket/ws/search` | `src\api\routes\websocket.py` |

## Файлы

- App: `src/api/app.py`
- Routes: `src/api/routes/` (17 routers)
- Guardrails Middleware: `src/api/middleware/guardrails.py`
- Auth: `src/api/dependencies/auth.py`
- DI: `src/api/dependencies/components.py`
