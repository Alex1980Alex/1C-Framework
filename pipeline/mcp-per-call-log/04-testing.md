# 04 Тестирование — P2.3

- `tests/unit/test_mcp_call_log.py` — 11 unit (success/soft-error/exception-reraise/opt-out/
  rotation/fail-soft/extra/truncation/wrap-shape/idempotency). Все PASS.
- ruff чистый по всем 4 файлам.
- Функциональный smoke в реальном venv сабмодуля: `from src.py_server.main` резолвится (нет регрессии),
  обёртка логирует ok/isError, идемпотентна.
- code-verify Уровень 2 (quality-review, read-only reviewer): PASS.
