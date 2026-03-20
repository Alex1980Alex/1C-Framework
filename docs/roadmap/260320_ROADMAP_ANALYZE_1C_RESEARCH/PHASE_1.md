# Phase 1: Analysis Quality Scorer

**Priority:** CRITICAL | **Effort:** 1 day | **Depends on:** -- | **Effect:** Measurable quality

**Goal:** Скрипт, который парсит ANALYSIS-REPORT.md и вычисляет structured quality score (0-100).

---

## Problem Statement

Без числовой метрики невозможно:
- Определить, улучшился ли анализ после итерации
- Автоматически решить KEEP/REVERT
- Сравнить качество двух версий отчёта
- Определить moment of convergence (когда остановиться)

---

## Algorithm

```
1. PARSE — извлечь структуру из ANALYSIS-REPORT.md:
   - requirements[]     из секции "1. Описание задачи / 1.1 Требования"
   - objects[]           из секции "2. Задействованные объекты"
   - modification_points[] из секции "4. План изменений"
   - sql_queries[]       из блоков ```sql в тексте
   - patterns[]          из секции "3.X Найденные паттерны"
   - open_questions[]    из секции "6. Риски и открытые вопросы"
   - verified_fields[]   из маркеров "✓ проверено get_metadata"
   - validated_queries[] из маркеров "✓ валидировано execute_query"

2. SCORE — вычислить 5 компонентов:
   requirements_score = (covered / total) * 30
   fields_score       = (verified / total_in_sql) * 25
   patterns_score     = (with_pattern / modification_points) * 20
   sql_score          = (validated / total_queries) * 15
   questions_score    = (1 - open / max_open) * 10

3. OUTPUT:
   METRIC: {total_score}
   BREAKDOWN: req={req_score} fields={fields_score} patterns={pat_score} sql={sql_score} questions={q_score}
   GAPS: [{type, detail}, ...]
```

---

## Markers in ANALYSIS-REPORT.md

Scorer ищет специальные маркеры, которые Executor/Reviewer вставляют:

```markdown
### 2.1 Основные объекты
- Справочник.Контрагенты — поле гкс_КодОрганизации ✓ get_metadata
- РегистрСведений.АдресаОрганизаций — поле Адрес ✗ не проверено

### 4. План изменений
#### Точка 1: Добавить движение по регистру
- Образец: ОбщийМодуль.РаботаСМаршрутнымиЛистами.ОбработкаПроведения ✓ pattern
- SQL: ```sql ВЫБРАТЬ ... ИЗ ... ``` ✓ execute_query
```

Маркеры:
- `✓ get_metadata` — поле проверено через MCP
- `✗ не проверено` — поле не проверено (gap)
- `✓ pattern` — найден образец из конфигурации
- `✓ execute_query` — SQL валидирован на реальных данных
- `[REQ-N]` — привязка к требованию N

---

## Tasks

### 1.1 Parser

```python
# scripts/score-analysis-report.py
"""Parse ANALYSIS-REPORT.md and compute structured quality score."""

import re
import json
import sys
from pathlib import Path

def parse_report(text: str) -> dict:
    """Extract structure from ANALYSIS-REPORT.md."""
    # Extract requirements (numbered items in section 1.1)
    # Extract modification points (### Точка N: ...)
    # Extract SQL queries (```sql ... ```)
    # Extract verified fields (✓ get_metadata markers)
    # Extract patterns (✓ pattern markers)
    # Extract open questions (section 6)
    ...

def compute_score(parsed: dict) -> dict:
    """Compute 5-component quality score."""
    ...

def format_output(score: dict) -> str:
    """Format for Reviewer parsing: METRIC: N, BREAKDOWN: ..., GAPS: [...]"""
    ...
```

### 1.2 CLI Interface

```bash
# Usage:
python scripts/score-analysis-report.py path/to/ANALYSIS-REPORT.md

# Output:
METRIC: 73
BREAKDOWN: req=24/30 fields=15/25 patterns=16/20 sql=12/15 questions=6/10
GAPS: [{"type":"field_unverified","detail":"Справочник.Контрагенты.гкс_КодОрганизации"},{"type":"query_invalid","detail":"Запрос в точке 3 не валидирован"}]
```

### 1.3 Tests

- Тест на пустой отчёт → score 0
- Тест на идеальный отчёт (все маркеры) → score 100
- Тест на частично заполненный → корректный breakdown
- Тест на отчёт без SQL → sql_score компонент = max (нет SQL = нечего проверять)

---

## Deliverables

- [ ] `scripts/score-analysis-report.py` — scorer
- [ ] `tests/test_score_analysis_report.py` — unit tests
- [ ] Документация маркеров в `analyze-1c-task-v2/SKILL.md`

## Acceptance Criteria

1. Scorer корректно парсит реальный ANALYSIS-REPORT из предыдущих задач
2. Output формат парсится Reviewer промптом (regex: `METRIC:\s*([\d.]+)`)
3. GAPS список содержит actionable items для Executor
4. Score 0-100, монотонно растёт при добавлении маркеров
