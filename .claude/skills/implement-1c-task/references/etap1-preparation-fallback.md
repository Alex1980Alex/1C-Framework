# Этап 1: Подготовка — детали fallback'ов (шаг 3)

**Path-fallback при File-not-found (Designer→EDT flatten):**

ANALYSIS-REPORT'ы используют Designer-style пути из выгрузки конфигурации (например `Documents/<Имя>/Ext/ManagerModule.bsl`, `DataProcessors/<Имя>/Forms/<Форма>/Ext/Form/Module.bsl`). EDT в открытом проекте хранит модули по своему layout'у (`DataProcessors/<Имя>/Forms/<Форма>/Module.bsl` без `Ext/Form/`). При расхождении `read_method_source(project, <designer_path>, ...)` падает с `File not found`.

```
EDT-MCP: list_modules(project, objectName="<ИмяОбъектаКонфигурации>")
  → массив { module_path, module_type } для всех модулей объекта
```

Из массива выбрать `module_path` совпадающий по типу (`ManagerModule` / `ObjectModule` / `FormModule` / `CommandModule`) и повторить `read_method_source` с EDT-путём. Соответствие Designer→EDT зафиксировать в IMPLEMENTATION-PROGRESS.md, чтобы последующие точки той же задачи использовали уже разрешённый путь без повторного fallback'а.

**Fallback (edt-mcp недоступен):** структура модуля и тело метода читаются без EDT.
```
bsl-code-search: get_module_ast(file_path)
  → процедуры/функции в модуле (имена + диапазоны строк)
ИЛИ
bsl-semantic-search: bsl_object_info(object_name)
  → метаданные объекта + список модулей + call graph stats
bsl-semantic-search: bsl_coding_context(object_name, task_description)
  → агрегированный контекст: object info + dependencies + style + similar code

Read(file_path, offset=method_start_line, limit=method_length)
  → текущий код точки вставки (через стандартный Read)
```

**Ограничения fallback'а** (зафиксировать в IMPLEMENTATION-PROGRESS.md):
- Нет `get_content_assist` — автодополнение имён перечислений/регистров недоступно, проверять вручную через `bsl-platform-context` или `Grep` по конфигурации.
- Нет `get_symbol_info` — типы параметров/возвращаемых значений выводить из сигнатуры в `get_module_ast` или из аннотаций кода.
- Нет `search_in_code` по проекту EDT — заменяется на `Grep` + `bsl_search` (семантический).
