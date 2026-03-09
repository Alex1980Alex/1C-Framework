# Чеклист готовности: Фаза 65 — Hybrid Reranking BSL

**Приоритет:** MEDIUM | **Срок:** 2-3 дня | **Зависимости:** Фаза 60

## Предусловия
- [ ] Фаза 60 завершена: BM25 и Vector Search стабильно возвращают top-50
- [ ] AST парсер доступен для AST-aware reranker (из Фазы 59)
- [ ] LLM доступен через Z.AI (GLM-5) для LLM reranker stage
- [ ] Eval dataset (Фаза 58) готов для замера Precision
- [ ] Утверждён SLA: < 500ms на весь pipeline

## Артефакты (файлы/код)
- [ ] `src/bsl/search/hybrid_pipeline.py` — 5-stage pipeline с параллельным BM25 + Vector
- [ ] `src/bsl/search/rrf_fusion.py` — Reciprocal Rank Fusion: top-50 + top-50 → top-20
- [ ] `src/bsl/search/ast_reranker.py` — ранжирование по структурному совпадению (AST)
- [ ] `src/bsl/search/llm_reranker.py` — LLM финальное ранжирование → top-5
- [ ] Конфигурация: веса RRF `k`, таймауты LLM, размеры top-N

## Метрики приёмки
- [ ] Precision@5 >= baseline + 10-15%
- [ ] Latency p95 < 500ms (BM25 5ms + Vector 50ms параллельно + reranking)
- [ ] Recall@20 не ниже чистого Vector search (RRF не отсекает релевантное)
- [ ] LLM cost: токены в пределах бюджета (только top-20 контекст)

## Интеграционные проверки
- [ ] Параллельность: BM25 и Vector запускаются одновременно (проверка логов)
- [ ] Circuit Breaker: LLM таймаут → fallback на AST-reranker top-5
- [ ] AST-reranker: корректная обработка кода с синтаксическими ошибками
- [ ] Формат ответа: JSON с `score`, `source_type`, `rerank_stage`

## Блокеры для следующих фаз
- [ ] Без reranking pipeline блокируется качество Фазы 66 (Coding Assistant: точность контекста)
- [ ] Без логирования промежуточных скорингов невозможна оптимизация весов
