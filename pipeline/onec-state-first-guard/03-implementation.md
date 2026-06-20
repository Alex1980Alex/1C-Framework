# 03 — Реализация

- [`.claude/hooks/onec-state-first-guard.py`](../../.claude/hooks/onec-state-first-guard.py) — PreToolUse `Write|Edit|MultiEdit`; `_is_1c_file` (расширение + дерево конфигурации) + `_has_active_1c_pipeline` (title-префикс «1С-задача (» + stage<5, реестр `pipeline/_1c_index.json`) + advisory `system_message`. Opt-out `ONEC_STATE_FIRST_DISABLE=1`, graceful (`BaseHook.run`).
- [`tests/unit/test_onec_state_first_guard.py`](../../tests/unit/test_onec_state_first_guard.py) — 2 unit-теста (детект 1С-файла; детект активного pipeline).
- `settings.local.json` — регистрация в `PreToolUse` matcher `Write|Edit` рядом с `tdd-guard`.
- [ADR-026](../../.claude/skills/architecture-research/adr/026-state-first-1c-pipeline-enforcement.md) + research-cache + MEMORY.md (`feedback-1c-pipeline-state-first`).
