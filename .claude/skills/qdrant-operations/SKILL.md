---
name: qdrant-operations
description: "Qdrant Operations — управление коллекциями Qdrant, sparse vectors, snapshots. ИСПОЛЬЗУЙ когда создаёшь/настраиваешь коллекции Qdrant, мигрируешь с ChromaDB, настраиваешь named vectors (dense+bm25), делаешь snapshot/rebuild. Триггеры: 'qdrant', 'collection', 'sparse vectors', 'snapshot', 'named vectors', 'rebuild', 'миграция с ChromaDB', 'qdrant collection'. НЕ для embedding моделей (→ embedding-models)."
---

# Qdrant Operations

## Когда использовать
- "qdrant collection", "sparse vectors", "snapshot"
- "миграция", "rebuild", "named vectors"
- Настройка Qdrant, проблемы с хранилищем, переход с ChromaDB

## Архитектура коллекции

**Стандартный layout (PDF/wiki/skills, named vectors):**
- **dense**: cosine, 1024 dims (E5 multilingual)
- **bm25**: sparse vector с IDF modifier (Qdrant native tokenizer, russian)

Payload: `original_id`, `content`, `document_id`, `page_number`, `section`, `chunk_index`

**BSL Phase 8.12 layout (single dense vector, no sparse):**
- `bsl_code_v4` (4096d cosine, Qwen3 standard pooling) — primary BSL collection после Phase 8.12.3 baseline
- `bsl_code_v4_late` (4096d cosine, Qwen3 Late Chunking 8.12.9) — A/B arm для quality regression 8.12.8
- `bsl_code_v3` (1024d, E5 legacy) — старая E5 baseline, **drop в Phase 8.11.3**

Payload BSL: `chunk_id`, `content`, `name`, `chunk_type`, `symbol_type`, `is_export`, `module_path`, `module_name`, `module_type`, `params`, `calls`, `signature`, `region`, `line_start`, `line_end`, `object_type`, `object_name`, `caller_count`

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
| query_points error | Missing `using="dense"` | Добавить `using="dense"` при named vectors. Для BSL Phase 8.12 коллекций (single-vector) — `using` НЕ нужен |
| `client.search` AttributeError | qdrant-client ≥1.13 убрал `search()` | Использовать `client.query_points(query=vec, ...).points` |
| TEI 413 Payload Too Large | Сервер enforce `MAX_CLIENT_BATCH_SIZE` (default 32) | Слайсить буфер на стороне клиента (см. `Qwen3TEIEmbedder.client_batch_size` в `scripts/reindex_bsl_qwen3.py`) |
| Dimension mismatch | .env override E5 model | Проверить `EMBEDDING__MODEL` (1024d, не 384d) |

## Docker

```bash
docker run -p 6333:6333 -p 6334:6334 -v qdrant_data:/qdrant/storage qdrant/qdrant:v1.17.1
```

## Файлы
- Implementation: `src/pdf_framework/vector_store/providers/qdrant.py`
- Base: `src/pdf_framework/vector_store/base.py`
- Config: `src/pdf_framework/config/vector_store.py`
