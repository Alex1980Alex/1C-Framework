# CLAUDE.md — PDF Vector & Graph Framework

## Project Overview

Framework for intelligent PDF document processing using Vector databases (semantic search, RAG) and Graph databases (knowledge graphs, entity relations).

## Tech Stack

- **Python 3.11+**
- **LangChain** — LLM integration, tools, chains
- **LangGraph** — Agent orchestration, state management
- **ChromaDB / Qdrant / FAISS** — Vector stores
- **Neo4j / NetworkX** — Graph stores
- **MCP** — Model Context Protocol server
- **FastAPI** — REST API

## Project Structure

```
src/
  pdf_framework/      # Core library
    loaders/          # PDF loading (pymupdf, pdfplumber)
    processing/       # Splitting, cleaning, metadata
    embeddings/       # Embedding providers
    vector_store/     # Vector DB (base + providers)
    graph_store/      # Graph DB (base + providers)
    search/           # Unified hybrid search
    agents/           # LangGraph agents
    tools/            # LangChain tools
    chains/           # LangChain chains
    schemas/          # Pydantic data models
  mcp_server/         # MCP server for Claude Code
  api/                # REST API (FastAPI)
  cli/                # CLI interface (Typer)
```

## Hooks + Skills + MCP — ФУНДАМЕНТАЛЬНЫЙ ПРИНЦИП

**ВСЯ работа строится через триаду — на ЛЮБОМ уровне:**

```
СОБЫТИЕ (что произошло?)  →  ЗНАНИЕ (что делать?)  →  ИНСТРУМЕНТ (чем сделать?)
```

| Уровень | Событие | Знание | Инструмент |
|---------|---------|--------|------------|
| Разговор | Обсуждение | Решение | Реализация |
| Автоматизация | Hook (.py) | Skill (.md) | MCP Tool |

**Если решение принято в разговоре — оно ДОЛЖНО стать артефактом (Hook/Skill/MCP/MEMORY). Иначе — потеряно.**

### Правило: КАЖДАЯ работа оставляет артефакты триады

Не просто "думай через триаду" — **закрепляй результат**, чтобы следующие сессии использовали его автоматически:

| Ситуация | Действие | Артефакт |
|----------|----------|----------|
| Исследовал тему по 1С | Сохрани в кеш | `skills/1c-doc-research/cache/<тема>.md` |
| Исследовал технологию | Сохрани в кеш | `skills/tech-research/cache/<тема>.md` |
| Нашёл повторяющийся паттерн | Создай/обнови hook | `hooks/<name>.py` + settings.json |
| Описал процедуру/workflow | Создай/обнови skill | `skills/<name>/SKILL.md` |
| Добавил API-функциональность | Добавь MCP tool | `src/mcp_server/server.py` |
| Обнаружил баг/workaround | Обнови MEMORY.md | `memory/MEMORY.md` |

### Самоусиливающийся цикл:
```
Работа → артефакт (hook/skill/cache) → следующая сессия использует →
→ лучше работает → новый артефакт → ...
```

### Чеклист перед завершением задачи:
1. Новые знания закешированы? (1С → `1c-doc-research/cache/`, Tech → `tech-research/cache/`)
2. Повторяющееся действие автоматизировано? (Hook)
3. Процедура описана для переиспользования? (Skill)
4. Внешний инструмент доступен через MCP? (Tool)
5. Баги/паттерны записаны? (MEMORY.md)

### Не каждая задача требует все 3 компонента:
- **Hooks + Skills** — автоматизация workflow (детекция → инструкция)
- **Skills + MCP** — доменное знание + инструменты (исследование → API)
- **Только Skill** — процедурное знание (шаблон, чеклист)
- **Только Hook** — простой триггер (валидация, подсказка)

### Домены знаний (кеш):
- **1С-платформа** → `1c-doc-research` (8 категорий, its.1c.ru, §X.Y)
- **RAG/ML/Python** → `tech-research` (7 категорий, official docs, GitHub)

### ФАБРИКА ТРИАДЫ — главный процесс

**Любое решение проходит через 5 шагов фабрики** (полное описание в skill `triad-factory`):

```
ВХОД → ШАГ 1: Классификация (5 вопросов Q1-Q5)
     → ШАГ 2: Формула (комбинация Hook/Skill/MCP/Cache/Enforcer)
     → ШАГ 3: Генерация (создать файлы по шаблонам)
     → ШАГ 4: Связывание (settings.json, реестры, MEMORY)
     → ШАГ 5: Верификация (тесты) → ВЫХОД
```

**Быстрая классификация:**

| Вопрос | Да → |
|--------|------|
| Автоматически на событие? | Hook |
| Есть процедура/знание? | Skill |
| Нужен внешний инструмент? | MCP |
| Накапливать знания? | Cache |
| Принудительно выполнять? | Enforcer |

