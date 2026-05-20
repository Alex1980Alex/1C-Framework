# Project Context — 1С-Framework

> Контекст проекта для OpenSpec-валидации и AI-агентов.
> Полный контекст в [CLAUDE.md](../CLAUDE.md) (главный source of truth).

## Что это за репозиторий

**PDF Vector & Graph Framework** + **1С:Предприятие конфигурация Управление транспортом на ПЛК (ИБTransportManagementDevelop)**. Два больших домена в одном monorepo:

1. **Python framework** (`src/`) — RAG/Graph pipeline на LangChain/LangGraph, Qdrant, FastAPI, MCP server, BSL semantic search.
2. **1С BSL конфигурация** (submodule `ИБTransportManagementDevelop/Конфигурация`) — прикладное решение для приёмки/отгрузки зерна на ПЛК Сморгонь.

OpenSpec используется **только** для 1С-задач (бизнес-фичи): change-id обычно несёт префикс `gkstcplk-NNNN` из JIRA-номера.

## Tech stack

### 1С-сторона (главный target SDD)

- **Платформа**: 1С:Предприятие 8.3.27
- **Конфигурация**: BSL + EDT (Eclipse Development Tools)
- **Расположение исходников**: `ИБTransportManagementDevelop/Конфигурация/src/` (submodule)
- **Документация задач**: `configuration/<task-folder>/docs/<sub-task>/` (submodule per JIRA-задача)
- **Тесты**: VA BDD (`features/`), Vanessa Automation runner (`tools/vanessa/`)

### Python-сторона (вспомогательная)

- Python 3.11+, async-first
- LangChain / LangGraph / FastAPI / Typer / MCP
- Qdrant (Qwen3-Embedding-8B 4096d, alignment 2026-04-30)

## MCP-серверы для разработки 1С

| Сервер | Назначение |
|---|---|
| `edt-mcp` | чтение/запись BSL-модулей, валидация запросов, EDT errors |
| `1c-mcp-crud` | live запросы/код к инфобазе, метаданные |
| `bsl-debugger` | OneScript static analysis |
| `bsl-semantic-search` | semantic search по 3900+ BSL-модулям (Qdrant + Neo4j call graph) |
| `1c-debug-hmr` | live BP-trace через RDBG (default since 2026-05-10, HMR wrapper) |

Preflight для любой 1С-задачи: `python scripts/smoke_test_implement_1c_task.py --json` (exit 0 = Full mode).

## Структура репозиториев (3-уровневая, важно для git)

```
1С-Framework/                                       ← MAIN repo (level 1, единственный .git/)
├── configuration/                                  ← level 2: обычная папка main
│   └── <task-folder>/                              ← level 3: SUBMODULE (gitlink)
│       └── docs/<sub-task>/ANALYSIS-REPORT.md + IMPLEMENTATION-PROGRESS.md
├── ИБTransportManagementDevelop/                   ← level 2: обычная папка main
│   └── Конфигурация/                               ← level 3: SUBMODULE (gitlink) — BSL src/
└── openspec/changes/<change-id>/                   ← в main repo
```

Одна 1С-задача = **3 коммита** (BSL submodule, docs submodule, main repo gitlinks bump). Подробности см. в skill `implement-1c-task` v2.7 → Этап 8.

## Ключевые конвенции

- **JIRA-теги в BSL-коде**: `// GKSTCPLK-NNNN` либо `// GKSTCPLK-NNNN Начало` / `// GKSTCPLK-NNNN Конец` для блоков.
- **Имена объектов 1С** имеют префикс `гкс_` (например `гкс_РегистрацияНаПЛК`, `гкс_СтатусыДопускаВагоновКВскрытию`).
- **kebab-case ASCII** для openspec change-id (не cyrillic). Pre-existing исключений нет.
- **Шаблоны процедур**: «зелёный коридор» (`гкс_НастройкиОтключенияВходногоКонтроляКачества`) и «усиленный контроль» (`гкс_НастройкиУсиленногоКонтроляКачества`) — образцы для регистров-настроек.
- **RLS-паттерн**: `РазрешитьЧтениеИзменение ГДЕ ЗначениеРазрешено(<главное измерение>)`.
- **Periodicity**: настройки не периодические (mainTable=true, измерение `ДатаНачала` как часть PK для эмуляции истории).

## Ограничения

- Кириллические пути в git → требуют `git -c core.quotepath=false` для читаемости status (CLAUDE.md запрещает менять `git config` глобально).
- EDT-MCP `write_module_source` правит **только** исходники проекта; для применения к live-инфобазе обязателен `mcp__edt-mcp__update_database` (см. Этап 6 в skill implement-1c-task).
- `1c-mcp-crud:execute_code` запрещает `Возврат` вне процедуры/функции (top-level wrap'ит код анонимно). Workaround: `Если/Иначе` ветки с `Результат =` (см. skill implement-1c-task Известные ограничения).

## Source of truth

При любых противоречиях между OpenSpec change'ом и [CLAUDE.md](../CLAUDE.md) — побеждает CLAUDE.md (живой документ с актуальными ограничениями и архитектурными решениями).
