# F-1.5 — Планирование: stage-advancement 1С-пайплайна по артефактам

**Срез:** B′ F-1.5 (продолжение F-1). **Решение:** ADR-019 B′ (мост через хуки).

## Цель
F-1 завёл pipeline-state (этап 1). F-1.5 — **двигает этапы по факту**: запись `ANALYSIS-REPORT` → этапы 1+2 done
(Планирование+Дизайн, analyze Фазы 1–3/4–5); `IMPLEMENTATION-PROGRESS` → этап 3 done (Кодирование). Состояние
отражает реальный прогресс, а не «застыло на 1».

## Подход (тот же B′ — хук, методику не трогаем)
**Новый PostToolUse-хук** `pipeline-1c-advance` (matcher `Write|Edit`): на запись 1С-артефакта резолвит CURRENT
1С-пайплайн и `mark_done` соответствующих этапов. PostToolUse — рабочий механизм (protocol.py: «confirmed 2026-03-29»;
фреймворк уже юзает posttooluse-auto-git-save и др.).

## Точки интеграции (переиспускаем)
- `HookInput.tool_name`/`.tool_input.file_path` (PostToolUse payload).
- `pipeline_state.resolve_current()` (CURRENT, ставит F-1 ensure) + `load()` + `mark_done()`.
- **Guard 1С-пайплайна:** `state["title"].startswith("1С-задача")` — метка, которую F-1 `ensure_pipeline_1c` уже пишет
  в title. → не двигаем чужой (framework-dev) пайплайн при случайной записи.

## Граница F-1.5
- **В:** advance этапов 1,2 (ANALYSIS-REPORT) + 3 (IMPLEMENTATION-PROGRESS).
- **НЕ в:** этап 4 (Тестирование) — двигается при `/run-1c-tests`/тест-артефакте (F-1.6/тест-проводка); гейт G4 = F-2;
  approve этапа 2 — действие человека (не авто).

## Инварианты / риски
- Behavior-preserving: хук трогает ТОЛЬКО 1С-пайплайн (guard по title); не-1С Write игнор.
- best-effort: `advance_for_artifact` в try/except → None; PostToolUse не блокирует.
- Не понижать: `mark_done` только если этап ещё не done (идемпотентно).
- Откат: снять PostToolUse-запись из settings.json + удалить хук + `advance_for_artifact`.

## DoD
unit: advance_for_artifact матчит ANALYSIS-REPORT→(1,2)/IMPLEMENTATION-PROGRESS→(3), не-артефакт→None, guard режет не-1С;
live: запись ANALYSIS-REPORT в 1С-CURRENT-пайплайне двигает этапы; не-1С пайплайн не затронут; ruff/compile; без регрессий.
