# TOOL-PLAN — B′ хвост (impl-1c-bprime-tail)

| Этап | Инструменты | Quality |
|---|---|---|
| Планирование | architecture-research, Bash/Grep (.run-state схема, audit_query) | ✓ хорошо — сигналы verified до дизайна |
| Дизайн | architecture-research | ✓ хорошо — 3 пункта развязаны, каждый обратим |
| Кодирование | create-hook, Write/Edit, ruff/py_compile | ✓ хорошо — 5 файлов чисто с 1й |
| Тестирование | evaluation-benchmark, pytest, синтетический PostToolUse/UPS, tool_usage_report на реальном логе | ✓ хорошо — 17 passed + 3 live-DoD с 1й; W показал реальные данные сессии |

Лог — авто `hook-invocations.jsonl` (этот прогон сам себя инструментировал: W-отчёт на session-id показал Edit/Bash/Write/Skill). Шкала ✓/⚠/✗.
