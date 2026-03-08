---
description: Активация проекта 1С в Serena с проверкой, git commit и опциональной индексацией (спрашивает пользователя)
argument_description: Имя проекта из списка Serena (например, 260119_GKSTCPLK-1981) или путь к проекту
---

# Активация проекта 1С (Hooks + Skills + MCP Integration)

Эта команда реализует полный workflow триады **Hooks + Skills + MCP**:

```
Команда → Serena Activate → Hook проверяет → Git Commit + Индексация (если нужно)
```

## Аргумент

**$ARGUMENTS** - имя проекта, тикет или путь:
- Полное имя проекта: `260119_GKSTCPLK-1981`
- Только тикет: `GKSTCPLK-1981` (поиск в реестре)
- Абсолютный путь: `D:\1С-Framework\src\projects\configuration\260119_GKSTCPLK-1981`

## Workflow

### Шаг 0: Поиск проекта в реестре (если указан тикет)

```python
# Если $ARGUMENTS не полный путь и не точное имя проекта
Read("cache/projects-registry.json")

# Найти проект по частичному совпадению
# Например: "GKSTCPLK-1981" найдёт "260119_GKSTCPLK-1981"
# Результат: полное имя проекта для Serena
```

### Шаг 1: Активация проекта в Serena

```python
mcp__serena__activate_project(project="<полное_имя_проекта>")
```

**Результат:** Hook `serena-index-checker.py` автоматически проверяет индексацию

### Шаг 2: Обработка результата хука

После активации проекта хук проверяет **четыре условия** (в порядке приоритета):
1. 🔴 **Memory задачи** - есть ли pending memory задачи (ОБЯЗАТЕЛЬНО)
2. 🔴 Есть ли незакоммиченные изменения в git (ОБЯЗАТЕЛЬНО)
3. ⚠️ Проиндексирован ли проект для семантического поиска (ОПЦИОНАЛЬНО - спрашивает)
4. ⚠️ **Serena memories** - есть ли memories для проекта (АВТОМАТИЧЕСКИ создаёт)

#### Вариант A: Всё в порядке (✅)

```json
{
  "continue": true,
  "systemMessage": "✅ Memory: нет pending memory задач\n✅ Git: нет незакоммиченных изменений\n✅ Проект проиндексирован..."
}
```

**Действие:** Готово к работе. Сообщить пользователю.

#### Вариант B: Есть pending Memory задачи (🔴 MANDATORY)

```json
{
  "continue": true,
  "systemMessage": "🔴 [MEMORY SAVE MANDATORY] Есть незавершённые memory задачи!",
  "claudeFallback": {
    "hook_name": "serena-index-checker",
    "task": "Выполнить memory задачи",
    "prompt": "Выполни ВСЕ pending memory задачи...",
    "priority": "high"
  }
}
```

**Действие:** Claude ОБЯЗАН выполнить memory задачи ПЕРВЫМ!

#### Вариант C: Есть незакоммиченные изменения (🔴)

```json
{
  "continue": true,
  "systemMessage": "🔴 [GIT COMMIT PENDING] Проект имеет незакоммиченные изменения!",
  "claudeFallback": {
    "hook_name": "serena-index-checker",
    "task": "Git commit изменений проекта",
    "prompt": "Выполни коммит изменений проекта...",
    "priority": "high"
  }
}
```

**Действие:** Claude ОБЯЗАН выполнить git commit автоматически!

#### Вариант D: Проект НЕ проиндексирован (⚠️ ОПЦИОНАЛЬНО)

```json
{
  "continue": true,
  "systemMessage": "⚠️ [INDEX OPTIONAL] Проект НЕ проиндексирован!",
  "claudeFallback": {
    "hook_name": "serena-index-checker",
    "task": "Спросить пользователя об индексации",
    "prompt": "СПРОСИТЬ пользователя перед индексацией...",
    "priority": "normal"
  }
}
```

**Действие:** Claude ОБЯЗАН СПРОСИТЬ пользователя хочет ли он индексацию!

#### Вариант E: Нет Serena memories (⚠️ АВТОМАТИЧЕСКИ)

```json
{
  "continue": true,
  "systemMessage": "⚠️ [MEMORIES MISSING] Проект НЕ имеет Serena memories!\n📁 Найдена папка docs/ (N файлов)",
  "claudeFallback": {
    "hook_name": "serena-index-checker",
    "task": "Создать Serena memories для проекта",
    "prompt": "Изучи структуру проекта и создай memories...",
    "priority": "high"
  }
}
```

