# 43.4 Справочник инструментов 1С — pipeline (trivial)

**План.** Пользователь попросил полный список инструментов для решения 1С-задач (основа TOOL-PLAN).
**Дизайн.** Новый файл `43.4_СПРАВОЧНИК_ИНСТРУМЕНТОВ.md` — перечень по 4 этапам + шаблон TOOL-PLAN; заземление
на `allowed-tools` команд analyze/implement + методику va-bdd (не по памяти). Линки из 43.1/43.3/TOC.
**Реализация.** Создан 43.4 (сквозные + Этап1-2 + Этап3 + Этап4 таблицы, ⭐ primary-инструмент, шаблон);
правки 43.3 Шаг 1 (ссылка), 43.1 «Состав главы», 00_СОДЕРЖАНИЕ.
**Тест.** Инструменты сверены с frontmatter: analyze (bsl-semantic-search/bsl-platform-context/1c-mcp-crud/
pdf-vector-graph/1c-debug-hmr), implement (edt-mcp 16 + 1c-mcp-crud + bsl-debugger + 1c-debug-hmr 13),
va-bdd (1c-mcp-crud primary + run-bdd.ps1 + mcp-onec-test-runner). Ссылки на 16.5/36 валидны.
