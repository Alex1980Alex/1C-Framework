# Чеклист готовности: Фаза 60 — Code-Optimized Embeddings

**Приоритет:** HIGH | **Срок:** 2-3 дня | **Зависимости:** Фаза 58

## Предусловия
- [ ] Фаза 58 завершена: eval dataset доступен для сравнения
- [ ] Ollama установлена, модель `qwen3-embedding:4b-q4_K_M` доступна
- [ ] Текущий pipeline (nomic-embed-text 768d) стабилен для снятия baseline
- [ ] Qdrant поддерживает создание новой коллекции с 1024d

## Артефакты (файлы/код)
- [ ] `src/bsl/embeddings/qwen3_provider.py` — провайдер Qwen3 Embedding через Ollama API
- [ ] `scripts/migrate_bsl_embeddings.py` — скрипт миграции: перегенерация всех векторов
- [ ] `scripts/benchmark_bsl_embeddings.py` — сравнение nomic vs Qwen3 на eval dataset
- [ ] `reports/phase60_benchmark.md` — отчёт с таблицей метрик
- [ ] Конфигурация `.env`: `BSL_EMBEDDING_MODEL=qwen3-embedding:4b-q4_K_M`

## Метрики приёмки
- [ ] Recall@10 >= baseline nomic + 55%
- [ ] MRR не ниже nomic baseline
- [ ] Latency генерации эмбеддинга < 200ms (p95, CPU-only)
- [ ] Все модули из ground truth имеют эмбеддинги в новой коллекции

## Интеграционные проверки
- [ ] Новая Qdrant коллекция `bsl_code_v3` создана с размерностью 1024
- [ ] Поиск по BSL коду возвращает семантически релевантные сниппеты
- [ ] Hybrid search (FTS5 + Qdrant) работает с новыми эмбеддингами
- [ ] Fallback: при недоступности Ollama — понятная ошибка, не crash

## Блокеры для следующих фаз
- [ ] Без code-optimized эмбеддингов блокируется Фаза 63 (Contextual Search)
- [ ] Без миграции блокируется Фаза 65 (Hybrid Reranking)
- [ ] Смена размерности — breaking change, откат требует пересоздания индекса
