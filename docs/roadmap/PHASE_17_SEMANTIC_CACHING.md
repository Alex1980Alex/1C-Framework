# Phase 17: Semantic Caching & Query Optimization

**Приоритет:** ВЫСОКИЙ | **Квартал:** Q1 2026 | **Версия:** v0.8.0
**Источники:** Verba, Pathway, Quivr
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Каждый запрос пересчитывает эмбеддинг (~2с для E5-large) и вызывает LLM.
Повторные и похожие запросы не кэшируются.

## Решение

Семантический кэш: если новый запрос >= 0.95 похож на кэшированный, возвращаем кэш.
Embedding LRU кэш + LLM response cache + invalidation при переиндексации.

## Реализовано

| Шаг | Задача | Детали |
|-----|--------|--------|
| 17.1 | **Embedding cache** | LRU кэш эмбеддингов запросов (TTL 1 час) |
| 17.2 | **Semantic cache** | Cosine similarity >= 0.95 -> возврат кэша |
| 17.3 | **Response cache** | LLM ответы с привязкой к query + strategy |
| 17.4 | **Cache invalidation** | Очистка при переиндексации документа |

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `src/pdf_framework/search/semantic_cache.py` | SemanticCache |
| `src/pdf_framework/embeddings/cache/` | Embedding cache layer |
| `src/api/routes/cache.py` | API для управления кэшем |

## Результаты

- Повторные запросы: с кэшем < 1с (vs 38с без кэша)
- Embedding cache: LRU с конфигурируемым TTL
- Semantic cache: cosine similarity threshold 0.95
- Cache invalidation при reindex через API
