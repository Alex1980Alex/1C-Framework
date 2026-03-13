# Реализация задачи 1С

Выполни реализацию задачи по конфигурации 1С, используя **skill implement-1c-task** (8-этапный pipeline v2).

## Задача от пользователя:
$ARGUMENTS

---

## Инструкция

**Используй skill implement-1c-task** — единый источник методологии реализации.

Skill определяет:
- 8 последовательных этапов (Подготовка → Валидация запросов → BSL → Статанализ → Верификация → Тестирование → Документация → Git)
- 3 основных MCP-сервера: **EDT-MCP**, **1c-mcp-toolkit**, **bsl-debug-server**
- Вспомогательные: Serena, bsl-semantic-search, bsl-platform-context
- Обязательные циклы проверки и правила

### 3 MCP-сервера — обязательное использование

#### EDT-MCP — чтение и запись кода
- `list_projects` → имя проекта (ПЕРВЫМ)
- `get_module_structure` / `read_method_source` → читать код перед модификацией
- `write_module_source` → записать изменения в модуль
- `get_project_errors` → проверить ошибки ПОСЛЕ каждой записи
- `validate_query` → проверить SQL ДО записи
- `find_references` → найти вызовы изменённых методов

#### 1c-mcp-toolkit — живые данные
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
- Тестирование на данных: execute_query подтверждает корректность
- IMPLEMENTATION-PROGRESS.md с результатами каждого этапа
- Git commit

---

## ВАЖНО:
- Применяется ПОСЛЕ analyze-1c-task-v2 — нужен готовый ANALYSIS-REPORT
- Вносить изменения строго в порядке из ANALYSIS-REPORT
- КАЖДЫЙ SQL → validate_query + execute_query ДО записи
- КАЖДАЯ запись → get_project_errors ПОСЛЕ записи
- Проведение документов = ПОЛЬЗОВАТЕЛЬ (Claude не имеет GUI)
- НЕ модифицировать файлы вне списка из ANALYSIS-REPORT
