# Маппинг MCP-инструментов на этапы реализации

## EDT-MCP (основной — чтение/запись кода)

| Этап | Инструмент | Назначение |
|---|---|---|
| 1 Подготовка | `list_projects` | Получить имя проекта EDT (ПЕРВЫМ!) |
| 1 Подготовка | `get_module_structure` | Обзор методов модуля (актуальные строки) |
| 1 Подготовка | `read_method_source` | Прочитать тело метода перед модификацией |
| 2 Валидация | `validate_query` | Проверить синтаксис SQL ДО записи |
| 3 BSL | `write_module_source` | Записать изменённый код |
| 3 BSL | `get_project_errors` | Проверить ошибки ПОСЛЕ записи |
| 3 BSL | `get_content_assist` | Автодополнение имён перечислений/регистров |
| 5 Верификация | `find_references` | Найти вызовы изменённых методов |
| 5 Верификация | `get_project_errors` | Финальная проверка ошибок |

## 1c-mcp-toolkit (живые данные)

| Этап | Инструмент | Назначение |
|---|---|---|
| 1 Подготовка | `get_metadata` | Проверить имена полей, типы реквизитов |
| 2 Валидация | `execute_query` | Прогнать SQL на живой базе (тест) |
| 6 Тестирование | `execute_code` | Подготовить тестовые данные |
| 6 Тестирование | `execute_query` | Проверить результат после проведения |
| 6 Тестирование | `execute_code` | Очистить тестовые данные |

## bsl-debug-server (анализ и отладка)

| Этап | Инструмент | Назначение |
|---|---|---|
| 4 Статанализ | `bsl_analyze` | Линтер для BSL-кода |
| 4 Статанализ | `bsl_execute` | Проверить чистую логику (без базы) |
| 4 Статанализ | `bsl_debug_start/step/variables` | Пошаговая отладка |

## bsl-semantic-search refactor (рефакторинг, добавлено 2026-04-19)

Активируется когда задача содержит рефакторинг (rename / замена тела / удаление с проверкой references).
Routing matrix v2 (`src/bsl/semantic_search/refactor/routing_matrix.yaml`) выбирает backend автоматически.

| Этап | Инструмент | Назначение |
|---|---|---|
| 1 Подготовка | `bsl_find_references` | Cross-file поиск вызовов (primary, заменяет EDT-MCP `find_references` для rename-сценариев) |
| 3 BSL | `bsl_rename_symbol` | Переименование функции/переменной с verification (dry_run → confirm_token → apply) |
| 3 BSL | `bsl_replace_method_body` | Атомарная замена тела метода (без line drift после предыдущих Edit) |
| 3 BSL | `bsl_insert_after_method` | Вставка нового метода после якорного |
| 3 BSL | `bsl_insert_before_method` | Вставка нового метода перед якорным |
| 5 Верификация | `bsl_safe_delete_symbol` | Удаление с проверкой references (0 callers = safe) |

**Когда применять:**
- Rename процедуры/переменной/параметра → `bsl_rename_symbol` (ВСЕГДА dry_run first)
- Замена тела существующего метода → `bsl_replace_method_body` (вместо ручного `write_module_source` с line numbers)
- Добавление нового метода рядом с существующим → `bsl_insert_after_method` (якорь стабильнее, чем startLine)

**Когда НЕ применять:**
- Добавление нового функционала (новые реквизиты, формы, подсистемы) → EDT-MCP `write_module_source` напрямую
- Точечная правка 1-2 строк внутри метода → EDT-MCP `write_module_source` с `searchReplace`
- Динамические вызовы (`Выполнить("Метод()")`) → manual tier (routing matrix вернёт `manual_required`)

**Полный workflow:** [.claude/skills/bsl-refactoring-workflow/SKILL.md](../../bsl-refactoring-workflow/SKILL.md)
**Symbol-anchored editing:** [.claude/skills/bsl-symbol-editing/SKILL.md](../../bsl-symbol-editing/SKILL.md)

## Ограничения

- **bsl-debug-server**: OneScript, НЕ 1С:Предприятие. Нет доступа к Документы/Регистры/Справочники
- **1c-mcp-toolkit**: COM-подключение, НЕ GUI. Нельзя проводить документы, нажимать кнопки
- **EDT-MCP**: требует запущенный 1C:EDT с плагином EDT-MCP (порт 8765)

## Обязательные циклы

```
SQL:  validate_query → execute_query (тест) → write_module_source
Код:  write_module_source → get_project_errors → read_method_source (верификация)
Итог: bsl_analyze → get_project_errors (общий) → execute_query (результат)
```

## Gotchas (из опыта)

- EDT-MCP project name: `list_projects` возвращает имя проекта в workspace, не имя задачи
- SQL `ПустаяСсылка`: БЕЗ скобок в ЗНАЧЕНИЕ(): `ЗНАЧЕНИЕ(Перечисление.xxx.ПустаяСсылка)` — НЕ `ПустаяСсылка()`
- SQL `.Синоним`: enum values НЕ имеют `.Синоним` — запрос упадёт
- `get_project_errors`: проверять severity="ERROR", WARNING допустимы
- `write_module_source`: после записи строки сдвигаются — использовать `read_method_source` для верификации
