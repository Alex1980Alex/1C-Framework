# Phase 23: Production Hardening

**Приоритет:** НИЗКИЙ | **Квартал:** Q3 2026 | **Версия:** v0.14.0
**Источники:** Onyx, R2R, PrivateGPT, Haystack
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Текущая система работает в development режиме. Для production-развёртывания критичны:

1. **Стабильность Vector Store** — ChromaDB с HNSW corruption при сбоях, нет horizontal scaling
2. **Нет rate limiting** — API может быть перегружен
3. **Нет OpenAI-compatible API** — нельзя использовать существующие клиенты
4. **Нет контейнеризации** — ручной деплой, зависимости от окружения
5. **Нет SSO/RBAC** — только API key, нет ролевой модели
6. **Нет health monitoring** — нет метрик производительности и алертов

## Текущее состояние

### Что уже есть
- **BaseVectorStore** (`src/pdf_framework/vector_store/base.py`): абстрактный интерфейс
- **ChromaVectorStore** (`src/pdf_framework/vector_store/providers/chroma.py`): единственный провайдер
- **Config** поддерживает `provider: Literal["chroma", "qdrant", "faiss"]` — но реализован только chroma
- **FastAPI app** (`src/api/app.py`): REST API без rate limiting
- **Auth** (`src/api/routes/auth.py`): базовая API key аутентификация
- **Multi-tenancy** (Phase 12): базовая изоляция данных
- **Observability** (Phase 11): `ObservabilityTracer` — но только logging, нет метрик

### Чего не хватает
- Qdrant / pgvector провайдеры
- Rate limiting и throttling
- OpenAI-compatible API endpoints
- Docker Compose для полного стека
- SSO (OAuth2/OIDC) и RBAC
- Prometheus metrics + Grafana dashboards
- Health checks и liveness probes
- Graceful shutdown и connection pooling

---

## Архитектура решения

```
Production Stack
  ├─ Vector Store Providers:
  │   ├─ ChromaDB (dev, small datasets)
  │   ├─ Qdrant (production, scalable)          ← NEW
  │   └─ PostgreSQL + pgvector (unified DB)     ← NEW
  │
  ├─ API Layer:
  │   ├─ FastAPI + Rate Limiting (slowapi)      ← NEW
  │   ├─ OpenAI-compatible /v1/chat/completions ← NEW
  │   ├─ Health checks (/health, /ready)        ← ENHANCE
  │   └─ Prometheus metrics (/metrics)          ← NEW
  │
  ├─ Auth & Security:
  │   ├─ OAuth2/OIDC (Keycloak, Azure AD)      ← NEW
  │   ├─ RBAC (admin, editor, viewer)           ← NEW
  │   └─ Audit logging                          ← NEW
  │
  └─ Infrastructure:
      ├─ Docker Compose (app + qdrant + redis)  ← NEW
      ├─ Graceful shutdown                      ← NEW
      └─ Connection pooling (SQLite WAL mode)   ← NEW
```

---

## Пошаговый план

### 23.1. Qdrant Vector Store Provider

**Новый файл:** `src/pdf_framework/vector_store/providers/qdrant.py`

