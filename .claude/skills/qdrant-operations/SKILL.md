# Qdrant Operations

## Когда использовать
- "qdrant collection", "sparse vectors", "snapshot"
- "миграция", "rebuild", "named vectors"
- Настройка Qdrant, проблемы с хранилищем, переход с ChromaDB

## Архитектура коллекции

Named vectors:
- **dense**: cosine, 1024 dims (E5 multilingual)
- **bm25**: sparse vector с IDF modifier (Qdrant native tokenizer, russian)

Payload: `original_id`, `content`, `document_id`, `page_number`, `section`, `chunk_index`

## ID Conversion

Qdrant требует UUID или int:
```python
# _to_qdrant_id(): deterministic UUID5 from string
uuid5(namespace="a1b2c3d4-...", name=chunk_id) → UUID
# original_id сохраняется в payload для обратного маппинга
```

## Ключевые операции

```python
# Инициализация (создаёт коллекцию если нет)
await store.initialize()

# Dense поиск
results = await store.search(query_embedding, k=5)

# Hybrid RRF (dense + sparse)
results = await store.hybrid_search(query_embedding, query_text, k=5)
# Внутри: Prefetch(dense) + Prefetch(bm25) → FusionQuery(rrf)

# MMR (diversity)
results = await store.search_mmr(query_embedding, k=5, fetch_k=20)
# Важно: MMR с named vectors → r.vector["dense"]

# Rebuild sparse vectors
await store.rebuild_sparse_vectors()  # idempotent, scrolls all points

# Delete by source
await store.delete_by_filter({"source": "file.pdf"})
```

## Конфиг

```env
VECTOR_STORE__PROVIDER=qdrant
VECTOR_STORE__QDRANT_URL=http://localhost:6333
VECTOR_STORE__QDRANT_API_KEY=
VECTOR_STORE__DIMENSIONS=1024
VECTOR_STORE__DISTANCE_METRIC=cosine
VECTOR_STORE__QDRANT_BM25_ENABLED=true
VECTOR_STORE__QDRANT_BM25_LANGUAGE=russian
VECTOR_STORE__QDRANT_BM25_K=1.2
VECTOR_STORE__QDRANT_BM25_B=0.75
```

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| ID error (not UUID/int) | String ID не конвертирован | Использовать `_to_qdrant_id()` (UUID5) |
| MMR vector error | Named vectors: `r.vector` → dict | Использовать `r.vector["dense"]` |
| BM25 0 results | Sparse vectors не построены | `await store.rebuild_sparse_vectors()` |
| query_points error | Missing `using="dense"` | Добавить `using="dense"` при named vectors |
| Dimension mismatch | .env override E5 model | Проверить `EMBEDDING__MODEL` (1024d, не 384d) |

## Docker

```bash
docker run -p 6333:6333 -p 6334:6334 -v qdrant_data:/qdrant/storage qdrant/qdrant:v1.12.0
```

## Файлы
- Implementation: `src/pdf_framework/vector_store/providers/qdrant.py`
- Base: `src/pdf_framework/vector_store/base.py`
- Config: `src/pdf_framework/config/vector_store.py`
