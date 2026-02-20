# Evaluation & Benchmark

## Когда использовать
- "оценить качество поиска", "метрики", "regression test"
- "RAGAS", "benchmark", "precision", "recall", "NDCG"
- "feedback", "обратная связь", "self-learning"
- Сравнение стратегий, оптимизация параметров

---

## Для пользователя — оценка и feedback

### CLI

```bash
# Базовый benchmark
python -m src.cli.main eval --dataset "data/eval/benchmark.json"

# С выбором стратегии и evaluator
python -m src.cli.main eval --dataset "data/eval/benchmark.json" \
    --strategy hybrid --evaluator ragas

# AutoRAG — автоматический подбор параметров
python -m src.cli.main autorag --dataset "data/eval/benchmark.json" \
    --strategies vector,hybrid,bm25 --k-values 3,5,10
```

### Feedback Loop (Phase 22) — self-learning pipeline

5 компонентов замкнутого цикла обучения:

| Компонент | Класс | Назначение |
|-----------|-------|-----------|
| **Collector** | `FeedbackCollector` | SQLite хранение: query, answer, score, strategy, timestamp |
| **Store** | `FeedbackStore` | Async CRUD: `add()`, `get_positive()`, `get_negative()`, `get_stats()` |
| **Tuner** | `StrategyTuner` | Адаптация весов стратегий по фидбеку (learning_rate=0.1) |
| **Few-Shot** | `FewShotProvider` | Подбор похожих позитивных Q&A для промпта (threshold=0.7) |
| **Booster** | `ContentBooster` | Boost score популярных чанков (max_boost=1.3x) |

**Pipeline:**
```
User feedback → FeedbackCollector (SQLite)
  → StrategyTuner.tune_weights() → адаптация vector/hybrid/graphrag весов
  → FewShotProvider → few-shot примеры в промптах
  → ContentBooster → boost при поиске
```

```bash
# API
curl -X POST http://localhost:8000/feedback/submit \
    -d '{"query": "конфигуратор", "result_id": "chunk_123", "feedback": "positive", "score": 5}'

curl http://localhost:8000/feedback/stats

# CLI
python -m src.cli.main feedback stats
python -m src.cli.main feedback tune
```

Web UI: кнопки thumbs up/down в чате.

### Regression Gates (CI/CD)

Проверка перед деплоем: NDCG > 0.70

---

## Internals — метрики и реализация

## Метрики

| Метрика | Формула | Диапазон | Что измеряет |
|---------|---------|----------|-------------|
| Precision@k | hits / k | 0-1 | Доля релевантных в top-k |
| Recall@k | hits / total_relevant | 0-1 | Покрытие релевантных |
| MRR | 1 / rank(first_hit) | 0-1 | Позиция первого хита |
| NDCG@k | DCG / IDCG | 0-1 | Качество ранжирования |
| MAP | Σ(P@k) / total_relevant | 0-1 | Средняя точность |

## RAG Triad (LLM-based)

| Метрика | Вопрос | Входы |
|---------|--------|-------|
| Context Relevance | "Релевантен ли контекст запросу?" | query + chunks |
| Groundedness | "Ответ основан на контексте?" | answer + chunks |
| Answer Relevance | "Ответ отвечает на вопрос?" | query + answer |

## Python API

```python
dataset = EvalDataset.from_csv("eval_data.csv")
report = await runner.run(dataset, strategy="hybrid", k=5)
print(f"P@5={report.precision_at_5:.2%}, NDCG@10={report.ndcg_at_10:.2%}")
```

## RAGAS Integration

```python
adapter = RAGASAdapter()
results = await adapter.evaluate(ragas_dataset,
    metrics=["faithfulness", "answer_relevancy", "context_precision"])
```

## AutoRAG

```python
grid = ParameterGrid({'k': [5, 10], 'rerank': [True, False], 'vector_weight': [0.3, 0.5, 0.7]})
results = await optimizer.run(grid, metric="ndcg_at_10")
```

## Best Practices
1. Track P50/P95/P99 latency
2. Группировать запросы по типу
3. Regression gates: NDCG > 0.70 перед деплоем
4. Обновлять baseline после оптимизации

## Связанные скиллы

- `framework-cli` — CLI команды eval, autorag, feedback
- `framework-config` — .env параметры
- `framework-troubleshooting` — performance

## Файлы
- Runner: `src/pdf_framework/evaluation/runner.py`
- Metrics: `src/pdf_framework/evaluation/metrics.py`
- RAGAS: `src/pdf_framework/evaluation/ragas_adapter.py`
- RAG Triad: `src/pdf_framework/evaluation/rag_evaluator.py`
- AutoRAG: `src/pdf_framework/optimization/autorag.py`
- Feedback Collector: `src/pdf_framework/feedback/collector.py`
- Feedback Store: `src/pdf_framework/feedback/store.py`
- Strategy Tuner: `src/pdf_framework/feedback/tuner.py`
- Few-Shot Provider: `src/pdf_framework/feedback/few_shot.py`
- Score Booster: `src/pdf_framework/feedback/boost.py`
