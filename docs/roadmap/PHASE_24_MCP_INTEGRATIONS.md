# Phase 24: Qdrant Native BM25 + FTS5 Fallback

**Приоритет:** ВЫСОКИЙ | **Квартал:** Q1 2026 | **Версия:** v0.15.0
**Статус: РЕАЛИЗОВАНО**

> Оригинальная Phase 24 (MCP Native & Tool Integration) перенумерована в Phase 25.
> Подробности: [PHASE_25_MCP_INTEGRATIONS.md](PHASE_25_MCP_INTEGRATIONS.md)

---

## Проблема

BM25 индекс (FTS5 SQLite) содержал 8414 чанков с ID из эпохи ChromaDB, которых нет в Qdrant (439 чанков). Поиск BM25 находил совпадения, но не мог получить контент из vector store, возвращая 0 результатов.

## Решение

Qdrant 1.15.5 поддерживает нативный BM25 через sparse vectors + server-side inference. Миграция BM25 в Qdrant устраняет проблему синхронизации, FTS5 с pymorphy3 сохранён как fallback.

## Реализовано

| Шаг | Задача | Детали |
|-----|--------|--------|
| 24.1 | **Config** | `qdrant_bm25_enabled`, `qdrant_bm25_language`, `bm25_backend` в settings |
| 24.2 | **Qdrant sparse vectors** | `SparseVectorParams(modifier=Modifier.IDF)` в коллекции |
| 24.3 | **Dense + BM25 коллекция** | Named vectors: "dense" (1024d) + "bm25" (sparse) |
| 24.4 | **hybrid_search()** | Prefetch dense + BM25, `FusionQuery(Fusion.RRF)` server-side |
| 24.5 | **BaseVectorStore** | `hybrid_search()` + `supports_native_bm25()` интерфейс |
| 24.6 | **HybridSearchStrategy** | Использует native BM25 когда доступен |
| 24.7 | **FTS5 fallback** | `chunk_meta.original_content` для автономного BM25 |
| 24.8 | **Rebuild из Qdrant** | `build_bm25_index.py` читает из Qdrant, не ChromaDB |
| 24.9 | **UI + API** | Кнопка "Пересобрать BM25", `POST /documents/rebuild-bm25` |

## Ключевые файлы

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/config.py` | +BM25 backend settings |
| `src/pdf_framework/vector_store/providers/qdrant.py` | +sparse vectors, +hybrid_search() |
| `src/pdf_framework/vector_store/base.py` | +hybrid_search(), +supports_native_bm25() |
| `src/pdf_framework/search/strategies/hybrid_search.py` | +native BM25 routing |
| `src/pdf_framework/search/strategies/bm25_search.py` | +FTS5 fallback via chunk_meta |
| `src/pdf_framework/search/bm25_store.py` | +original_content в chunk_meta |
| `build_bm25_index.py` | Rebuild из Qdrant |
| `src/api/routes/documents.py` | +POST /documents/rebuild-bm25 |
| `src/ui/pages/documents.py` | +кнопка "Пересобрать BM25" |

## Результаты

- Qdrant collection: dense (1024d) + bm25 sparse vectors + IDF modifier
- BM25 FTS5 index: 953 чанков, pymorphy3 lemmatization
- BM25 латентность: 5-14ms vs vector 415-475ms (50-60x быстрее)
- Hybrid search: Qdrant native RRF (dense+BM25 prefetch) + graph merge
- Все 953 чанка синхронизированы между Qdrant и FTS5
