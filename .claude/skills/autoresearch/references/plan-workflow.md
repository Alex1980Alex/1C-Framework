# /autoresearch:plan — Интерактивный Wizard

## Обзор

Wizard проводит пользователя через 5 gates для создания полного рецепта AutoResearch.
Результат: директория `data/autoresearch/{idea-name}-{date}/` с готовыми файлами.

## 5 Gates

### Gate 1: SCOPE — Что улучшать?

```
Какие файлы/директории в scope? (glob pattern)
> src/api/**/*.py
```

Валидация: паттерн должен матчить хотя бы 1 файл.

### Gate 2: METRIC — Как измерять?

```
Команда, которая выводит числовую метрику:
> pytest tests/api/ --benchmark-json=bench.json | jq '.benchmarks[].stats.mean'
```

Валидация: команда должна выводить число.

### Gate 3: DIRECTION — Направление улучшения

```
Метрика должна расти или уменьшаться?
> lower is better
```

Варианты: `higher is better` | `lower is better`

### Gate 4: VERIFY — Тестовая команда

```
Как проверить что ничего не сломалось?
> pytest tests/ -q
```

Валидация: команда должна возвращать exit code 0.

### Gate 5: BASELINE — Замер и цель

```
Измеряю текущее значение... Baseline: 142ms
Целевое значение? (необязательно)
> < 100ms
```

## Выходные артефакты

```
data/autoresearch/{idea-name}-{date}/
├── autoresearch.md          # Живой документ с планом
├── executor-prompt.md       # Промпт для Executor агента
├── reviewer-prompt.md       # Промпт для Reviewer агента
└── run.bat                  # Команда запуска
```

### Шаблон autoresearch.md

```markdown
# AutoResearch Session: {название}

## Goal
{описание цели}

## Scope
{glob pattern}

## Metric
`{verify command}`
Direction: {higher|lower} is better

## Baseline
{значение} (measured {дата})

## Target
{целевое значение}

## Current Best
{значение} (iteration N, commit hash)

## History
| Iter | Change | Before | After | Verdict | Why |
|------|--------|--------|-------|---------|-----|

## Dead Ends (don't retry)

## Next Ideas
- [ ] ...

## Comparator Reviews
```