### Создание нового компонента:
- **Любое решение** → пропусти через Фабрику (ШАГ 1-5) из skill `triad-factory`
- Hook → используй skill `create-hook` (шаблон + чеклист)
- Skill → используй skill `doc-to-skill` (конвертер)
- Домен → Фабрика определит формулу: Hook + Skill + Cache + Enforcer

**Фабрика (программа):** skill `triad-factory` | **Реализация (знание):** skill `hooks-skills-mcp-triad`

---

## Development Rules

- All store implementations extend abstract base classes in `*/base.py`
- Use Pydantic models from `schemas/` as data contracts
- Async-first: all I/O operations are `async`
- Configuration via `pydantic-settings` (`.env` file)
- Provider pattern: easy to swap Vector/Graph/Embedding providers

## Ralph Wiggum — Autonomous Loop Rules

When running inside a Ralph Wiggum loop (automated iterative execution):

### Iteration Behavior
- At the start of each iteration, check `git log --oneline -5` and `git diff --stat` to understand what was done previously
- Prioritize: critical changes first, cosmetic changes last
- Commit each meaningful change separately with message prefix `[RALPH]`
- If a task seems impossible after 3 attempts — explain why instead of infinite retries

### Completion Protocol
- When ALL task criteria are met, include the marker `RALPH_DONE` at the end of the response
- Alternative markers: `TASK_COMPLETE_OK`, `ALL_DONE`
- Never output the marker if ANY criterion is unmet
- Stop Hook will block premature stops and provide feedback

### Safety
- Do not modify files outside the specified scope
- Do not delete data/ directory contents without explicit instruction
- Always work in a git branch for large changes
- Prefer `git stash` over destructive operations

### Available Templates
Run autonomous loops via `scripts/ralph.bat` (Windows) or `scripts/ralph.sh` (Linux/Mac):
- `--template reindex` — verify full indexing pipeline
- `--template test-coverage` — increase test coverage to 80%+
- `--template evaluation` — RAGAS evaluation suite
- `--template documentation` — add docstrings to public API
- `--template lint` — fix all linter warnings

## Documentation Research Workflow

**Документация 1С:Предприятие 8.3.27 — ЭТАЛОН.** Это первоисточник, основа любого ответа.

When the user asks about 1C platform, objects, or any technology:

1. **ПЕРВЫМ — документация 1С** (POST /search/ask, strategy=hybrid, rerank=true)
2. **Параллельно — внешние источники** для ДОПОЛНЕНИЯ:
   - Приоритет 2: `its.1c.ru`, `v8.1c.ru` (официальные ресурсы вендора)
   - Приоритет 3: `infostart.ru` (экспертное сообщество, проверенный источник)
   - Приоритет 4: GitHub (stars > 100), official docs, arxiv (для tech)
3. **Верификация** — внешние данные ДОЛЖНЫ соответствовать документации. При конфликте — верна документация
4. **Атрибуция** — КАЖДЫЙ факт помечен источником: `[Документация 8.3.27, §X.Y]`, `[its.1c.ru]`, `[infostart.ru]`
5. **Источники** — ВСЕ использованные источники перечислены в конце ответа с указанием что из каждого взято

See `.claude/skills/1c-doc-research/SKILL.md` for full research protocol.

## Knowledge Cache

Два домена кеша знаний, каждый со своим шаблоном:

| Домен | Skill | Кеш | Категорий | Шаблон |
|-------|-------|-----|-----------|--------|
| **1С** | `1c-doc-research` | `skills/1c-doc-research/cache/` | 8 | object_type, §X.Y, BSL |
| **Tech** | `tech-research` | `skills/tech-research/cache/` | 7 | domain, version, pip install |

- **Фаза 0**: перед поиском проверить кеш (`cache/_index.json`) — если topic свежий (< 7 дней), использовать
- **Фаза 5**: после исследования сохранить результат в соответствующий кеш
- **Инвалидация**: по возрасту (> 7 дней → quick verify), по запросу пользователя
- **Хуки**: `knowledge-cache-reminder` создаёт mandatory задачу → `task-enforcer` блокирует stop

## Active Skills

| Skill | Тип | Назначение |
|-------|-----|-----------|
| `1c-doc-research` | Доменный | Исследование 1С: 5 фаз, кеш (8 категорий), атрибуция |
| `tech-research` | Доменный | Исследование RAG/ML/Python: 5 фаз, кеш (7 категорий) |
| `pdf-knowledge` | Доменный | MCP-инструменты для PDF search и indexing |
| `doc-to-skill` | Процедурный | Конвертер документации → SKILL.md |
| `create-hook` | Процедурный | Шаблон + чеклист для создания хуков |
| `triad-factory` | Программа | Фабрика: алгоритм создания компонентов (ШАГ 1-5, Q1-Q5) |
| `hooks-skills-mcp-triad` | Знание | Реализация триады в проекте (таблицы, pipelines) |
