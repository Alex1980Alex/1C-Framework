---
name: deployment
description: "Deployment — развёртывание PDF Framework в production. ИСПОЛЬЗУЙ когда настраиваешь Docker, production окружение, health checks, rate limiting, CORS, JWT авторизацию, мультитенантность, мониторинг. Триггеры: 'deploy', 'docker', 'production', 'health check', 'rate limiting', 'CORS', 'мультитенантность', 'JWT', 'мониторинг', 'docker compose'. НЕ для локальной разработки (→ framework-quickstart)."
---

# Deployment

## Когда использовать
- "deploy", "docker", "production"
- "health check", "rate limiting", "CORS"
- "мультитенантность", "авторизация", "JWT", "мониторинг"
- Настройка окружения, мониторинг, Docker compose

---

## Для пользователя — администрирование

### Мультитенантность

| Компонент | Изоляция |
|-----------|----------|
| Qdrant | Отдельная коллекция per tenant |
| BM25 FTS5 | Фильтр по tenant_id |
| Graph Store | Отдельный граф per tenant |
| Cache | Ключ включает tenant_id |

```bash
# CLI
pdf-framework tenant create --id company-a
pdf-framework tenant list
pdf-framework tenant delete --id company-a

# Индексация и поиск в тенанте
python -m src.cli.main index "doc.pdf" --tenant company-a
python -m src.cli.main search "запрос" --tenant company-a
```

```bash
# API
curl -X POST http://localhost:8000/tenants/ \
    -d '{"id": "company-a", "name": "Company A"}'
curl -X POST http://localhost:8000/search/ \
    -H "X-Tenant-ID: company-a" -d '{"query": "запрос"}'
```

### Авторизация (JWT + RBAC)

| Роль | Права |
|------|-------|
| **viewer** | Поиск, чтение |
| **editor** | + индексация, удаление |
| **admin** | + управление тенантами, настройками |

```bash
pdf-framework auth token --tenant company-a --role admin
curl -H "Authorization: Bearer <jwt-token>" http://localhost:8000/search/ ...
```

```env
AUTH__ENABLED=true
AUTH__JWT_SECRET=your-secret-key-min-32-chars-long
AUTH__JWT_EXPIRATION_HOURS=24
```

### Мониторинг

| Компонент | Назначение | Настройка |
|-----------|-----------|-----------|
| JSON Tracing | Логи операций | `OBSERVABILITY__TRACER=jsonfile` |
| Langfuse | LLM traces, costs | `LANGFUSE__ENABLED=true` |
| Prometheus | Метрики | `GET /metrics/` |
| HTML Dashboard | Визуализация | `GET /metrics/html` |

```env
LANGFUSE__ENABLED=true
LANGFUSE__PUBLIC_KEY=pk-...
LANGFUSE__SECRET_KEY=sk-...
LANGFUSE__HOST=https://cloud.langfuse.com
```

Prometheus: `search_requests_total`, `search_latency_seconds`, `index_chunks_total`, `cache_hits_total`, `llm_tokens_total`

---

## Infrastructure — Docker и запуск

## Docker Compose Stack

| Сервис | Image | Port | Назначение |
|--------|-------|------|-----------|
| `api` | python:3.11-slim | 8000 | FastAPI + Gradio UI |
| `qdrant` | qdrant:v1.12.0 | 6333, 6334 | Vector store (API + gRPC) |
| `db` | pgvector:pg16 | 5432 | PostgreSQL + pgvector |
| `redis` | redis:7-alpine | 6379 | Cache + rate limiting |
| `nginx` | nginx:alpine | 80, 443 | Reverse proxy |
| `prometheus` | prom/prometheus | 9090 | Metrics |
| `grafana` | grafana:latest | 3000 | Dashboards |

## Health Checks

| Endpoint | Назначение | Returns |
|----------|-----------|---------|
| `GET /health` | Full health | vector_store, graph_store, llm, disk_space |
| `GET /health/ready` | K8s readiness | 200/503 по vector_store |
| `GET /health/live` | K8s liveness | 200 if alive |

## Rate Limiting

- **In-memory**: Token bucket (100 req/60s default)
- **Redis**: Distributed rate limiting
- Key: X-API-Key → `apikey:{key}`, X-Forwarded-For → `ip:{ip}`
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`

```env
RATE_LIMIT__ENABLED=true
RATE_LIMIT__REQUESTS_PER_MINUTE=60
RATE_LIMIT__BURST=10
```

## Async Workers / ARQ Queue (Phase 59)

Тяжёлые задачи (индексация, граф, evaluation) выполняются асинхронно через ARQ + Redis.

| Компонент | Назначение |
|-----------|-----------|
| `src/workers/worker.py` | ARQ Worker entry point (factory: `create_worker()`) |
| `src/workers/tasks/indexing.py` | index_document, rebuild_bm25, rebuild_embeddings |
| `src/workers/tasks/graph.py` | rebuild_graph (entities + relations) |
| `src/workers/tasks/evaluation.py` | run_evaluation (RAGAS) |

### Запуск Worker

```bash
# Worker (отдельный процесс)
arq src.workers.worker.WorkerSettings

# Или через Makefile
make worker
```

### Конфигурация

```env
QUEUE__REDIS_URL=redis://localhost:6379
QUEUE__MAX_JOBS=10
QUEUE__JOB_TIMEOUT=3600
QUEUE__RETRY_ATTEMPTS=3
QUEUE__RETRY_DELAY_SECONDS=60
```

### Постановка задач

```bash
# Async индексация через API
curl -X POST http://localhost:8000/documents/index-async \
    -F "file=@document.pdf" -F 'options={"graph": true}'

# Статус задачи
curl http://localhost:8000/jobs/{job_id}

# Streaming прогресса (SSE)
curl http://localhost:8000/jobs/{job_id}/progress
```

### Progress Tracking

Каждая задача обновляет прогресс в Redis (0-100%):
- **Indexing**: loading → chunking → indexing → embedding → bm25 → complete
- **Graph**: retrieving → extracting → storing → relations → complete
- **Evaluation**: loading → evaluating → complete

---

## Запуск

```bash
# Development
uvicorn src.api.app:app --reload --port 8000

# Production
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --workers 4

# Docker
docker compose -f docker/docker-compose.yml up -d

# GPU Docker
docker compose -f docker/docker-compose.gpu.yml up -d

# MCP Server
python -m src.mcp_server.server
```

## Связанные скиллы

- `framework-config` — все .env переменные
- `framework-api` — все REST API endpoints
- `framework-troubleshooting` — ошибки и миграция

## Файлы
- App: `src/api/app.py`
- Routes: `src/api/routes/`
- Health: `src/api/routes/health.py`
- Rate limit: `src/api/middleware/rate_limit.py`
- Auth: `src/api/dependencies/auth.py`
- Docker: `docker/Dockerfile`, `docker/docker-compose.yml`
- MCP: `src/mcp_server/server.py`
- Workers: `src/workers/worker.py`, `src/workers/tasks/`
