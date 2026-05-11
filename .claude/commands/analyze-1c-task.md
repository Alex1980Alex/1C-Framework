---
description: Комплексный 5-фазный анализ задачи 1С:Предприятие через skill `analyze-1c-task-v2`. Создаёт ANALYSIS-REPORT.md с пронумерованными точками модификации для последующего /implement-1c-task. Поддерживает флаг `--trace` для опциональной Фазы 2.5 Runtime Trace (live BP-trace через 1c-debug-hmr).
allowed-tools:
  - mcp__bsl-semantic-search__bsl_search
  - mcp__bsl-semantic-search__bsl_hybrid_search
  - mcp__bsl-semantic-search__bsl_call_graph
  - mcp__bsl-semantic-search__bsl_impact_analysis
  - mcp__bsl-semantic-search__bsl_object_info
  - mcp__bsl-platform-context__search
  - mcp__bsl-platform-context__getMember
  - mcp__bsl-platform-context__getMembers
  - mcp__1c-mcp-crud__get_metadata
  - mcp__1c-mcp-crud__get_metadata_structure
  - mcp__1c-mcp-crud__list_metadata_objects
  - mcp__1c-mcp-crud__execute_query
  - mcp__1c-mcp-crud__validate_query
  - mcp__1c-mcp-crud__find_references_to_object
  - mcp__pdf-vector-graph__search_documents
  - mcp__pdf-vector-graph__ask_question
  - mcp__memory-orchestrator__route_and_save
  - mcp__1c-debug-hmr__debug_health_check
  - mcp__1c-debug-hmr__debug_connect
  - mcp__1c-debug-hmr__debug_disconnect
  - mcp__1c-debug-hmr__debug_set_breakpoint
  - mcp__1c-debug-hmr__debug_get_breakpoints
  - mcp__1c-debug-hmr__debug_ping
  - mcp__1c-debug-hmr__debug_stack_trace
  - mcp__1c-debug-hmr__debug_variables
  - mcp__1c-debug-hmr__debug_evaluate
  - mcp__1c-debug-hmr__debug_step
  - mcp__1c-debug-hmr__debug_targets
---

# Комплексный анализ задачи 1С

Выполни полный анализ задачи по разработке 1С, используя **skill `analyze-1c-task-v2`** (5-фазная методология).

## Задача от пользователя:
$ARGUMENTS

---

## Инструкция

**Используй skill `analyze-1c-task-v2`** — единый источник методологии анализа.

Skill определяет:
- 5 последовательных фаз (Требования → Объекты → **[опц. Фаза 2.5 Runtime Trace]** → Алгоритм → План → Верификация)
- Допущенные MCP-инструменты (`bsl-semantic-search`, `bsl-platform-context`, `1c-mcp-crud`, `pdf-vector-graph`, `ast-grep` через профиль bsl, **`1c-debug-hmr` для Фазы 2.5**)
- Формат отчёта `ANALYSIS-REPORT.md` (с опциональной секцией «3.Y Runtime Trace»)
- Best practices и common pitfalls

### Входные данные

Из `$ARGUMENTS` извлеки:
1. **Путь к ТЗ** — файл с описанием задачи (обычно `*ТЗ*.md` или `*TS*.md` в папке задачи)
2. **Путь к `src/`** — корень исходников конфигурации
3. **Флаг `--trace`** (опц.) — активирует Фазу 2.5 Runtime Trace
4. Дополнительный контекст (если есть)

### Результат

Файл **`ANALYSIS-REPORT.md`** в папке задачи со структурой:
1. Описание задачи (требования + суть проблемы)
2. Задействованные объекты конфигурации (таблицы по группам)
3. Детальный анализ механизма (по каждому объекту с кодом)
4. План изменений (пронумерованные точки модификации, с маркерами `[ADDED]`/`[MODIFIED]`/`[REFACTOR]`)
5. Чек-лист верификации
6. Риски и открытые вопросы (опционально)

---

## ВАЖНО

- Для BSL используй **`bsl-semantic-search`** (не Serena для парсинга BSL — для BSL нет LSP).
- Используй **`bsl-platform-context`** для проверки API платформы 1С:8.3.27 (типы, методы, свойства, конструкторы).
- Используй **`bsl-semantic-search`** (`bsl_search`/`bsl_hybrid_search`) для поиска похожего кода в 3 900+ модулях.
- Используй **`pdf-vector-graph`** (`search_documents`/`ask_question`) для поиска в индексированной документации 1С.
- Используй **`1c-mcp-crud`** (`get_metadata`/`validate_query`/`execute_query`) для верификации имён полей и SQL-запросов на живой базе.
- **Для сложных runtime-алгоритмов** (≥3 ветвлений по runtime-данным: `Пользователи.ТекущийПользователь()`, `ПолучитьФункциональнуюОпцию`, `Тип(Параметр)`) используй опциональную **Фазу 2.5 Runtime Trace** через `1c-debug-hmr` — см. skill для протокола. Триггер: флаг `--trace` в `$ARGUMENTS` или self-decision skill'а. Output: секция «3.Y Runtime Trace» в ANALYSIS-REPORT с Entry/Stack/Variables/Branch evaluation/**Discrepancies** (static vs runtime).
- Сохрани результат анализа в файл `ANALYSIS-REPORT.md`, а также в память через **`memory-orchestrator`** (`route_and_save`) для последующих сессий.
