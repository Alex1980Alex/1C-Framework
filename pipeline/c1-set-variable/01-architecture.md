# C1 — setVariable / setExpression (roadmap 260708, W3)

## Проблема
Отладчик читает переменные (`debug_variables`/`debug_evaluate`), но НЕ умеет их **изменять** в точке останова. Это блокирует runtime hypothesis-testing («а что если тут X=0?») и 80% ценности drop-frame (C5). Enum RDBG содержит `valueModified` (event 9), но `_handle_command` его скипает — запись значений не реализована.

## Live-зонд (этап 1, выполнен 2026-07-11 на MFM, harness = B1 held-JOB)
Проверял: принимает ли `evalExpr` side-effecting присваивание.
- `evalExpr("ТаймаутСек = 999")` → **`Булево=false`**. В BSL `=` в контексте выражения = **сравнение**, не присваивание. Наивный подход НЕ работает.
- `evalExpr('Выполнить("ТаймаутСек = 999")')` → **`withErrors: «Ожидается выражение»`**. `Выполнить` void, evalExpr требует значение-выражение. BSL не имеет assignment-выражения (нет walrus).
- **Вывод:** evalExpr-присваивание фундаментально невозможно. Нужен нативный RDBG-setter.

## Найденный механизм (yukon39 RDBG-reference + XSD)
RDBG-команда **`modifyValue`** (`RDBGModifyValueRequest`/`Response`):
- Запрос: `targetID` + `modifyDataPath` (CalculationSourceDataStorage = stackLevel + srcCalcInfo[expressionResultID + calcItem{itemType=expression, expression=<имя>}]) + `newValueInfo` + `timeout`.
- `NewValueInfo` (XSD:92) = choice `variant` (unknown/val/expr) + `value` + **`valueExpression`** (BSL-строка).
- **`variant="expr"` + `valueExpression="<BSL>"`** → ставит значение как результат произвольного BSL-выражения (число/строка/дата/`Новый ...`). Максимально гибко и просто (одна строка).
- Ответ синхронный: `processed` (bool) + `newValueState` (значение после) + `errorDescr`.

`modifyDataPath` = ТОТ ЖЕ `CalculationSourceDataStorage`, что `expr` в `eval_expression` → переиспользуем готовый билдер `src_calc_info`.

## Scope
- **[ADDED]** `RDBGClient.modify_value(name, value_expr, target_uuid, stack_level)` — POST `modifyValue`, парс `{processed, newValueState, errorDescr}`.
- **[ADDED]** MCP-tool `debug_set_variable(name, value_expression, target_id, stack_level, verify)` — guard `{old, new, changed, processed}` + `security_note` (произвольный BSL в rphost).
- **[ADDED]** unit-тесты (билдер запроса + tool: guard, not-connected, no-target, verify on/off).
- Docs: skill `1c-debug-hmr` (tool-таблица Inspection→+setter), roadmap §18, память.

## НЕ в scope
- C4 watchpoint (эмуляция поверх C1 — отдельный пункт W5).
- `variant="val"` с raw-value-кодированием — `valueExpression` покрывает все кейсы проще; val-вариант defer (не нужен).
- Массовый setVariables — единичный set достаточен для hypothesis-test.

## Риск / открытый вопрос (закрывается этапом 4 live-тестом)
Точная сериализация `newValueInfo` (XSD моделирует choice, Java-класс держит variant+value раздельно). Гипотеза: `variant="expr"` + `valueExpression`. Live-тест на held-JOB (мутировать `ТаймаутСек`→777, прочитать назад) подтверждает/корректирует формат. B1-урок: рантайм-семантику RDBG unit-тесты билдера не ловят → live обязателен.
