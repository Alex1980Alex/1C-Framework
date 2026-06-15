# 04 — Тестирование

## Unit
- `test_tool_usage_report.py`: **9 passed** (3 прежних aggregate/rollup/append_eff + 6 новых resolve_task_dir).
- `test_pipeline_state_colocation.py`: 9 passed (is_registered не задел).
- Широкий sweep `-k "pipeline or onec or tool_usage or hook"`: **206 passed, 14 skipped**.

## Smoke (изолированный tmp-реестр)
override→manual | --slug→task_dir | авто-1С(CURRENT registered)→task_dir | авто-generic→None | --slug-generic→pipeline/gen.
Живой: ruff + py_compile чисто.

## code-verify (субагент a00349718) — PASS
quality-review + behavior-preservation. `--task-dir`/`--rollup`/stdout сохранены; гард `is_registered` реально
предотвращает сюрприз-запись (подтверждено: generic CURRENT не в реестре → None). 2 рекомендации применены.

## DoD
- [x] TOOL-USAGE-REPORT.md резолвится через реестр (state_dir) — единый источник
- [x] backward compat --task-dir; авто-1С; generic-safe (None)
- [x] 9 unit + 206 sweep + code-verify PASS
- [x] цель: все файлы задачи (.pipeline-state.json / LOOPS.md / TOOL-USAGE-REPORT.md) в папке задачи через один источник
