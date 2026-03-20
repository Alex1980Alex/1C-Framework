---
name: autoresearch
description: >
  AutoResearch v2 — автономный цикл улучшений с измеримыми метриками.
  ИСПОЛЬЗУЙ когда нужно итеративно УЛУЧШИТЬ, ОПТИМИЗИРОВАТЬ, УСКОРИТЬ,
  УМЕНЬШИТЬ ОШИБКИ, ПОВЫСИТЬ ПОКРЫТИЕ, или запустить АВТОНОМНЫЙ ЦИКЛ
  улучшений любого кода или процесса. Скилл анализирует идею, подбирает
  инструменты, создаёт уникальный рецепт (autoresearch.md + промпты + run.bat)
  и запускает автономный цикл с тремя агентами (Executor + Reviewer + Comparator).
  Домены: Python, BSL/1С, документация, тесты, производительность, безопасность.
  Триггеры: 'autoresearch', 'автономный цикл', 'улучши', 'оптимизируй',
  'уменьши ошибки', 'повысь покрытие', 'ускорь', 'reduce errors', 'improve',
  'optimize', 'benchmark', 'качество кода', 'measure and improve', 'keep/revert'.
  НЕ для разовых правок (→ обычный Write/Edit), НЕ для исследования (→ tech-research).
commands:
  - /autoresearch           # Анализ идеи → создание рецепта → запуск
  - /autoresearch:plan      # Интерактивный wizard (scope, metric, verify)
  - /autoresearch:security  # STRIDE + OWASP аудит (read-only)
ultrathink: true
---

# AutoResearch — Автономный цикл улучшений

## Обзор

Универсальный паттерн итеративных улучшений с измеримыми метриками.
Один движок, разные домены. Каждый домен — свой рецепт (метрика, инструменты, verify).

**Принцип:** `measure → change → verify → keep/revert → repeat`

## Алгоритм (10 фаз)

```
 1. IDEA      → Сформулировать гипотезу улучшения
 2. ANALYZE   → ultrathink: глубокий анализ проблемы и подходов
 3. BASELINE  → Зафиксировать текущую метрику (git commit)
 4. RECIPE    → Выбрать рецепт домена (метрика + tools + verify)
 5. EXECUTE   → Executor вносит ОДНО изменение
 6. REVIEW    → Reviewer запускает verify, фиксирует метрику
 7. COMPARE   → Comparator: слепое A/B каждые 5 итераций
 8. LOG       → Записать в autoresearch.jsonl
 9. DECIDE    → metric↑ → KEEP (commit) | metric↓ → REVERT
10. REPEAT    → Следующая итерация или стоп
```

### Логика решений

| Условие | Действие | Git |
|---------|----------|-----|
| `metric_new > metric_old` | KEEP | `git commit -m "[AR] +${delta} описание"` |
| `metric_new <= metric_old` | REVERT | `git revert HEAD --no-edit` |
| `iteration % 5 == 0` | A/B TEST | Comparator: слепое сравнение |
| 5 итераций без улучшений | STOP | Завершить цикл |

## Агенты

### Executor
- Вносит **одно** изменение по рецепту домена
- Не оценивает результат — только выполняет
- Коммитит изменение: `git commit -m "[AR] описание"`

### Reviewer
- Запускает verify-команду домена
- Сравнивает метрику с предыдущей
- Беспристрастен: только цифры → verdict (KEEP/REVERT)

### Comparator (каждые 5 итераций)
- Слепое сравнение: baseline vs текущее состояние
- Запускает полный eval, не зная какая версия какая
- Финальный арбитр при спорных дельтах

## Persistence (между сессиями)

### autoresearch.md — живой документ
```markdown
# AutoResearch: [название задачи]
Домен: skills | Метрика: F1 | Baseline: 0.6049
Итерация: 7 | Текущая: 0.72 | Тренд: ↑ +0.12
## Активная гипотеза
Переписать description скилла X в pushy стиле
## Следующие шаги
1. Улучшить search-pipeline-debug description
2. Запустить eval-skill-router.py
```

### autoresearch.jsonl — лог экспериментов
```jsonl
{"ts":"2026-03-15T10:23:00","iter":1,"metric":0.6049,"delta":0,"action":"baseline"}
{"ts":"2026-03-15T10:25:30","iter":2,"metric":0.6651,"delta":0.0602,"action":"keep","desc":"YAML+config fix"}
{"ts":"2026-03-15T10:28:00","iter":3,"metric":0.6500,"delta":-0.0151,"action":"revert","desc":"bad keyword"}
```

