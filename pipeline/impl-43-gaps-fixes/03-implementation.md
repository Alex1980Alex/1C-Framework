# 03 — Кодирование

## Изменённые файлы
| Файл | Фикс | Суть |
|---|---|---|
| `.claude/hooks/onec-task-completion-stop.py` | H5 + H2 | `_iter_1c_pipelines` / `_onec_pipeline_updated` / `_incomplete_onec_pipeline` (заменили `_onec_task_this_session`); `config_edit` в `_collect_signals`; `_write_loops_report`; перестроен `main()` |
| `.claude/hooks/shared/pipeline_1c_bridge.py` | H7 | `_ARTIFACT_MIN_CHARS=200` + `_artifact_has_content`; guard в `advance_for_artifact` |
| `scripts/git_post_commit_reindex.py` | call-graph | константы `CALL_GRAPH_*`; `_call_graph_stale` / `_touch_call_graph_sentinel` / `_spawn_call_graph`; проводка в `main()` (троттл) |
| `.claude/skills/run-1c-task/SKILL.md` | H6 | этап 2.4 preflight ТЗ + ссылка на LOOPS.md в финале |
| `docs/.../43.5_СКВОЗНАЯ_КАРТА.md` | все | закрытие H1–H7, фикс ссылок на удалённые `memory/research-protocol-stop` |
| `docs/.../43.3_МАРШРУТИЗАЦИЯ...md` | H1 | tool-effectiveness = отчётный (убран ложный «сигнал в skill-learning») |

## Тесты
| Файл | Добавлено |
|---|---|
| `tests/unit/test_onec_task_completion_stop.py` | `config_edit` в ожидаемых dict; переименованы предикат-тесты на `_onec_pipeline_updated`; `test_incomplete_onec_pipeline_h5` |
| `tests/unit/test_pipeline_1c_bridge.py` | `test_advance_h7_content_guard`; обновлён `test_advance_best_effort` (реальный файл >порог) |

## Граничные проверки
- Все 4 фикса graceful (exception → exit 0 / return None / pass).
- `code-skill-enforcer` сматчил `SKILL (` в таблице LOOPS → переписано в `SKILL-методика 1С`.
- ruff + py_compile чисто по всем .py.
