---
description: Активация проекта в Serena. Опционально — используется когда ты хочешь работать с project-specific memories или навигацией через LSP.
argument_description: Имя проекта (например, 260119_GKSTCPLK-1981), тикет (GKSTCPLK-1981) или абсолютный путь
---

# Активация проекта в Serena

> **История:** раньше эта команда реализовывала большой workflow через хук `serena-index-checker.py` (проверка git → индексация → memories). Хук больше не существует (удалён при переработке hook-инфраструктуры), поэтому команда сведена к минимуму. Контекст удаления — см. [Serena Audit](../../docs/roadmap/260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md).
>
> **Когда эта команда реально нужна:**
> - Ты собираешься использовать Serena LSP-инструменты (`find_symbol`, `find_referencing_symbols`, `replace_symbol_body`) на **Python-коде фреймворка** — на BSL они не работают, там EDT-MCP.
> - Ты хочешь прочитать или записать project-specific `memories` в `.serena/memories/`.
>
> **Когда НЕ нужна:** реализация задачи 1С через `/implement-1c-task` — там используются EDT-MCP + 1c-mcp-crud + bsl-debug-server, Serena не требуется.

## Аргумент

**$ARGUMENTS** — имя проекта, тикет или путь:

- Полное имя проекта: `260119_GKSTCPLK-1981`
- Только тикет: `GKSTCPLK-1981` (ищется в `cache/projects-registry.json`)
- Абсолютный путь: `D:\1С-Framework\src\projects\configuration\260119_GKSTCPLK-1981`

## Workflow

### Шаг 1: Определить имя проекта

Если `$ARGUMENTS` — не полный путь и не точное имя, искать в реестре:

```python
Read("cache/projects-registry.json")
# найти проект по частичному совпадению (например, "GKSTCPLK-1981" → "260119_GKSTCPLK-1981")
```

### Шаг 2: Активировать проект

```python
mcp__serena__activate_project(project="<полное_имя_проекта>")
```

### Шаг 3: Прочитать memories (если есть)

```python
memories = mcp__serena__list_memories()
# Если memories найдены — прочитать project_overview и любые другие релевантные задаче
if memories:
    mcp__serena__read_memory("project_overview")  # если существует
```

**Замечание:** memories есть только у тех проектов, где ты их когда-то сам записал через `write_memory`. Большинство 1С-проектов их не имеют, и это нормально — основной контекст задачи в `ANALYSIS-REPORT.md`.

### Шаг 4: (Опционально) Записать memory для будущих сессий

Если в процессе работы обнаружил что-то, что стоит помнить в следующих сессиях:

```python
mcp__serena__write_memory(
    memory_name="feature-X-gotcha",
    content="Краткая заметка о неочевидной детали"
)
```

Memories живут в `.serena/memories/<имя>.md` и гитигнорятся автоматически (`.serena/.gitignore`) — это **личный** слой заметок, не засоряет project docs.

## Что эта команда БОЛЬШЕ НЕ делает

Раньше (через несуществующий хук `serena-index-checker.py`) обещалось:

- ❌ **Автоматическая проверка git и принудительный коммит** — теперь это отдельный `git-commit-enforcer` Stop-хук, который сработает сам при попытке закончить сессию
- ❌ **Проверка и принудительное выполнение pending memory-задач** — теперь это `session-memory-save` и `task-enforcer`
- ❌ **AskUserQuestion про индексацию** — индексация `bsl_code_v2` делается отдельным скриптом `scripts/index-*.py`, не через активацию
- ❌ **Автосоздание `project_overview` и `project_tasks` memories** — делается вручную через `write_memory` по мере надобности
- ❌ **Обработка `claudeFallback`** — хук не существует, fallback не возвращается

Не нужно ждать от этой команды этих действий. Соответствующие гарантии дают другие компоненты (enforcer-хуки, отдельные скрипты индексации).

## Ограничения Serena на этом проекте

- **`.serena/project.yml` → `language: bsl`** — BSL не поддерживается Serena (нет LSP). Все LSP-инструменты (`find_symbol`, `find_referencing_symbols`, `replace_symbol_body`, `insert_after_symbol`, `get_symbols_overview`) **мертвы**.
- Работают только language-agnostic тулы: `list_dir`, `find_file`, `search_for_pattern`, `read_memory`/`write_memory`, `think_about_*`.
- Если нужны LSP-тулы на **Python-коде фреймворка** — смена `language: bsl` → `python` в `.serena/project.yml` оживляет их на `src/pdf_framework/`, `src/memory/`, `.claude/hooks/` (337 файлов). Это **отдельное решение**, см. Решение 2 в [Serena Audit](../../docs/roadmap/260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md).

## Примеры использования

```
/activate-project 260119_GKSTCPLK-1981
/activate-project GKSTCPLK-1981
/activate-project D:\1С-Framework\src\projects\configuration\260119_GKSTCPLK-1981
```
