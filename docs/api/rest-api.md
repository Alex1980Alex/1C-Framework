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

## Health

### GET /health/

Базовая проверка здоровья.

**Ответ:**
```json
{"status": "ok"}
```

### GET /health/ready

Проверка готовности: доступность векторного и графового хранилищ.

**Ответ (готов):**
```json
{
  "status": "ready",
  "vector_store": {"count": 150},
  "graph_store": {"nodes": 42}
}
```

**Ответ (не готов):**
```json
{
  "status": "not_ready",
  "error": "Connection refused"
}
```

### GET /health/live

Проверка живости процесса.

**Ответ:**
```json
{"status": "alive"}
```

---

## Документы

### POST /documents/index

Индексировать PDF-документ: загрузить, разбить на чанки, вычислить эмбеддинги, сохранить.

**Запрос:**
```json
{
  "file_path": "C:/docs/report.pdf"
}
```

**Ответ (200):**
```json
{
  "document_id": "a1b2c3d4e5f6g7h8",
  "chunks_stored": 42,
  "embeddings_computed": 42
}
```

**Ошибки:**
- `404` — файл не найден
- `500` — ошибка обработки

### GET /documents/stats

Статистика индекса.

**Ответ:**
```json
{
  "vector_store": {
    "document_count": 150
  },
  "graph_store": {
    "node_count": 89,
    "edge_count": 134,
    "connected_components": 5,
    "density": 0.034
  }
}
```

### DELETE /documents/{document_id}

Удалить документ и все его чанки из векторного хранилища.

**Ответ (200):**
```json
{
  "deleted_chunks": 42,
  "document_id": "a1b2c3d4e5f6g7h8"
}
```

**Ошибки:**
- `404` — документ не найден
- `500` — ошибка удаления

---

## Поиск

### POST /search/

Поиск по индексированным документам.

**Запрос:**
```json
{
  "query": "машинное обучение",
  "strategy": "hybrid",
  "k": 5,
  "filter": {"language": "ru", "document_type": "documentation"},
  "rerank": true,
  "expand_query": false
}
```

Параметры:
| Поле | Тип | По умолчанию | Описание |
|------|-----|-------------|----------|
| `query` | string | (обязательно) | Поисковый запрос |
| `strategy` | string | `"vector"` | Стратегия: `vector`, `graph`, `hybrid`, `mmr`, `two_stage` |
| `k` | int | `5` | Количество результатов |
| `filter` | dict | `null` | Фильтр по метаданным, например `{"language": "ru", "document_type": "documentation"}` |
| `rerank` | bool | `true` | Включить переранжирование результатов через cross-encoder |
| `expand_query` | bool | `false` | Включить расширение запроса (генерация дополнительных формулировок) |

**Ответ:**
```json
{
  "query": "машинное обучение",
  "results": [
    {
      "chunk_id": "doc1_chunk_abc123",
      "content": "Методы машинного обучения включают...",
      "score": 0.892,
      "source": "vector",
      "metadata": {"language": "ru", "document_type": "documentation"}
    }
  ],
  "total_found": 5,
  "search_type": "hybrid",
  "elapsed_ms": 45.3
}
```

### POST /search/ask

Задать вопрос и получить LLM-ответ на основе найденных документов (RAG).

**Запрос:**
```json
{
  "question": "Какие методы машинного обучения описаны в документе?",
  "strategy": "hybrid",
  "k": 5,
  "filter": {"language": "ru", "document_type": "documentation"},
  "rerank": true,
  "expand_query": false
}
```

Параметры:
| Поле | Тип | По умолчанию | Описание |
|------|-----|-------------|----------|
| `question` | string | (обязательно) | Вопрос на естественном языке |
| `strategy` | string | `"hybrid"` | Стратегия: `vector`, `graph`, `hybrid`, `mmr`, `two_stage` |
| `k` | int | `5` | Количество результатов для контекста |
| `filter` | dict | `null` | Фильтр по метаданным, например `{"language": "ru", "document_type": "documentation"}` |
| `rerank` | bool | `true` | Включить переранжирование результатов через cross-encoder |
| `expand_query` | bool | `false` | Включить расширение запроса (генерация дополнительных формулировок) |

**Ответ:**
```json
{
  "answer": "В документе описаны следующие методы: ...",
  "sources": [
    "C:/docs/report.pdf",
    "C:/docs/paper.pdf"
  ],
  "search_type": "hybrid",
  "elapsed_ms": 2340.7
}
```

---

## CORS

По умолчанию разрешены все origin (`["*"]`). Настройте через переменную:

```
API__CORS_ORIGINS=["http://localhost:3000","https://myapp.com"]
```

## Аутентификация

В текущей версии аутентификация не реализована. API рассчитан на локальное использование. Для продакшена рекомендуется добавить middleware аутентификации или использовать reverse proxy (nginx, Traefik).
