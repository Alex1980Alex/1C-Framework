# Протокол автономного цикла AutoResearch v2

## 10-фазный цикл

### Phase 0: ANALYZE (только первая итерация) — ultrathink

Глубокий анализ идеи пользователя:
- Какие инструменты нужны? (MCP, CLI, тесты)
- Как измерить прогресс? (метрика + verify command)
- Какой подход? (по файлу, по категории, по объекту)

**Выход:** `data/autoresearch/{idea}/`
- `autoresearch.md` — живой документ с планом
- `executor-prompt.md` — промпт Executor
- `reviewer-prompt.md` — промпт Reviewer
- `run.bat` — команда запуска

### Phase 1: REVIEW

Executor читает контекст:
```
1. autoresearch.md — текущее состояние, dead ends, next ideas
2. git log --oneline -10 — последние коммиты
3. autoresearch.jsonl (last 5) — результаты последних итераций
```

### Phase 2: IDEATE — ultrathink

Executor выбирает ОДНО изменение:
- Паттерны успешных изменений (из истории)
- Dead ends (НЕ повторять)
- Remaining ideas (из autoresearch.md)

Формулирует гипотезу: "Если сделать X, метрика улучшится потому что Y"

### Phase 3: MODIFY

Executor делает ОДНО атомарное изменение:
- Объяснимо в 1 предложении
- Затрагивает только файлы в scope
- Минимальный diff

### Phase 4: COMMIT

```bash
git add -A && git commit -m "[AR-{iter}] {description}"
```

Коммит ДО верификации — чтобы `git revert` был чистым.

### Phase 5: VERIFY (Reviewer)

Reviewer выполняет:
1. Запускает verify command → получает новую метрику
2. Запускает test command → pass/fail
3. Проверяет: файлы вне scope не затронуты?
4. Проверяет: нет ли regression в других метриках?

### Phase 6: DECIDE (Reviewer)

| Verdict | Условие | Действие |
|---------|---------|----------|
| **KEEP** | метрика улучшилась И тесты прошли И нет регрессий | оставить коммит |
| **REVERT** | метрика ухудшилась ИЛИ тесты упали ИЛИ регрессия | `git revert HEAD --no-edit` |
| **FIX** | тесты упали, но идея хорошая | Executor получает 1 попытку |
| **SKIP** | метрика не изменилась | revert для чистоты кода |

### Phase 7: COMPARE (Comparator — каждые N итераций)

Каждые 5 итераций запускается Comparator:
- Слепое A/B: baseline code vs current code
- Оценка: качество кода (1-10), читаемость (1-10), сложность (1-10)
- Если код деградировал при лучшей метрике → рекомендация "пересмотреть подход"
- Результат в `autoresearch.md` секция `## Comparator Reviews`

### Phase 8: LOG

```
1. Append to autoresearch-results.tsv (iteration, timestamp, commit, change, metric_before, metric_after, delta, tests, verdict, reason)
2. Append to autoresearch.jsonl (full JSON record)
3. Update autoresearch.md (History table + Dead Ends + Next Ideas)
```

### Phase 9: REPEAT

Проверки:
- Target достигнут? → AUTORESEARCH_DONE
- Max iterations? → stop
- Plateau (5 итераций без улучшений)? → stop
- Иначе → Phase 1
