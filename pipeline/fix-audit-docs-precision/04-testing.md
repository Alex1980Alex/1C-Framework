# Testing — fix-audit-docs-precision

## Регресс-тесты
[`tests/unit/test_audit_docs_precision.py`](../../tests/unit/test_audit_docs_precision.py) — **19 тестов, все PASS**.
- Fix 1: prefix `/v1` из конструктора, root `""`, `/{stem}` fallback (3).
- Fix 2: акроним-мангл 6 кейсов + guard `_r_a_g_ not in` (parametrized).
- Fix 3: токен-матч документирован/нет (2), кэш `_all_docs_text`/`_all_skills_text` идемпотентен (2).
- Fix 4: `_package_exports` parse/None/missing (3) + **инвариант guard'а** (rec ревьюера #1): каждый извлечённый memory/bsl класс из пакета с `__all__` обязан быть в `__all__` (2).
- E2E: `run_audit()` → 0 doc-gaps в endpoint/strategy/hook (1).

## Верификация
- `py_compile` OK, `ruff check --line-length 100` clean.
- **Саботаж:** старый мангл даёт `graph_r_a_g_auto` (запрещён тестом) → тест реально сцеплен с фиксом.
- **code-verify (bug-fix-validation):** ревьюер-субагент read-only → **[CODE-VERIFY-PASS]**, root cause подтверждён чтением реальных `app.py`/`__init__.py`; 3 не-блокирующих рекомендации (rec#1 закрыт тестом, rec#2 caveat в docstring, rec#3 комментарий к e2e).
- **Тайминг баннера:** аудит live 0.41с << 4с budget → SessionStart-баннер `audit-coverage-check.py` следующей сессии сам покажет 22+24.

## Остаточный сигнал (не баг)
22 doc + 24 skill = реальные «экспортированные-но-нигде-не-упомянутые» классы + хуки без упоминания в скиллах. Документировать их — решение пользователя, не задача этого фикса.
