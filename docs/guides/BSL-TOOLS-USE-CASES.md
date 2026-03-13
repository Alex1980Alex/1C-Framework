# BSL-инструменты: EDT-MCP vs ast-grep vs Serena

> Когда какой инструмент использовать для работы с BSL-кодом 1С:Предприятие

## Сводная таблица

| Задача | EDT-MCP | ast-grep | Serena | Рекомендация |
|--------|---------|----------|--------|-------------|
| Структура модуля | `get_module_structure` | `ast_grep(pattern)` | `get_symbols_overview` | **EDT-MCP** — точная карта с регионами и контекстом |
| Чтение метода | `read_method_source` | — | `find_symbol(include_body)` | **EDT-MCP** — по имени, без знания пути |
| Чтение модуля | `read_module_source` | — | Read файла | **EDT-MCP** — диапазон строк, не нужен полный путь |
| Запись BSL | `write_module_source` | — | `replace_symbol_body` | **EDT-MCP** — searchReplace + проверка синтаксиса |
| Типизация переменных | `get_symbol_info` | — | — | **Только EDT-MCP** — inferred types |
| Автодополнение | `get_content_assist` | — | — | **Только EDT-MCP** — контекст конфигурации |
| Переход к определению | `go_to_definition` | — | — | **Только EDT-MCP** — семантическая навигация |
| Поиск всех ссылок | `find_references` | — | — | **Только EDT-MCP** — код, формы, роли, подсистемы |
| Граф вызовов | `get_method_call_hierarchy` | — | — | **Только EDT-MCP** — callers/callees через BM-index |
| Паттерн-анализ BSL | — | `ast_grep(pattern)` | — | **Только ast-grep** — структурный поиск по AST |
| Валидация запросов | `validate_query` | — | — | **Только EDT-MCP** — семантика + метаданные |
| Ошибки проекта | `get_project_errors` | — | — | **Только EDT-MCP** — полный EDT анализ |
| Поиск по коду (текст) | `search_in_code` | — | `search_for_pattern` | **EDT-MCP** — regex + фильтр по типу метаданных |
| Поиск по коду (AST) | — | `ast_grep(pattern)` | — | **Только ast-grep** — структурные паттерны |
| Метаданные объектов | `get_metadata_details` | — | XML парсинг | **EDT-MCP** — native, полные свойства |
| Список модулей | `list_modules` | — | `find_file` | **EDT-MCP** — фильтр по типу объекта |
| Рефакторинг (rename) | `rename_metadata_object` | — | — | **Только EDT-MCP** — обновление всех ссылок |
| Рефакторинг (delete) | `delete_metadata_object` | — | — | **Только EDT-MCP** — очистка ссылок |
| Добавление реквизита | `add_metadata_attribute` | — | — | **Только EDT-MCP** |
| Скриншот формы | `get_form_screenshot` | — | — | **Только EDT-MCP** — PNG из WYSIWYG |
| Обновление БД | `update_database` | — | — | **Только EDT-MCP** |
| Запуск отладки | `debug_launch` | — | — | **Только EDT-MCP** |
| TODO/FIXME маркеры | `get_tasks` | — | — | **Только EDT-MCP** |
| Закладки | `get_bookmarks` | — | — | **Только EDT-MCP** |

## Когда использовать EDT-MCP

**Всегда**, когда EDT запущен и проект открыт. Это самый мощный инструмент (33 tools).

**Уникальные возможности (нет аналогов):**
- Типизация (`get_symbol_info`) — единственный способ узнать тип переменной в динамическом BSL
- Валидация запросов (`validate_query`) — проверка с учётом реальных метаданных конфигурации
- Граф вызовов (`get_method_call_hierarchy`) — семантический, через BM-index
- Рефакторинг (`rename/delete_metadata_object`) — безопасное переименование с обновлением всех ссылок
- Скриншоты форм (`get_form_screenshot`) — визуализация UI
- Деплой (`update_database`) + отладка (`debug_launch`)