```python
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
)

class QdrantVectorStore(BaseVectorStore):
    """Qdrant-backed vector store for production use.

    Advantages over ChromaDB:
    - No HNSW corruption on crashes
    - Horizontal scaling (sharding, replication)
    - Built-in filtering (no separate metadata store)
    - REST + gRPC API
    - Cloud hosting available
    """

    def __init__(self, settings: VectorStoreSettings):
        self._settings = settings
        self._client: AsyncQdrantClient | None = None

    async def initialize(self) -> None:
        """Connect to Qdrant and create collection if needed.

        Connection options:
        - Local: qdrant_url = "localhost:6333"
        - Cloud: qdrant_url = "https://xxx.qdrant.io"
        - In-memory: qdrant_url = ":memory:" (for testing)
        """
        self._client = AsyncQdrantClient(
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key or None,
        )

        collections = await self._client.get_collections()
        exists = any(c.name == self._settings.collection_name
                    for c in collections.collections)

        if not exists:
            await self._client.create_collection(
                collection_name=self._settings.collection_name,
                vectors_config=VectorParams(
                    size=self._settings.dimensions or 1024,
                    distance=Distance.COSINE,
                ),
            )

    async def add_documents(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> list[str]:
        """Add documents with embeddings and metadata."""
        points = [
            PointStruct(
                id=chunk.id,
                vector=embedding,
                payload={
                    "content": chunk.content,
                    "document_id": chunk.document_id,
                    "page_number": chunk.page_number or 0,
                    "section": chunk.section,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        await self._client.upsert(
            collection_name=self._settings.collection_name,
            points=points,
        )
        return [p.id for p in points]

    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search with optional metadata filtering."""
        qdrant_filter = self._build_filter(filter) if filter else None

        results = await self._client.search(
            collection_name=self._settings.collection_name,
            query_vector=query_embedding,
            limit=k,
            query_filter=qdrant_filter,
        )
        return self._to_search_results(results)

    async def search_mmr(
        self,
        query_embedding: list[float],
        k: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """MMR search using Qdrant's built-in diversity."""
        # Fetch more candidates, then apply MMR locally
        candidates = await self.search(query_embedding, k=fetch_k, filter=filter)
        # Reuse ChromaVectorStore._mmr_selection logic
        ...

    async def delete(self, ids: list[str]) -> None:
        """Delete documents by IDs."""
        await self._client.delete(
            collection_name=self._settings.collection_name,
            points_selector=ids,
        )

    async def count(self) -> int:
        info = await self._client.get_collection(self._settings.collection_name)
        return info.points_count

    async def clear(self) -> None:
        await self._client.delete_collection(self._settings.collection_name)
        await self.initialize()

    def _build_filter(self, filter_dict: dict) -> Filter:
        """Convert dict filter to Qdrant Filter."""
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filter_dict.items()
        ]
        return Filter(must=conditions)
```

### 23.2. PostgreSQL + pgvector Provider

**Новый файл:** `src/pdf_framework/vector_store/providers/pgvector.py`

```python
import asyncpg
from pgvector.asyncpg import register_vector

class PgVectorStore(BaseVectorStore):
    """PostgreSQL + pgvector for unified database approach.

    Advantages:
    - Vector + metadata + BM25 в одной СУБД
    - ACID transactions
    - Proven reliability
    - Full SQL capabilities for complex filters
    """

    def __init__(self, settings: VectorStoreSettings):
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Create connection pool and tables.

        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            document_id TEXT NOT NULL,
            page_number INTEGER,
            section TEXT DEFAULT '',
            chunk_index INTEGER DEFAULT 0,
            metadata JSONB DEFAULT '{}',
            embedding vector(1024),
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX idx_chunks_embedding ON document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);

        CREATE INDEX idx_chunks_document ON document_chunks(document_id);
        CREATE INDEX idx_chunks_metadata ON document_chunks USING gin(metadata);
        """
        self._pool = await asyncpg.create_pool(
            dsn=self._settings.pg_dsn,
            min_size=2,
            max_size=10,
        )
        await register_vector(self._pool)
        await self._create_tables()

    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Cosine similarity search with optional JSONB filter."""
        query = """
            SELECT id, content, document_id, page_number, section,
                   chunk_index, metadata,
                   1 - (embedding <=> $1::vector) AS score
            FROM document_chunks
            WHERE 1=1
        """
        params = [query_embedding]

        if filter:
            for i, (key, value) in enumerate(filter.items(), start=2):
                query += f" AND metadata->>'{key}' = ${i}"
                params.append(str(value))

        query += " ORDER BY embedding <=> $1::vector LIMIT $" + str(len(params) + 1)
        params.append(k)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return self._rows_to_results(rows)
```

### 23.3. Rate Limiting

**Модификация:** `src/api/app.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ...

# Per-endpoint limits
@router.post("/search/")
@limiter.limit("30/minute")
async def search_documents(request: Request, ...):
    ...

@router.post("/search/ask")
@limiter.limit("10/minute")
async def ask_question(request: Request, ...):
    ...

@router.post("/index/")
@limiter.limit("5/minute")
async def index_document(request: Request, ...):
    ...
```

**Настройки:**

```python
class RateLimitSettings(BaseSettings):
    enabled: bool = True
    default_limit: str = "60/minute"
    search_limit: str = "30/minute"
    ask_limit: str = "10/minute"
    index_limit: str = "5/minute"
    storage_backend: str = "memory"      # "memory" or "redis"
    redis_url: str = "redis://localhost:6379"
```

