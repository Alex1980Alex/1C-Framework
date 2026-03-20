# Roadmap: Delegation Learning System

**Date:** 2026-03-20 | **Status:** PLANNING

**Goal:** Превратить делегирование из ad hoc решений в самообучающуюся систему с outcome tracking, feedback loop и итеративным улучшением.

**Skill:** [delegation-classifier](../../.claude/skills/delegation-classifier/SKILL.md)

---

## Текущее состояние (broken)

| Компонент | Статус | Проблема |
|-----------|--------|----------|
| `z-ai-write-guard.py` | Работает для кода | `.md` exempt, `docs/` exempt → docs проходят мимо |
| `z-ai-delegation-enforcer.py` | Работает частично | "дорожная карта" не матчится ни одним сигналом |
| Outcome tracking | **Отсутствует** | Нет данных: что делегировали, какой результат, сколько rewrite |
| Learning loop | **Отсутствует** | Правила статичны, не улучшаются от опыта |
| Pre-task analysis | **Отсутствует** | Нет структурированного "pause and classify" |

---

## Итерации улучшений

### Iteration 1: Foundation (immediate)

**Цель:** Начать записывать outcomes, починить очевидные дыры в хуках.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 1.1 Создать `data/delegation-outcomes.jsonl` | Файл + формат записи | 5 min |
| 1.2 Fix `z-ai-write-guard.py`: `.md` > 50 lines в `docs/` не exempt | Патч хука | 30 min |
| 1.3 Fix `z-ai-delegation-enforcer.py`: добавить "дорожн", "roadmap", "план фаз" | Патч хука | 15 min |
| 1.4 Создать skill `delegation-classifier` | SKILL.md с матрицей + outcome format | DONE |
| 1.5 Зарегистрировать в `skill-router-config.json` | Bundle entry | 10 min |
| 1.6 Первая запись outcome (текущая сессия) | JSONL entry для roadmap-задачи | 5 min |

**Acceptance:** write guard блокирует `docs/*.md` > 50 строк, enforcer матчит "дорожная карта".

### Iteration 2: Outcome Tracking Hook (1 day)

**Цель:** Автоматическая запись outcomes при каждом Write > 15 строк.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 2.1 Hook `delegation-outcome-tracker.py` (PreToolUse:Write) | Записывает estimated fields в JSONL при крупных Write | 2h |
| 2.2 Интеграция с SessionState | Track: delegated=true если был llm_complete | 1h |
| 2.3 Stop hook addition: summary append | При Stop — дописать actual_lines, rewrite_pct | 1h |

**Логика:**
```
PreToolUse:Write fires → content > 15 lines?
  YES → record: {task_id, content_type, estimated_lines, delegated: session.has_llm_delegation()}
  NO → skip
```

**Проблема:** PostToolUse не работает (bug #6305). Используем PreToolUse (содержит content в tool_input) + Stop hook для финализации.

**Acceptance:** После каждого крупного Write в `data/delegation-outcomes.jsonl` появляется запись.

### Iteration 3: Learning Analysis Script (1 day)

**Цель:** Скрипт, который анализирует outcomes и предлагает adjustments.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 3.1 `scripts/analyze-delegation.py` | Читает outcomes, считает метрики, предлагает adjustments | 3h |
| 3.2 CLI dashboard | Таблица: accuracy, delegation rate, avg rewrite %, token savings | 1h |
| 3.3 Adjustment recommendations | "docs→Medium confirmed (N=12, avg rewrite 8%)" | 1h |

**Вывод скрипта:**
```
=== Delegation Health Report ===
Total outcomes: 47
Classification accuracy: 72% (target: 80%)
Delegation rate: 45% (target: 60%)
Avg rewrite %: 18% (target: < 25%)

=== Under-delegated (should have been delegated) ===
docs/roadmap/*.md: 8 cases, avg 150 lines, all classified Never → should be Medium
templates/*.md: 3 cases, avg 80 lines → should be Soft

=== Adjustments recommended ===
1. ADD to _MEDIUM_SIGNALS: "дорожн", "roadmap", "план фаз", "создай документ"
2. CHANGE: docs/ exempt → docs/ only exempt for < 50 lines
3. ADD override: docs/roadmap = Medium (confirmed by 8 outcomes)
```

**Acceptance:** Скрипт запускается, выводит actionable recommendations.

### Iteration 4: Auto-Adjustment (2 days)

**Цель:** Скрипт применяет рекомендации автоматически (с подтверждением).

| Task | Deliverable | Effort |
|------|-------------|--------|
| 4.1 Авто-патч `z-ai-delegation-enforcer.py` | Добавление keywords из recommendations | 3h |
| 4.2 Авто-обновление матрицы в `delegation-classifier/SKILL.md` | Override rules из outcomes | 2h |
| 4.3 Eval script: before/after comparison | Запуск delegation-enforcer с test prompts | 3h |

**Паттерн:** AutoResearch для delegation:
```
measure (outcomes) → analyze (script) → adjust (auto-patch) → verify (eval) → keep/revert
```

**Acceptance:** Adjustments применяются автоматически, eval показывает improvement.

### Iteration 5: Integration with AutoResearch (1 day)

**Цель:** Delegation quality как домен в AutoResearch v2.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 5.1 Recipe `delegation` в autoresearch.ps1 | Verify = analyze-delegation.py, scope = hooks/ + skills/ | 2h |
| 5.2 Template `delegation-quality.md` | Instructions для Executor | 1h |
| 5.3 Ralph template `delegation` | ralph.bat --template delegation | 1h |

**Acceptance:** `autoresearch.ps1 -Domain delegation` запускает цикл улучшений.

---

## Dependency Graph

```
Iter 1 (Foundation) ─────→ Iter 2 (Outcome Hook) ─→ Iter 3 (Analysis Script)
                                                              │
                                                              ▼
                                                     Iter 4 (Auto-Adjust)
                                                              │
                                                              ▼
                                                     Iter 5 (AutoResearch)
```

---

## Метрики успеха

| Metric | Current | After Iter 1 | After Iter 3 | After Iter 5 |
|--------|---------|-------------|-------------|-------------|
| Classification accuracy | ~50% (guess) | ~60% (fix obvious) | ~75% (from data) | ~85% (auto-tuned) |
| Delegation rate (>30 lines) | ~30% | ~45% (fix exempts) | ~55% (from patterns) | ~65% (optimized) |
| Outcome tracking | 0% | 100% (manual) | 100% (auto) | 100% (auto) |
| Token savings | ~20% | ~35% | ~50% | ~65% |
| Under-delegation rate | ~40% | ~25% | ~15% | ~10% |

---

## Ключевой принцип

**Каждая ошибка делегирования = один outcome record = данные для улучшения.**

Не "я буду лучше решать" (голословно), а "вот 47 записей, из них 8 docs classified Never→должно быть Medium, патч enforcer добавляет 3 keyword, eval подтверждает +12% accuracy" (измеримо).

Система учится не потому что мы "помним", а потому что outcomes записаны и анализируются.
