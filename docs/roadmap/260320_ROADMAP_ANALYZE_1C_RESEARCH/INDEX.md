# Analyze-1C-Research: Трёхагентный анализ задач 1С

**Date:** 2026-03-20 | **Status:** PHASES 1-6 DONE, PHASE 7 TODO

**Goal:** Итеративный анализ задач 1С:Предприятие с тремя агентами (Executor + Reviewer + Comparator), измеримой метрикой качества и интеграцией с AutoResearch + Ralph Wiggum.

**Base:** analyze-1c-task-v2 (5 фаз), autoresearch.ps1 (three-agent engine), Ralph Wiggum (autonomous loop)

---

## Проблема

Текущий `analyze-1c-task-v2` — **однопроходный** анализ. Один агент выполняет все 5 фаз и сам оценивает результат. Проблемы:

1. **Нет объективной оценки** — анализ не верифицируется независимым ревьюером
2. **Нет метрики качества** — невозможно измерить "насколько хороший анализ"
3. **Нет итераций** — пропущенные требования, непроверенные поля остаются навсегда
4. **Нет persistence** — при обрыве сессии контекст теряется

AutoResearch v2 решает эти проблемы для кода (ruff errors, F1). Нужна адаптация для домена **анализа задач 1С**.

---

## Целевая архитектура

```
┌──────────────────────────────────────────────────────────┐
│  Level 1: Loop Manager                                   │
│  ralph.bat --template 1c-analysis   (автономный)         │
│  /analyze-1c-task:research          (интерактивный)       │
│  analyze-1c-research.ps1            (headless)            │
└───────────────────────┬──────────────────────────────────┘
                        │ iteration loop
┌───────────────────────▼──────────────────────────────────┐
│  Level 2: Three-Agent Engine                             │
│                                                          │
│  ┌────────────┐  ┌─────────────┐  ┌───────────────────┐ │
│  │  EXECUTOR   │  │  REVIEWER    │  │   COMPARATOR      │ │
│  │  Phases 1-4 │→ │  Phase 5    │→ │   (every 3 iter)  │ │
│  │  + feedback │  │  + scoring  │  │   blind A/B       │ │
│  │  fix        │  │  + MCP      │  │   report vs report│ │
│  └────────────┘  └─────────────┘  └───────────────────┘ │
│                                                          │
│  Persistence: analysis-session/                          │
│    analysis-report.md  (живой отчёт)                     │
│    autoresearch.md     (state: iter, metric, dead ends)  │
│    reviewer_feedback.json (gap list для Executor)        │
│    autoresearch.jsonl  (история итераций)                │
│    logs/executor_N.txt, reviewer_N.txt, comparator_N.txt │
└───────────────────────┬──────────────────────────────────┘
                        │ MCP calls
┌───────────────────────▼──────────────────────────────────┐
│  Level 3: MCP Infrastructure                             │
│  bsl-semantic-search   → поиск паттернов в конфигурации  │
│  1c-mcp-toolkit        → get_metadata, execute_query     │
│  bsl-platform-context  → API платформы 1С                │
│  serena                → символьный анализ кода          │
│  pdf-vector-graph      → документация 1С 8.3.27          │
└──────────────────────────────────────────────────────────┘
```

---

## Structured Quality Score (метрика)

В отличие от кода (ruff errors, F1), у анализа нет числовой метрики "из коробки". Определяем **analysis_score (0-100)**:

| Компонент | Вес | Как считать |
|-----------|-----|-------------|
| Requirements coverage | 30% | `covered_requirements / total_requirements` |
| Fields verified | 25% | `verified_fields / total_fields_in_sql` (через get_metadata) |
| Patterns found | 20% | `points_with_pattern / total_modification_points` |
| SQL validated | 15% | `validated_queries / total_queries` (через execute_query) |
| Open questions resolved | 10% | `1 - open_questions / max_open_questions` |

**Direction:** higher is better. **Target:** >= 85.

Scorer парсит секции ANALYSIS-REPORT.md и считает score автоматически.

---

## Phases

