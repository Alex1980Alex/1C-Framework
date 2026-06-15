# B′ хвост — Дизайн (self-approve)

## F-1.6
- **EDIT** `pipeline_1c_bridge.py` +`advance_test_done(file_path)`: имя==`.run-state.json` → json.load → `chain` непуст И все `status=="passed"` → resolve_current + 1С-guard → `mark_done(4)`. best-effort.
- **EDIT** `pipeline-1c-advance.py`: после `advance_for_artifact` ещё `advance_test_done(path)` (объединить вывод).
- **TEST:** chain all-passed→(4); частично-passed→None; не-runstate→None; best-effort.

## W
- **NEW** `scripts/tool_usage_report.py`:
  - читает `data/hook-invocations.jsonl` (tail), фильтр `correlationid==run_id` (или `--session`); агрег по `tool`: calls, errors (`outcome=='error' or error`), avg `elapsed_ms`.
  - `--task-dir <p>` → пишет `<p>/TOOL-USAGE-REPORT.md` (таблица + слот quality ✓/⚠/✗).
  - всегда → append строки в `data/tool-effectiveness.jsonl` (`{run_id, tool, calls, errors, avg_ms}`).
  - `--rollup` → читает `tool-effectiveness.jsonl` → cross-task per-tool {calls, error_pct, avg_ms} → stdout/markdown.
  - stdlib only; atomic-ish append.
- **NEW** `tests/unit/test_tool_usage_report.py`: агрег по фейковому jsonl (tmp), rollup.

## input-ingestion
- **EDIT** `pipeline_1c_bridge.py` +`classify_1c_task(prompt) -> dict{is_1c, jira, ttype, ask}`:
  - `is_1c` = JIRA `[A-Z]{2,}-\d+` ИЛИ (1С-сигнал: `гкс_`/CamelCase-кириллица/`Документ.`/`провед`/`реквизит` + таск-глагол `доработ|исправ|добав|создать|реализ`).
  - `ttype`: «исправ…ошибк» → T2; «не учт|тестирован…нов…функционал|доработать…не учтено» → T3; иначе T1.
  - `ask` = True если is_1c И нет JIRA И тип неоднозначен (T1 по умолчанию, но источник чат) → подсказать спросить.
- **NEW** `.claude/hooks/onec-task-input.py` (UPS): не слэш-команда + `classify_1c_task().is_1c` → `system_message` с протоколом V.6 (тип, ASK-если-ambiguous, folder `configuration/260304…/docs/<YYMMDD_slug>/`, prior-load для T3). best-effort, не блокирует.
- **EDIT** `settings.json`: UPS-группа → `onec-task-input.py` (timeout 5).
- **TEST:** classify_1c_task — T1/T2/T3 по примерам (2182/2177/2236), не-1С→is_1c False.

## DoD (общий)
pytest зелёный (unit collision-immune) · live: F-1.6 (.run-state passed→этап4), W (report+rollup на фейк-логе), input (хук на «исправь ошибку гкс_…» инъектит протокол) · ruff/compile/settings · без регрессий.
**Откат:** каждый пункт независим (см. 01).
