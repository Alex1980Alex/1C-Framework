# 01 — Планирование: Skills-system hardening

## Задача
5 пунктов улучшения системы наполнения скиллов (по итогам живого аудита):
1. Разгрести pending-очередь skill-learning (78 записей, риск тихого TTL-reject ~12.07).
2. Довести skill-lint до 0 errors.
3. Устранить «случайно нерутуемые» скиллы (27 не в router-config).
4. Синхронизировать числа в CLAUDE.md.
5. Поднять eval-покрытие топ-активированных скиллов.

## Контекст (факты аудита)
- pending=78 / rejected=0 / saved-total=3 → выход конвейера мёртв.
- `data/_skill_lint.json` = устаревший снапшот (48 errors), свежий lint = 0 errors.
- router-config: 53 bundles; 27 dirs не упомянуты (часть — slash/делегация, часть — выпали).
- CLAUDE.md: «45 bundles», skill_library «80», learned_patterns «44» — дрейф.
- evals.yaml: 3 из 99; live-baseline сломан (project-aware claude-cli → delta=0).

## Точки изменения
- MCP skill-learning: confirm/reject pending.
- `.claude/skills/skill-router-config.json`: +bundles, +`_unrouted_intentional`.
- `CLAUDE.md`: числа.
- `.claude/skills/<top10>/evals.yaml`: новые кейсы.
- `data/_skill_lint.json`: refresh (gitignored).
