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
1. **Idea-to-Recipe** — каждая идея анализируется и превращается в уникальный рецепт (инструменты + промпты + run.bat)
2. **Dual-agent** — Executor делает изменения, Reviewer блокирует регрессии
3. **Интеграция с Ralph Wiggum** — расширяет, а не заменяет существующий цикл
4. **Универсальность** — Python, BSL/1С, документация, тесты, безопасность — каждый домен со своими инструментами
5. **Session persistence** — живой документ + JSONL для возобновления между сессиями/контекстами

---

## 2. Архитектура

### 2.1 Принцип: Idea → Analysis → Recipe → Run

Каждая идея уникальна и требует своего набора инструментов, метрик и подходов.
`/autoresearch` НЕ заполняет фиксированный шаблон — он **создаёт уникальный рецепт**.

```
ВЫ: даёте идею (в чате)
      │
      ▼
/autoresearch (Claude анализирует идею)
      │
      ├── 1. ПОНЯТЬ: что именно улучшить?
      ├── 2. ИНСТРУМЕНТЫ: какие MCP, CLI, тесты нужны?
      ├── 3. МЕТРИКА: как ЧИСЛОМ измерить прогресс?
      ├── 4. ПОДХОД: по 1 файлу? по 1 категории? по 1 объекту?
      ├── 5. ПРОМПТЫ: Executor (что делать) + Reviewer (что проверять)
      └── 6. СКРИПТ: run.bat — готовая команда запуска
      │
      ▼
СОЗДАЁТ: data/autoresearch/{idea-name}-{date}/
      ├── autoresearch.md        ← полный план с инструментами и подходом
      ├── executor-prompt.md     ← промпт Executor (инструменты, scope, правила)
      ├── reviewer-prompt.md     ← промпт Reviewer (метрика, тесты, criteria)
      └── run.bat                ← запуск: ralph.bat с кастомным промптом
      │
      ▼
ВЫ: запускаете run.bat → работает автономно
```

### 2.2 Каждая идея — свой рецепт

Разные задачи требуют разных инструментов, метрик и подходов:

```
ИДЕЯ: "улучши BSL-код"              ИДЕЯ: "ускорь API"
┌─────────────────────┐             ┌─────────────────────┐
│ Инструменты:        │             │ Инструменты:        │
│ - bsl_analyze       │             │ - pytest-benchmark   │
│ - bsl-platform-ctx  │             │ - cProfile           │
│ - EDT-MCP           │             │ - Read/Write/Edit    │
│                     │             │                      │
│ Метрика:            │             │ Метрика:             │
│ - bsl_analyze errors│             │ - avg response ms    │
│                     │             │                      │
│ Подход:             │             │ Подход:              │
│ - 1 модуль за раз   │             │ - 1 endpoint за раз  │
│                     │             │                      │
│ Executor:           │             │ Executor:            │
│ - пишет BSL         │             │ - профилирует        │
│ - bsl-platform-ctx  │             │ - оптимизирует код   │
│   для проверки API  │             │                      │
│                     │             │ Reviewer:            │
│ Reviewer:           │             │ - benchmark          │
│ - bsl_analyze       │             │ - pytest             │
│ - проверка регрессий│             │ - latency сравнение  │
└─────────────────────┘             └──────────────────────┘

ИДЕЯ: "изучи конфигурацию 1С"       ИДЕЯ: "улучши документацию"
┌─────────────────────┐             ┌──────────────────────┐
│ Инструменты:        │             │ Инструменты:         │
│ - get_metadata      │             │ - interrogate        │
│ - find_references   │             │ - audit-docs         │
│ - execute_query     │             │ - Read/Write         │
│ - EDT-MCP           │             │                      │
│                     │             │ Метрика:             │
│ Метрика:            │             │ - % documented funcs │
│ - % изученных объект│             │                      │
│                     │             │ Подход:              │
│ Подход:             │             │ - 1 модуль за раз    │
│ - 1 объект за итерац│             │                      │
│ - 6 фаз на объект   │             │ Executor:            │
│                     │             │ - пишет docstrings   │
│ Executor:           │             │                      │
│ - запрашивает MCP   │             │ Reviewer:            │
│ - формулирует знания│             │ - interrogate score  │
│                     │             │ - pytest (не сломал) │
│ Reviewer:           │             └──────────────────────┘
│ - проверяет на базе │
│ - валидирует факты  │
└─────────────────────┘
```

