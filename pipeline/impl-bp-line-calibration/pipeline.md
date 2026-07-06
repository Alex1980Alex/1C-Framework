# impl-bp-line-calibration — компактный пайплайн (ADR-018)

**Задача (запрос пользователя):** встроить авто-калибровку номеров строк в отладочный контур, чтобы BP-verification не мучился со сдвигом строк repo-src ↔ deployed-конфигурация (live-кейс сессии: BP на 67 молчал, реальная строка 70).

## 1. Планирование
Вариант «инструкция в скилле» отвергнут в пользу первоклассного инструмента: калибровка = переиспользование coverage-механизма (hit + auto-Continue) — веер silent-BP вокруг целевой строки.

## 2. Дизайн
Два MCP-tool в [mcp_debug_server.py](../../tools/bsl-debug-server/mcp_debug_server.py):
- `debug_calibrate_lines(object_id, line, module_type, property_id, radius=8)` — регистрирует coverage-веер `[line±radius]` + один `set_breakpoints`, состояние в `client._calibrations`.
- `debug_calibrate_result(object_id?, clear=True, keep_bp_on_nearest=True)` — fired-строки из `_coverage_tracked`, `nearest_fired`, `offset`; чистит веер (coverage-ключи + BP-кэш + перепуш workspace, пустой кэш → явный пустой `bpWorkspace`-push), оставляет обычный BP на nearest (создаёт запись в кэше явно, если её нет — HMR-restart case).

## 3. Кодирование
+2 tools (~120 строк) поверх готовых `bsl_coverage.register_line` / `record_hit_and_continue` / `set_breakpoints(lines=[...])`. Скиллы: [1c-debug-hmr](../../.claude/skills/1c-debug-hmr/SKILL.md) (таблица 27 tools + Шаблон 5a + caveat «окно JOB-halt 1–2 с») и [implement-1c-task](../../.claude/skills/implement-1c-task/SKILL.md) (Этап 5.x: обязательный Шаг 0 калибровки + JOB-window note).

## 4. Тестирование
[tests/test_calibration.py](../../tools/bsl-debug-server/tests/test_calibration.py) — 7 unit (веер+coverage-регистрация, clamp radius/floor строки, not-connected, fired/offset/cleanup/keep-nearest, no-fire hint + пустой workspace push, no-active, keep_bp=False). Прогон: 7/7 + полный сьют обёртки **280 passed**. Тест вскрыл и закрыл реальную дыру: keep-nearest при пустом BP-кэше (HMR-restart) — запись создаётся явно.

**Активация:** HMR перечитает `mcp_debug_server.py` автоматически; для появления схем НОВЫХ tools в текущей сессии Claude Code — `/mcp reconnect`.
