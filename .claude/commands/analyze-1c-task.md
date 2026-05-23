---
description: Комплексный 5-фазный анализ задачи 1С:Предприятие через skill `analyze-1c-task-v2`. Создаёт ANALYSIS-REPORT.md с пронумерованными точками модификации для последующего /implement-1c-task. Поддерживает флаг `--trace` для опциональной Фазы 2.5 Runtime Trace (live BP-trace через 1c-debug-hmr).
allowed-tools:
  - Read
  - Glob
  - Grep
  - Write
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
- 5 последовательных фаз (Требования → Объекты → Алгоритм → План → Верификация)
- Допущенные MCP-инструменты (Serena, ast-grep, bsl-platform-context, bsl-semantic-search, pdf-vector-graph)
- Формат отчёта
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

## ВАЖНО:
- Для BSL используй  (не Serena для парсинга BSL!)
- Используй  для проверки API платформы
- Используй  для поиска похожего кода
- Используй  для поиска в документации 1С
- Сохрани результат анализа в файл, а также в память через
