# Implementation — known-issues слой tool-health (ADR-055)

Генерация кода делегирована claude-cli-sonnet (Token Economy), ревью Opus.

| Файл | Изменение |
|------|-----------|
| `data/reports/tools/known_issues.json` | **NEW** config `{tool:{reason,ref,review_by}}` + qa_run/qa_generate (review_by 2026-08-31) |
| `scripts/analyze_tool_health.py` | вердикт `known-issue` (🔕) в `_VERDICT_ORDER`/`_VERDICT_MARK`; `_load_known_issues`/`_review_expired` (fail-closed)/`_apply_known_issues` (overlay после `apply_infra_to_tools`); sidecar `known_issues[]`+`recovered_known_issues[]` |
| `.claude/hooks/tool-health-banner-on-start.py` | чтение `known_issues`/`recovered`; `recovered` ломает silence; строки баннера «✅ …сними suppression» / «🔕 подавлено»; healed-fix (known-issue в `current_active` → не «вылечено») |
| `scripts/tool_verdict_history.py` | тренд: broken→known-issue НЕ «вылечено» (code-verify рек.1, симметрия баннеру) |

## Механика (whack-a-mole убран)
overlay `verdict→known-issue` → sidecar `alerts` фильтр `(broken,degraded)` его исключает → баннерный `broken` пуст → `_escalate_broken` не зовётся → mandatory-задача не заводится. Виден: 🔕 в отчёте-таблице + строка баннера.

## Live-верификация
`counts: broken 2→0, known-issue 2`; `alerts` без qa_*; баннер: «🔕 подавлено known-issue (2): qa_run, qa_generate»; эскалации нет. xpass/expiry — юнит-покрыты.

## Отложено (отдельная задача)
Реальный фикс qa_run (binary-путь / `infra_error`→junit в `mcp_1c_stdio_launcher.py`) + upstream issue (getThickClientInfo). Зарегистрировано в roadmap 260718 (нота ADR-055). Снять known-issue после закрытия.