| Phase | Name | Priority | Effort | Depends On | Deliverable |
|-------|------|----------|--------|------------|-------------|
| **1** | Analysis Quality Scorer | CRITICAL | 1d | -- | [PHASE_1.md](PHASE_1.md) |
| **2** | Agent Prompt Templates | CRITICAL | 1d | -- | [PHASE_2.md](PHASE_2.md) |
| **3** | Runner Script | HIGH | 1-2d | 1, 2 | [PHASE_3.md](PHASE_3.md) |
| **4** | In-Session Subagents | HIGH | 1d | 1, 2 | [PHASE_4.md](PHASE_4.md) |
| **5** | Ralph Integration | MEDIUM | 0.5d | 3 | [PHASE_5.md](PHASE_5.md) |
| **6** | Skill Update v3.0 | MEDIUM | 0.5d | 4 | [PHASE_6.md](PHASE_6.md) |
| **7** | Eval & Benchmark | LOW | 1-2d | 1 | [PHASE_7.md](PHASE_7.md) |

**Total: 6-9 days**

---

## Implementation Order

```
Sprint 1 (2 дня): FOUNDATION
  +-- Phase 1: Analysis Quality Scorer
  +-- Phase 2: Agent Prompt Templates (parallel)

Sprint 2 (2 дня): ENGINE
  +-- Phase 3: Runner Script (headless)
  +-- Phase 4: In-Session Subagents (parallel)

Sprint 3 (1 день): INTEGRATION
  +-- Phase 5: Ralph Integration
  +-- Phase 6: Skill Update v3.0

Sprint 4 (1-2 дня): VALIDATION
  +-- Phase 7: Eval & Benchmark
```

---

## Dependency Graph

```
Phase 1 (Scorer) ──────┬──→ Phase 3 (Runner) ──→ Phase 5 (Ralph)
                        │
Phase 2 (Prompts) ──┬──┘──→ Phase 4 (Subagents) → Phase 6 (Skill v3)
                    │
                    └──────→ Phase 7 (Eval)
```

---

## Отличия от AutoResearch для кода

| Аспект | AutoResearch (код) | Analyze-1C-Research |
|--------|-------------------|---------------------|
| Executor делает | Правит код | Улучшает ANALYSIS-REPORT.md |
| Метрика | ruff errors, F1 | Structured quality score (0-100) |
| Verify | Тесты + линтер | Парсинг отчёта + MCP валидация |
| REVERT означает | git revert кода | Откат к предыдущей версии отчёта |
| Comparator сравнивает | Код A vs B | Отчёт A vs B |
| Plateau threshold | 5 итераций | 3 итерации (анализ быстрее) |
| Типичный цикл | 10-20 итераций | 3-7 итераций |
| MCP tools | Минимально | Активно (get_metadata, execute_query, bsl_search) |
| Dead Ends | Кодовые подходы | Неверные гипотезы об архитектуре задачи |

---

## Роли агентов

### Executor — фазы 1-4, доработка по feedback

**Инструменты:** Read, Write, Edit, Git, bsl-semantic-search, 1c-mcp-toolkit, bsl-platform-context, serena, Grep/Glob

**Протокол:**
1. Итерация 1: полный анализ фаз 1-4 → ANALYSIS-REPORT.md
2. Итерация N>1: читает `reviewer_feedback.json`, улучшает ОДНУ слабую область:
   - `requirement_gap` → добавить покрытие требования, найти modification point
   - `field_unverified` → вызвать get_metadata, проверить имя поля
   - `pattern_missing` → вызвать bsl_search/bsl_hybrid_search, найти аналог
   - `query_invalid` → вызвать execute_query, валидировать SQL
   - `open_question` → исследовать и закрыть вопрос
3. Git commit: `[AR-{N}] {описание улучшения}`

**Ограничения:** не оценивает свой анализ, не запускает scorer

### Reviewer — фаза 5 + scoring + MCP verification

**Инструменты:** Read (read-only), Bash (scorer), Git, 1c-mcp-toolkit (execute_query для проверки SQL)

