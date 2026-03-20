---
name: delegation-classifier
description: >
  Классификация задач для делегирования на Z.AI. Предварительный анализ ПЕРЕД генерацией:
  оценка output size, выбор уровня (Soft/Medium/Hard/Never), трекинг outcomes,
  обучение на опыте. Триггеры: 'классифицировать задачу', 'delegation classifier',
  'что делегировать', 'оценка делегирования', 'delegation outcome', 'delegation feedback'.
  НЕ для самого процесса делегирования — используй z-ai-delegation.
version: 1.0.0
updated: 2026-03-20
tags: [delegation, classification, learning, token-economy, feedback-loop]
---

# Delegation Classifier — Классификация + Обучение на опыте

## Проблема

Текущий процесс делегирования — реактивный: хуки напоминают ПОСЛЕ начала работы.
Нет предварительного анализа, нет записи outcomes, нет обучения.

Результат: Opus генерирует 200+ строк docs/templates самостоятельно, потому что:
1. `.md` файлы exempt от write guard
2. `docs/` exempt от write guard
3. Решение "Never/Hard/Medium" принимается ad hoc, без структуры
4. Нет данных о прошлых delegation outcomes для обучения

## Алгоритм: PRE-TASK Analysis (обязательный)

```
ПЕРЕД любой генерацией > 15 строк:

1. ESTIMATE — оценить объём output
   - Сколько файлов?
   - Сколько строк на файл? (< 30 | 30-100 | 100-300 | 300+)
   - Тип контента? (code | docs | template | config | mixed)

2. CLASSIFY — определить уровень по матрице
   Входы: content_type × output_size × complexity
   Выход: Soft | Medium | Hard | Never

3. CHECK HISTORY — проверить outcomes для похожих задач
   Grep: data/delegation-outcomes.jsonl
   Вопрос: "Были ли задачи такого типа? Какой был rewrite %?"
   Если rewrite > 50% на похожей задаче → повысить уровень на 1

4. DECIDE — финальное решение
   - Never: делай сам (architecture, debug, < 30 lines)
   - Hard: Z.AI draft → thorough Opus review
   - Medium: Z.AI draft → accuracy review
   - Soft: Z.AI draft → формат check
   - ORCHESTRATOR: если 3+ файлов → decompose per file

5. RECORD START — записать в outcomes
   {"task_id": ..., "estimated_level": ..., "estimated_lines": ..., "started_at": ...}
```

## Матрица классификации

```
                    │ < 30 lines │ 30-100 lines │ 100-300 lines │ 300+ lines  │
────────────────────┼────────────┼──────────────┼───────────────┼─────────────┤
code (.py/.ts/.bsl) │ Never      │ Hard         │ Hard          │ Orchestrator│
docs (.md)          │ Never      │ Medium       │ Medium        │ Orchestrator│
template/config     │ Never      │ Soft         │ Medium        │ Orchestrator│
mixed (code+docs)   │ Never      │ Hard         │ Hard          │ Orchestrator│
```

### Override rules (исключения из матрицы)

| Условие | Override | Причина |
|---------|----------|---------|
| Architecture decision | → Never | Требует полный контекст проекта |
| Security-sensitive | → Never | Z.AI может пропустить уязвимости |
| Debugging/investigation | → Never | Интерактивный процесс |
| Bulk formatting (10+ items) | → Soft | Шаблонная работа |
| History: rewrite > 50% на похожем | → +1 level (Medium→Hard→Never) | Опыт показал низкое качество Z.AI |
| History: rewrite < 10% на похожем | → -1 level (Hard→Medium→Soft) | Опыт показал высокое качество Z.AI |

## Outcome Tracking

### Формат записи: `data/delegation-outcomes.jsonl`

```jsonl
{"ts":"2026-03-20T15:30:00Z","task_id":"roadmap-analyze-1c","task_type":"docs","content_type":"md","estimated_lines":200,"actual_lines":215,"files_count":8,"level":"Never","delegated":false,"rewrite_pct":0,"reason":"classified as architecture","correct_level":"Medium","lesson":"docs/roadmap are Medium, not Never — architecture is only INDEX.md"}
{"ts":"2026-03-20T16:00:00Z","task_id":"scorer-script","task_type":"code","content_type":"py","estimated_lines":80,"actual_lines":95,"files_count":1,"level":"Hard","delegated":true,"rewrite_pct":15,"reason":"standard parsing code","correct_level":"Hard","lesson":"parsing scripts delegate well with clear spec"}
```

