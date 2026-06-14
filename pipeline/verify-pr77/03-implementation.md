# 03 — Реализация

## Верификация PR #77 (выполнено ранее)
Verdict **PASS** по runtime-поверхностям:
- MCP cold-start (`server.py`): фоновый прогрев S1 стартует через +3 мс после старта
  транспорта без tool-call, `ready in 7.82s` (живой Qdrant). `timeout: 600000` в
  `.mcp.json` подтверждён.
- `jobs.py`: после import опц. зависимость не в `sys.modules` → импорт отложен; все 4
  маршрута `/jobs*` регистрируются.
- `planner.py`: старое `.format()` → `KeyError` на литеральных JSON-скобках; новое
  `.replace("{query}", …)` корректно.
- `agent.py`: публичный конструктор отдаёт скомпилированный граф; узел `executor`
  есть, фантомного `execute` нет.
- 1С-сабмодули: gitlink резолвятся на heads/master (dangling нет).
Продуктовый код не менялся; временный драйвер удалён.

## T2 — .gitmodules (ВЫПОЛНЕНО)
Коммит `3691d65fe` `fix(submodule): map stray gitlinks tree-sitter-bsl-src +
multilspy-fork` (+8 строк, только `.gitmodules`).

## T3 — пайплайн (ТЕКУЩЕЕ)
Этот набор 01–04 заменил trivial `pipeline.md`.

## T1 / T4 — ОЖИДАЮТ решения пользователя по scope-стратегии (gate)
Тело PR пишется после выбора опции A/B/C, т.к. зависит от итогового объёма PR.
