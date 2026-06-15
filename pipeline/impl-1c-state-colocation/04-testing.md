# 04 — Тестирование

## Unit
- `test_pipeline_state_colocation.py`: **9 passed** (вкл. `test_relocate_convergence_partial_crash`).
- Связанные: `test_pipeline_1c_bridge.py` + `test_onec_task_completion_stop.py` — зелёные.
- Широкий прогон `-m unit -k "pipeline or onec or hook or import_smoke or git_hooks"`: **680 passed, 14 skipped** (после фикса коллизии src/shared в helper'е).

## Изолированный smoke (tmp-реестр)
- generic vs 1С-профиль; state_dir реестр vs generic; relocate-on-artifact (generic→task_dir, generic удалён, идемпотентно, mark_done в папке задачи); iter_states (оба).

## E2E миграция gkstcplk-2567 (прод)
- `.pipeline-state.json` + `LOOPS.md` перенесены в папку задачи рядом с ANALYSIS-REPORT/IMPLEMENTATION-PROGRESS/TOOL-USAGE-REPORT.
- stages = реальные файлы (ANALYSIS-REPORT.md ×2 / IMPLEMENTATION-PROGRESS.md / .run-state.json).
- `pipeline/gkstcplk-2567/` удалён; реестр `pipeline/_1c_index.json` заполнен.
- H3 false-negative исправлен: LOOPS.md «W per-task: есть» (state_dir резолвит TOOL-USAGE-REPORT.md в папке задачи).

## Хуки preflight (синтетический Stop)
- `pipeline-protocol-stop`, `onec-task-completion-stop`, `git-commit-enforcer`, `docs-change-enforcer` → **ok** (видят 1С-state в папке задачи через реестр, не ложно-блокируют).

## code-verify (субагент a2a90266) — PASS
- quality-review + behavior-preservation. Generic-поток строго сохранён, 6 инвариантов держатся, anti-false-block не нарушен.
- 2 minor-рекомендации применены (сходимость relocate + _slugify) + покрыты тестом.

## DoD
- [x] Состояние/LOOPS/stages 1С → папка задачи; этап 4 = `.run-state.json` там же
- [x] Generic-поток не задет (тест + reviewer)
- [x] Миграция gkstcplk-2567 + 9 unit + 680 sweep + code-verify PASS
