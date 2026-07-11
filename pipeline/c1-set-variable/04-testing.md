# C1 — Тестирование

## Unit (14 тестов, `tests/test_c1_set_variable.py`) — PASS
- `TestModifyValueBuilder`: request собирается по XSD (cmd=modifyValue, modifyDataPath/newValueInfo/stackLevel/expression/itemType/variant/valueExpression/timeout=5000); `_escape_xml` на value_expr (`Ф < 5 & "т"` → `&lt;`/`&amp;`/`&quot;`); override `timeout_ms=250`; no-target → ValueError.
- `TestExtractModifyResult`: success (newValueState/correctly)→(True,None); failure (processed+errorDescr)→(False,«Деление на 0»); withErrors→не processed; пусто→(False,None); non-dict→tolerated.
- Tool: guard old/new/changed + 2 read'а; verify=False → 0 read'ов, old/new=None; not_connected; no_stopped_target; невалидный expr → processed=False + error (tool не падает).
- Регресс всего wrapper'а: **484 passed** (было 470), 0 фейлов.

## Live-валидация (RDBG 8.3.27.1936, база MFM `260507_DEV_ATERLETSKIY_53196`, held-JOB harness B1) — PASS
Обязательна (B1-урок: рантайм-семантику RDBG unit-тесты не ловят). Зонд определил механизм и поймал 2 бага (timeout-мс, парсер success-shape).

| Проверка | Результат |
|---|---|
| Зонд: evalExpr-присваивание | `evalExpr("X = 999")` → Булево (сравнение); `Выполнить("...")` → «Ожидается выражение». **Не работает** → нужен нативный modifyValue |
| Число-мутация | `debug_set_variable("ТаймаутСек","777")` → newValueState correctly=777; **независимый eval через MCP → 777** (120→777 персистит) |
| Строка + произвольный BSL | `КлючУдержания := "key-" + Строка(ТаймаутСек)` → «key-777» (выражение вычислено, читает переменную фрейма); MCP cross-check → «key-777» |
| Негатив (BSL-ошибка) | `"1/0"` → processed=false + errorDescr «Деление на 0»; tool не падает |
| timeout unit | "3" → «в течение 3 миллисекунд» → default выставлен 5000 мс |
| Парсер обеих shape | success→PROCESSED:True; failure→PROCESSED:False+error |

## code-verify (Уровень 2, субагент a268abb9, quality-review + bug-fix) — **PASS [CODE-VERIFY-PASS]**
XML бит-в-бит по XSD; обе shape разобраны; envelope-паритет `debug_evaluate`; XML-инъекция закрыта; исключения не текут. 2 не-блокирующие ноты (порядок-зависимость в недостижимой смешанной shape; асимметрия эскейпинга vs предсуществующий eval_expression) — «оставить как есть».

## Вывод
C1 реализован, unit-покрыт (14), live-validated end-to-end, code-verify PASS. Готов к коммиту.