### 2.3 Общая схема выполнения

```
  data/autoresearch/{idea}/autoresearch.md  (рецепт)
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  run.bat (или ralph.bat --template autoresearch)            │
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

### 2.4 Три агента: Executor + Reviewer + Comparator

> Архитектура вдохновлена [Skills 2.0 Skill Creator](260315_skills_2_0_research.md),
> который использует 4 агента: Executor, Grader, Comparator, Analyzer.
> Мы адаптируем 3 из 4 (Analyzer встроен в autoresearch.md как Dead Ends + Next Ideas).

```
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│       EXECUTOR          │  │       REVIEWER           │  │      COMPARATOR         │
│       (Agent 1)         │  │       (Agent 2)          │  │      (Agent 3)          │
│                         │  │                          │  │                         │
│ Роль: ДЕЛАТЬ            │  │ Роль: ПРОВЕРЯТЬ          │  │ Роль: СРАВНИВАТЬ        │
│                         │  │                          │  │                         │
│ Инструменты:            │  │ Инструменты:             │  │ Инструменты:            │
│ - Read/Write/Edit       │  │ - Read (read-only)       │  │ - Read (read-only)      │
│ - Bash (build, run)     │  │ - Bash (тесты, метрики)  │  │ - Bash (benchmark)      │
│ - Git (commit, diff)    │  │ - Git (diff, log)        │  │ - Git (diff, log)       │
│ - MCP tools (по задаче) │  │ - Grep (поиск регрессий) │  │                         │
│                         │  │                          │  │ Запускается:            │
│ НЕ делает:              │  │ НЕ делает:               │  │ - Каждые N итераций     │
│ - Не запускает тесты    │  │ - Не пишет код           │  │ - Или по запросу        │
│ - Не оценивает свой код │  │ - Не коммитит            │  │                         │
│                         │  │                          │  │ Делает:                 │
│ Выход:                  │  │ Выход:                   │  │ - Слепое A/B сравнение  │
│ git commit + diff       │  │ verdict JSON             │  │   baseline vs current   │
│                         │  │ {                        │  │ - Без знания "кто есть  │
│                         │  │   "metric_before": 142,  │  │   кто" (unbiased)       │
│                         │  │   "metric_after": 128,   │  │ - Общая оценка качества │
│                         │  │   "tests_pass": true,    │  │   (не только метрика)   │
│                         │  │   "regression": false,   │  │                         │
│                         │  │   "verdict": "KEEP",     │  │ Выход:                  │
│                         │  │   "reason": "-14ms"      │  │ comparison JSON         │
│                         │  │ }                        │  │ {                       │
│                         │  │                          │  │   "winner": "B",        │
│                         │  │                          │  │   "quality_A": 6,       │
│                         │  │                          │  │   "quality_B": 8,       │
│                         │  │                          │  │   "notes": "B cleaner"  │
│                         │  │                          │  │ }                       │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

**Когда запускается Comparator:**
- Каждые **5 итераций** (или настраиваемо)
- Сравнивает текущий код vs baseline (git stash/checkout)
- Оценивает не только метрику, но и **качество кода, читаемость, сложность**
- Может рекомендовать **откат всей серии** если код стал хуже при лучшей метрике

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

### Фаза 7: Eval-система для скилла AutoResearch

**Цель:** Измеримое тестирование самого скилла autoresearch (из Skills 2.0)

> Skills 2.0 Skill Creator включает eval-систему: 20 промптов, A/B бенчмарк,
> слепое сравнение. Применяем тот же подход к нашему скиллу.

