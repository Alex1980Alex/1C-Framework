# Пайплайн: Глубокий анализ 1c-debug-hmr + дорожная карта автономной отладки

**Тип:** research/analysis (deliverable = дорожная карта; продуктового кода/тестов НЕТ — только docs/cache).

## Этап 1 — Анализ (Планирование) ✅
- Живой health-check контура отладки (dbgs :1550, ragent -debug -http, 5 инфобаз) — реальный прогон.
- Глубокий разбор `mcp_debug_server.py` (4083 стр) + 9 модулей — параллельный агент (RDBG XML-транспорт, BP, variables, step, event-loop, snapshot, coverage, техдолг).
- Изучение SKILL, кэш-ресёрча BP-race, предыдущего 260511 deep-analysis.

## Этап 2 — Дизайн (карта улучшений) ✅ approved
- GitHub best-practices автономной отладки (DAP, 1С-экосистема, TTD/rr, LLM-debugging ADI/InspectCoder/SWE-Doctor, надёжность) — параллельный агент.
- **Артефакт:** [`docs/roadmap/260708_ROADMAP_AUTONOMOUS_1C_DEBUGGING.md`](../../docs/roadmap/260708_ROADMAP_AUTONOMOUS_1C_DEBUGGING.md) — эпики A (автономность) / B (root-fixes) / C (DAP-gaps), волны W1-W5.
- **Кэш:** `.claude/skills/architecture-research/cache/autonomous-1c-debugging-2026.md` + `_index.json`.

## Этапы 3-4 — Кодирование / Тестирование — N/A
Реализация улучшений (W1: `debug_inspect_frame` и др.) — по approve пользователя, отдельным пайплайном. Данная задача завершается на дизайн-артефакте (дорожная карта).
