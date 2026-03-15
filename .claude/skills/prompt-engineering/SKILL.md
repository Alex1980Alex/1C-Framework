---
name: prompt-engineering
description: "Prompt Engineering (DSPy) — оптимизация промптов через DSPy модули. ИСПОЛЬЗУЙ когда оптимизируешь промпты (MIPROv2), настраиваешь A/B тестирование качества ответов, улучшаешь grading/rewriting/analysis. Триггеры: 'DSPy', 'оптимизация промптов', 'A/B testing', 'MIPROv2', 'метрики качества ответов', 'prompt optimization'. НЕ для RAG pipeline (→ search-pipeline-debug)."
---

# Prompt Engineering (DSPy)

## Когда использовать
- "DSPy", "оптимизация промптов", "A/B testing"
- "MIPROv2", "метрики качества ответов"
- Улучшение качества grading, rewriting, analysis

## DSPy Modules

| Модуль | Input → Output | Назначение |
|--------|---------------|-----------|
| `GraderModule` | question, document → relevance | Document relevance grading |
| `RewriterModule` | question, feedback → rewritten_query | Query improvement |
| `AnalyzerModule` | question, context → answer | Analytical answers |
| `PlannerModule` | question → plan_json | Analysis planning |
| `EvidenceModule` | question, aspects, chunks → evidence_json | Evidence extraction |
| `ComparatorModule` | entities, criteria, evidence → table_json | Comparison tables |

## Метрики (Weighted Composite)

| Метрика | Вес | Что измеряет |
|---------|-----|-------------|
| Completeness | 0.35 | Keyword overlap с ground truth |
| Accuracy | 0.30 | Jaccard similarity (words) |
| Table Presence | 0.15 | Markdown table detection (`\|...\|`) |
| Groundedness | 0.20 | Citation count ([1], [2]) |

## Workflow

```python
# 1. Загрузить dataset
optimizer = DSPyOptimizer(dataset_path="data/dspy_evaluation_dataset.json")
optimizer.load_dataset()

# 2. Добавить пары Q&A
optimizer.add_pair(EvaluationPair(question="...", answer="...", question_type="factual"))

# 3. Запустить оптимизацию (MIPROv2)
result = await optimizer.optimize(max_trials=50, module_names=["grader", "rewriter"])
# → OptimizationResult {metrics_before, metrics_after, improvement_pct}

# 4. Загрузить оптимизированный модуль
grader = optimizer.load_optimized_module("grader")
```

## API

| Endpoint | Метод | Назначение |
|----------|-------|-----------|
| `/optimization/stats` | GET | Статистика (enabled, dataset size, last result) |
| `/optimization/optimize` | POST | Запуск оптимизации (max_trials, modules) |
| `/optimization/dataset` | GET | Просмотр Q&A pairs |
| `/optimization/dataset/add` | POST | Добавить пары |
| `/optimization/last-result` | GET | Результат последнего запуска |

## Файлы
- Optimizer: `src/pdf_framework/optimization/dspy_optimizer.py`
- Modules: `src/pdf_framework/optimization/dspy_modules.py`
- Metrics: `src/pdf_framework/optimization/dspy_metrics.py`
- API: `src/api/routes/optimization.py`
- Data: `data/dspy_optimized/` (saved modules)
