# Phase 16: BM25 Lexical Search + Hybrid Fusion

**Приоритет:** ВЫСОКИЙ | **Квартал:** Q1 2026 | **Версия:** v0.7.0
**Источники:** Kotaemon, Haystack, RAGFlow, Onyx
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Терминологические запросы ("модуль внешнего соединения") не находятся через vector search,
потому что эмбеддинги не могут точно матчить специфические термины 1С.

## Решение

BM25 полнотекстовый поиск через SQLite FTS5 + pymorphy3 lemmatization + RRF fusion.

## Реализовано

| Шаг | Задача | Детали |
|-----|--------|--------|
| 16.1 | **BM25 индекс** | SQLite FTS5, `data/bm25_index.db` |
| 16.2 | **BM25 Search Strategy** | `BM25SearchStrategy` в SearchManager |
| 16.3 | **Reciprocal Rank Fusion** | `score(d) = SUM 1/(k + rank_i(d))`, k=60 |
| 16.4 | **Hybrid обновлён** | `hybrid = RRF(vector, bm25, graph)` |
| 16.5 | **pymorphy3 lemmatization** | Русская морфология для BM25 (NDCG@10 = 52.16 по RusBEIR) |
| 16.6 | **Header propagation** | Заголовки разделов в метаданных чанков |

## Phase 16.2: Lemmatization + Header Propagation

- pymorphy3 для русской лемматизации (лучший подход по RusBEIR benchmark)
- `chunk_meta` таблица с `original_content` для восстановления текста
- Заголовки разделов (h1/h2/h3) пропагируются в дочерние чанки

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `src/pdf_framework/search/bm25_store.py` | BM25Store (FTS5 + pymorphy3) |
| `src/pdf_framework/search/strategies/bm25_search.py` | BM25SearchStrategy |
| `src/pdf_framework/search/strategies/hybrid_search.py` | HybridSearchStrategy (RRF) |
| `build_bm25_index.py` | Скрипт rebuild из Qdrant |

## Результаты

- 953 чанка в FTS5 индексе
- BM25 латентность: 5-14ms vs vector 415-475ms (50-60x быстрее)
- Русская морфология: "регистром" находит "регистр", "накопления" находит "накопление"
