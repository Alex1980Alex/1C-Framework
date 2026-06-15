# F-2 — Кодирование (реализовано)

- **EDIT** `shared/pipeline_1c_bridge.py` — `gate_1c_implement(prompt) -> {ok,hard,reason}` (derive_slug → load → 1С-guard по title → этап 2 done+approved? best-effort → ok).
- **EDIT** `.claude/hooks/pipeline-gate.py` — ветка `cmd == "implement-1c-task"` → `gate_1c_implement` → `block` если hard (opt-out `PIPELINE_GATE_DISABLE` работает и тут).
- **EDIT** `tests/unit/test_pipeline_1c_bridge.py` — +2 collision-immune (no-pipeline→ok, best-effort→ok).

Generic pl-* гейт не тронут. best-effort (сбой→ok, не блокируем). Откат = revert ветки + функция + тесты.
