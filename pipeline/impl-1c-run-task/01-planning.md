# /run-1c-task — Планирование (этап 1)

## Запрос пользователя
Доработки к B′: для 1С-задачи добавить AUTO-режим (полный прогон без паузы на ревью).
Решения (AskUserQuestion): **одна команда `/run-1c-task <вход>`**, объём **analyze→implement→test**.

## Что есть сейчас (B′)
- Гейтованный поток: `/analyze-1c-task` → [пауза/ревью/approve] → `/implement-1c-task`.
- Гейт F-2 (`gate_1c_implement`) хард-блокирует implement до approve дизайна (этап 2).
- `pipeline_1c_bridge.py`: derive_slug, ensure_pipeline_1c, advance_for_artifact, gate_1c_implement,
  advance_test_done, classify_1c_task.

## Чего не хватает
- Нет способа прогнать всю задачу без паузы (для доверенных/готовых-ТЗ случаев).
- Нет единой точки входа «прогнать 1С-задачу целиком».

## Сигналы (verified)
- Гейтованный поток построен на slash-командах `/analyze-1c-task` + `/implement-1c-task` (preflight-хуки).
- Skill-делегирование (оркестратор зовёт скиллы, НЕ переинвокит slash) → гейт F-2 (UPS на /implement-1c-task)
  в AUTO-потоке НЕ срабатывает; значит approve в AUTO нужен только для консистентности state, не для обхода блока.
- `pipeline_state` CLI: init / done <slug> N / approve <slug> — все есть (stdlib).

## Объём
1 helper (`resolve_task_input`) + 1 команда (`run-1c-task.md`) + 1 скилл (`run-1c-task/SKILL.md`) + тесты.
Методику 1С (analyze-1c-task-v2 / implement-1c-task) НЕ трогаем — только оркестрация.
