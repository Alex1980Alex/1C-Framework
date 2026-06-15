# F-1.5 — Кодирование (реализовано)

- **EDIT** [`shared/pipeline_1c_bridge.py`](../../.claude/hooks/shared/pipeline_1c_bridge.py) — `_ARTIFACT_STAGES` + `advance_for_artifact(path)` (ANALYSIS-REPORT→1,2 · IMPLEMENTATION-PROGRESS→3; guard по title-метке F-1; best-effort; идемпотентно).
- **NEW** [`.claude/hooks/pipeline-1c-advance.py`](../../.claude/hooks/pipeline-1c-advance.py) — PostToolUse (Write|Edit), best-effort, не блокирует.
- **EDIT** `.claude/settings.json` — PostToolUse-группа `matcher:"Write|Edit"` → хук (timeout 5).
- **EDIT** [`tests/unit/test_pipeline_1c_bridge.py`](../../tests/unit/test_pipeline_1c_bridge.py) — +3 advance-теста (collision-immune: regex-маппинг, non-artifact→None, best-effort).

Инварианты соблюдены: guard режет не-1С пайплайны (live-доказано), best-effort, идемпотентно, PostToolUse не блокирует. Откат = settings-группа + хук + функция + тесты.
