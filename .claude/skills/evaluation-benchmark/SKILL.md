# Evaluation & Benchmark

## Когда использовать
- "оценить качество поиска", "метрики", "regression test"
- "RAGAS", "benchmark", "precision", "recall", "NDCG"
- Сравнение стратегий, оптимизация параметров

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

## Запуск

```python
# 1. Dataset (CSV: query, relevant_chunk_ids, category)
dataset = EvalDataset.from_csv("eval_data.csv")

# 2. Run benchmark
report = await runner.run(dataset, strategy="hybrid", k=5)

# 3. Analyze
print(f"P@5={report.precision_at_5:.2%}, R@5={report.recall_at_5:.2%}")
print(f"NDCG@10={report.ndcg_at_10:.2%}, MRR={report.mrr:.2%}")
```

## RAGAS Integration

```python
adapter = RAGASAdapter()
results = await adapter.evaluate(ragas_dataset,
    metrics=["faithfulness", "answer_relevancy", "context_precision"])
```

## AutoRAG Optimization (Phase 20)

```python
grid = ParameterGrid({'k': [5, 10], 'rerank': [True, False], 'vector_weight': [0.3, 0.5, 0.7]})
results = await optimizer.run(grid, metric="ndcg_at_10")
```

## Best Practices
1. Track P50/P95/P99 latency, не только avg
2. Группировать запросы по типу (simple/complex/thematic)
3. Regression gates: NDCG > 0.70 перед деплоем
4. Обновлять baseline после каждой оптимизации

## Файлы
- Runner: `src/pdf_framework/evaluation/runner.py`
- Metrics: `src/pdf_framework/evaluation/metrics.py`
- RAGAS: `src/pdf_framework/evaluation/ragas_adapter.py`
- RAG Triad: `src/pdf_framework/evaluation/rag_evaluator.py`
- Regression: `src/pdf_framework/evaluation/regression.py`
- AutoRAG: `src/pdf_framework/optimization/autorag.py`
