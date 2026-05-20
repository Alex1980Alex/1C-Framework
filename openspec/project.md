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