**Лучшие сценарии:**
1. Code review — `get_project_errors` + `get_module_structure` + `get_symbol_info`
2. Навигация по коду — `go_to_definition` + `find_references` + `get_method_call_hierarchy`
3. Рефакторинг — `rename_metadata_object` + `find_references` (preview)
4. Написание кода — `get_content_assist` + `write_module_source` (с проверкой синтаксиса)
5. Анализ задачи — `get_metadata_details` + `list_modules` + `search_in_code`

## Когда использовать ast-grep

**Для структурного поиска паттернов в BSL**, когда нужен AST, а не текст.

**Уникальные возможности:**
- Поиск по структуре AST (не текстовый grep)
- Мета-переменные: `$NAME`, `$$$PARAMS`
- Работает без EDT (офлайн, легковесный)
- Поддержка BSL через кастомную грамматику

**Лучшие сценарии:**
1. Найти все процедуры с определённой сигнатурой:
   ```
   ast_grep(pattern="Процедура $NAME($$$PARAMS) Экспорт", language="bsl")
   ```
2. Найти антипаттерны (конкатенация строк вместо СтрШаблон):
   ```
   ast_grep(pattern="$A + $B + $C", language="bsl")
   ```
3. Найти все вызовы конкретного метода:
   ```
   ast_grep(pattern="ОбщегоНазначения.$METHOD($$$ARGS)", language="bsl")
   ```
4. Массовый анализ без запущенного EDT

**Ограничения:**
- Не знает типы переменных (только синтаксис)
- Не знает метаданные конфигурации
- Не может валидировать запросы 1С

## Когда использовать Serena

**Для работы с XML-структурой проекта и файловой навигации**, когда EDT не запущен.

**Сценарии:**
1. EDT не запущен — Serena как fallback для чтения BSL
2. XML-анализ — формы, роли, подсистемы (структура, не код)
3. Файловая навигация — `find_file`, `list_dir`
4. Быстрая замена тела метода — `replace_symbol_body` (без проверки синтаксиса)

**Ограничения для BSL:**
- 30-40% надёжность при анализе BSL-кода (XML парсинг vs семантика)
- Не знает типы, не валидирует запросы, нет графа вызовов

## Матрица принятия решений

```
Задача по BSL?
  ├── EDT запущен?
  │   ├── Да → EDT-MCP (всегда предпочтительнее)
  │   │   └── Нужен AST-паттерн? → ast-grep дополнительно
  │   └── Нет → ast-grep (паттерны) + Serena (навигация)
  └── Задача по метаданным/формам?
      ├── EDT запущен? → EDT-MCP (get_metadata_details, get_form_screenshot)
      └── Нет → Serena (XML парсинг)
```

## Комбинирование инструментов

### Пример 1: Полный анализ модуля
```python
# 1. Структура (EDT-MCP)
get_module_structure(project, "Documents/Взвешивание/ObjectModule.bsl")
# 2. Антипаттерны (ast-grep)
ast_grep(pattern="Запрос.Текст = $A + $B", language="bsl")
# 3. Ошибки (EDT-MCP)
get_project_errors(project, objects=["Документ.гкс_Взвешивание"])
```

### Пример 2: Рефакторинг метода
```python
# 1. Кто вызывает метод? (EDT-MCP)
get_method_call_hierarchy(project, module, "СтарыйМетод", direction="callers")
# 2. Где определён? (EDT-MCP)
go_to_definition(project, "МодульМенеджера.СтарыйМетод")
# 3. Переименовать (EDT-MCP)
rename_metadata_object(project, "CommonModule.Модуль", "НовоеИмя")
```

### Пример 3: Code Review
```python
# 1. Сводка ошибок (EDT-MCP)
get_problem_summary(project)
# 2. Критичные ошибки (EDT-MCP)
get_project_errors(project, severity="BLOCKER")
# 3. Конкатенация строк (ast-grep)
ast_grep(pattern='$A + " " + $B', language="bsl")
# 4. Типы подозрительных переменных (EDT-MCP)
get_symbol_info(project, file, line, column)
```
