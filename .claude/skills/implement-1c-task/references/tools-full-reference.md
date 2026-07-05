# Полный набор EDT-MCP по этапам

Дополняет hot-path таблицу в SKILL.md; по implement задействовано ~36 из 70 тулов.

- **Этап 0 Preflight:** `get_edt_version` · `get_server_status` · `list_toolsets` · `enable_toolset` (+ `list_projects`).
- **Этап 1 Подготовка (read/nav):** + `get_metadata_objects` · `get_metadata_details` · `get_configuration_properties` · `list_subsystems` · `get_subsystem_content` · `go_to_definition` · `get_method_call_hierarchy`.
- **Этап 3 BSL + CRUD метаданных:** + `create_metadata` · `modify_metadata` · `rename_metadata_object` · `delete_metadata` · `adopt_metadata_object` · `create_project` (kind=extension); settable-свойства — `get_metadata_details(assignable=true)`.
- **Этап 4 Статанализ (EDT-валидация):** `get_problem_summary` · `get_markers` · `get_check_description` — комплементарно `bsl_lint.py`/`bsl_analyze`.
- **Этап 5 Верификация:** `revalidate_objects` (+ `find_references` / `get_method_call_hierarchy`).
- **Этап 6 Тест/применение к БД:** `update_database` · `run_yaxunit_tests` (YAXUnit-юнит-проверка) · `resync_to_disk`.
- **Recovery (любой этап):** `clean_project`.
- **Прочее:** discovery по тегам (Этап 1) — `get_tags` · `get_objects_by_tags`; YAXUnit-конфиг (Этап 6) — `list_configurations` (имя runtime-client); сквозное — `get_tool_guide` (preconditions тула перед нетривиальным вызовом); deprecated — ~~`debug_yaxunit_tests`~~ → `run_yaxunit_tests(debug=true)`.
- **⚠ Деструктивные (confirm-гейт, только по явному запросу):** `update_database` · `delete_metadata` · `rename_metadata_object`.
- **Вне пайплайна (админ/инфра — НЕ шаги задачи):** `create_infobase` · `delete_infobase` · `create_launch_config` · `delete_launch_config` · `delete_project` · `export_configuration_to_xml` · `import_configuration_from_xml` · `generate_translation_strings` · `translate_configuration` · `get_translation_project_info`.

> Отладочный EDT-MCP-тулсет (`debug_launch` · `debug_status` · `set_breakpoint` · `remove_breakpoint` · `list_breakpoints` · `wait_for_break` · `get_variables` · `evaluate_expression` · `step` · `resume` · `terminate_launch` · `get_applications`) — **альтернатива `1c-debug-hmr`** для BP-verification Этапа 5.x внутри EDT (основной путь — `1c-debug-hmr`). Полный справочник 70 тулов — skill [`edt-mcp`](../../edt-mcp/SKILL.md).

## 1c-debug-hmr — полная таблица инструментов (Этап 5.x BP-verification)

| Инструмент | Когда использовать |
|---|---|
| `debug_health_check` | Этап 0: structured probe среды (`mode="probe"` / `"prepare"`); <1с вместо 5-7 manual TCP/HTTP probes |
| `debug_connect` | Этап 0 / Этап 5.x: attach как Debug UI к dbgs.exe :1550 (**сначала** Shift+F5 в Конфигураторе/EDT — иначе `ibInDebug`). `force_recycle_rphost=True` — Solution A для pre-existing rphost gap |
| `debug_set_breakpoint` | Этап 5.x (шаг 2): BP в новой/изменённой процедуре через UUID метаданных, `propertyID` auto-resolve |
| `debug_get_breakpoints` | Этап 5.x (шаг 3): verify BP в client cache |
| `debug_break_on_next` | Этап 5.x (fallback a): catch-all для следующей BSL-операции в attached rphost |
| `debug_ping` | Этап 5.x (шаг 5): диспатч событий (targetStarted/callStackFormed/rteProcessing); также крутится в фоне `_ping_loop` |
| `debug_stack_trace` | Этап 5.x (шаг 6): кадры stack'а в момент остановки (cache hit из push event, без явного `target_id`) |
| `debug_variables` | Этап 5.x (шаг 7): локальные переменные в текущем кадре (auto-resolve через `last_stopped_target_id`) |
| `debug_evaluate` | Этап 5.x: любое BSL-выражение в контексте остановки (composite types до 4096 char) |
| `debug_step` | Этап 5.x (шаг 8): Continue / Step / StepIn / StepOut |
| `debug_session_summary` | Этап 7: вывод session-метрик (BP fire, eval, UI+ retries) в IMPLEMENTATION-PROGRESS |
| `debug_session_diff` | Этап 5.y: regression diff против baseline `prev_session_id` из footer'а PROGRESS |
| `debug_disconnect` | Этап 5.x: clean teardown (опционально — HMR session переживает reload) |

**Когда применять:** в режиме **Full** — по умолчанию для BP-verification всех `[ADDED]`/`[MODIFIED]` точек (Этап 5.x). В режиме **Full (no-BP)** — SKIP с пометкой. См. [16.7 Autonomous Debug Workflow](../../../../docs/framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.7_Autonomous_Debug_Workflow.md) §16.7.10 для setup и [36.7 HMR Subprocess Wrapper](../../../../docs/framework%20documentation/3_ИНСТРУМЕНТЫ/3.5_AUTONOMOUS_DEBUG_CONTROL/36.7_HMR_Subprocess_Wrapper.md) для HMR-специфики. Skill: [1c-debug-hmr](../../1c-debug-hmr/SKILL.md).
