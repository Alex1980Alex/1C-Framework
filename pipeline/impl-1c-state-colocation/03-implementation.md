# 03 — Кодирование

## Изменённые файлы
| Файл | Что |
|---|---|
| `.claude/hooks/shared/pipeline_state.py` | реестр (`_read/_write_registry`, `_rel_to_root`, `register_1c`, `state_dir`, `relocate_1c`, `iter_states`, `is_1c`); `STAGES_1C`; `_state_path`→`state_dir`; `init_task(task_dir=)`+профиль по title; `artifact_path`/`render_status`→`state_dir`; CLI `--task-dir`; `_slugify` в публичных функциях |
| `.claude/hooks/shared/pipeline_1c_bridge.py` | relocate-on-artifact в `advance_for_artifact`; `ensure_pipeline_1c(task_dir=)` |
| `.claude/hooks/pipeline-protocol-stop.py` | `_iter_all_states`/`_pipeline_used_since` через `iter_states()` (graceful fallback) |
| `.claude/hooks/onec-task-completion-stop.py` | `_iter_1c_pipelines` через `iter_states()`; `_write_loops_report`→`state_dir` (бонус: чинит H3 false-negative) |
| `.claude/skills/run-1c-task/SKILL.md` | init `--task-dir` при kind=folder |
| `.claude/commands/run-1c-tests.md` | резолв `.run-state.json` в папку задачи для 1С |

## Тесты
- `tests/unit/test_pipeline_state_colocation.py` (9, новый): generic не задет, 1С-профиль, state_dir, relocate (+ сходимость при крэше), iter_states, render_status, is_1c.
- `tests/unit/test_onec_task_completion_stop.py`: helper `_isolate_pipeline` (collision-immune изоляция iter_states).

## Reviewer-fixes (code-verify PASS a2a90266): честная сходимость relocate (read из generic на retry) + `_slugify` в register/state_dir/relocate (чинит латентный case-mismatch JIRA-slug).