**Действие:** Claude АВТОМАТИЧЕСКИ создаёт memories:
1. Изучает структуру проекта через `mcp__serena__list_dir`
2. Читает файлы из папки `docs/` (если есть задачи)
3. Создаёт `project_overview` memory
4. Если есть задачи - создаёт `project_tasks` memory

#### Вариант F: Нужны несколько действий (🔴 + 🔴 + ⚠️ + ⚠️)

Хук объединяет задачи в один `claudeFallback` (порядок: Memory → Git → Index → Serena Memories):
```json
{
  "claudeFallback": {
    "task": "Memory задачи + Git commit + Индексация + Serena Memories",
    "prompt": "ШАГ 1: Memory Tasks...\n---\nШАГ 2: Git Commit...\n---\nШАГ 3: Индексация...\n---\nШАГ 4: Serena Memories..."
  }
}
```

### Шаг 3: Автоматическое выполнение Memory задач (если требуется)

Если хук вернул `[MEMORY SAVE MANDATORY]`, выполнить:

```python
# 1. Сохранить каждую pending задачу в память
mcp__memory-ai__save_important_message(
    content="<содержимое задачи>",
    importance=0.8,
    category="session_progress"
)

# 2. Обновить статус задачи в active-todos.json
```

### Шаг 4: Автоматический Git Commit (если требуется)

Если хук вернул `[GIT COMMIT PENDING]`, выполнить:

```bash
# 1. Проверить статус
git status "<путь_к_проекту>"

# 2. Добавить изменения
git add "<путь_к_проекту>"

# 3. Создать коммит
git commit -m "feat(<имя_проекта>): обновление конфигурации проекта

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

### Шаг 5: Индексация (ОПЦИОНАЛЬНО - спросить пользователя!)

Если хук вернул `[INDEX OPTIONAL]`, **СНАЧАЛА спросить пользователя**:

```python
# ОБЯЗАТЕЛЬНО СПРОСИТЬ ПОЛЬЗОВАТЕЛЯ!
AskUserQuestion(
    questions=[{
        "question": "Проект не проиндексирован. Хотите выполнить индексацию для семантического поиска?",
        "header": "Индексация",
        "options": [
            {"label": "Да (Recommended)", "description": "Индексировать проект для семантического поиска BSL кода"},
            {"label": "Нет", "description": "Пропустить индексацию, продолжить без семантического поиска"}
        ],
        "multiSelect": False
    }]
)
```

**ТОЛЬКО если пользователь выбрал "Да"**, выполнить:

```python
# 1. BSL индексация
mcp__1c-docs-rag__index_bsl_project(
    project_path="<путь_к_проекту>",
    chunk_mode="smart",
    force=False
)

# 2. XML индексация
mcp__1c-docs-rag__index_xml_project(
    project_path="<путь_к_проекту>/src",
    xml_types=["subsystems", "forms", "rights", "languages"]
)
```

**Если пользователь выбрал "Нет"** - пропустить индексацию и продолжить.

### Шаг 6: Создание Serena Memories (если отсутствуют)

Если хук вернул `[MEMORIES MISSING]`, автоматически создать memories:

```python
# 1. Изучить структуру проекта
mcp__serena__list_dir(relative_path=".", recursive=False)
mcp__serena__list_dir(relative_path="docs", recursive=True)  # если есть

# 2. Прочитать задачи из docs/ (если найдены файлы с задачами)
Read("<путь_к_проекту>/docs/<файл_задачи>.md")

# 3. Создать project_overview memory
mcp__serena__write_memory(
    memory_name="project_overview",
    content="""# Обзор проекта <имя_проекта>

## Структура
- src/ - исходный код конфигурации 1С
- docs/ - документация и задачи

## Конвенции
- Язык: BSL (1С:Предприятие)
- Кодировка: UTF-8
"""
)

# 4. Создать project_tasks memory (если есть задачи)
mcp__serena__write_memory(
    memory_name="project_tasks",
    content="# Задачи проекта\n\n[Содержимое из docs/]"
)
```

### Шаг 7: Проверка результата

```python
# Показать статус индексации
mcp__1c-docs-rag__get_indexed_projects()
```

## Карта проектов

Полный список доступных проектов находится в реестре: `cache/projects-registry.json`

Для просмотра списка используй команду: `/list-projects`

| Тикет | Примерное имя |
|-------|---------------|
| `GKSTCPLK-2042` | `260121_GKSTCPLK-2042` |
| `GKSTCPLK-1981` | `260119_GKSTCPLK-1981` |
| `demo-accounting` | `demo-accounting` |

## Что показать пользователю

```
🚀 Активация проекта: $ARGUMENTS

