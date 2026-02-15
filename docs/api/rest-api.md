# REST API Reference

Фреймворк предоставляет REST API через FastAPI с автоматической документацией (Swagger UI).

## Запуск

```bash
# Через CLI
pdf-framework server --host 0.0.0.0 --port 8000

# Или напрямую
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

После запуска:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Health (`/health`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Полная проверка здоровья с статусом компонентов |
| GET | `/health/ready` | Kubernetes readiness probe |
| GET | `/health/live` | Kubernetes liveness probe |

### GET /health

```json
{
  "status": "ok",
  "components": {
    "vector_store": {"status": "ok", "count": 1012},
    "graph_store": {"status": "ok", "nodes": 3166, "edges": 3528},
    "bm25_store": {"status": "ok", "count": 1012}
  }
}
```

### GET /health/ready

```json
{"status": "ready", "timestamp": "2026-02-12T10:00:00Z"}
```

### GET /health/live

```json
{"status": "alive", "timestamp": "2026-02-12T10:00:00Z"}
```

---

## Authentication (`/auth`)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/auth/token` | Создать JWT токен |
| POST | `/auth/validate` | Валидировать JWT токен |

### POST /auth/token

**Запрос:**
```json
{
  "api_key": "your-api-key",
  "tenant_id": "default",
  "role": "admin"
}
```

**Ответ:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "tenant_id": "default",
  "role": "admin",
  "expires_in_hours": 24
}
```

### POST /auth/validate

**Запрос:**
```json
{"token": "eyJhbGciOiJIUzI1NiIs..."}
```

**Ответ:**
```json
{
  "valid": true,
  "tenant_id": "default",
  "role": "admin",
  "issued_at": "2026-02-12T10:00:00Z",
  "expires_at": "2026-02-13T10:00:00Z"
}
```

---

## Documents (`/documents`)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/documents/upload` | Загрузить PDF файл |
| POST | `/documents/index` | Индексировать PDF |
| POST | `/documents/index/stream` | Индексация с потоковым прогрессом (NDJSON) |
| POST | `/documents/index/batch/stream` | Пакетная индексация нескольких PDF |
| POST | `/documents/index/delta` | Инкрементальная индексация |
| GET | `/documents/index/delta/stats` | Статистика дельта-индексации |
| POST | `/documents/index/delta/clear` | Очистить дельта-кеш |
| GET | `/documents/files` | Список PDF файлов на диске |
| GET | `/documents/registry` | Реестр документов с метаданными |
| PATCH | `/documents/{document_id}` | Обновить метаданные документа |
| GET | `/documents/` | Список индексированных документов |
| GET | `/documents/stats` | Статистика индекса |
| DELETE | `/documents/clear` | Очистить всё векторное хранилище |
| POST | `/documents/rebuild-sparse` | Перестроить sparse BM25 vectors в Qdrant |
| POST | `/documents/rebuild-bm25` | Перестроить FTS5 BM25 индекс |
| DELETE | `/documents/{document_id}` | Удалить документ и его чанки |

### POST /documents/index

**Запрос:**
```json
{"file_path": "D:/data/pdfs/document.pdf"}
```

**Ответ (200):**
```json
{
  "document_id": "a1b2c3d4e5f6g7h8",
  "chunks_stored": 1012,
  "embeddings_computed": 1012
}
```

**Ошибки:** `404` — файл не найден, `409` — индексация уже выполняется, `500` — ошибка обработки.

### POST /documents/index/stream

Потоковая индексация с прогрессом. Возвращает NDJSON (`application/x-ndjson`).

**Запрос:** аналогичен `/documents/index`

**Поток событий:**
```json
{"event": "start", "file_path": "document.pdf"}
{"event": "progress", "stage": "loading", "progress": 0.1}
{"event": "progress", "stage": "splitting", "progress": 0.3}
{"event": "progress", "stage": "embedding", "progress": 0.6, "batch": 2, "total_batches": 4}
{"event": "progress", "stage": "indexing", "progress": 0.9}
{"event": "complete", "document_id": "a1b2c3d4e5f6g7h8", "chunks_stored": 1012}
```

### POST /documents/index/batch/stream

Пакетная индексация нескольких PDF файлов.

**Запрос:**
```json
{
  "file_paths": ["doc1.pdf", "doc2.pdf"],
  "build_graph": true
}
```

### GET /documents/stats

```json
{
  "vector_store": {"document_count": 1012},
  "graph_store": {"node_count": 3166, "edge_count": 3528, "connected_components": 690}
}
```

### POST /documents/rebuild-bm25

