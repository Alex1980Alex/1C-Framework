# 02 — Дизайн

## Источник результата — сайдкар
`TOOL-RESULTS.json` = `{tool: саммари-результата}` в папке задачи рядом с отчётом. Читается
`load_results(--results <json> | авто <target>/TOOL-RESULTS.json)`; best-effort → {} (нет файла / битый JSON /
не-dict). Значения → однострочный str (защита блока от случайного `\n`).

## report_md (block format)
`report_md(by_tool, key, results=None)` — обратносовместима (results опционален). Чеклист обязательных петель
без изменений; секции по категориям → **блок на инструмент**: `**\`tool\`** · N вызов · M ошиб · Xms · q` +
`· назначение: <tool_summary>` + `· результат: <results.get(tool) | "—">`. Таблица + `_cell` удалены
(в backtick-спане пайп не ломает markdown).

## Оркестрация
run-1c-task шаг 9: Claude СНАЧАЛА пишет TOOL-RESULTS.json (результаты по факту), затем генерит отчёт.

## Approved: пользователь (формат выбран AskUserQuestion: блок на инструмент).