### 23.4. OpenAI-Compatible API

**Новый файл:** `src/api/routes/openai_compat.py`

```python
router = APIRouter(prefix="/v1", tags=["openai-compatible"])

class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    model: str = "pdf-rag"
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False

class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict]
    usage: dict

@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    components: Components = Depends(get_components),
):
    """OpenAI-compatible chat completions with RAG.

    Compatible with:
    - OpenAI Python SDK
    - LangChain ChatOpenAI
    - Any OpenAI-compatible client

    Usage:
      from openai import OpenAI
      client = OpenAI(base_url="http://localhost:8000/v1", api_key="your-key")
      response = client.chat.completions.create(
          model="pdf-rag",
          messages=[{"role": "user", "content": "Что такое регистр накопления?"}],
      )
    """
    # Extract last user message as question
    question = next(
        (m["content"] for m in reversed(request.messages) if m["role"] == "user"),
        "",
    )

    # Use RAG agent for answer
    # ... search + generate ...

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid4().hex[:12]}",
        created=int(time.time()),
        model=request.model,
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": answer},
            "finish_reason": "stop",
        }],
        usage={
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    )

@router.post("/chat/completions")  # stream=True
async def chat_completions_stream(...):
    """SSE streaming for OpenAI-compatible clients."""
    async def event_generator():
        # ... stream chunks via SSE ...
        yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    return {
        "object": "list",
        "data": [
            {"id": "pdf-rag", "object": "model", "owned_by": "pdf-framework"},
            {"id": "pdf-search", "object": "model", "owned_by": "pdf-framework"},
        ],
    }
```

### 23.5. Docker Compose

**Новый файл:** `docker-compose.yml`

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - VECTOR_STORE__PROVIDER=qdrant
      - VECTOR_STORE__QDRANT_URL=http://qdrant:6333
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./data:/app/data
    depends_on:
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    ports:
      - "7860:7860"
    environment:
      - API_URL=http://app:8000
    depends_on:
      - app

volumes:
  qdrant_data:
  redis_data:
```

**Новый файл:** `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[production]"

COPY src/ src/
COPY data/cache/ data/cache/

EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 23.6. SSO/RBAC (OAuth2 + Roles)

**Новый файл:** `src/api/middleware/auth.py`

```python
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"       # Full access: index, search, config, eval
    EDITOR = "editor"     # Index + search + feedback
    VIEWER = "viewer"     # Search + chat only

class User(BaseModel):
    user_id: str
    email: str
    roles: list[Role]
    tenant_id: str = "default"

class AuthMiddleware:
    """OAuth2/OIDC authentication middleware.

    Supports:
    - API Key (existing, for backward compatibility)
    - OAuth2 Bearer token (Keycloak, Azure AD, Auth0)
    - Session cookie (for UI)
    """

    def __init__(self, settings: AuthSettings):
        ...

    async def authenticate(self, request: Request) -> User:
        """Extract and validate credentials."""

    def require_role(self, role: Role):
        """Dependency injection for role-based access control.

        Usage:
            @router.post("/index")
            async def index(user: User = Depends(auth.require_role(Role.EDITOR))):
                ...
        """
```

### 23.7. Prometheus Metrics

**Новый файл:** `src/api/middleware/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Request metrics
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["endpoint"])

# Search metrics
SEARCH_COUNT = Counter("search_total", "Total searches", ["strategy"])
SEARCH_LATENCY = Histogram("search_duration_seconds", "Search latency", ["strategy"])
CACHE_HIT_COUNT = Counter("cache_hits_total", "Cache hits", ["cache_type"])

# Index metrics
INDEX_COUNT = Counter("index_total", "Documents indexed")
CHUNKS_STORED = Gauge("chunks_stored_total", "Total chunks in vector store")

# LLM metrics
LLM_CALLS = Counter("llm_calls_total", "LLM API calls", ["model", "purpose"])
LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens used", ["model", "type"])

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")
```

### 23.8. Health Checks & Graceful Shutdown

**Модификация:** `src/api/app.py`

