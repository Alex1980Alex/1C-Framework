# Migration Guide

## v0.5 → v0.15 (ChromaDB → Qdrant)

### Breaking Changes

1. **Vector Store**: ChromaDB заменён на Qdrant

```env
# Было
VECTOR_STORE__PROVIDER=chroma

# Стало
VECTOR_STORE__PROVIDER=qdrant
VECTOR_STORE__QDRANT_URL=http://localhost:6333
```

2. **Embedding Model**: all-MiniLM-L6-v2 (384d) → multilingual-e5-large (1024d)

```env
# Было
EMBEDDING__MODEL=all-MiniLM-L6-v2
EMBEDDING__DIMENSIONS=384

# Стало
EMBEDDING__MODEL=intfloat/multilingual-e5-large
EMBEDDING__DIMENSIONS=1024
```

3. **E5 Model Prefixes**: E5 модели требуют префиксы

- Поиск: `"query: "` + запрос
- Индексация: `"passage: "` + текст

Фреймворк добавляет их автоматически.

### Migration Steps

```bash
# 1. Установить Qdrant
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant

# 2. Обновить .env
VECTOR_STORE__PROVIDER=qdrant
EMBEDDING__MODEL=intfloat/multilingual-e5-large
EMBEDDING__DIMENSIONS=1024

# 3. Полная переиндексация (обязательно — размерности изменились)
pdf-framework index path/to/document.pdf
```

### Data Migration

Миграция данных из ChromaDB в Qdrant **не поддерживается** — требуется полная переиндексация. Это связано с:
- Изменение размерности эмбеддингов (384 → 1024)
- Новый формат ID (детерминированные SHA-256)
- Добавление sparse BM25 vectors

---

## v0.15 → v1.0 (Production Hardening)

### New Features

1. **BM25 Sparse Vectors** — встроены в Qdrant (Phase 24)
2. **LLM Reranker** — Claude Sonnet вместо CrossEncoder (Phase 25)
3. **Section-Aware Search** — FTS5 multi-column (Phase 27)
4. **Hybrid Loader** — PyMuPDF4LLM + Docling + Vision OCR (Phase 28)

### Configuration Changes

```env
# Реранкер (было cross-encoder, стало LLM)
AGENT__RERANKER_TYPE=llm          # llm | cross_encoder | colbert

# BM25 вес в hybrid search
SEARCH__BM25_WEIGHT=0.3

# Section-aware search
SEARCH__SECTION_AWARE_ENABLED=true
```

### Data Migration

```bash
# Перестроить BM25 индекс (Phase 24)
curl -X POST http://localhost:8000/documents/rebuild-bm25

# Перестроить sparse vectors (Phase 24)
curl -X POST http://localhost:8000/documents/rebuild-sparse
```

---

## v1.0 → v1.5 (Enterprise)

### New Features

- Multi-Document KB (collections, scoped search)
- DSPy Prompt Optimization
- ColBERT Late Interaction
- Research Agent v2
- LightRAG Mode
- Multi-Agent Orchestration
- Enterprise Analytics
- ONNX/OpenVINO embedding backends

### Configuration Changes

```env
# ONNX backend для эмбеддингов (7x CPU speedup)
EMBEDDING__BACKEND=onnx           # torch | onnx | openvino

# LangGraph checkpointing
AGENT__CHECKPOINTER=sqlite        # sqlite | memory

# LightRAG auto-selection
SEARCH__LIGHTRAG_ENABLED=true
```

Переиндексация **не требуется** для обновления v1.0 → v1.5.

---

## v1.5 → v2.0 (Phase 47-50: Search Quality)

### Jina Embeddings v3 (Phase 47)

Переход с локальной E5 модели на Jina v3 API:

| | E5 (local) | Jina v3 (API) |
|---|---|---|
| Качество MTEB | ~63% | 68.5% |
| Task prompting | ручные префиксы | нативный API |
| Matryoshka | нет | 1024→512→256 |
| GPU нужен | да | нет |
| Стоимость | $0 | ~$0.02/1M tokens (10M free) |

### Шаги миграции

1. **Получить API ключ** на [jina.ai/embeddings](https://jina.ai/embeddings/)

2. **Обновить `.env`:**
```env
EMBEDDING__PROVIDER=jina
EMBEDDING__MODEL=jina-embeddings-v3
EMBEDDING__JINA_API_KEY=jina_xxxxx
```

3. **Dry run** (показать план без выполнения):
```bash
python scripts/migrate_embeddings.py --provider jina --jina-key jina_xxxxx --dry-run
```

4. **Выполнить миграцию:**
```bash
python scripts/migrate_embeddings.py --provider jina --jina-key jina_xxxxx
```

Скрипт автоматически:
- Переэмбеддит все чанки через Jina API
- Пересоздаст Qdrant коллекцию (если dimensions изменились)
- Перестроит BM25 sparse vectors
- Перестроит graph entity embeddings

5. **Опционально: уменьшить размерность** (Matryoshka truncation):
```bash
python scripts/migrate_embeddings.py --provider jina --jina-key jina_xxxxx --jina-truncate-dim 512
```

### Contextual Retrieval (Phase 50)

Включить обогащение чанков контекстом (Anthropic pattern, +5-10% recall):

```env
CONTEXTUAL_RETRIEVAL__ENABLED=true
CONTEXTUAL_RETRIEVAL__MODEL=claude-haiku-4-5-20251001
```

Требует переиндексации: `POST /documents/index` с `contextual=true`.

### Откат

Переключение обратно на E5:
```env
EMBEDDING__PROVIDER=local
EMBEDDING__MODEL=intfloat/multilingual-e5-large
```

Для полной консистентности запустить обратную миграцию:
```bash
python scripts/migrate_embeddings.py --provider local
```
