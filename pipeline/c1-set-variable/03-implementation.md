# C1 — Реализация

Файл: `tools/bsl-debug-server/mcp_debug_server.py` (+175 строк, submodule).

## Добавлено
1. **`RDBGClient.modify_value(name, value_expr, target_uuid=None, stack_level=0, variant="expr", timeout_ms=5000) -> list[dict]`** (после `eval_expression`).
   - POST `?cmd=modifyValue`, тело по XSD `RDBGModifyValueRequest`: base_fields + `targetID` + `modifyDataPath` (CalculationSourceDataStorage = stackLevel + srcCalcInfo[expressionResultID + calcItem{itemType=expression, expression}]) + `newValueInfo` (variant + valueExpression) + `timeout`.
   - Переиспользует билдеры `_calc`/`_rdbg`/`_build_request`/`_target_id_light`/`_base_fields`/`_parse_response` + `_resolve_target_uuid`/`_ensure_target_attached`. Новых примитивов нет.
   - `_escape_xml(name)` + `_escape_xml(value_expr)` — XML-безопасность (BSL `<`/`"`/`&`).
   - Синхронный (не event-driven как evalExpr) — без `_pending_evals`/ping-loop.
   - **`timeout_ms` в МИЛЛИСЕКУНДАХ** (live: "3" → «в течение 3 миллисекунд»; default 5000).

2. **`_extract_modify_result(parsed) -> (processed, error)`** (module-level, перед tool).
   - SUCCESS-shape: `newValueState.evalResultState == "correctly"` → processed=True (НЕТ элемента `processed`).
   - FAILURE-shape: `processed=false` + `errorDescr` (base64 → decoded).
   - `withErrors` → processed=False. Пусто/non-dict/unknown → (False, None).

3. **MCP-tool `debug_set_variable(name, value_expression, target_id="", stack_level=0, verify=True) -> str`** (после `debug_evaluate`).
   - guard `{old, new, changed}` (verify=True: eval до/после), `processed`, `error`, `raw`, `security_note`.
   - envelope not_connected / no_stopped_target / graceful except — паритет `debug_evaluate`.

## Отклонения от дизайна (02)
- `timeout_sec` → **`timeout_ms`** (live-находка: RDBG `timeout` в мс, не сек). Design предполагал сек — исправлено по факту зонда.
- `_extract_modify_result` расширен веткой `newValueState.evalResultState` — исходный дизайн ждал `processed`-элемент на success, но RDBG его НЕ шлёт (первый прогон дал processed=False на успехе → баг парсера пойман live, исправлен).

## Обратимость
Чистое добавление 3 сущностей + 1 тест-файл. Реверс = удалить блоки. `.mcp.json` не тронут (mcp_debug_server.py уже HMR-watched). Новый tool в MCP — после `/mcp reconnect` (harness кеширует tools/list); клиент-метод грузится по HMR сразу.