**Артефакты:**
```
data/eval/autoresearch/
├── eval_prompts.json              # 20 eval-промптов (10 должны триггерить, 10 нет)
├── eval_results.json              # Результаты последнего прогона
└── eval_baseline.json             # Baseline: без скилла (vanilla Claude)

scripts/
├── eval-autoresearch.py           # Прогон eval: запускает агентов, считает метрики
└── eval-autoresearch-report.py    # Отчёт: trigger accuracy, A/B comparison
```

**Eval-промпты (примеры):**
```json
[
  {"prompt": "Уменьши количество ошибок ruff в src/", "should_trigger": true, "expected_tools": ["ruff"]},
  {"prompt": "Оптимизируй время ответа API", "should_trigger": true, "expected_tools": ["pytest-benchmark"]},
  {"prompt": "Изучи документ ЗаказНаПеревозку", "should_trigger": false, "expected_skill": "1c-doc-research"},
  {"prompt": "Сделай git commit", "should_trigger": false, "expected_skill": null},
  {"prompt": "Повысь покрытие тестами до 80%", "should_trigger": true, "expected_tools": ["pytest-cov"]},
  {"prompt": "Запусти автономный цикл улучшения BSL", "should_trigger": true, "expected_tools": ["bsl_analyze"]}
]
```

**Метрики eval:**
- **Trigger accuracy**: % правильных срабатываний/несрабатываний
- **Tool selection accuracy**: правильно ли подобраны инструменты
- **Recipe quality**: autoresearch.md содержит scope + metric + verify?
- **A/B**: с autoresearch vs без (vanilla Ralph) — кол-во итераций до target

**Критерии завершения:**
- [ ] 20 eval-промптов покрывают все 7 шаблонов + негативные кейсы
- [ ] Trigger accuracy > 90%
- [ ] Tool selection accuracy > 85%
- [ ] A/B показывает преимущество autoresearch vs vanilla

---

### Фаза 8: Dashboard + Reporting

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

> **Trigger Tuning** (из Skills 2.0): описание должно быть "настойчивым" (pushy) —
> недотриггеринг чаще, чем перетриггеринг. Бюджет: ~2% контекстного окна.

```yaml
---
name: autoresearch
description: >
  ИСПОЛЬЗУЙ ЭТОТ СКИЛЛ когда пользователь хочет что-то УЛУЧШИТЬ, ОПТИМИЗИРОВАТЬ,
  УСКОРИТЬ, УМЕНЬШИТЬ ОШИБКИ, ПОВЫСИТЬ ПОКРЫТИЕ, или запустить АВТОНОМНЫЙ ЦИКЛ
  улучшений любого кода или процесса. Скилл анализирует идею, подбирает инструменты,
  создаёт уникальный рецепт (autoresearch.md + промпты + run.bat) и запускает
  автономный цикл с тремя агентами (Executor + Reviewer + Comparator).
  Домены: Python, BSL/1С, документация, тесты, производительность, безопасность.
  Ключевые слова: autoresearch, автономный цикл, улучши, оптимизируй, уменьши ошибки,
  повысь покрытие, ускорь, reduce errors, improve, optimize, benchmark, качество кода.
commands:
  - /autoresearch           # Анализ идеи → создание рецепта → запуск
  - /autoresearch:plan      # Интерактивный wizard (scope, metric, verify)
  - /autoresearch:security  # STRIDE + OWASP аудит (read-only)
triggers:
  - "autoresearch"
  - "autonomous loop"
  - "автономный цикл"
  - "optimize"
  - "оптимизируй"
  - "улучши"
  - "уменьши ошибки"
  - "повысь покрытие"
  - "ускорь"
---
```

### 10-фазный цикл (три агента)

> **ultrathink** встроен в Phase 0 и Phase 2 для максимального рассуждения
> при анализе идеи и генерации гипотез (Skills 2.0: ultrathink в SKILL.md
> включает extended thinking на 31999 токенов).

