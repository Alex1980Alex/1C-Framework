# 04 — Тестирование

- `pytest tests/unit/test_check_submodule_push_order.py -m unit` → **5 passed** (block / allow-on-remote / unchanged / not-initialized / noop — детерминированно через mock `_run`).
- `compileall` хелпера → **exit 0**; `ruff check` (хелпер + тест) → **All checks passed**.
- `adr/_index.json` после добавления ADR-027 → **VALID JSON**.
- `bash -n scripts/git_hooks/pre-push` → **syntax OK** (правка не сломала shell).
- Smoke: `check_submodule_push_order.py HEAD HEAD` (нет изменения gitlink) → exit 0; без аргументов → exit 0; block-путь покрыт unit-тестом (`_on_remote=""`).

**Вердикт: PASS.**
