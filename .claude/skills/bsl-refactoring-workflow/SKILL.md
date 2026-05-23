---
name: bsl-refactoring-workflow
description: "Symbol-first workflow для рефакторинга BSL кода. 5-категорийная матрица выбора инструмента, интеграция с bsl_rename_symbol, bsl-symbol-editing, EDT-MCP. Заменяет Serena refactoring workflow."
version: 1.0.0
updated: 2026-04-19
tags: [1c, bsl, refactoring, workflow, rename, symbol]
triggers:
  - рефакторинг BSL
  - переименовать метод
  - переименовать переменную
  - rename symbol bsl
  - bsl refactoring
  - символ-первый рефакторинг
---

# BSL Refactoring Workflow — Symbol-first

Инструкции по выбору инструментов для рефакторинга BSL кода.
Базируется на [Serena evaluation methodology](https://oraios.github.io/serena/04-evaluation/000_evaluation-intro.html), адаптированной под наш стек.

## Decision Matrix — 5 категорий

Перед каждым рефакторингом — определить категорию задачи:

| Категория | Пример | Symbol-aware инструмент | Native Edit |
|---|---|---|---|
| **1. Navigation** | «Где вызывается `РассчитатьОстаток`?» | `find_references` (EDT-MCP), `bsl-semantic-search` | Grep если знаешь где |
| **2. Small edits** | Правка 1-2 строк, фикс бага | — | **Native Edit** |
| **3. Large edits** | Замена тела функции, новый метод | **`bsl-symbol-editing`** (replace/insert) | `write_module_source` напрямую |
| **4. Cross-file refactoring** | Переименование экспортного метода | **`bsl_rename_symbol`** (MCP) | — |
| **5. Workflow** | Обновление XML форм, конфигурация | — | **Native Edit** + EDT-MCP validate |

## Workflow: Переименование символа (Category 4)

### Шаг 1: Классификация символа

Определить тип символа для выбора backend'а:

| Тип символа | Пример | Backend | Уверенность |
|---|---|---|---|
| `local_variable` | `Перем Старый` внутри тела | ast-grep (in-file) | Высокая |
| `parameter` | Параметр процедуры | ast-grep (in-file) | Высокая |
| `module_local_proc` | Приватная процедура | ast-grep (in-file) | Высокая |
| `module_export_proc` | `Функция Метод() Экспорт` | ast-grep (cross-file по графу) | Средняя |
| `form_handler` | `&НаКлиенте Процедура ПриОткрытии` | ast-grep + XML | Средняя |
| `unknown` | Динамический вызов, `Выполнить()` | **manual tier** | Низкая |

### Шаг 2: Вызов bsl_rename_symbol

```
mcp__bsl-semantic-search__bsl_rename_symbol(
    uri: "file:///path/to/Module.bsl",
    line: 42,
    character: 10,
    new_name: "НовоеИмя",
    dry_run: true       // ВСЕГДА сначала dry_run
)
```

### Шаг 3: Анализ результата

**dry_run=True возвращает план изменений:**
- `status: "plan"` — показать план пользователю
- `files_affected` — список затронутых файлов
- `edits` — конкретные правки

**dry_run=False (подтверждение):**
- Передать `confirm_token` из dry_run
- Система применит изменения и верифицирует

### Шаг 4: Обработка Manual Tier

Если `status: "manual_required"` — автоматика не может безопасно переименовать:

1. Прочитать `manual_instruction.suggested_approach`
2. Использовать ручные инструменты:
   - **Grep** — найти все вхождения имени
   - **Edit** — заменить по файлам
   - **EDT GUI F2** — интерактивное переименование в EDT
   - **ast-grep --interactive** — полуавтоматический режим

## Workflow: Symbol-anchored editing (Category 3)

### Замена тела метода

```
1. skill: bsl-symbol-editing → bsl_replace_method_body
2. get_module_structure → найти метод
3. read_method_source → прочитать тело
4. write_module_source searchReplace → заменить
5. get_project_errors → верифицировать
```

### Добавление нового метода

```
1. skill: bsl-symbol-editing → bsl_insert_after_method
2. get_module_structure → найти якорный метод
3. write_module_source insertAfterLine → вставить
4. get_project_errors → верифицировать
```

## Интеграция с implement-1c-task

При реализации задач через `/implement-1c-task`:

| Этап implement | Когда привлекать bsl-refactoring-workflow |
|---|---|
| Этап 3 (Модификация) | При переименовании → Category 4 workflow |
| Этап 3 (Модификация) | При замене/добавлении методов → Category 3 workflow |
| Этап 5 (Верификация) | `find_references` для проверки влияния |

## Fallback Chain

Если основной инструмент недоступен:

```
bsl_rename_symbol (MCP)
  ↓ не отвечает
ast-grep-mcp (pattern matching)
  ↓ не отвечает
EDT-MCP find_references + manual Edit
  ↓ EDT не запущен
Grep + Edit (native, manual)
```

## Ограничения

- **Cross-file rename экспортных методов** — работает через ast-grep pattern matching + Neo4j граф, не через LSP
- **Form handlers** — затрагивают BSL + XML, требуют проверки обеих частей
- **Dynamic calls** (`Выполнить()`, `ОтправитьСобытие()`) — только manual tier
- **BSL LS** — отложен до R1.3, in-file only когда будет подключён
