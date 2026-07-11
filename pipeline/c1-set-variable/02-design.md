# C1 — Дизайн реализации

## 1. `RDBGClient.modify_value` (клиент, ~зеркало `eval_expression`)

```python
async def modify_value(self, name, value_expr, target_uuid=None, stack_level=0,
                       variant="expr", timeout_sec=3) -> dict:
    target_uuid = self._resolve_target_uuid(target_uuid)
    if not target_uuid:
        raise ValueError("modify_value: no target_uuid and no last_stopped")
    await self._ensure_target_attached(target_uuid)
    expr_result_id = str(uuid.uuid4())
    src_calc_info = _calc("expressionResultID", expr_result_id) + _calc(
        "calcItem", _calc("itemType", "expression") + _calc("expression", name))
    modify_data_path = _calc("stackLevel", str(stack_level)) + _calc("srcCalcInfo", src_calc_info)
    new_value_info = _calc("variant", variant) + _calc("valueExpression", value_expr)
    body = _build_request(
        self._base_fields(),
        _rdbg("targetID", _target_id_light(target_uuid)),
        _rdbg("modifyDataPath", modify_data_path),
        _rdbg("newValueInfo", new_value_info),
        _rdbg("timeout", str(timeout_sec)),
    )
    root = await self._post("modifyValue", body)   # ?cmd=modifyValue
    parsed = _parse_response(root)                 # [{processed, newValueState/errorDescr}]
    return parsed[0] if parsed else {}
```
- Переиспользует `_base_fields`/`_calc`/`_rdbg`/`_target_id_light`/`_build_request`/`_post`/`_resolve_target_uuid`/`_ensure_target_attached`/`_parse_response` — новых примитивов НЕ вводим.
- Синхронный ответ (не event-driven как evalExpr) → без `_pending_evals`/ping-loop; проще.
- `variant` параметризован (default "expr"); "unknown"→Неопределено, "val" не поддерживаем (не нужен).

## 2. MCP-tool `debug_set_variable` (зеркало `debug_evaluate` + guard)

```python
@mcp.tool()
async def debug_set_variable(name, value_expression, target_id="", stack_level=0, verify=True) -> str:
    client = _get_client()
    if not (client._attached and client._registered): return _error_json("Not connected...", "not_connected")
    target_id, _ = await _resolve_stopped_target(client, target_id)
    if not target_id: return _error_json("No stopped targets", "no_stopped_target")
    old = await _read_scalar(client, name, target_id, stack_level) if verify else None   # eval_expression
    res = await client.modify_value(name, value_expression, target_id, stack_level)
    processed = str(res.get("processed", "")).lower() == "true"
    new = await _read_scalar(client, name, target_id, stack_level) if verify else None
    return json.dumps({
        "name": name, "value_expression": value_expression, "stack_level": stack_level,
        "processed": processed, "old": old, "new": new,
        "changed": (old != new) if verify else None,
        "raw": res,
        "security_note": "modifyValue исполняет valueExpression как BSL в rphost — не передавать untrusted",
    }, ensure_ascii=False, indent=2)
```
- **guard `{old, new, changed}`** (roadmap §18 C1): читаем до/после (`verify=True`) → агент видит эффект; `verify=False` пропускает лишние reads.
- `_read_scalar` — тонкий хелпер над `eval_expression` (берёт `resultValueInfo.pres`/`valueString`|`valueDecimal`|`valueBoolean`|`valueDateTime`, best-effort строкой). Внутренний, не tool.
- Graceful-envelope `except` как у `debug_evaluate` (RDBG 400 «только в остановленном предмете» и т.п.).
- **security_note в ответе при мутации** (roadmap §7.4 нота 2, паритет с logpoints).

## 3. Тесты (unit, зеркало `test_held_job_b1`/`test_mcp_debug_server` паттернов)
- `test_modify_value_builds_request` — мок `_post`, проверить: cmd="modifyValue", body содержит `<...modifyDataPath>` со `stackLevel`+`expression=name`, `newValueInfo` с `variant=expr`+`valueExpression=value`, `targetID`.
- `test_modify_value_no_target_raises` — без target и last_stopped → ValueError.
- `test_modify_value_parses_processed` — мок RDBG-ответ `processed=true`+newValueState → dict.
- `test_debug_set_variable_not_connected` / `_no_stopped_target` — envelope.
- `test_debug_set_variable_guard` — мок client.modify_value + eval → old/new/changed в JSON.
- `test_debug_set_variable_verify_false` — reads не зовутся, old/new=None.
- Мок-клиент по образцу `_HeldClient` (test_held_job_b1) — `modify_value` AsyncMock + `eval_expression` возвращает scalar.

## 4. Live-валидация (этап 4, held-JOB harness, ОБЯЗАТЕЛЬНА — B1-урок)
1. `debug_evaluate("ТаймаутСек")` → old=300.
2. `debug_set_variable("ТаймаутСек", "777")` → `processed=true`, `newValueState`=777.
3. `debug_evaluate("ТаймаутСек")` → 777 (мутация фрейма персистит).
4. Негатив: `debug_set_variable("ТаймаутСек", "1/0")` → processed=false/errorDescr (BSL-ошибка выражения не роняет tool).
Если формат `newValueInfo` неверен (400/processed=false на валидном) — корректировать сериализацию (variant-only / valueExpression-only) по фактической ошибке.

## 5. Обратимость / деплой
- Чистое добавление (1 метод + 1 tool + тесты) в `mcp_debug_server.py` (HMR-watched — reload без потери session). Реверс = удалить блоки.
- Новый tool виден после HMR list_changed (при кеше harness — `/mcp reconnect`); клиент-метод грузится сразу.
- `.mcp.json` не трогаем (mcp_debug_server.py уже watched как inner-server).

## Гейт
Дизайн одобрен (задача авторизована пользователем «Браться за C1»). Переход к этапу 3.
