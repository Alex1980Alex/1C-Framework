# 02 — Дизайн

## Механизм (реестр + relocate-on-artifact + 1С-профиль)
- **Реестр** `pipeline/_1c_index.json` = `{slug: task_dir(rel-POSIX)}`. `_state_path` → `state_dir(slug)` (реестр→task_dir, иначе generic).
- **STAGES_1C** профиль (артефакты = реальные файлы), выбор по `is_1c(title)` в `init_task`; `task_dir` → register сразу.
- **relocate-on-artifact**: `relocate_1c(slug, task_dir)` переносит generic→папку задачи (read из current/generic → register → _save → удалить generic); идемпотентно + сходимость при частичном краше. Зов из `advance_for_artifact` (task_dir = dirname артефакта).
- **3 читателя** через единый `iter_states()` (generic glob + реестр) с graceful-fallback.
- `docs-change-enforcer` — БЕЗ правки (substring `configuration/` + `.pipeline-state.json` уже покрывают).

## Риски отстреляны: CURRENT (slug, не путь) не задет; relocate идемпотентен+сходится; submodule consistent (ANALYSIS-REPORT уже там); атомарность tmp+replace; glob-гонки дедуп по slug; backward-compat (реестр пуст для generic).

## Approved: пользователь (ExitPlanMode). Маппинг этапа 4 = `.run-state.json` в папке задачи (AskUserQuestion).