Перестраивает FTS5 BM25 индекс из данных Qdrant.

```json
{
  "status": "rebuilt",
  "old_count": 950,
  "new_count": 1012,
  "elapsed_seconds": 2.3
}
```

---

## Search (`/search`)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/search/` | Поиск по документам |
| POST | `/search/ask` | Вопрос-ответ (RAG) |
| POST | `/search/analyze` | Аналитический RAG (Phase 33) |
| POST | `/search/research` | Deep research agent v2 (Phase 36) |
| POST | `/search/multi-agent` | Multi-agent оркестрация (Phase 39) |

### POST /search/

**Запрос:**
```json
{
  "query": "справочники в 1С",
  "strategy": "hybrid",
  "k": 10,
  "filter": {"language": "ru"},
  "rerank": true,
  "expand_query": false,
  "collection_id": null
}
```

| Поле | Тип | По умолчанию | Описание |
|------|-----|-------------|----------|
| `query` | string | (обязательно) | Поисковый запрос |
| `strategy` | string | `"hybrid"` | Стратегия: `vector`, `bm25`, `hybrid`, `mmr`, `two_stage`, `section`, `graph`, `graphrag_local`, `graphrag_global`, `lightrag` |
| `k` | int | `10` | Количество результатов |
| `filter` | dict | `null` | Фильтр по метаданным |
| `rerank` | bool | `true` | LLM реранкинг |
| `expand_query` | bool | `false` | Расширение запроса |
| `collection_id` | string | `null` | Поиск в рамках коллекции |

**Ответ:**
```json
{
  "query": "справочники в 1С",
  "results": [
    {
      "chunk": {
        "id": "chunk_abc123",
        "content": "5.8.Справочники...",
        "metadata": {
          "document_id": "a1b2c3d4",
          "page_number": 45,
          "section_title": "5.8.Справочники",
          "breadcrumb": "Глава 5 > 5.8.Справочники"
        }
      },
      "score": 0.892
    }
  ],
  "total_found": 10,
  "search_type": "hybrid",
  "elapsed_ms": 450.3
}
```

### POST /search/ask

**Запрос:**
```json
{
  "question": "Какие типы справочников описаны в документе?",
  "strategy": "hybrid",
  "k": 10,
  "stream": false
}
```

**Ответ:**
```json
{
  "answer": "В документе описаны следующие типы справочников...",
  "sources": ["document.pdf"],
  "search_type": "hybrid",
  "elapsed_ms": 2340.7
}
```

При `stream: true` — SSE (`text/event-stream`) с потоковой генерацией ответа.

### POST /search/analyze

Аналитический RAG — сравнение, структурированный вывод.

**Запрос:**
```json
{
  "question": "Сравни справочники и документы",
  "output_format": "comparison_table"
}
```

### POST /search/research

Deep research agent — планирование, сбор доказательств, синтез.

**Запрос:**
```json
{
  "question": "Как устроена система регистров в 1С?",
  "max_iterations": 5
}
```

### POST /search/multi-agent

Multi-agent — 4 агента с verify→rewrite loop.

**Запрос:**
```json
{
  "question": "Подробно объясни архитектуру справочников",
  "agents": ["retriever", "analyzer", "synthesizer", "verifier"]
}
```

---

## Chat (`/chat`)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/chat/message` | Отправить сообщение (с потоковой генерацией) |
| GET | `/chat/history/{thread_id}` | История разговора |
| DELETE | `/chat/history/{thread_id}` | Очистить историю |
| GET | `/chat/threads` | Список активных тредов |
| GET | `/chat/stats/{thread_id}` | Статистика треда |

### POST /chat/message

**Запрос:**
```json
{
  "message": "Расскажи про справочники",
  "thread_id": "thread_abc123",
  "stream": true
}
```

---

## Graph (`/graph`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/graph/stats` | Статистика графа знаний |
| GET | `/graph/entities` | Поиск/список сущностей |
| DELETE | `/graph/clear` | Очистить граф |
| POST | `/graph/build-communities` | Leiden community detection + LLM summaries |
| POST | `/graph/build-entity-embeddings` | Построить эмбеддинги сущностей (LightRAG) |
| GET | `/graph/entity-embeddings/stats` | Статистика эмбеддингов сущностей |
| GET | `/graph/neighbors/{entity_id}` | Соседние сущности |

### GET /graph/stats

```json
{
  "node_count": 3166,
  "edge_count": 3528,
  "connected_components": 690,
  "density": 0.0007
}
```

### GET /graph/entities

```
GET /graph/entities?name=справочник&entity_type=concept&limit=20
```

