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