**Протокол:**
1. Запускает `python scripts/score-analysis-report.py analysis-report.md`
2. Для непроверенных полей: вызывает get_metadata → верифицирует
3. Для непроверенных SQL: вызывает execute_query → валидирует
4. Выносит verdict: KEEP / IMPROVE / REVERT
5. Формирует `reviewer_feedback.json` с конкретным списком gaps
6. Обновляет `autoresearch.md` (history, dead ends)

**Формат вывода:**
```
METRIC: 73
GAPS: 3 (1 field_unverified, 1 pattern_missing, 1 query_invalid)
VERDICT: IMPROVE
REASON: Score 73 < target 85, 3 gaps found
```

### Comparator — каждые 3 итерации

**Инструменты:** Read (read-only), Git (diff)

**Протокол:**
1. Читает текущий ANALYSIS-REPORT.md (версия B)
2. `git show {baseline}:analysis-report.md` (версия A)
3. Слепое сравнение по 5 критериям (1-10):
   - Полнота покрытия требований
   - Корректность SQL запросов
   - Использование паттернов конфигурации
   - Практичность плана модификаций
   - Качество тест-плана

---

## Стоп-условия

| Условие | Действие |
|---------|----------|
| `analysis_score >= 85` | SUCCESS: target reached |
| 3 итерации без улучшения score | PLATEAU: manual review needed |
| `max_iterations` reached (default 7) | TIMEOUT: best result saved |
| Все gaps = 0 | PERFECT: все проверки пройдены |
| Executor не сделал коммит | SKIP: нечего улучшать |

---

## Workflow пользователя

```bash
# Вариант 1: Интерактивный (в Claude Code)
> /analyze-1c-task:research
> GKSTCPLK-1234: Добавить расчёт суммы НДС по маршрутным листам
# Claude: Executor → Reviewer → improve → Reviewer → ... → ANALYSIS-REPORT.md

# Вариант 2: Headless (скрипт)
.\scripts\analyze-1c-research.ps1 -TaskFile docs/tasks/GKSTCPLK-1234.md -TargetScore 85

# Вариант 3: Автономный (Ralph)
scripts\ralph.bat --template 1c-analysis --task docs/tasks/GKSTCPLK-1234.md --max-iterations 7
```

---

## Session Directory Structure

```
data/analyze-1c-research/{task-id}/
  task.md                    # Исходное ТЗ
  analysis-report.md         # Живой ANALYSIS-REPORT (обновляется каждую итерацию)
  autoresearch.md            # State: iteration, bestMetric, plateau, dead ends
  autoresearch.jsonl         # Лог итераций (JSON Lines)
  autoresearch-results.tsv   # Табличный лог
  reviewer_feedback.json     # Текущие gaps для Executor
  logs/
    executor_1.txt           # Полный вывод Executor итерации 1
    executor_2.txt
    reviewer_1.txt           # Полный вывод Reviewer итерации 1
    reviewer_2.txt
    comparator_3.txt         # Comparator (каждые 3 итерации)
```

---

## Target Metrics

| Metric | Current (v2.0) | Target (v3.0) | Improvement |
|--------|----------------|---------------|-------------|
| Analysis score | N/A (unmeasured) | >= 85/100 | Measurable |
| Fields verified | ~30% (manual) | >= 90% (auto) | 3x |
| Patterns from config | ~20% | >= 80% | 4x |
| SQL validated | 0% | >= 90% | New capability |
| Requirements covered | ~80% (subjective) | >= 95% (scored) | Objective |
| Iterations to quality | 1 (no iteration) | 3-5 (converges) | Self-improving |
| Persistence | None | Full session | Resume support |

---

## Risk & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| MCP tools unavailable (1C server down) | Scoring incomplete | Scorer graceful: skip MCP checks, reduce max score |
| Score doesn't correlate with real quality | False confidence | Phase 7: eval dataset with human-scored ground truth |
| Too many iterations (token burn) | Cost | Default max 7, plateau threshold 3 |
| Executor loops on same gap | Dead ends grow | Dead Ends list in autoresearch.md, Executor checks before acting |
| Large ТЗ exceeds context | Truncation | Executor reads task.md from file, not from prompt |