---

## Cache (`/cache`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/cache/stats` | Статистика всех кешей (embedding, LLM, document, semantic) |
| POST | `/cache/clear` | Очистить все кеши |

---

## Metrics (`/metrics`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/metrics` | Метрики системы (JSON) |
| GET | `/metrics/html` | Dashboard метрик (HTML) |
| POST | `/metrics/reset` | Сбросить счётчики |

---

## Feedback (`/feedback`)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/feedback/submit` | Отправить отзыв (Phase 22) |
| GET | `/feedback/stats` | Статистика отзывов |
| GET | `/feedback/examples/positive` | Позитивные примеры для few-shot |
| POST | `/feedback/tune` | Тюнинг весов стратегий по отзывам |
| POST | `/feedback/clear` | Очистить старые отзывы |

### POST /feedback/submit

```json
{
  "query": "справочники",
  "answer": "...",
  "rating": 5,
  "strategy": "hybrid",
  "comment": "Точный ответ"
}
```

---

## Table of Contents (`/toc`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/toc/{document_id}` | Дерево оглавления документа |
| GET | `/toc/{document_id}/section/{section_number}` | Детали раздела |
| POST | `/toc/{document_id}/generate-summaries` | Генерация LLM-саммари для разделов |

### GET /toc/{document_id}

```json
{
  "document_id": "a1b2c3d4",
  "total_chunks": 1012,
  "total_sections": 45,
  "summaries_available": 12,
  "tree": [
    {
      "section_number": "5.1",
      "title": "Общие сведения",
      "chunk_count": 15,
      "page_start": 1,
      "page_end": 8,
      "children": [...]
    }
  ]
}
```

---

## Collections (`/collections`)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/collections/` | Создать коллекцию |
| GET | `/collections/` | Список коллекций |
| GET | `/collections/{collection_id}` | Детали коллекции |
| PATCH | `/collections/{collection_id}` | Обновить метаданные |
| DELETE | `/collections/{collection_id}` | Удалить коллекцию |
| POST | `/collections/{collection_id}/documents` | Добавить документы |
| DELETE | `/collections/{collection_id}/documents/{document_id}` | Удалить документ из коллекции |
| GET | `/collections/{collection_id}/documents` | Список документов коллекции |

### POST /collections/

```json
{
  "name": "Глава 5",
  "description": "Документация по объектам конфигурации"
}
```

---

## OpenAI-Compatible API (`/v1`)

Совместимость с OpenAI SDK — можно использовать существующие клиенты.

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/v1/chat/completions` | Chat completions (RAG) |
| POST | `/v1/embeddings` | Создать эмбеддинги |
| GET | `/v1/models` | Список доступных моделей |

### POST /v1/chat/completions

```json
{
  "model": "pdf-rag",
  "messages": [{"role": "user", "content": "Что такое справочники?"}],
  "stream": false
}
```

---

## DSPy Optimization (`/optimization`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/optimization/stats` | Статистика оптимизации |
| POST | `/optimization/optimize` | Запуск MIPROv2 оптимизации |
| GET | `/optimization/dataset` | Просмотр evaluation dataset |
| POST | `/optimization/dataset/add` | Добавить Q&A пары |
| GET | `/optimization/last-result` | Результат последнего запуска |

---

## Enterprise Analytics (`/analytics`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/analytics/summary` | Сводка аналитики |
| GET | `/analytics/queries` | Статистика запросов |
| GET | `/analytics/queries/recent` | Последние запросы (limit 1-500) |
| GET | `/analytics/costs` | Стоимость по моделям |
| GET | `/analytics/audit` | Журнал аудита (limit 1-1000) |
| GET | `/analytics/audit/stats` | Статистика аудита |
| GET | `/analytics/audit/user/{user_id}` | Аудит по пользователю |

### GET /analytics/summary

```json
{
  "queries": {"total": 150, "avg_latency_ms": 450, "strategies": {"hybrid": 80, "bm25": 50}},
  "costs": {"total_usd": 12.50, "by_model": {"claude-sonnet-4-5": 10.0}},
  "audit": {"total_events": 500}
}
```

---

## CORS

```env
API__CORS_ORIGINS=["http://localhost:3000","https://myapp.com"]
```

По умолчанию разрешены все origin (`["*"]`).

## Аутентификация

JWT аутентификация через `/auth/token`. Роли: `viewer`, `editor`, `admin`.

Настройка:
```env
AUTH__ENABLED=true
AUTH__SECRET_KEY=your-secret-key
AUTH__API_KEYS=["key1","key2"]
```
