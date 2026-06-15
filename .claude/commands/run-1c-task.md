---
description: AUTO-прогон 1С-задачи целиком (analyze→implement→test) БЕЗ паузы на ревью первого этапа. Вход — JIRA-код / описание из чата / путь к папке ТЗ (определяется автоматически). Для ревью ANALYSIS-REPORT перед кодом используй гейтованный поток /analyze-1c-task → /implement-1c-task.
---

# /run-1c-task — AUTO-прогон 1С-задачи

Прогнать задачу 1С целиком в AUTO-режиме, используя **skill run-1c-task**.

## Вход:
$ARGUMENTS

(JIRA-код, описание из чата, ИЛИ путь к папке ТЗ — определится автоматически через `resolve_task_input`.)

---

## Инструкция

**Используй skill run-1c-task** — оркестратор 4 этапов generic-пайплайна БЕЗ паузы на ревью первого этапа:
analyze (`analyze-1c-task-v2`) → **авто-approve** → implement (`implement-1c-task`) → test (`run-1c-tests`).

Skill определяет:
- детект входа (`resolve_task_input`: folder / jira / chat) → slug + источник;
- последовательный прогон методик analyze→implement→test (методики НЕ дублируются — скилл их оркестрирует);
- **авто-approve** дизайна после анализа (главное отличие от гейтованного потока — нет паузы на человека);
- хард-правило: критическая ошибка / неоднозначность на любом этапе → **СТОП и вопрос** (AUTO ≠ игнор блокеров).

> **Нужен ревью ANALYSIS-REPORT перед кодом?** Используй гейтованный поток:
> `/analyze-1c-task <задача>` → (правки отчёта) → `/implement-1c-task <отчёт>`.

## Результат
- ANALYSIS-REPORT.md + IMPLEMENTATION-PROGRESS.md + зелёные BDD-тесты (этап 4) + TOOL-USAGE-REPORT.md (W).
- pipeline-state `pipeline/<slug>/`: все 4 этапа `done`, дизайн `approved` (авто).
