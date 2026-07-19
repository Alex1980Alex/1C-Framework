# Implementation — локальный Saturday-nudge (ADR-055 слой 2, напоминание)

Выбор пользователя: локальный вариант (не облачный routine). Генерация хука делегирована claude-cli-sonnet.

| Файл | Изменение |
|------|-----------|
| `.claude/hooks/known-issue-saturday-nudge-on-start.py` | **NEW** SessionStart-хук: по субботам (`weekday()==5`) сюрфейсит не-истёкшие known-issue из `known_issues.json`, once/day (STATE-dedup), opt-out `KNOWN_ISSUE_NUDGE_DISABLE=1` |
| `.claude/settings.json` | регистрация в SessionStart (после tool-health-banner, timeout 3) |
| ADR-055 + roadmap NEXT | нота про хук |

## Механика
Читает `data/reports/tools/known_issues.json` (reuse конфига ADR-055), фильтр `_review_expired` (истёкшие ведёт эскалация tool-health-banner, не nudge). Best-effort: срабатывает только если сессия открыта в субботу (пользователь принял это ограничение против облака).

## Live
Суббота 2026-07-25 → nudge [qa_generate, qa_run]; вс 2026-07-19 → тихо; после review_by (2026-09-05) → тихо. Сегодня (вс) end-to-end — тихо.
