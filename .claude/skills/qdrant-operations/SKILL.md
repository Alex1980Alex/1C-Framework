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

**Phase 8 production layout (после switchover 2026-04-30, см. roadmap §26-§28):**

7 коллекций на **Qwen3-Embedding-8B 4096d cosine**, single dense vector (no sparse), через TEI Docker:

| Коллекция | Points | Назначение |
|-----------|--------|------------|
| `bsl_code_v4_late` | 24 455 | **Production BSL retrieval** (Late Chunking pooling) |
| `bsl_code_v4` | 24 455 | Research baseline (std pooling) |
| `framework_code_v1` | 21 242 | Self-search фреймворка (см. §25) |
| `pdf_documents` | 830 | PDF RAG (Глава 5 1С Документация) |
| `wiki_pages_v1` | 3 073 | Wiki entities |
| `graph_embeddings` | 6 694 | KG entities |
| `learned_patterns` | 44 | Learning hooks |

**Не на Qwen3 (исключения):**
- `visual_grounding` (5 pts × 768d nomic) — defer (low ROI миграция)
- `skill_library`, `conversation_memory`, `experience_embeddings` (0 pts × 1024d) — Phase 9 candidate (memory hooks на Ollama nomic 768d, требуется alignment всей подсистемы)

**Dropped 2026-04-30** (§27 cleanup): `bsl_code_v3` (E5 1024d legacy), `experience_embeddings_e5_legacy`, `learned_patterns_e5_legacy`.

**Sparse BM25** в текущих 4096d-коллекциях НЕ используется (single-vector layout). Для hybrid retrieval нужен ручной BM25 SQLite (см. `cache/docs-mcp/hybrid_search.db` для FTS5 fallback).

**Payload (универсальный для re-embed через `scripts/reembed_collection.py`):** обязательно содержит `text` (default) или `content` (для legacy коллекций) — текст для эмбеддинга.

**Payload BSL** (`bsl_code_v4*`): `chunk_id`, `content`, `name`, `chunk_type`, `symbol_type`, `is_export`, `module_path`, `module_name`, `module_type`, `params`, `calls`, `signature`, `region`, `line_start`, `line_end`, `object_type`, `object_name`, `caller_count`

**Payload framework_code_v1**: `relative_path`, `content`, `language`, `chunk_type`, `symbol_name`, `line_start`, `line_end`, `mtime`, `sha1`

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
