# Этап 4 — Тестирование

## Тест-план (из дизайна)
Stop-enforcer 6+ кейсов, инъектор, ruff/compile, валидность settings.json, code-verify.

## Результаты
- **ruff + compile:** clean (оба хука).
- **Инъектор:** prompt→systemMessage (PIPELINE-PROTOCOL) ✓; empty→None ✓; opt-out→None ✓.
- **Stop-enforcer (monkeypatched temp paths):**
  | # | кейс | ожид | факт |
  |---|------|------|------|
  | 1 | no-writes | allow | None ✓ |
  | 2 | writes/no-pipeline | block | block ✓ |
  | 3 | writes/pipeline-used | allow | None ✓ |
  | 4 | writes/pipeline-stale | block | block ✓ |
  | 5 | opt-out env | allow | None ✓ |
  | 6 | no session_id | allow | None ✓ |
  | 7 | aware-ts/naive (post-fix) | allow, no crash | None ✓ |
- **settings.json:** валиден; оба хука зарегистрированы (UPS + Stop).

## Вердикт code-verify
**PASS** (quality-review, субагент `a3e5c6a9b`). Deadlock-safety — главный риск — закрыт строго:
чистый диалог не блокируется (требует реального Write-сигнала); выход из блока всегда достижим
(создать pipeline-артефакт ИЛИ opt-out); любая аномалия → fail-OPEN (allow). Применены 2 правки
(naive/aware `_parse_dt`, точность комментария).

## Известное ограничение → ЗАКРЫТО (2026-06-14)
`MultiEdit`/`NotebookEdit` не имеют PreToolUse-матчера в settings.json → правки ими не логируются
→ enforcer их раньше не видел (недо-блок, безопасная сторона; репо использует Edit/Write).
**Закрыто** вторым сигналом `_git_session_edit` (git status + mtime >= старт сессии) — ловит
файл-чейндж любым инструментом, НЕ трогая settings.json (без побочки на чужие PreToolUse-хуки).
mtime-bound отсекает pre-session грязь; авто-артефакты (docs/wiki/log.md) в denylist. См. пайплайн
`pipeline/stop-enforcer-git-signal/` + регрессия `tests/unit/test_pipeline_protocol_git_signal.py`.

## Итог
Реализация соответствует дизайну и выбору пользователя (все задачи, hard сразу). Готово к проду
со след. сессии (settings читаются на старте). Активна эта задача — первый живой прогон пайплайна.