```
Phase 0: ANALYZE (только первая итерация) — ultrathink
  Claude анализирует идею пользователя:
  - Какие инструменты нужны? (MCP, CLI, тесты)
  - Как измерить прогресс? (метрика + verify command)
  - Какой подход? (по файлу, по категории, по объекту)
  - Создаёт: autoresearch.md + executor-prompt.md + reviewer-prompt.md + run.bat

Phase 1: REVIEW
  Executor читает: autoresearch.md + git log -10 + autoresearch.jsonl (last 5)
  Понимает: что уже пробовали, что работало, что dead end

Phase 2: IDEATE — ultrathink
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

Phase 7: COMPARE (Comparator — каждые N итераций)
  Каждые 5 итераций (настраиваемо) запускается Comparator:
  - Слепое A/B: baseline code (git stash) vs current code
  - Оценка: не только метрика, но и качество кода, читаемость, сложность
  - Если код деградировал при лучшей метрике → рекомендация "пересмотреть подход"
  - Результат в autoresearch.md секция "## Comparator Reviews"

Phase 8: LOG
  Append to autoresearch-results.tsv
  Append to autoresearch.jsonl
  Update autoresearch.md (History table + Dead Ends + Next Ideas)

Phase 9: REPEAT
  Проверить: target достигнут? → RALPH_DONE
  Проверить: max iterations? → stop
  Иначе → Phase 1
```

---

## 5. Трёхагентная реализация

### Вариант A: Три вызова `claude -p` (простой, надёжный)

```powershell
# В autoresearch.ps1

for ($i = 1; $i -le $MaxIterations; $i++) {

    # 1. EXECUTOR: одна итерация изменений
    $executorPrompt = @"
Ты — EXECUTOR в AutoResearch v2. Итерация $i.
Прочитай data/autoresearch/{idea}/autoresearch.md.
Сделай ОДНО атомарное изменение для улучшения метрики.
Git commit с prefix [AR-$i].
НЕ запускай тесты. НЕ оценивай свой код.
"@
    claude -p $executorPrompt --dangerously-skip-permissions `
        > "data/autoresearch/{idea}/executor_$i.txt" 2>&1

    # 2. REVIEWER: проверка изменений
    $reviewerPrompt = @"
Ты — REVIEWER в AutoResearch v2. Итерация $i.
1. git diff HEAD~1 — прочитай изменения
2. Запусти: $verifyCommand — получи метрику
3. Запусти: $testCommand — тесты проходят?
4. Проверь: файлы вне scope ($scope) не затронуты?
5. Выведи JSON verdict: {metric_before, metric_after, tests_pass, verdict, reason}
6. Если verdict=REVERT: выполни git revert HEAD --no-edit
7. Обнови data/autoresearch/{idea}/autoresearch.md (History, Dead Ends)
"@
    claude -p $reviewerPrompt --dangerously-skip-permissions `
        > "data/autoresearch/{idea}/reviewer_$i.txt" 2>&1

    # 3. COMPARATOR: каждые 5 итераций — слепое A/B сравнение
    if ($i % 5 -eq 0) {
        $comparatorPrompt = @"
Ты — COMPARATOR в AutoResearch v2. Слепое A/B сравнение.
1. Прочитай текущий код в scope: $scope
2. git stash && git checkout {baseline_commit} — прочитай baseline код
3. git checkout - && git stash pop — вернись
4. Сравни версию A и B БЕЗ знания какая baseline, какая current
5. Оцени: качество кода (1-10), читаемость (1-10), сложность (1-10)
6. Выведи JSON: {winner, quality_A, quality_B, readability_A, readability_B, notes}
7. Обнови autoresearch.md секцию '## Comparator Reviews'
"@
        claude -p $comparatorPrompt --dangerously-skip-permissions `
            > "data/autoresearch/{idea}/comparator_$i.txt" 2>&1
    }
}
```

### Вариант B: Subagent внутри одной сессии (продвинутый)

```
# В SKILL.md — инструкция для Claude Code

