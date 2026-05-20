# Project Context — 1С-Framework

> Контекст проекта для OpenSpec-валидации и AI-агентов.
> Полный контекст в [CLAUDE.md](../CLAUDE.md) (главный source of truth).

## Что это за репозиторий

**PDF Vector & Graph Framework** + **1С:Предприятие конфигурация Управление транспортом на ПЛК (ИБTransportManagementDevelop)**. Два больших домена в одном monorepo:

1. **Python framework** (`src/`) — RAG/Graph pipeline на LangChain/LangGraph, Qdrant, FastAPI, MCP server, BSL semantic search.
2. **1С BSL конфигурация** (submodule `ИБTransportManagementDevelop/Конфигурация`) — прикладное решение для приёмки/отгрузки зерна на ПЛК Сморгонь.

OpenSpec используется **только** для 1С-задач (бизнес-фичи): change-id обычно несёт префикс `gkstcplk-NNNN` из JIRA-номера.
