# 01 — Планирование: co-location состояния 1С-пайплайна в папке задачи

Полный план (одобрен пользователем через ExitPlanMode): `~/.claude/plans/synchronous-chasing-thunder.md`.

## Задача
Для 1С-задачи `.pipeline-state.json`, `LOOPS.md` и имена этапов (stages.artifact) перенести из generic
`pipeline/<slug>/` в ПАПКУ ЗАДАЧИ `configuration/<parent>/docs/<task>/` рядом с ANALYSIS-REPORT.md/
IMPLEMENTATION-PROGRESS.md/TOOL-USAGE-REPORT.md. Generic-поток (не-1С) — без изменений.

## Решения пользователя
- Этап 4 (Тестирование) → `.run-state.json`, в папке задачи.
- Все артефакты пайплайна co-located в папке задачи.

## Карта (Explore-агент): точка истины пути = `pipeline_state._state_path`; 3 независимых читателя
(pipeline-protocol-stop, onec-task-completion-stop, docs-change-enforcer skip); 1С-развилка в pipeline_1c_bridge.
