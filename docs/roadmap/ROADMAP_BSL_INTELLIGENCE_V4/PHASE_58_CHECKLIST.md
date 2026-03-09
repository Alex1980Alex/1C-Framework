# Чеклист готовности: Фаза 58 — Eval Dataset & Baseline

**Приоритет:** CRITICAL | **Срок:** 1-2 дня | **Зависимости:** нет

## Предусловия
- [ ] Qdrant запущен (Docker, localhost:6333), коллекция `bsl_code_v2` содержит данные
- [ ] SQLite FTS5 индекс (`data/bsl_fts5.db`) актуален
- [ ] Утверждён список 4 категорий запросов: Functionality, API, Business Logic, Cross-module
- [ ] Определены критерии ground truth (какие модули считаются релевантными)
- [ ] Python 3.11+, зависимости установлены (`qdrant-client`, `numpy`)

## Артефакты (файлы/код)
- [ ] `data/eval/bsl_ground_truth_100.json` — 100 пар (query, expected_modules), по ~25 на категорию
- [ ] `scripts/generate_bsl_eval_dataset.py` — скрипт создания/пополнения датасета
- [ ] `src/bsl/evaluation/metrics.py` — Recall@k, MRR, Precision@k
- [ ] `scripts/run_bsl_baseline.py` — запуск baseline и логирование результатов
- [ ] `reports/phase58_baseline.md` — отчёт с таблицами метрик по категориям

## Метрики приёмки
- [ ] Датасет >= 100 пар (по ~25 на категорию)
- [ ] Recall@10 измерен и зафиксирован (baseline)
- [ ] Recall@5 измерен и зафиксирован
- [ ] MRR измерен и зафиксирован
- [ ] P@5 измерен и зафиксирован
- [ ] Метрики рассчитаны для всех 4 категорий (нет NaN)

## Интеграционные проверки
- [ ] FTS5: ключевые слова из датасета находятся через SQLite
- [ ] Qdrant: эмбеддинги существуют для всех модулей из ground truth
- [ ] Hybrid: RRF fusion FTS5 + Qdrant возвращает результаты
- [ ] `run_bsl_baseline.py` отрабатывает без ошибок
- [ ] Баланс категорий: Cross-module запросы действительно кросс-модульные

## Блокеры для следующих фаз
- [ ] Без ground truth невозможно измерить улучшения в Фазах 59-67
- [ ] Без `metrics.py` невозможна автоматизация бенчмарков
- [ ] Несоответствие ID в ground truth и в Qdrant/FTS5 → ложные результаты
