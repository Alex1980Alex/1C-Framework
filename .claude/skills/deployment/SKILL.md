# Deployment

## Когда использовать
- "deploy", "docker", "production"
- "health check", "rate limiting", "CORS"
- Настройка окружения, мониторинг, Docker compose

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
- Key extraction: X-API-Key → `apikey:{key}`, X-Forwarded-For → `ip:{ip}`
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`

## API Routes (13 routers)

| Route | Назначение |
|-------|-----------|
| `/documents` | Upload, index (sync/stream/batch/delta), list, rebuild BM25 |
| `/search` | Vector/BM25/hybrid/section-first + reranking |
| `/search/ask` | RAG Q&A с streaming |
| `/chat` | WebSocket conversational RAG |
| `/graph` | Entity/relation queries, traversal |
| `/optimization` | DSPy stats, optimize, dataset |
| `/auth` | JWT tokens, RBAC |
| `/analytics` | Query/cost tracking, audit logs |

## Environment Variables

```env
ANTHROPIC_API_KEY=sk-...
VECTOR_STORE__PROVIDER=qdrant
VECTOR_STORE__QDRANT_URL=http://localhost:6333
EMBEDDING__MODEL=intfloat/multilingual-e5-large
AGENT__MODEL=claude-opus-4-6
AGENT__BASE_URL=                  # Z.AI proxy if needed
LOG_LEVEL=INFO
```

## Запуск

```bash
# Development
uvicorn src.api.app:app --reload --port 8000

# Production
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --workers 4

# Docker
docker compose -f docker/docker-compose.yml up -d

# MCP Server
python -m src.mcp_server.server
```

## Файлы
- App: `src/api/app.py`
- Routes: `src/api/routes/` (13 routers)
- Health: `src/api/routes/health.py`
- Rate limit: `src/api/middleware/rate_limit.py`
- DI: `src/api/dependencies/components.py`
- Docker: `docker/Dockerfile`, `docker/docker-compose.yml`
- MCP: `src/mcp_server/server.py` (12 tools)