📍 Шаг 1: Активация в Serena
   └─▶ mcp__serena__activate_project ✅

📍 Шаг 2: Проверка Memory задач (Hook)
   └─▶ [✅ Нет pending] или [🔴 MEMORY SAVE MANDATORY]

📍 Шаг 3: Memory Tasks (если требуется)
   └─▶ Сохранение в память ✅

📍 Шаг 4: Проверка git статуса (Hook)
   └─▶ [✅ Нет изменений] или [🔴 Git Commit Required]

📍 Шаг 5: Git Commit (если требуется)
   └─▶ git add + git commit ✅

📍 Шаг 6: Проверка индексации (Hook)
   └─▶ [✅ Проиндексирован] или [⚠️ Не проиндексирован]

📍 Шаг 7: Вопрос пользователю (если не проиндексирован)
   └─▶ "Хотите выполнить индексацию?" → Да/Нет

📍 Шаг 8: Индексация (только если пользователь выбрал "Да")
   └─▶ BSL: N файлов
   └─▶ XML: N файлов

📍 Шаг 9: Проверка Serena memories (Hook)
   └─▶ [✅ Memories есть] или [⚠️ MEMORIES MISSING]

📍 Шаг 10: Создание memories (автоматически если отсутствуют)
   └─▶ Проверка папки docs/
   └─▶ Создание project_overview
   └─▶ Создание project_tasks (если есть задачи)

🔍 Доступные инструменты:
- mcp__bsl-semantic-search__search_bsl_code - семантический поиск
- mcp__bsl-semantic-search__intelligent_search - интеллектуальный поиск
- mcp__serena__find_symbol - символы (Python/JS/TS)
- mcp__ast-grep-mcp__ast_grep - AST анализ BSL
```

## Критические правила

1. **Claude ОБЯЗАН** выполнить `claudeFallback` если хук его вернул
2. **Порядок выполнения:** Memory → Git → Index (строго в этом порядке!)
3. **Memory задачи ПЕРВЫМИ** - всегда выполнять до других задач
4. **СПРОСИТЬ пользователя** перед индексацией (пользователь может отказаться)
5. **После индексации** (если выбрана) проверить результат через `get_indexed_projects()`

## Интеграция (Hooks + Skills + MCP)

```
┌─────────────────────────────────────────────────────────────────┐
│  /activate-project                                               │
│      │                                                           │
│      ▼                                                           │
│  ┌────────────────┐                                              │
│  │ MCP: Serena    │  ← Активация проекта                        │
│  │ activate_proj  │                                              │
│  └───────┬────────┘                                              │
│          │                                                       │
│          ▼                                                       │
│  ┌────────────────┐                                              │
│  │ HOOK: serena-  │  ← PostToolUse проверяет git + индексацию   │
│  │ index-checker  │                                              │
│  └───────┬────────┘                                              │
│          │                                                       │
│          ▼                                                       │
│  ┌────────────────┐     ┌────────────────┐                       │
│  │ claudeFallback │ ──▶ │ Bash: git add  │  ← Авто-коммит       │
│  │ (если есть     │     │ git commit     │                       │
│  │  изменения)    │     └────────────────┘                       │
│  └───────┬────────┘                                              │
│          │                                                       │
│          ▼                                                       │
│  ┌────────────────┐     ┌────────────────┐                       │
│  │ claudeFallback │ ──▶ │ AskUserQuestion│  ← СПРОСИТЬ!         │
│  │ (если не инд.) │     │ Да/Нет?        │                       │
│  └───────┬────────┘     └───────┬────────┘                       │
│          │                      │                                 │
│          │              [Если Да]                                 │
│          │                      ▼                                 │
│          │              ┌────────────────┐                       │
│          └─────────────▶│ MCP: 1c-docs-  │  ← Индексация         │
│                         │ rag.index_bsl  │                       │
│                         └────────────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Примечания

- Команда реализует паттерн из `Hooks + Skills + MCP.md`
- Hook срабатывает автоматически на `mcp__serena__activate_project`
- Claude должен автономно обрабатывать `claudeFallback`
