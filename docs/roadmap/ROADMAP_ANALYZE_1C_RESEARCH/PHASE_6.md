# Phase 6: Skill Update v3.0

**Priority:** MEDIUM | **Effort:** 0.5 day | **Depends on:** Phase 4 | **Effect:** User interface

**Goal:** Обновить `analyze-1c-task-v2/SKILL.md` до v3.0 с командой `:research` и интеграцией AutoResearch.

---

## Changes to SKILL.md

### 6.1 Frontmatter update

```yaml
---
name: analyze-1c-task-v2
description: >
  5-фазная методология анализа задачи 1С:Предприятие.
  Требования -> Объекты -> Алгоритм -> План -> Верификация.
  v3.0: Итеративный режим с 3 агентами (Executor + Reviewer + Comparator).
version: 3.0.0
updated: 2026-03-XX
tags: [1c, analysis, bsl, configuration, methodology, autoresearch, three-agent]
ultrathink: true
commands:
  - /analyze-1c-task-v2             # Однопроходный анализ
  - /analyze-1c-task:research       # Итеративный с 3 агентами + scoring
---
```

### 6.2 New section: AutoResearch Integration

```markdown
## Итеративный режим: /analyze-1c-task:research

### Принцип
Executor (фазы 1-4) → Reviewer (фаза 5 + scoring) → fix gaps → repeat.
Три агента с разделением обязанностей (как AutoResearch v2).

### Метрика: Analysis Quality Score (0-100)
| Компонент | Вес | Источник |
|-----------|-----|----------|
| Requirements coverage | 30% | Маркеры [REQ-N] в плане |
| Fields verified | 25% | Маркеры ✓ get_metadata |
| Patterns found | 20% | Маркеры ✓ pattern |
| SQL validated | 15% | Маркеры ✓ execute_query |
| Open questions | 10% | Секция 6 |

### Стоп-условия
- Score >= 85 (target)
- 3 итерации без улучшения (plateau)
- Max 7 итераций
- Все gaps = 0

### Запуск
- Интерактивный: `/analyze-1c-task:research` в Claude Code
- Headless: `.\scripts\analyze-1c-research.ps1 -TaskFile task.md`
- Автономный: `scripts\ralph.bat --template 1c-analysis --task task.md`
```

### 6.3 Updated output format

Добавить маркеры в шаблон ANALYSIS-REPORT.md:

```markdown
## 2. Задействованные объекты конфигурации
### 2.1 Основные объекты (требуют изменения)
- Документ.МаршрутныйЛист — поле СуммаНДС ✓ get_metadata
- РегистрНакопления.ДвиженияТранспорта — поле Сумма ✗ не проверено

## 4. План изменений
### Точка модификации 1: Добавить реквизит [REQ-1]
- Образец: Документ.ЗаказНаПеревозку.СуммаНДС ✓ pattern
- SQL: ```sql ВЫБРАТЬ ... ``` ✓ execute_query

## Метаданные анализа
- Score: 87/100
- Iterations: 4
- Session: data/analyze-1c-research/GKSTCPLK-1234/
```

### 6.4 Skill router config

Update `skill-router-config.json` — add keywords for `:research` command:

```json
{
  "bundle": "1c-analysis",
  "keywords": ["analyze-1c-task:research", "итеративный анализ 1С", "трёхагентный анализ"],
  "skills": ["analyze-1c-task-v2"]
}
```

---

## Deliverables

- [ ] Updated `analyze-1c-task-v2/SKILL.md` v3.0
- [ ] Updated ANALYSIS-REPORT.md template with markers
- [ ] Updated `skill-router-config.json` (if needed)
- [ ] Updated MEMORY.md reference

## Acceptance Criteria

1. `/analyze-1c-task:research` recognized by skill system
2. SKILL.md documents both single-pass and iterative modes
3. Marker format (✓/✗) documented for Executor and Scorer
4. Output format includes metadata section with score and iteration count
