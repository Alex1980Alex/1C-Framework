# 04 — Тестирование

- `pytest tests/unit/test_onec_state_first_guard.py -m unit` → **2 passed** (детект 1С-файла + детект активного pipeline, детерминированно через monkeypatch).
- `compileall` хука → **exit 0**; `ruff check` (хук + тест) → **All checks passed**.
- `settings.local.json` после регистрации в PreToolUse → **VALID JSON**.
- Smoke (synthetic PreToolUse): non-1С → silent ✓; opt-out (`ONEC_STATE_FIRST_DISABLE=1`) → silent ✓; 1С-файл → silent при наличии активного 1С-pipeline (корректно — state-first соблюдён; nudge-путь покрыт unit-тестом `_has_active_1c_pipeline=False`).

**Вердикт: PASS.**
