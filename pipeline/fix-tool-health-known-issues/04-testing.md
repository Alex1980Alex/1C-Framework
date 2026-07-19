# Testing — known-issues слой (ADR-055)

## Юнит — [`tests/unit/test_tool_health_known_issues.py`](../../tests/unit/test_tool_health_known_issues.py), 14 PASS
- `_review_expired`: future→False, past/missing/None/непарсимая→True (fail-closed) — 5 кейсов.
- `_apply_known_issues`: broken→known-issue (+underlying+reason), healthy→recovered(xpass), degraded/ineffective→known-issue, expired→оставляет verdict, missing-date→не подавляет, config-absent(`{}`)→noop, tool-absent→skip.
- реестр: known-issue в `_VERDICT_ORDER`+`_VERDICT_MARK` (защита рендера от KeyError).
- тренд (рек.1): broken→known-issue НЕ в `healed_tools`, broken→healthy — в.

## Верификация
- `py_compile` + `ruff --line-length 100` — clean (4 файла).
- **Live-прогон** `analyze_tool_health.py`: broken 2→0, known-issue 2; qa_* не в `alerts`; баннер (синтетический SessionStart) → «🔕 подавлено known-issue (2)», без «✅ вылечено», без эскалации.
- **code-verify** (quality+bug-fix, субагент read-only) → **[CODE-VERIFY-PASS]**: escalation-suppression / fail-soft / fail-closed / xpass / healed-fix / регрессия — все PASS. Рек.1 (тренд) закрыта + покрыта тестом. Рек.2 (отдельная 🔕-секция в _latest.md) — опционально, пропущено (тулы видны в общей таблице).
- Регресс audit: 22 теста `test_audit_docs_precision.py` зелёные (не задеты).

## Задачи
2 tool-health mandatory-задачи (qa_run/qa_generate) закрыты с дисп. ADR-055.
