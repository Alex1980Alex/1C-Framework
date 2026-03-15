# AutoResearch v2: Дорожная карта

**Дата:** 2026-03-15
**Статус:** Проектирование
**Z.AI:** unavailable (all providers failed), writing directly

---

## 1. Обзор и цели

**AutoResearch v2** — обобщённый автономный цикл улучшений для Claude Code. Пользователь даёт идею → Claude анализирует, создаёт команду → пользователь запускает → система работает автономно с двумя агентами (Executor + Reviewer).

**Вдохновение:**
- [Karpathy/autoresearch](https://github.com/karpathy/autoresearch) — 630 строк, ML-оптимизация, ~100 экспериментов за ночь
- [Goenka/autoresearch](https://github.com/uditgoenka/autoresearch) — обобщение для любых задач, 8-фазный цикл
- [Pi-autoresearch](https://github.com/davebcn87/pi-autoresearch) — session persistence, backpressure checks

**Ключевое отличие нашей версии:**
1. **Dual-agent** — Executor делает изменения, Reviewer блокирует регрессии
2. **Интеграция с Ralph Wiggum** — расширяет, а не заменяет существующий цикл
3. **Универсальность** — Python, BSL/1С, документация, тесты, безопасность
4. **Session persistence** — живой документ + JSONL для возобновления между сессиями/контекстами

---

## 2. Архитектура

### 2.1 Общая схема

```
  ПОЛЬЗОВАТЕЛЬ
      │
      │ "Уменьши время ответа API на 30%"
      ▼
┌─────────────────────────────────────────────────────────────┐
│  /autoresearch:plan (wizard)                                │
│                                                             │
│  1. Scope:  src/api/**/*.py                                 │
│  2. Metric: avg response time (ms)                          │
│  3. Direction: lower is better                              │
│  4. Verify:  pytest tests/api/ --benchmark-json=bench.json  │
│  5. Baseline: 142ms                                         │
│  6. Target:  < 100ms                                        │
│  7. Template: python-performance                             │
│                                                             │
│  → Генерирует autoresearch.md + команду запуска             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  ralph.bat --template autoresearch                          │
│  (или: /loop 20 /autoresearch)                              │
│                                                             │
│  ┌──────────────────────────────────────────────────┐       │
│  │            ITERATION LOOP                         │       │
│  │                                                   │       │
│  │  ┌─────────────┐    ┌──────────────┐              │       │
│  │  │  EXECUTOR    │    │  REVIEWER     │              │       │
│  │  │  (Agent 1)   │───▶│  (Agent 2)    │              │       │
│  │  │              │    │               │              │       │
│  │  │ 1. Review    │    │ 1. Diff check │              │       │
│  │  │ 2. Ideate    │    │ 2. Tests      │              │       │
│  │  │ 3. Modify    │    │ 3. Metric     │              │       │
│  │  │ 4. Commit    │    │ 4. Verdict    │              │       │
│  │  └─────────────┘    └──────┬───────┘              │       │
│  │                            │                      │       │
│  │                    ┌───────┴───────┐               │       │
│  │                    │   DECISION    │               │       │
│  │                    │               │               │       │
│  │                    │ KEEP / REVERT │               │       │
│  │                    │ / FIX / SKIP  │               │       │
│  │                    └───────┬───────┘               │       │
│  │                            │                      │       │
│  │                    ┌───────┴───────┐               │       │
│  │                    │     LOG       │               │       │
│  │                    │ (TSV + JSONL) │               │       │
│  │                    └───────┬───────┘               │       │
│  │                            │                      │       │
│  │                    ┌───────┴───────┐               │       │
│  │                    │   REPEAT      │               │       │
│  │                    └───────────────┘               │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
                  │
                  ▼
        autoresearch.md          (living document)
        autoresearch-results.tsv (metric log)
        autoresearch.jsonl       (full experiment log)
```

### 2.2 Dual-Agent: Executor + Reviewer

```
┌────────────────────────────────┐   ┌────────────────────────────────┐
│         EXECUTOR               │   │         REVIEWER               │
│                                │   │                                │
│ Роль: ДЕЛАТЬ изменения         │   │ Роль: ПРОВЕРЯТЬ изменения      │
│                                │   │                                │
│ Инструменты:                   │   │ Инструменты:                   │
│ - Read/Write/Edit файлы        │   │ - Read файлы (read-only)       │
│ - Bash (build, run)            │   │ - Bash (тесты, метрики)        │
│ - Git (commit, diff)           │   │ - Git (diff, log)              │
│ - MCP tools (по задаче)        │   │ - Grep/Glob (поиск регрессий)  │
│                                │   │                                │
│ НЕ делает:                     │   │ НЕ делает:                     │
│ - Не запускает тесты сам       │   │ - Не пишет код                 │
│ - Не оценивает свой код        │   │ - Не коммитит                  │
│                                │   │ - Не решает "keep/revert"      │
│                                │   │   (только рекомендует)         │
│ Выход: git commit + diff       │   │ Выход: verdict JSON            │
│                                │   │ {                              │
│                                │   │   "metric_before": 142,        │
│                                │   │   "metric_after": 128,         │
│                                │   │   "tests_pass": true,          │
│                                │   │   "regression": false,         │
│                                │   │   "verdict": "KEEP",           │
│                                │   │   "reason": "14ms faster"      │
│                                │   │ }                              │
└────────────────────────────────┘   └────────────────────────────────┘
```

**Протокол взаимодействия:**

```
1. EXECUTOR читает autoresearch.md → понимает контекст
2. EXECUTOR делает ONE атомарное изменение
3. EXECUTOR делает git commit (с prefix [AR-{iteration}])
4. REVIEWER получает: diff, scope, metric command, baseline
5. REVIEWER запускает verify command → получает новую метрику
6. REVIEWER запускает тесты → pass/fail
7. REVIEWER проверяет: нет ли изменений вне scope
8. REVIEWER выносит verdict: KEEP / REVERT / FIX
9. Если REVERT → git revert HEAD --no-edit
10. Если FIX → EXECUTOR получает feedback, ещё 1 попытка
11. LOG → append to TSV + JSONL
12. UPDATE autoresearch.md → добавить результат итерации
```

### 2.3 Интеграция с Ralph Wiggum

```
                    Ralph Wiggum (существующий)
                    ┌─────────────────────────┐
                    │ ralph.bat               │
                    │   │                     │
Новый шаблон ──────▶│   ├── --template autoresearch  ◀── НОВОЕ
                    │   ├── --template quality │
                    │   ├── --template 1c-study│
                    │   └── ...               │
                    └─────────┬───────────────┘
                              │
                    ┌─────────▼───────────────┐
                    │ ralph_activator.py       │
                    │ + detect "autoresearch"  │◀── РАСШИРИТЬ
                    │   keywords in prompt     │
                    └─────────┬───────────────┘
                              │
                    ┌─────────▼───────────────┐
                    │ ralph_wiggum_stop.py     │
                    │ + read autoresearch.md   │◀── РАСШИРИТЬ
                    │   target metric reached? │
                    └─────────────────────────┘
```

---

## 3. Фазы реализации

### Фаза 1: Skill + Plan Wizard (фундамент)

**Цель:** Создать SKILL.md и интерактивный wizard /autoresearch:plan

**Артефакты:**
```
.claude/skills/autoresearch/
├── SKILL.md                              # Главный скилл (8-фазный цикл)
├── references/
│   ├── autonomous-loop-protocol.md       # Детальный протокол 8 фаз
│   ├── core-principles.md                # 7 принципов
│   ├── plan-workflow.md                  # /autoresearch:plan wizard
│   ├── dual-agent-protocol.md            # Протокол Executor↔Reviewer
│   └── results-logging.md               # Форматы TSV + JSONL
└── templates/
    ├── python-quality.md                 # Шаблон: ruff + mypy
    ├── python-performance.md             # Шаблон: benchmark speed
    ├── bsl-quality.md                    # Шаблон: BSL ошибки
    ├── 1c-study.md                       # Шаблон: изучение конфигурации
    ├── test-coverage.md                  # Шаблон: покрытие тестами
    ├── documentation.md                  # Шаблон: docstrings coverage
    └── security-audit.md                # Шаблон: STRIDE + OWASP
```

**Критерии завершения:**
- [ ] SKILL.md загружается через `Skill('autoresearch')`
- [ ] /autoresearch:plan проводит через 5 gates (scope, metric, direction, verify, baseline)
- [ ] Генерирует autoresearch.md с полным контекстом задачи

---

### Фаза 2: Dual-Agent Engine

**Цель:** Реализовать двухагентное выполнение (Executor + Reviewer)

**Артефакты:**
```
scripts/
├── autoresearch.ps1                      # PowerShell launcher (Windows)
├── autoresearch.sh                       # Bash launcher (Linux/Mac)
└── autoresearch-reviewer.md              # Промпт для Reviewer агента

.claude/hooks/
├── autoresearch_orchestrator.py          # Hook: координация двух агентов
```

**Механизм dual-agent через Claude Code:**

```powershell
# autoresearch.ps1 — основной цикл

for ($i = 1; $i -le $MaxIterations; $i++) {
    # 1. EXECUTOR: одна итерация изменений
    claude -p $ExecutorPrompt --dangerously-skip-permissions `
        > executor_output.txt 2>&1

    # 2. REVIEWER: проверка изменений
    claude -p $ReviewerPrompt --dangerously-skip-permissions `
        > reviewer_output.txt 2>&1

    # 3. Парсинг verdict из reviewer_output.txt
    $verdict = Extract-Verdict reviewer_output.txt

    # 4. Применение решения
    if ($verdict -eq "REVERT") {
        git revert HEAD --no-edit
    }

    # 5. Логирование
    Add-Content autoresearch-results.tsv "$i`t$commit`t$metric`t$verdict`t$desc"
}
```

**Критерии завершения:**
- [ ] Executor делает изменение + commit
- [ ] Reviewer проверяет + выносит verdict
- [ ] REVERT работает автоматически
- [ ] TSV лог ведётся корректно

---

### Фаза 3: Session Persistence

**Цель:** Возобновление между сессиями/контекстами без потери прогресса

**Артефакты:**
```
data/autoresearch/
├── autoresearch.md                       # Living document: цель, прогресс, dead ends
├── autoresearch-results.tsv              # Метрики по итерациям
├── autoresearch.jsonl                    # Полный лог экспериментов
└── {session-id}/                         # Артефакты конкретной сессии
    ├── executor_output_{iter}.txt
    └── reviewer_output_{iter}.txt
```

**Формат autoresearch.md (живой документ):**

```markdown
# AutoResearch Session: API Response Time Optimization

## Goal
Reduce avg API response time from 142ms to <100ms

## Scope
src/api/**/*.py

## Metric
`pytest tests/api/ --benchmark-json=bench.json | jq '.benchmarks[].stats.mean'`
Direction: lower is better

## Baseline
142ms (measured 2026-03-15 14:30)

## Current Best
128ms (iteration 7, commit abc1234)

## History
| Iter | Change | Before | After | Verdict | Why |
|------|--------|--------|-------|---------|-----|
| 1 | Add response caching | 142 | 135 | KEEP | -7ms, tests pass |
| 2 | Async DB queries | 135 | 128 | KEEP | -7ms, tests pass |
| 3 | Inline serializer | 128 | 131 | REVERT | +3ms regression |
| 4 | Connection pooling | 128 | 128 | SKIP | no change |

## Dead Ends (don't retry)
- Inline serializer (iter 3): makes code worse, +3ms
- Connection pooling (iter 4): already pooled by framework

## Next Ideas
- [ ] Lazy loading of related objects
- [ ] Query optimization (N+1 detection)
- [ ] Response compression
```

**Формат autoresearch.jsonl:**

```json
{"iter":1,"ts":"2026-03-15T14:32:00Z","commit":"abc1234","change":"Add response caching","metric_before":142,"metric_after":135,"tests_pass":true,"verdict":"KEEP","reviewer_reason":"-7ms, tests pass","files_changed":["src/api/routes/search.py"],"diff_lines":12}
{"iter":2,"ts":"2026-03-15T14:37:00Z","commit":"def5678","change":"Async DB queries","metric_before":135,"metric_after":128,"tests_pass":true,"verdict":"KEEP","reviewer_reason":"-7ms, tests pass","files_changed":["src/api/dependencies/components.py"],"diff_lines":24}
```

**Критерии завершения:**
- [ ] autoresearch.md обновляется после каждой итерации
- [ ] Новая сессия читает autoresearch.md и продолжает с last iteration
- [ ] Dead ends не повторяются

---

### Фаза 4: Ralph Wiggum интеграция

**Цель:** Добавить шаблон `autoresearch` в ralph.bat + расширить hooks

**Изменения в существующих файлах:**

1. **scripts/ralph.bat** — новый template `autoresearch`:
```batch
) else if "%USE_TEMPLATE%"=="autoresearch" (
    echo [TEMPLATE] autoresearch
    set "PROMPT=ЗАДАЧА: Запусти AutoResearch v2 цикл. ..."
)
```

2. **ralph_activator.py** — добавить детекцию autoresearch-задач:
```python
AUTORESEARCH_SIGNALS = [
    "autoresearch", "автоисследование", "автономный цикл",
    "optimize", "оптимизируй", "улучши метрику",
    "reduce errors", "уменьши ошибки",
]
```

3. **ralph_wiggum_stop.py** — проверка target metric:
```python
def _check_autoresearch_target(self):
    """Read autoresearch.md, check if target metric reached."""
    ar_file = PROJECT_DIR / "data" / "autoresearch" / "autoresearch.md"
    # Parse current best vs target
    # If current_best meets target → RALPH_DONE
```

**Критерии завершения:**
- [ ] `ralph.bat --template autoresearch` запускает полный цикл
- [ ] ralph_activator детектит autoresearch-задачи
- [ ] ralph_wiggum_stop проверяет target из autoresearch.md

---

### Фаза 5: Шаблоны задач (Templates)

**Цель:** Готовые шаблоны для типовых задач

| Шаблон | Scope | Metric | Verify Command |
|--------|-------|--------|----------------|
| python-quality | `src/**/*.py` | ruff errors + mypy errors | `ruff check src/ --output-format json \| jq '.length'` |
| python-performance | `src/**/*.py` | response time (ms) | `pytest --benchmark-json=b.json` |
| bsl-quality | `src/bsl/**/*.bsl` | bsl_analyze errors | `bsl_analyze --format json \| jq '.length'` |
| 1c-study | `.claude/skills/1c-*/cache/` | coverage % | `python scripts/1c_coverage.py` |
| test-coverage | `tests/**/*.py` | coverage % | `pytest --cov=src --cov-report=json` |
| documentation | `src/**/*.py` | undocumented % | `interrogate src/ -f 100 --generate-badge .` |
| security-audit | `src/**/*.py` (read-only) | findings count | `bandit -r src/ -f json \| jq '.results \| length'` |

**Критерии завершения:**
- [ ] Каждый шаблон: scope + metric + verify command + baseline script
- [ ] /autoresearch:plan предлагает подходящий шаблон по описанию задачи

---

### Фаза 6: Security Audit Mode

**Цель:** Read-only /autoresearch:security для STRIDE + OWASP аудита

**Отличия от основного цикла:**
- НЕ модифицирует код
- Итерации = анализ разных attack vectors
- Метрика = количество найденных уязвимостей × severity
- Лог = findings с file:line + OWASP category + STRIDE tag

**Артефакты:**
```
security/{timestamp}-audit/
├── overview.md                 # Общий отчёт
├── threat-model.md             # STRIDE threat model
├── attack-surface-map.md       # Поверхность атаки
├── findings.md                 # Все находки (file:line + severity)
├── owasp-coverage.md           # Покрытие OWASP Top 10
├── recommendations.md          # Рекомендации по исправлению
└── security-audit-results.tsv  # TSV лог итераций
```

**Критерии завершения:**
- [ ] /autoresearch:security создаёт полный audit report
- [ ] Покрывает OWASP Top 10 + STRIDE
- [ ] Не модифицирует код (только Read + Grep)

---

### Фаза 7: Dashboard + Reporting

**Цель:** Визуализация прогресса AutoResearch

**Артефакты:**
```
scripts/autoresearch-dashboard.py          # CLI dashboard (TSV → таблица + график)
src/ui/pages/autoresearch_dashboard.py     # Streamlit UI
```

**CLI dashboard:**
```
$ python scripts/autoresearch-dashboard.py

AutoResearch: API Response Time Optimization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Iterations: 12 | Kept: 7 | Reverted: 4 | Skipped: 1
Baseline: 142ms | Current: 98ms | Target: <100ms | STATUS: REACHED

142 ┤████
135 ┤███
128 ┤██████████
 98 ┤█████████████████████ ← current best

Top improvements:
  1. Async DB queries       -14ms  (iter 2)
  2. Response caching        -7ms  (iter 1)
  3. Lazy loading            -9ms  (iter 8)
```

---

## 4. SKILL.md — ключевые элементы

### YAML Frontmatter

```yaml
---
name: autoresearch
description: "Autonomous goal-directed iteration. Modify → Verify → Keep/Discard → Repeat."
commands:
  - /autoresearch        # Unlimited loop
  - /autoresearch:plan   # Interactive wizard
  - /autoresearch:security  # STRIDE + OWASP audit
triggers:
  - "autoresearch"
  - "autonomous loop"
  - "автономный цикл"
  - "optimize metric"
  - "улучши метрику"
---
```

### 8-фазный цикл (dual-agent)

```
Phase 1: REVIEW
  Executor читает: autoresearch.md + git log -10 + autoresearch.jsonl (last 5)
  Понимает: что уже пробовали, что работало, что dead end

Phase 2: IDEATE
  Executor выбирает ОДНО изменение на основе:
  - Паттернов успешных изменений (из истории)
  - Dead ends (НЕ повторять)
  - Remaining ideas (из autoresearch.md)
  Формулирует гипотезу: "Если сделать X, метрика улучшится потому что Y"

Phase 3: MODIFY
  Executor делает ОДНО атомарное изменение
  Правило: объяснимо в 1 предложении
  Правило: затрагивает только файлы в scope

Phase 4: COMMIT
  Executor: git add -A && git commit -m "[AR-{iter}] {description}"
  ДО верификации — чтобы revert был чистым

Phase 5: VERIFY (Reviewer)
  Reviewer запускает verify command → новая метрика
  Reviewer запускает тесты → pass/fail
  Reviewer проверяет: файлы вне scope не затронуты?
  Reviewer проверяет: нет ли regression в других метриках?

Phase 6: DECIDE (Reviewer)
  KEEP   — метрика улучшилась И тесты прошли И нет регрессий
  REVERT — метрика ухудшилась ИЛИ тесты упали ИЛИ регрессия
  FIX    — тесты упали, но идея хорошая → Executor получает 1 попытку
  SKIP   — метрика не изменилась, нет смысла держать (revert для чистоты)

Phase 7: LOG
  Append to autoresearch-results.tsv
  Append to autoresearch.jsonl
  Update autoresearch.md (History table + Dead Ends + Next Ideas)

Phase 8: REPEAT
  Проверить: target достигнут? → RALPH_DONE
  Проверить: max iterations? → stop
  Иначе → Phase 1
```

---

## 5. Двухагентная реализация

### Вариант A: Два вызова `claude -p` (простой, надёжный)

```powershell
# В autoresearch.ps1

# Executor prompt (полный контекст + инструкция на ONE изменение)
$executorPrompt = @"
Ты — EXECUTOR в AutoResearch v2.
Прочитай data/autoresearch/autoresearch.md.
Сделай ОДНО атомарное изменение для улучшения метрики.
Git commit с prefix [AR-$iteration].
НЕ запускай тесты. НЕ оценивай свой код.
"@

# Reviewer prompt (diff + verify command)
$reviewerPrompt = @"
Ты — REVIEWER в AutoResearch v2.
1. git diff HEAD~1 — прочитай изменения
2. Запусти: $verifyCommand — получи метрику
3. Запусти: $testCommand — тесты проходят?
4. Проверь: файлы вне scope ($scope) не затронуты?
5. Выведи JSON verdict: {metric_before, metric_after, tests_pass, verdict, reason}
6. Если verdict=REVERT: выполни git revert HEAD --no-edit
"@

claude -p $executorPrompt --dangerously-skip-permissions
claude -p $reviewerPrompt --dangerously-skip-permissions
```

### Вариант B: Subagent внутри одной сессии (продвинутый)

```
# В SKILL.md — инструкция для Claude Code

После каждого изменения (Phase 3-4), вызови Agent tool:

Agent(prompt="Ты REVIEWER. Проверь последний коммит:
  1. git diff HEAD~1
  2. Запусти {verify_command}
  3. Запусти {test_command}
  4. Verdict: KEEP/REVERT/FIX/SKIP + reason
  Если REVERT: git revert HEAD --no-edit",
  subagent_type="general")
```

### Рекомендация: начать с Вариант A (два вызова), мигрировать на B позже.

---

## 6. TSV-формат логирования

```
# autoresearch-results.tsv
# Columns: iteration, timestamp, commit, change, metric_before, metric_after, delta, tests, verdict, reason
1	2026-03-15T14:32:00Z	abc1234	Add response caching	142	135	-7	pass	KEEP	-7ms, stable
2	2026-03-15T14:37:00Z	def5678	Async DB queries	135	128	-7	pass	KEEP	-7ms, stable
3	2026-03-15T14:42:00Z	ghi9012	Inline serializer	128	131	+3	pass	REVERT	+3ms regression
4	2026-03-15T14:47:00Z	jkl3456	Connection pooling	128	128	0	pass	SKIP	no change
```

---

## 7. Интеграция с существующей инфраструктурой

| Компонент | Текущее состояние | Изменения для AutoResearch v2 |
|-----------|-------------------|-------------------------------|
| `scripts/ralph.bat` | 7 шаблонов | +1 шаблон `autoresearch` |
| `ralph_activator.py` | Детектит factory/research/phase | +AUTORESEARCH_SIGNALS |
| `ralph_wiggum_stop.py` | Criteria JSON + markers | +проверка target metric из autoresearch.md |
| `ralph_state.py` | .ralph_active, criteria, counter | Без изменений (совместимо) |
| Task Protocol | Classify → Skill → Execute | AutoResearch = отдельный flow (не блокируется) |
| Z.AI delegation | >30 строк → delegate | Executor/Reviewer промпты < 30 строк (exempt) |
| Git hooks | auto-git-save, commit-enforcer | AutoResearch коммитит сам ([AR-N] prefix) |
| Skill Router | 16 bundles | +autoresearch bundle |

---

## 8. Команды пользователя

### Быстрый старт
```bash
# Запуск через ralph с шаблоном
scripts\ralph.bat --template autoresearch --max-iterations 20

# Запуск с кастомной целью
scripts\ralph.bat 15 "Goal: ruff check src/ = 0 errors. Metric: ruff error count. Verify: ruff check src/ --output-format json | jq length. AutoResearch protocol."
```

### Интерактивный режим
```
> /autoresearch:plan
Wizard:
  1. Какую метрику улучшить? > Время ответа API
  2. Scope файлов? > src/api/**/*.py
  3. Команда проверки? > pytest tests/api/ --benchmark-json=b.json
  4. Направление? > lower is better
  5. Целевое значение? > < 100ms
  Baseline: 142ms
  Ready! Запустить? > yes
```

### Security audit
```
> /autoresearch:security
  Scope: src/
  Target: OWASP Top 10 + STRIDE
  Mode: READ-ONLY
  Output: security/20260315-audit/
```

---

## 9. Метрики успеха

| Метрика | Baseline | Цель (через 2 недели) |
|---------|----------|----------------------|
| Шаблоны работают end-to-end | 0 | 7 шаблонов |
| Dual-agent verdict accuracy | — | >90% correct KEEP/REVERT |
| Session resume работает | нет | Да (autoresearch.md) |
| Среднее итераций до target | — | < 15 |
| Пользователь запускает 1 командой | нет | Да |
| Ralph интеграция | нет | Полная |

---

## 10. Приоритет фаз

| Фаза | Приоритет | Зависимости | Оценка сложности |
|------|-----------|-------------|------------------|
| 1. Skill + Plan Wizard | P0 | — | Medium |
| 2. Dual-Agent Engine | P0 | Фаза 1 | High |
| 3. Session Persistence | P0 | Фаза 2 | Medium |
| 4. Ralph интеграция | P1 | Фаза 2 | Low |
| 5. Шаблоны задач | P1 | Фаза 1 | Low |
| 6. Security Audit | P2 | Фаза 1 | Medium |
| 7. Dashboard | P3 | Фаза 3 | Low |

---

## Связанные документы

- [AutoResearch Comprehensive](260314_AutoResearch_Comprehensive.md) — 10 направлений
- [AutoResearch 1C Study](260314_ROADMAP_AUTORESEARCH_1C_STUDY.md) — изучение конфигурации
- [Ralph Wiggum docs](../documentation/Claude%20Code%20Docs/2.%20Создавайте%20с%20Claude%20Code/Автономные%20циклы%20Ralph%20Wiggum.md)
- [Goenka autoresearch](https://github.com/uditgoenka/autoresearch)
- [Karpathy autoresearch](https://github.com/karpathy/autoresearch)
- [Pi-autoresearch](https://github.com/davebcn87/pi-autoresearch)
