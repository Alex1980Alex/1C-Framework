# 04 — Тестирование

- `pytest tests/unit/test_pipeline_1c_bridge.py -m unit` → **87 passed** (было 80; +7: C1 actionless ask_action ×2, C4 veto-able/immune ×2, C2/C3 resolve_active ×3 + gate-converge/block ×2).
- `ruff check` + `compileall` на каждом шаге → **clean / exit 0**.
- **code-verify reviewer** (bug-fix-validation) для C2/C3 → **PASS**: root-cause устранён (единая идентификация), JIRA-поток цел, регрессия (implement-без-analyze → блок) корректна, best-effort/edge цел, тесты минимальны.
- onec-task-input smoke: standalone-вывод пуст для ВСЕХ ветвей (auto-ветвь — неизменённый код — тоже) → артефакт standalone-вызова, не регресс правки.

**Вердикт: PASS.**