```python
@app.get("/health")
async def health():
    """Basic liveness probe."""
    return {"status": "ok"}

@app.get("/ready")
async def readiness():
    """Readiness probe — checks all dependencies.

    Returns 503 if:
    - Vector store unreachable
    - Embedding model not loaded
    - LLM API unreachable
    """
    checks = {}
    try:
        count = await components.vector_store.count()
        checks["vector_store"] = {"status": "ok", "documents": count}
    except Exception as e:
        checks["vector_store"] = {"status": "error", "error": str(e)}

    # ... check embedding engine, LLM, etc. ...

    all_ok = all(c["status"] == "ok" for c in checks.values())
    status_code = 200 if all_ok else 503
    return JSONResponse(content={"status": "ready" if all_ok else "not_ready", "checks": checks}, status_code=status_code)

@app.on_event("shutdown")
async def shutdown():
    """Graceful shutdown — close connections."""
    if components.vector_store:
        # Close vector store connection
        ...
    if components.bm25_store:
        await components.bm25_store.close()
    if components.semantic_cache:
        await components.semantic_cache.close()
```

---

## Модифицируемые файлы

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/vector_store/providers/qdrant.py` | **NEW**: Qdrant provider |
| `src/pdf_framework/vector_store/providers/pgvector.py` | **NEW**: pgvector provider |
| `src/api/routes/openai_compat.py` | **NEW**: OpenAI-compatible API |
| `src/api/middleware/auth.py` | **NEW**: OAuth2/RBAC middleware |
| `src/api/middleware/metrics.py` | **NEW**: Prometheus metrics |
| `docker-compose.yml` | **NEW**: Full stack Docker Compose |
| `Dockerfile` | **NEW**: Application Dockerfile |
| `Dockerfile.ui` | **NEW**: UI Dockerfile |
| `src/api/app.py` | **MODIFY**: +rate limiting, +health/ready, +graceful shutdown |
| `src/pdf_framework/vector_store/__init__.py` | **MODIFY**: +qdrant, +pgvector in factory |
| `src/pdf_framework/config.py` | **MODIFY**: +RateLimitSettings, +AuthSettings, +qdrant/pg settings |
| `pyproject.toml` | **MODIFY**: +`qdrant-client`, +`asyncpg`, +`pgvector`, +`slowapi`, +`prometheus-client` |

## Настройки

```python
class VectorStoreSettings(BaseSettings):
    # Existing
    provider: Literal["chroma", "qdrant", "faiss", "pgvector"] = "chroma"
    persist_dir: Path = PROJECT_ROOT / "data" / "vector_db"
    collection_name: str = "pdf_documents"
    distance_metric: Literal["cosine", "euclidean", "dot"] = "cosine"
    dimensions: int = 1024

    # Qdrant
    qdrant_url: str = "localhost:6333"
    qdrant_api_key: str = ""

    # pgvector
    pg_dsn: str = "postgresql://user:pass@localhost:5432/pdfrag"

class AuthSettings(BaseSettings):
    provider: Literal["api_key", "oauth2"] = "api_key"
    oauth2_issuer: str = ""
    oauth2_audience: str = ""
    oauth2_jwks_uri: str = ""
    admin_api_keys: list[str] = []

class RateLimitSettings(BaseSettings):
    enabled: bool = True
    default_limit: str = "60/minute"
    search_limit: str = "30/minute"
    ask_limit: str = "10/minute"
    index_limit: str = "5/minute"
```

## Порядок реализации

1. Qdrant provider (наибольшая отдача — стабильность)
2. Rate limiting (быстрая реализация, важно для production)
3. Health checks + graceful shutdown
4. Prometheus metrics
5. OpenAI-compatible API
6. Docker Compose
7. pgvector (опционально, если нужен PostgreSQL)
8. SSO/RBAC (последний — самый сложный)

## Верификация

1. Qdrant: индексация 54 PDF → поиск → результаты идентичны ChromaDB
2. Rate limiting: >30 req/min → 429 Too Many Requests
3. OpenAI API: `openai.ChatCompletion.create()` работает с нашим сервером
4. Docker Compose: `docker compose up` → все сервисы healthy
5. Health/ready: при недоступности Qdrant → `/ready` = 503
6. Metrics: Prometheus scraping → Grafana dashboard
7. RBAC: viewer не может индексировать, admin может всё
