# Реализация задачи 1С

Выполни реализацию задачи по конфигурации 1С, используя **skill implement-1c-task** (8-этапный pipeline v2).

## Задача от пользователя:
$ARGUMENTS

---

## Инструкция

**Используй skill implement-1c-task** — единый источник методологии реализации.

Skill определяет:
- **Этап 0 Preflight (ОБЯЗАТЕЛЬНО)** — `debug_health_check(mode="probe")` через `1c-debug-hmr` + handshakes `edt-mcp` / `1c-mcp-crud` / `bsl-debug-server` → выбор режима pipeline (**Full** / **Full (no-BP)** / Code-only / Read-only verify / Read-only research). Без этого skill уходит в этапы где нужные tool-вызовы не существуют.
- 8 последовательных этапов (Подготовка → Валидация запросов → BSL → Статанализ → Верификация (вкл. Live BP-verification 5.x) → Тестирование → Документация → Git)
- 4 основных MCP-сервера: **EDT-MCP**, **1c-mcp-crud**, **bsl-debug-server**, **1c-debug-hmr** (последний опциональный, нужен для BP-verification Этапа 5.x)
- Вспомогательные: bsl-semantic-search (+ fallback для Этапа 1), bsl-code-search, bsl-platform-context
- Обязательные циклы проверки и правила

> **История версий скилла:** v2.7.0 (2026-05-11) — интеграция `1c-debug-hmr` в Этап 0 (`debug_health_check`) и Этап 5.x (Live BP-verification 8-шаговый протокол для каждой `[ADDED]`/`[MODIFIED]` точки + regression diff Этапа 5.y через `debug_session_diff`). Footer IMPLEMENTATION-PROGRESS.md получил маркер `<!-- debug_session_id: <UUID> -->` для baseline. Источник: [roadmap 260510](../../docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md). v2.3.0 (2026-05-05) — Этап 0 Preflight + fallback Этапа 1 через `bsl-semantic-search` / `bsl-code-search` / `Read` когда `edt-mcp` отсутствует. v2.1.1 (2026-04-14) — откат Этапа 0 «Активация Serena» после [углублённого аудита](../../docs/roadmap/260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md).

### 3 MCP-сервера — обязательное использование

#### EDT-MCP — чтение и запись кода
- `list_projects` → имя проекта (ПЕРВЫМ)
- `get_module_structure` / `read_method_source` → читать код перед модификацией
- `write_module_source` → записать изменения в модуль
- `get_project_errors` → проверить ошибки ПОСЛЕ каждой записи
- `validate_query` → проверить SQL ДО записи
- `find_references` → найти вызовы изменённых методов

#### 1c-mcp-crud — живые данные
- `get_metadata` → проверить имена полей, типы
- `execute_query` → прогнать SQL на живой базе (ДО и ПОСЛЕ)
- `execute_code` → подготовить/очистить тестовые данные

#### bsl-debug-server — анализ и отладка
- `bsl_analyze` → статический анализ BSL-кода (линтер)
- `bsl_execute` → проверить чистую логику (без базы, только OneScript)

### Обязательные циклы (НИКОГДА НЕ ПРОПУСКАТЬ)

1. **Перед записью SQL:** `validate_query` → `execute_query` (тест) → запись
2. **После записи кода:** `write_module_source` → `get_project_errors` → `read_method_source` (верификация)
3. **После всех изменений:** `bsl_analyze` → `get_project_errors` (общий) → `execute_query` (результат)
4. **После записи кода с [MODIFIED] (Этап 5.x BP-verification, режим Full):** `debug_set_breakpoint(line=<MODIFIED_LINE>)` → trigger через `execute_code` → `debug_ping` → `debug_stack_trace` (assert `frames[0].lineNo == MODIFIED_LINE`) → `debug_step(action="Continue")`. Fallback: `debug_break_on_next` → `force_recycle_rphost=True` (только dev-среда). При невозможности — SKIP с обоснованием в IMPLEMENTATION-PROGRESS.md, иначе блок перехода на Этап 6.

### Входные данные

Из $ARGUMENTS извлеки:
1. **ANALYSIS-REPORT.md** — файл отчёта анализа (от analyze-1c-task-v2)
2. **Путь к src/** — корень исходников конфигурации
3. Дополнительные инструкции (если есть)

### Результат

- BSL/XML изменения через EDT-MCP (write_module_source)
- Все SQL проверены: validate_query + execute_query на живых данных
- Статический анализ: bsl_analyze = 0 ошибок
- EDT проверка: get_project_errors = 0 ошибок
- **BP-verification (Этап 5.x, режим Full):** BP-trace для КАЖДОЙ `[ADDED]`/`[MODIFIED]` точки в IMPLEMENTATION-PROGRESS.md (или обоснованный SKIP). Footer `<!-- debug_session_id: <UUID> -->` для baseline следующего прогона.
- Тестирование на данных: execute_query подтверждает корректность
- IMPLEMENTATION-PROGRESS.md с результатами каждого этапа + блок «Debug session» (если режим Full)
- Git commit

---

## ВАЖНО:
- Применяется ПОСЛЕ analyze-1c-task-v2 — нужен готовый ANALYSIS-REPORT
- Вносить изменения строго в порядке из ANALYSIS-REPORT
- КАЖДЫЙ SQL → validate_query + execute_query ДО записи
- КАЖДАЯ запись → get_project_errors ПОСЛЕ записи
- КАЖДАЯ `[MODIFIED]` точка в режиме Full → BP-verification через `1c-debug-hmr` (Этап 5.x)
- Проведение документов = ПОЛЬЗОВАТЕЛЬ (Claude не имеет GUI)
- НЕ модифицировать файлы вне списка из ANALYSIS-REPORT

## Используемые MCP-инструменты

При вызове skill доступны (помимо стандартного набора):
- `mcp__edt-mcp__*` — основной путь
- `mcp__1c-mcp-crud__*` — живые данные
- `mcp__bsl-debugger__*`, `mcp__bsl-semantic-search__*`, `mcp__bsl-code-search__*` — анализ
- `mcp__1c-debug-hmr__*` — Этап 0 `debug_health_check` + Этап 5.x BP-verification + Этап 5.y regression diff (по умолчанию; plain `mcp__1c-debug__*` через `IMPLEMENT_1C_USE_PLAIN_DEBUG=true`)
