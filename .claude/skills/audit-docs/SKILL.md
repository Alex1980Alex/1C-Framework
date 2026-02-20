---
name: audit-docs
description: "Аудит кода vs документации vs скиллов. Сканирует кодовую базу, извлекает реализованные фичи, сравнивает с пользовательской документацией и скиллами, выводит отчёт и/или авто-обновляет. Триггеры: '/audit-docs', 'аудит документации', 'проверить покрытие', 'audit docs', 'check docs coverage', 'актуализировать документацию', 'обновить доки'. Параметры: --update (авто-обновление), --json (JSON формат), --fix (action items)."
---

# Audit Docs — аудит Code ↔ Documentation ↔ Skills

## Вызов

```
/audit-docs              # Отчёт о gaps (markdown)
/audit-docs --update     # Авто-обновить docs и skills
/audit-docs --json       # JSON формат
```

## Что делает

Скрипт `scripts/audit_docs_skills.py` сканирует 6 категорий фич из кода и сравнивает
с пользовательской документацией (`docs/framework documentation/`) и скиллами (`.claude/skills/`):

| Категория | Источник | Целевые доки | Целевой скилл |
|-----------|----------|-------------|---------------|
| REST API Endpoints | `src/api/routes/*.py` | `06.2_REST_API.md` | `framework-api` |
| MCP Tools | `src/mcp_server/server.py` | `06.4_MCP_Server.md` | `framework-mcp-ui` |
| Search Strategies | `src/pdf_framework/search/strategies/` | `04.1_Обзор_стратегий.md` | `search-pipeline-debug` |
| CLI Commands | `src/cli/main.py` | `06.3_CLI.md` | `framework-cli` |
| Config Variables | `src/pdf_framework/config/*.py` | `02.2_Конфигурация.md` | `framework-config` |
| Agent Types | `src/pdf_framework/agents/*/agent.py` | `05.5_Специализированные_агенты.md` | `agent-orchestration` |

## Алгоритм выполнения

### Режим `--fix` (отчёт)

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/audit_docs_skills.py --fix
```

Выводит:
- Summary таблицу с покрытием по категориям
- Список doc gaps (фичи в коде, но не в документации)
- Список skill gaps (фичи в коде, но не в скиллах)
- Action items: что добавить в какой файл

Отчёт сохраняется в `docs/analysis/AUDIT_DOCS_SKILLS.md`.

### Режим `--update` (авто-обновление)

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/audit_docs_skills.py --update --fix
```

Автоматически вставляет недостающие фичи в целевые файлы:

| Updater | Что делает |
|---------|-----------|
| `update_rest_api_doc` | Находит/создаёт таблицы по роутерам, вставляет endpoint-строки |
| `update_mcp_doc` | Вставляет строки в таблицу MCP tools |
| `update_strategies_doc` | Вставляет строки в таблицу стратегий |
| `update_config_doc` | Группирует по префиксу, вставляет в существующие/новые секции |
| `update_cli_doc` | Вставляет строки в таблицу CLI-команд |
| `update_agent_doc` | Добавляет секции агентов в 05.5_Специализированные_агенты.md |
| `update_skill_file` | Добавляет "Незадокументированные" секции перед ## Файлы |

После обновления автоматически перезапускает аудит для проверки покрытия.

### Режим `--json`

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/audit_docs_skills.py --json --stdout
```

JSON с полями: `timestamp`, `summary`, `doc_gaps`, `skill_gaps`, `features`.

## Make targets

```bash
make audit-docs          # = --fix
make audit-docs-json     # = --json --stdout
make audit-docs-update   # = --update --fix
```

## Интерпретация результатов

| Покрытие | Статус | Действие |
|----------|--------|----------|
| 100% | Отлично | Ничего не нужно |
| 90-99% | Хорошо | Несколько пропущенных фич — добавить вручную или `--update` |
| 70-89% | Внимание | Значительные gaps — запустить `--update` |
| < 70% | Критично | Много незадокументированных фич — запустить `--update` + ручная проверка |

## Ограничения

- Аудит проверяет только **упоминание** фичи в тексте (case-insensitive), не глубину описания
- Agent types проверяются по имени директории (`rag`, `multi`, `plan_execute`), а не по классу
- Config vars извлекаются из Pydantic Settings классов (prefix + field_name)
- Авто-обновление добавляет **строки в таблицы**, но не создаёт подробные описания — нужна ручная доработка

## Файлы

| Файл | Назначение |
|------|-----------|
| `scripts/audit_docs_skills.py` | Основной скрипт (6 экстракторов + 7 updaters) |
| `docs/analysis/AUDIT_DOCS_SKILLS.md` | Последний отчёт |
| `docs/framework documentation/` | Целевая документация (45 файлов) |
| `.claude/skills/*/SKILL.md` | Целевые скиллы |
