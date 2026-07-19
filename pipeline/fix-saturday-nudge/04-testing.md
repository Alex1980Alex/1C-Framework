# Testing — Saturday-nudge

## Юнит [`tests/unit/hooks/test_known_issue_saturday_nudge.py`](../../tests/unit/hooks/test_known_issue_saturday_nudge.py) — 12 PASS
- `active_nudges`: суббота+non-expired→tools, вс→[], expired→[], missing-date→[], multiple→sorted.
- `_load_known_issues`: `_doc`-строка отфильтрована, missing-file→{}.
- dedup: mark/detect per-day.
- `execute()` (code-verify рек.1): opt-out→None, active→HookOutput, deduped→None, no-tools→None.

## Верификация
- settings.json валиден, `py_compile` + ruff clean.
- Live: суббота→nudge, вс→тихо, после review_by→тихо; end-to-end (вс)→тихо.
- **code-verify** субагентом (quality-review, read-only) → **[CODE-VERIFY-PASS]**: graceful (двойная обёртка, SessionStart не падает), Saturday-gate+non-expired корректны и консистентны с analyze_tool_health, dedup атомарен, advisory-only. Рек.1 (execute-тесты) закрыта; рек.2/3 (HOOK_NAME nit, mkstemp) — не требуются.

## Опущено
Облачный (email) вариант — не выбран пользователем (по запросу можно завести `/schedule` routine).