После каждого изменения (Phase 3-4), вызови Agent tool для Review:

Agent(prompt="Ты REVIEWER. Проверь последний коммит:
  1. git diff HEAD~1
  2. Запусти {verify_command}
  3. Запусти {test_command}
  4. Verdict: KEEP/REVERT/FIX/SKIP + reason
  Если REVERT: git revert HEAD --no-edit",
  subagent_type="general")

Каждые 5 итераций вызови Agent tool для Compare:

Agent(prompt="Ты COMPARATOR. Слепое A/B сравнение:
  1. Прочитай текущий код в {scope}
  2. git stash; git checkout {baseline}; прочитай код; git checkout -; git stash pop
  3. Оцени оба варианта по качеству, читаемости, сложности (1-10)
  4. JSON: {winner, quality_A, quality_B, notes}",
  subagent_type="general")
```

### Рекомендация: начать с Вариант A (три вызова), мигрировать на B позже.

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
| Три агента verdict accuracy | — | >90% correct KEEP/REVERT |
| Comparator A/B accuracy | — | >85% correct winner |
| Session resume работает | нет | Да (autoresearch.md) |
| Среднее итераций до target | — | < 15 |
| Пользователь запускает 1 командой | нет | Да |
| Ralph интеграция | нет | Полная |
| Eval trigger accuracy | — | >90% |
| Eval tool selection accuracy | — | >85% |

---

## 10. Приоритет фаз

| Фаза | Приоритет | Зависимости | Оценка сложности |
|------|-----------|-------------|------------------|
| 1. Skill + Plan Wizard | P0 | — | Medium |
| 2. Three-Agent Engine | P0 | Фаза 1 | High |
| 3. Session Persistence | P0 | Фаза 2 | Medium |
| 4. Ralph интеграция | P1 | Фаза 2 | Low |
| 5. Шаблоны задач | P1 | Фаза 1 | Low |
| 6. Security Audit | P2 | Фаза 1 | Medium |
| 7. Eval-система | P1 | Фаза 1 | Medium |
| 8. Dashboard | P3 | Фаза 3 | Low |

---

## 11. Источники из Skills 2.0 (интегрировано)

| Концепция из Skills 2.0 | Как применено в AutoResearch v2 |
|---|---|
| **4 агента** (Executor, Grader, Comparator, Analyzer) | 3 агента: Executor + Reviewer + Comparator. Analyzer = autoresearch.md |
| **Eval-система** (20 промптов, A/B) | Фаза 7: `data/eval/autoresearch/eval_prompts.json` |
| **Trigger Tuning** (pushy description) | YAML frontmatter: развёрнутый description с ключевыми словами |
| **Ultrathink** (extended thinking в SKILL.md) | Phase 0 (ANALYZE) и Phase 2 (IDEATE) — ultrathink для глубокого рассуждения |
| **Encoded Preference > Capability Uplift** | AutoResearch = Encoded Preference скилл (долговечный) |
| **Слепое A/B** (Comparator без знания "кто есть кто") | Phase 7 (COMPARE): каждые 5 итераций |
| **Чистый изолированный контекст** | Каждый `claude -p` = отдельный контекст (уже есть) |

Подробный анализ: [260315_skills_2_0_research.md](../260315_skills_2_0_research.md)

---

## Связанные документы

- [AutoResearch Comprehensive](260314_AutoResearch_Comprehensive.md) — 10 направлений
- [AutoResearch 1C Study](260314_ROADMAP_AUTORESEARCH_1C_STUDY.md) — изучение конфигурации
- [Ralph Wiggum docs](../documentation/Claude%20Code%20Docs/2.%20Создавайте%20с%20Claude%20Code/Автономные%20циклы%20Ralph%20Wiggum.md)
- [Goenka autoresearch](https://github.com/uditgoenka/autoresearch)
- [Karpathy autoresearch](https://github.com/karpathy/autoresearch)
- [Pi-autoresearch](https://github.com/davebcn87/pi-autoresearch)