### Поля outcome

| Поле | Тип | Описание |
|------|-----|----------|
| `ts` | ISO timestamp | Когда выполнялась задача |
| `task_id` | string | Короткий идентификатор задачи |
| `task_type` | enum | code, docs, template, config, mixed |
| `content_type` | string | Расширение файлов (.py, .md, .ps1, ...) |
| `estimated_lines` | int | Оценка до выполнения |
| `actual_lines` | int | Фактические строки (после) |
| `files_count` | int | Количество файлов |
| `level` | enum | Soft, Medium, Hard, Never |
| `delegated` | bool | Было ли делегировано на Z.AI? |
| `rewrite_pct` | int | % переписывания Opus после Z.AI (0 если не делегировано) |
| `reason` | string | Почему выбран этот уровень |
| `correct_level` | enum | Какой уровень был бы правильным (ретроспективно) |
| `lesson` | string | Что узнали (для обновления правил) |

### Когда записывать

1. **START** — после PRE-TASK Analysis (estimated fields)
2. **END** — после завершения задачи (actual fields + rewrite_pct + lesson)
3. **REVIEW** — при периодическом анализе (correct_level, если отличается)

## Периодический анализ (Learning Loop)

### Триггер: каждые 20 записей в outcomes или по запросу `/delegation-review`

### Алгоритм

```
1. LOAD outcomes (last 50 records)

2. COMPUTE accuracy:
   accuracy = count(level == correct_level) / total

3. FIND patterns:
   - Группировка по task_type: avg rewrite_pct per type
   - Группировка по content_type: avg rewrite_pct per extension
   - Under-delegated: delegated=false AND correct_level != "Never"
   - Over-delegated: delegated=true AND rewrite_pct > 50%

4. GENERATE adjustments:
   - Если docs avg rewrite < 20% → можно понизить (Hard→Medium)
   - Если code avg rewrite > 40% → повысить (Medium→Hard)
   - Если паттерн "X всегда Medium" → добавить в fast-path

5. UPDATE:
   - Обновить матрицу в SKILL.md (если стабильный паттерн из 5+ cases)
   - Добавить override rule
   - Обновить keywords в z-ai-delegation-enforcer.py (если miss)
   - Записать adjustment в MEMORY.md
```

### Метрики здоровья делегирования

| Метрика | Target | Как считать |
|---------|--------|-------------|
| Classification accuracy | > 80% | level == correct_level |
| Delegation rate | > 60% | delegated / total (для tasks > 30 lines) |
| Avg rewrite % | < 25% | mean(rewrite_pct) where delegated=true |
| Token savings estimate | > 70% | (delegated_lines / total_lines) * (1 - rewrite_pct/100) |
| Under-delegation rate | < 15% | not delegated AND correct != Never |

## Интеграция с существующими хуками

### z-ai-write-guard.py — FIX NEEDED

**Проблема:** `.md` в `_SKIP_EXTENSIONS`, `docs/` в `_EXEMPT_PREFIXES` → все docs проходят мимо.

**Fix:** Добавить content-based check для `.md` файлов:
```python
# Не пропускать .md если > 50 строк И не в .claude/
if ext == ".md" and line_count > 50:
    if not any(fp.startswith(p) for p in [".claude/", "data/"]):
        # Проверить delegation, не пропускать слепо
        ...
```

### z-ai-delegation-enforcer.py — EXTEND SIGNALS

**Проблема:** "создай дорожную карту" не матчится.

**Fix:** Добавить сигналы:
```python
_MEDIUM_SIGNALS += [
    "дорожн", "roadmap", "план реализаци",
    "создай документ", "напиши документ",
    "создай roadmap", "план фаз",
]

_ORCHESTRATOR_SIGNALS += [
    "по фазам", "несколько фаз", "для каждой фазы",
]
```

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| Классифицировать всё как Never | "Я лучше Z.AI" → потеря 80% токенов | Доверяй матрице, проверяй outcomes |
| Не записывать outcomes | Нет данных для обучения | ВСЕГДА записывай start + end |
| Делегировать architecture | Z.AI не знает контекст | Never для архитектуры, Medium для её документирования |
| Не делать periodic review | Правила устаревают | Каждые 20 задач: анализ + adjustment |
| Менять матрицу по 1 case | Шум, нестабильность | Минимум 5 cases с паттерном |
| docs = Never | Docs — идеальный кандидат для Medium | Override: docs 30+ lines = Medium |