## Рецепты доменов

| Домен | Метрика | Verify Command | Scope |
|-------|---------|----------------|-------|
| **Скиллы** | F1 (eval-skill-router.py) | `python scripts/eval-skill-router.py` | `.claude/skills/` |
| **Python** | ruff + mypy errors | `ruff check src/ --output-format json` | `src/` |
| **BSL** | bsl_analyze errors | `bsl_analyze --json` | `src/bsl/` |
| **1С конфиг** | coverage % | `python scripts/1c_coverage.py` | `cache/` |
| **Документация** | audit-docs score | `Skill('audit-docs')` | `docs/` |
| **Хуки** | eval-hooks accuracy | `python scripts/eval-hooks.py` | `.claude/hooks/` |
| **Безопасность** | findings count | `bandit -r src/ -f json` | `src/` |
| **Тесты** | coverage % | `pytest --cov=src --cov-report=json` | `tests/` |

## Интеграция с Ralph Wiggum

### Через ralph.bat (автономный — Уровень 2)
```bash
# Скиллы: улучшить F1 trigger accuracy
scripts\ralph.bat --template skill-health --max-iterations 15

# Python: 0 ruff errors
scripts\ralph.bat --template quality --max-iterations 20

# 1С: изучить конфигурацию
scripts\ralph.bat --template 1c-study --max-iterations 10
```

### Через /autoresearch (интерактивный — Уровень 3)
```
> /autoresearch
> Улучши F1 skill router до 0.85

Claude:
1. ANALYZE: текущий F1 = 0.6651, 81 FP, 13 FN
2. RECIPE: домен "Скиллы", verify = eval-skill-router.py
3. Создаёт autoresearch.md + autoresearch.jsonl
4. Генерирует scripts/autoresearch-skill-f1.ps1
5. Пользователь запускает скрипт
```

## Стоп-условия

- Достигнут целевой порог метрики
- 5 итераций подряд без улучшений (плато)
- Превышен лимит итераций (max_iterations)
- Критическая ошибка (тесты сломаны, код не компилируется)
- Маркер: `RALPH_DONE` (при работе через ralph.bat)

## Команды

### /autoresearch — Анализ идеи и запуск

```
> /autoresearch
> Улучши F1 skill router до 0.85

Claude:
1. ANALYZE: текущий F1, FP/FN breakdown
2. RECIPE: домен + tools + metric + verify
3. Создаёт data/autoresearch/{idea}/ (autoresearch.md + prompts + run.bat)
4. Запускает цикл или предлагает run.bat
```

### /autoresearch:plan — Интерактивный wizard

Проводит через 5 gates: Scope → Metric → Direction → Verify → Baseline.
См. [plan-workflow.md](references/plan-workflow.md)

### /autoresearch:security — STRIDE + OWASP аудит

Read-only режим. Итерации = анализ разных attack vectors.
См. [security-audit.md](templates/security-audit.md)

## Запуск

```bash
# Через autoresearch.ps1 (три агента)
.\scripts\autoresearch.ps1 -Domain skills -MaxIterations 15 -Target 0.85

# Через ralph.bat (шаблон)
scripts\ralph.bat --template autoresearch --max-iterations 20
```

## Справочники

- [autonomous-loop-protocol.md](references/autonomous-loop-protocol.md) — 10-фазный цикл
- [core-principles.md](references/core-principles.md) — 7 принципов
- [dual-agent-protocol.md](references/dual-agent-protocol.md) — протокол 3 агентов
- [results-logging.md](references/results-logging.md) — форматы TSV + JSONL
- [plan-workflow.md](references/plan-workflow.md) — wizard /autoresearch:plan

## Шаблоны доменов

- [python-quality.md](templates/python-quality.md) — ruff + mypy
- [python-performance.md](templates/python-performance.md) — benchmark
- [bsl-quality.md](templates/bsl-quality.md) — BSL ошибки
- [1c-study.md](templates/1c-study.md) — изучение конфигурации
- [test-coverage.md](templates/test-coverage.md) — покрытие тестами
- [documentation.md](templates/documentation.md) — docstrings
- [security-audit.md](templates/security-audit.md) — STRIDE + OWASP
