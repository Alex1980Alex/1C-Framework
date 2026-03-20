# Phase 7: Eval & Benchmark

**Priority:** LOW | **Effort:** 1-2 days | **Depends on:** Phase 1 | **Effect:** Quality validation

**Goal:** Датасет из 20+ реальных задач 1С с human-scored ground truth для валидации scorer и калибровки весов метрики.

---

## Problem Statement

Scorer (Phase 1) вычисляет quality score на основе маркеров. Но:
1. **Веса компонентов** (30/25/20/15/10) — экспертная оценка, не проверенная
2. **Корреляция с реальным качеством** — неизвестна
3. **Регрессии** — при изменении scorer нужно проверить на baseline

---

## Tasks

### 7.1 Eval Dataset

Файл: `data/eval/1c-analysis/eval_dataset.json`

Структура:

```json
[
  {
    "id": "GKSTCPLK-1234",
    "task_description": "Добавить расчёт суммы НДС по маршрутным листам",
    "analysis_report_path": "data/eval/1c-analysis/reports/GKSTCPLK-1234.md",
    "human_scores": {
      "requirements_coverage": 0.9,
      "fields_verified": 0.8,
      "patterns_found": 0.7,
      "sql_validated": 1.0,
      "open_questions_resolved": 0.6,
      "overall": 82
    },
    "expected_gaps": [
      {"type": "field_unverified", "detail": "РегистрСведений.СтатусыМЛ.Статус"},
      {"type": "pattern_missing", "detail": "Точка 3: нет образца"}
    ],
    "difficulty": "medium",
    "objects_count": 5,
    "modification_points": 4
  }
]
```

### 7.2 Sources for Eval Tasks

| Source | Count | Description |
|--------|-------|-------------|
| Real GKSTCPLK tasks (completed) | 5-8 | Реальные задачи с готовыми отчётами |
| Synthetic (generated) | 10-12 | Сгенерированные по паттернам конфигурации |
| Edge cases | 3-5 | Пустой отчёт, идеальный, только SQL, без SQL |

**Total: 20-25 tasks**

### 7.3 Eval Script

Файл: `scripts/eval-analysis-scorer.py`

```python
"""Evaluate analysis scorer against human-scored ground truth."""

def evaluate():
    dataset = load_dataset("data/eval/1c-analysis/eval_dataset.json")

    results = []
    for task in dataset:
        # Run scorer on report
        auto_score = run_scorer(task["analysis_report_path"])

        # Compare with human scores
        human_score = task["human_scores"]["overall"]
        delta = abs(auto_score - human_score)

        # Check gap detection
        auto_gaps = get_gaps(task["analysis_report_path"])
        expected_gaps = task["expected_gaps"]
        gap_precision, gap_recall = compute_gap_metrics(auto_gaps, expected_gaps)

        results.append({
            "id": task["id"],
            "auto_score": auto_score,
            "human_score": human_score,
            "delta": delta,
            "gap_precision": gap_precision,
            "gap_recall": gap_recall,
        })

    # Aggregate
    mae = mean([r["delta"] for r in results])
    correlation = pearsonr([r["auto_score"] for r in results],
                           [r["human_score"] for r in results])
    avg_gap_f1 = mean([2*r["gap_precision"]*r["gap_recall"] /
                       (r["gap_precision"]+r["gap_recall"]+1e-9)
                       for r in results])

    print(f"MAE: {mae:.1f}")
    print(f"Correlation: {correlation:.3f}")
    print(f"Gap F1: {avg_gap_f1:.3f}")
```

### 7.4 Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| MAE (Mean Absolute Error) | < 10 | Разница auto vs human score |
| Pearson correlation | > 0.8 | Корреляция auto vs human score |
| Gap detection F1 | > 0.7 | Точность обнаружения пробелов |

### 7.5 Weight Calibration

Если корреляция < 0.8, калибровать веса компонентов:

```python
from scipy.optimize import minimize

def calibrate_weights(dataset):
    """Find optimal weights that maximize correlation with human scores."""
    def objective(weights):
        auto_scores = [compute_score(task, weights) for task in dataset]
        human_scores = [task["human_scores"]["overall"] for task in dataset]
        return -pearsonr(auto_scores, human_scores)[0]

    result = minimize(objective, x0=[30, 25, 20, 15, 10],
                     bounds=[(0,50)]*5,
                     constraints={"type": "eq", "fun": lambda w: sum(w) - 100})
    return result.x
```

---

## Deliverables

- [ ] `data/eval/1c-analysis/eval_dataset.json` — 20+ задач
- [ ] `data/eval/1c-analysis/reports/` — ANALYSIS-REPORT.md для каждой задачи
- [ ] `scripts/eval-analysis-scorer.py` — eval скрипт
- [ ] Calibrated weights (если нужно)

## Acceptance Criteria

1. Dataset содержит >= 20 задач с human scores
2. MAE < 10 points (auto scorer close to human judgement)
3. Pearson correlation > 0.8
4. Gap detection F1 > 0.7
5. Eval script интегрируется в CI (optional)
