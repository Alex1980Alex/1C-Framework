# B′ хвост — Кодирование (реализовано)

**F-1.6** — `pipeline_1c_bridge.advance_test_done(path)` (`.run-state.json` все `chain[].status==passed` → этап 4 done, guard+best-effort) + вызов в `pipeline-1c-advance.py` (`advance_for_artifact or advance_test_done`).

**W** — `scripts/tool_usage_report.py` (stdlib): `--run-id`/`--session` → агрег `data/hook-invocations.jsonl` по tool (calls/errors/avg_ms) → `TOOL-USAGE-REPORT.md` + append `data/tool-effectiveness.jsonl`; `--rollup` cross-task. (`data/` gitignored — store runtime.)

**input-ingestion** — `pipeline_1c_bridge.classify_1c_task(prompt)` (is_1c/jira/T1-T2-T3/ask) + `onec-task-input.py` (UPS) → инъектит протокол V.6 при 1С-задаче из чата (не на слэш) + регистрация в settings.json.

**Тесты:** +6 в `test_pipeline_1c_bridge.py` (advance_test_done, classify T1/T2/T3, non-1c/ask) + новый `test_tool_usage_report.py` (3). Все collision-immune. Откат: каждый пункт независим (см. 01).
