---
name: bsl-symbol-editing
description: "Symbol-anchored editing для BSL модулей через EDT-MCP. Обёртки над read_method_source/write_module_source: замена тела метода, вставка до/после метода. Без LSP — работает через EDT."
version: 1.0.0
updated: 2026-04-19
tags: [1c, bsl, refactoring, edt-mcp, symbol-editing]
triggers:
  - заменить тело метода
  - вставить метод после
  - вставить метод перед
  - replace method body
  - insert after method
  - insert before method
  - bsl symbol editing
---

# BSL Symbol-Anchored Editing

Редактирование BSL модулей на уровне символов (методов/процедур/функций) через EDT-MCP.
Не требует LSP — работает поверх существующего EDT.

## Доступные операции

### 1. `bsl_replace_method_body` — Замена тела метода

Заменяет всё тело указанного метода новым содержимым.

```
Шаги:
1. mcp__edt-mcp__get_module_structure(project, modulePath)
   → получить карту методов (имена, startLine, endLine)
2. mcp__edt-mcp__read_method_source(project, modulePath, methodName)
   → прочитать текущее тело для подтверждения
3. mcp__edt-mcp__write_module_source(
     project, modulePath,
     mode: "searchReplace" | startLine/endLine,
     oldText: "<текущее тело>",
     newText: "<новое тело>"
   )
4. mcp__edt-mcp__get_project_errors(project)
   → проверить отсутствие синтаксических ошибок
```

### 2. `bsl_insert_after_method` — Вставка кода после метода

Вставляет новые процедуры/функции или код после конца указанного метода.

```
Шаги:
1. mcp__edt-mcp__get_module_structure(project, modulePath)
   → найти endLine целевого метода
2. mcp__edt-mcp__read_method_source(project, modulePath, methodName)
   → подтвердить последнюю строку
3. mcp__edt-mcp__write_module_source(
     project, modulePath,
     mode: "insertAfterLine",
     line: <endLine>,
     content: "<код для вставки>"
   )
4. mcp__edt-mcp__get_project_errors(project)
```

### 3. `bsl_insert_before_method` — Вставка кода перед методом

Вставляет новые процедуры/функции перед началом указанного метода.

```
Шаги:
1. mcp__edt-mcp__get_module_structure(project, modulePath)
   → найти startLine целевого метода
2. mcp__edt-mcp__write_module_source(
     project, modulePath,
     mode: "insertAfterLine",
     line: <startLine - 1>,
     content: "<код для вставки>"
   )
   — ИЛИ mode: "searchReplace" с добавлением перед сигнатурой метода
3. mcp__edt-mcp__get_project_errors(project)
```

## Когда использовать

| Ситуация | Операция | Альтернатива |
|---|---|---|
| Заменить логику метода целиком | `bsl_replace_method_body` | Native Edit для правки 1-2 строк |
| Добавить новый метод в модуль | `bsl_insert_after_method` | `write_module_source` напрямую |
| Добавить метод перед конкретным | `bsl_insert_before_method` | — |
| Удалить метод | `bsl_replace_method_body` с пустым телом | — |

## Предпосылки

- **EDT запущен** и проект открыт (иначе EDT-MCP не отвечает)
- **Имя проекта** известно (получить через `list_projects`)
- **Путь к модулю** известен (например: `Catalogs/Контрагенты/Ext/ObjectModule.bsl`)

## Взаимодействие с другими инструментами

- **bsl_rename_symbol** (MCP) — для переименования через ast-grep/multilspy
- **ast-grep-mcp** — для поиска паттернов перед редактированием
- **find_references** (EDT-MCP) — для проверки влияния изменений
- **bsl-semantic-search** — для навигации по зависимостям (Neo4j граф)
