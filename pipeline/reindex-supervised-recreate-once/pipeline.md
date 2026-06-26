# Пайплайн: `--recreate-once` для `reindex_supervised.py`

Тип: tooling / infra (Python). Medium (script + test). Запрошено пользователем как отдельная правка с code-verify.

## 1. План (Планирование)
Супервизор устойчивого reindex ([`reindex_supervised.py`](../../scripts/reindex_supervised.py)) умел только resume (`--skip-indexed`) → чистый rebuild коллекции (дроп дублей) приходилось делать ручным дропом. Добавить флаг `--recreate-once`.

## 2. Дизайн
Рассмотрены 2 варианта (после code-review):
- **Вариант 1** (первичный): дочерний `--recreate` на первом прогоне лестницы + watchdog `!=` (дроп = активность). Code-review нашёл **edge D**: краш/segfault дочернего в `model_load` ДО `create_collection` (стр.1915) → эскалация уходит в resume против НЕдропнутой коллекции → молча оставляет дубли, рапортует успех (документированный segfault torch2.10 попадает в это окно).
- **Вариант 2 (принят)**: дроп делает САМ супервизор один раз ДО лестницы (детерминированно, не зависит от дочернего); при неудаче дропа — **прерывание** (return 1), не resume. Устраняет edge D и race целиком. `_build_cmd`/`run_attempt` остаются оригинальными (watchdog `>`).

## 3. Реализация
- [`scripts/reindex_supervised.py`](../../scripts/reindex_supervised.py): хелпер `_drop_collection` (Qdrant DELETE, 404=успех, реальный сбой→False), `--recreate-once` arg, дроп-блок до лестницы с abort-on-failure, `main(argv)` для тестопригодности, `import urllib.error`, docstring-нота.
- [`tests/unit/test_reindex_supervised.py`](../../tests/unit/test_reindex_supervised.py): 5 unit-тестов (resume-cmd, passthrough, drop-then-run, **abort-if-drop-fails**, no-flag-no-drop).

## 4. Тест
ruff `All checks passed`, `py_compile` OK, **5/5 unit** (`-m unit`, CI=1). Code-verify Level-2 ревьюер: Вариант-1 → PARTIAL/[FAIL] (edge D) → Вариант-2 фикс → ре-верификация (ожидается PASS).
