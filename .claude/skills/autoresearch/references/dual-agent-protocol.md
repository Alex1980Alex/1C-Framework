# Протокол трёх агентов: Executor + Reviewer + Comparator

## Executor (Agent 1) — ДЕЛАЕТ

**Инструменты:** Read, Write, Edit, Bash (build/run), Git (commit/diff), MCP tools (по задаче)

**НЕ делает:** не запускает тесты, не оценивает свой код, не выносит verdict

**Протокол:**
1. Читает `autoresearch.md` — понимает контекст
2. Выбирает ОДНО изменение (не из Dead Ends)
3. Вносит атомарное изменение в scope
4. `git commit -m "[AR-{iter}] {description}"`

## Reviewer (Agent 2) — ПРОВЕРЯЕТ

**Инструменты:** Read (read-only), Bash (тесты/метрики), Git (diff/log), Grep

**НЕ делает:** не пишет код, не коммитит

**Протокол:**
1. `git diff HEAD~1` — читает изменения
2. Запускает verify command → получает метрику
3. Запускает test command → pass/fail
4. Проверяет: файлы вне scope не затронуты?
5. Выносит verdict JSON
6. Если REVERT: `git revert HEAD --no-edit`
7. Обновляет `autoresearch.md` (History, Dead Ends)

**Verdict JSON формат:**
```json
{
  "metric_before": 142,
  "metric_after": 128,
  "tests_pass": true,
  "regression": false,
  "verdict": "KEEP",
  "reason": "-14ms, tests pass, no regressions"
}
```

## Comparator (Agent 3) — СРАВНИВАЕТ

**Инструменты:** Read (read-only), Bash (benchmark), Git (diff/log)

**Запускается:** каждые 5 итераций (настраиваемо)

**Протокол:**
1. Читает текущий код в scope
2. `git stash && git checkout {baseline_commit}` → читает baseline код
3. `git checkout - && git stash pop` → возврат
4. Слепое сравнение A vs B (не зная какая версия текущая)
5. Оценка: качество (1-10), читаемость (1-10), сложность (1-10)
6. Обновляет `autoresearch.md` секцию `## Comparator Reviews`

**Comparison JSON формат:**
```json
{
  "winner": "B",
  "quality_A": 6,
  "quality_B": 8,
  "readability_A": 7,
  "readability_B": 8,
  "complexity_A": 5,
  "complexity_B": 4,
  "notes": "Version B has cleaner abstractions and less duplication"
}
```

## Реализация через claude -p

```
Iteration:
  1. claude -p $ExecutorPrompt  → executor_output.txt
  2. claude -p $ReviewerPrompt  → reviewer_output.txt
  3. Parse verdict → KEEP/REVERT/FIX/SKIP
  4. If REVERT → already done by Reviewer
  5. Every 5 iterations: claude -p $ComparatorPrompt → comparator_output.txt
  6. Log to TSV + JSONL
```

## Альтернатива: Subagent внутри одной сессии

```
Agent(prompt="Ты REVIEWER. Проверь git diff HEAD~1...",
      subagent_type="general")

Agent(prompt="Ты COMPARATOR. Слепое A/B сравнение...",
      subagent_type="general")
```
