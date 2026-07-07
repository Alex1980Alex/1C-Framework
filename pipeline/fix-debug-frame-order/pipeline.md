# fix-debug-frame-order (trivial, ADR-018 компактный)

**Задача:** live-проверка новых MCP-инструментов `debug_calibrate_lines`/`debug_calibrate_result` (1c-debug-hmr, 27 tools) на GKSTCPLK-2641 вскрыла дефект — hits калибровки не считались (`fired_lines=[]`) при физически сработавшем BP.

**План/Дизайн:** RDBG `callStackFormed` присылает стек outermost-first (фрейм остановки — последний элемент), а `coverage.record_hit_and_continue`, `logpoints._top_key/fire_logpoint`, `bp_conditions.auto_continue_if_unsatisfied` матчили `stack[0]`. Фикс — скан фреймов с конца (innermost-first), первый match = точка останова. Семантика single-frame стеков не меняется (существующие тесты зелёные).

**Код:** сабмодуль `tools/bsl-debug-server`, коммит `6fd1b1d` (coverage.py / logpoints.py / bp_conditions.py), запушен; gitlink bump в родителе `fb6b68c23`.

**Тест:**
- unit: `tests/test_calibration.py` 9 PASS + `tests/test_mcp_debug_server.py` 229 PASS;
- live (SVETLY, `гкс_АРМПромежуточныйКомпозит` ObjectModule:80, JOB-триггер): до фикса `fired_lines=[]` ×2, после — `fired_lines=[73,74,76,78,80,82]`, offset=0; logpoint отдал результат запроса (`строк=0`, deployed-код без правки 2641 — занесено в IMPLEMENTATION-PROGRESS задачи).
