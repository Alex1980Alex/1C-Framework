# Дорожная карта миграции: 1C-Enterprise_Framework -> 1С-Framework

**Дата создания:** 2026-03-06
**Источник:** `D:\1C-Enterprise_Framework` (запуск: `scripts\claude.bat`, профиль #7 lazy-mcp)
**Целевой проект:** `D:\1С-Framework` (PDF Vector & Graph Framework, v0.33+)
**Статус:** ПЛАНИРОВАНИЕ
**Launcher:** `claude --strict-mcp-config --mcp-config "D:\1C-Enterprise_Framework\.mcp\lazy-mcp.json"`

---

## Оглавление

1. [Резюме](#1-резюме)
2. [Инвентаризация компонентов источника](#2-инвентаризация-компонентов-источника)
3. [Целевая архитектура](#3-целевая-архитектура)
4. [Фазы миграции (Tier 1-5)](#4-фазы-миграции)
5. [Детальный план по компонентам](#5-детальный-план-по-компонентам)
6. [Конфигурация и MCP](#6-конфигурация-и-mcp)
7. [Риски и зависимости](#7-риски-и-зависимости)
8. [Критерии приёмки](#8-критерии-приёмки)
9. [Приложения](#9-приложения)

---

## 1. Резюме

### Что мигрирует

**1C-Enterprise_Framework** — экосистема AI-инструментов для разработки на платформе 1С:Предприятие. Включает 33+ MCP-серверов, семантический поиск по BSL-коду, автодокументирование, отладку, memory-системы, fine-tuning и CI/CD-пайплайн.

**1С-Framework** — production-ready фреймворк обработки PDF-документов с RAG, knowledge graphs, гибридным поиском (43 фазы завершены). Имеет зрелую инфраструктуру: Hooks + Skills + MCP триада, Task Protocol, Ralph Wiggum автономный цикл.

### Цель миграции

Объединить BSL/1C-инструментарий из 1C-Enterprise_Framework в единую платформу 1С-Framework, используя существующую инфраструктуру (hooks, skills, MCP, Qdrant, LangChain/LangGraph).

### Масштаб

| Метрика | Значение |
|---------|----------|
| Компонентов к миграции | 18 основных модулей |
| MCP-серверов к интеграции | 15 native + 20 on-demand |
| BSL-модулей проиндексировано | 3,908 |
| Сущностей в графе знаний | 3,166 entities, 3,528 edges |
| Фаз миграции | 5 Tier-ов, 18 шагов |
| Fine-tuning датасет | 10,000 BSL примеров |

---

## 2. Инвентаризация компонентов источника

### 2.1 Критические компоненты (MUST HAVE)

| # | Компонент | Путь в источнике | Технологии | LOC (прибл.) | Описание |
|---|-----------|------------------|------------|-------------|----------|
| 1 | **Auto-Documenter** | `autodocument/` | Node.js, TypeScript, tree-sitter-bsl | ~8,000 | MCP-сервер автогенерации документации BSL. Tree-sitter парсинг, 11 типов модулей, call graph, metadata XML, 5 AI-провайдеров с ротацией |
| 2 | **BSL Semantic Search** | `bsl-semantic-search/` | Python, FastMCP, Qdrant, Neo4j | ~5,000 | Семантический поиск по BSL-коду. 3,908 модулей, 768d embeddings (nomic-embed-text), граф-аналитика |
| 3 | **BSL Debugger** | `bsl-debugger/` | TypeScript, OneScript | ~3,900 | Интерактивная отладка BSL: 10 инструментов (breakpoints, step, variables, evaluate, stack) |
| 4 | **MCP 1C Integration** | `mcp-1c-integration/` | Python + 1C Extension | ~3,000 | Фреймворк разработки MCP-серверов для 1С. OAuth2, metadata extraction |
| 5 | **MCP 1C Server** | `mcp-1c-server/` | Python | ~2,000 | Готовый MCP-сервер для взаимодействия с 1С:Предприятие |
| 6 | **Sonar Integration** | `sonar_integration/` | Python | ~3,000 | SonarQube для BSL: правила, отчёты (HTML/Excel), CI-интеграция |
| 7 | **Serena LSP** | `serena/` | Python/TypeScript | ~10,000 | LSP-агент: symbol-level extraction, 30+ языков включая BSL |

### 2.2 Высокоприоритетные компоненты (SHOULD HAVE)

| # | Компонент | Путь в источнике | Технологии | LOC (прибл.) | Описание |
|---|-----------|------------------|------------|-------------|----------|
| 8 | **Memory Orchestrator** | `memory-orchestrator/` | Python | ~4,000 | Unified namespace для 4 memory-систем: episodic, semantic, vector, documentation |
| 9 | **AI Memory System** | `ai-memory-system/` | Python, TimescaleDB, Qdrant, Neo4j | ~5,000 | Долгосрочная память: conversations, importance scoring, entity extraction |
| 10 | **Shared LLM Rotation** | `shared/` | Python | ~2,000 | Мульти-провайдер LLM сервис: Mistral, OpenRouter, Gemini, Ollama с фоллбеком |
| 11 | **Claude Task Master** | `claude-task-master/` | Node.js/Python | ~5,000 | Управление задачами с AI-декомпозицией, 7 LLM-провайдеров |
| 12 | **BSL Fine-tuning** | `finetuning/` | Python, PyTorch, Colab | ~2,000 | Fine-tuning Qwen2.5-Coder-7B на BSL: LoRA, GGUF quantization |
| 13 | **Development Pipeline** | `development-pipeline/` | Python | ~3,000 | CI/CD: artifact store, import fixing, agent-based execution |

### 2.3 Средний приоритет (NICE TO HAVE)

| # | Компонент | Путь в источнике | Технологии | LOC (прибл.) | Описание |
|---|-----------|------------------|------------|-------------|----------|
| 14 | **AST Grep MCP** | `ast-grep-mcp/` | Python/Node.js | ~2,000 | AST-паттерн поиск для BSL и JS/TS |
| 15 | **Vector Memory MCP** | `vector-memory-mcp/` | Python | ~1,500 | Семантическая память с decay-механизмом |
| 16 | **Skill Learning MCP** | `skill-learning-mcp/` | Python | ~1,500 | Захват и персистенция навыков |
| 17 | **Lazy MCP** | `lazy-mcp/` | Python | ~3,000 | Proxy для on-demand загрузки MCP-серверов |
| 18 | **Docker MCP Pilot** | `docker-mcp-pilot/` | Docker, Bash | ~1,000 | Контейнеризация MCP-серверов (POC) |

### 2.4 Справочные материалы (НЕ мигрируют, используются как reference)

| Компонент | Путь | Причина |
|-----------|------|---------|
| `Проекты/` (25+ исследований) | `Проекты/` | Архив исследований, бэклог идей |
| `cursor-rules/` | `cursor-rules/` | Специфичны для Cursor IDE |
| `examples/` | `examples/` | Примеры кода (извлечь полезное) |
| `claude-auto-documenter-v2.BACKUP/` | Корень | Устаревшая версия auto-documenter |
| Временные файлы (`test_*.py`, `temp_*`) | Корень | Артефакты разработки |
| `.serena/memories/` | `.serena/` | Сессионная память Serena |
| `claude-memory.json` | Корень | Legacy memory формат |

---

## 3. Целевая архитектура

### 3.1 Размещение в структуре 1С-Framework

```
D:\1С-Framework\
├── src/
│   ├── pdf_framework/          # [Существующий] RAG/Search ядро (без изменений)
│   ├── api/                    # [Существующий] FastAPI REST API
│   ├── cli/                    # [Существующий] Typer CLI
│   ├── mcp_server/             # [Существующий] PDF MCP (12 tools)
│   ├── ui/                     # [Существующий] Streamlit UI
│   ├── workers/                # [Существующий] Background workers
│   │
│   ├── bsl/                    # [НОВЫЙ] BSL-инструментарий
│   │   ├── semantic_search/    # <- bsl-semantic-search (Python часть)
│   │   ├── sonar/              # <- sonar_integration
│   │   ├── mcp_integration/    # <- mcp-1c-integration
│   │   ├── mcp_server/         # <- mcp-1c-server
│   │   └── finetuning/         # <- finetuning
│   │
│   ├── memory/                 # [НОВЫЙ] Unified Memory
│   │   ├── orchestrator/       # <- memory-orchestrator
│   │   ├── ai_memory/          # <- ai-memory-system
│   │   ├── vector_memory/      # <- vector-memory-mcp
│   │   └── skill_learning/     # <- skill-learning-mcp
│   │
│   └── shared/                 # [НОВЫЙ] Общие сервисы
│       └── llm_rotation/       # <- shared/ (LLM rotation service)
│
├── tools/                      # [НОВЫЙ] Внешние инструменты (Node.js)
│   ├── auto-documenter/        # <- autodocument/ (Node.js MCP)
│   ├── bsl-debugger/           # <- bsl-debugger/ (Node.js MCP)
│   ├── ast-grep-mcp/           # <- ast-grep-mcp/
│   └── serena/                 # <- serena/ (LSP агент)
│
├── infra/                      # [НОВЫЙ] Инфраструктура
│   ├── lazy-mcp/               # <- lazy-mcp/
│   ├── docker-mcp/             # <- docker-mcp-pilot/
│   └── pipeline/               # <- development-pipeline/
│
├── .claude/
│   ├── hooks/                  # [Существующий] 17 hooks + новые
│   ├── skills/                 # [Существующий] 57 skills + новые BSL-скиллы
│   └── settings.json           # Обновить MCP конфигурацию
│
├── .mcp.json                   # [Обновить] Добавить BSL MCP серверы
├── .mcp/
│   └── lazy-mcp.json           # [НОВЫЙ] Конфиг lazy-mcp с профилями
│
└── docs/
    └── roadmap/
        └── MIGRATION_1C_ENTERPRISE_FRAMEWORK.md  # Этот документ
```

### 3.2 Принципы интеграции

1. **Изоляция языков**: Python-компоненты → `src/`, Node.js → `tools/`, инфраструктура → `infra/`
2. **Единый MCP**: все серверы регистрируются в `.mcp.json`, lazy-mcp как proxy
3. **Общий Qdrant**: BSL-коллекции рядом с PDF-коллекциями (разные collections)
4. **Общий LLM rotation**: один сервис для всех компонентов
5. **Триада сохраняется**: каждый компонент = Hook + Skill + MCP tool
6. **Существующая инфраструктура**: hooks, skills, task protocol — переиспользуются

### 3.3 Qdrant-коллекции после миграции

| Коллекция | Dims | Назначение | Источник |
|-----------|------|-----------|----------|
| `pdf_documents` | 1024 | PDF чанки (E5-large) | Существующий |
| `graph_embeddings` | 1024 | Entity/relation embeddings | Существующий |
| `bsl_code_v2` | 768 | BSL-модули (nomic-embed-text) | bsl-semantic-search |
| `ai_memory` | 768 | AI memory embeddings | ai-memory-system |
| `vector_patterns` | 768 | Learned patterns | vector-memory-mcp |

---

## 4. Фазы миграции

### Tier 1: Фундамент (Фазы 44-45)

**Цель:** Подготовить инфраструктуру, перенести ядро BSL-инструментов

#### Фаза 44: Инфраструктура миграции

**Scope:** Создание структуры директорий, настройка зависимостей, MCP конфигурация

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 44.1 | Создать директории `src/bsl/`, `src/memory/`, `src/shared/`, `tools/`, `infra/` | Структура каталогов | `ls` подтверждает создание |
| 44.2 | Обновить `pyproject.toml`: extras `[bsl]`, `[memory]`, `[llm-rotation]` | `pyproject.toml` | `pip install -e .[bsl]` проходит |
| 44.3 | Создать `.mcp/lazy-mcp.json` с профилями (pdf, bsl, full) | `.mcp/lazy-mcp.json` | Валидный JSON, Claude Code принимает |
| 44.4 | Обновить `.mcp.json`: добавить BSL MCP серверы | `.mcp.json` | Серверы доступны в Claude Code |
| 44.5 | Создать `tools/package.json` для Node.js компонентов | `tools/package.json` | `npm install` в tools/ проходит |
| 44.6 | Обновить `docker-compose.yml`: добавить BSL-сервисы | `docker/docker-compose.yml` | `docker compose config` валиден |
| 44.7 | Создать skill `bsl-development` (SKILL.md) | `.claude/skills/bsl-development/SKILL.md` | Skill router распознаёт BSL-запросы |
| 44.8 | Создать hook `bsl-tool-router.py` (PreToolUse) | `.claude/hooks/bsl-tool-router.py` | Роутит BSL-задачи к правильным инструментам |

**Зависимости:** Нет
**Оценка:** ~4 часа работы

#### Фаза 45: BSL Semantic Search + Sonar

**Scope:** Перенос ядра BSL-анализа (семантический поиск + SonarQube)

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 45.1 | Перенести `bsl-semantic-search/` → `src/bsl/semantic_search/` | Python модули | Импорты работают |
| 45.2 | Адаптировать Qdrant-клиент: использовать общий из `pdf_framework` | `src/bsl/semantic_search/engine.py` | Подключение к тому же Qdrant |
| 45.3 | Перенести `sonar_integration/` → `src/bsl/sonar/` | Python модули | CLI и API работают |
| 45.4 | Создать MCP tools для BSL search (FastMCP) | `src/bsl/semantic_search/mcp.py` | 3+ tools зарегистрированы |
| 45.5 | Интеграционный тест: поиск по BSL-коду через API | `tests/integration/test_bsl_search.py` | Поиск возвращает релевантные результаты |
| 45.6 | Создать кеш знаний `bsl-semantic-search` | `.claude/skills/bsl-development/cache/bsl-semantic-search.md` | Кешировано в 8 категориях |
| 45.7 | Перенести Qdrant-коллекцию `bsl_code_v2` (3,908 модулей) | Данные в Qdrant | `GET /collections/bsl_code_v2` возвращает 3,908 points |

**Зависимости:** Фаза 44
**Оценка:** ~6 часов

---

### Tier 2: Основные сервисы (Фазы 46-48)

**Цель:** MCP-интеграция с 1С, Auto-Documenter, BSL Debugger

#### Фаза 46: MCP 1C Integration + Server

**Scope:** Фреймворк MCP для 1С и готовый сервер

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 46.1 | Перенести `mcp-1c-integration/` → `src/bsl/mcp_integration/` | Python + 1C ext | Структура сохранена |
| 46.2 | Перенести `mcp-1c-server/` → `src/bsl/mcp_server/` | Python | Сервер запускается |
| 46.3 | Адаптировать пути и конфиг под новую структуру | `config.py`, `__init__.py` | Все импорты работают |
| 46.4 | Зарегистрировать в `.mcp.json` | `.mcp.json` | `bsl-platform-context` доступен в Claude Code |
| 46.5 | Тест: вызов MCP tool из Claude Code | Ручной тест | Tool возвращает метаданные 1С |
| 46.6 | Документация: обновить `docs/api/` | `docs/api/bsl-mcp.md` | Описаны все endpoints и tools |

**Зависимости:** Фаза 44
**Оценка:** ~4 часа

#### Фаза 47: Auto-Documenter (Profile #7)

**Scope:** Полный перенос auto-documenter (Node.js MCP server)

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 47.1 | Скопировать `autodocument/` → `tools/auto-documenter/` | Весь каталог | Файлы на месте |
| 47.2 | Обновить `mcp-start.js`: пути, env переменные | `tools/auto-documenter/mcp-start.js` | `node mcp-start.js` запускается |
| 47.3 | Установить зависимости: `npm install` в `tools/auto-documenter/` | `package.json`, `node_modules/` | Все deps установлены |
| 47.4 | Пересобрать TypeScript: `npm run build` | `build/` | Компиляция без ошибок |
| 47.5 | Зарегистрировать в `.mcp.json` с корректным cwd | `.mcp.json` | MCP server `auto-documenter` доступен |
| 47.6 | Тест: `generate_documentation` на тестовом BSL-проекте | Ручной тест | Документация сгенерирована |
| 47.7 | Тест: `autoreview` на тестовом BSL-проекте | Ручной тест | Code review отчёт создан |
| 47.8 | Тест: `autotestplan` на тестовом BSL-проекте | Ручной тест | Test plan создан |
| 47.9 | Создать skill `auto-documenter` (SKILL.md) | `.claude/skills/auto-documenter/SKILL.md` | Триггеры: 'документация BSL', 'generate_documentation', 'auto-documenter' |
| 47.10 | Перенести tree-sitter-bsl WASM grammar | `tools/auto-documenter/` | BSL парсинг работает |

**Зависимости:** Фаза 44
**Оценка:** ~5 часов

**Детали Auto-Documenter (Profile #7):**

Сервер #7 из 15 native серверов lazy-mcp. Ключевые возможности:
- **5 MCP tools**: `generate_documentation`, `autotestplan`, `autoreview`, `generate_inline_docs`, `generate_dependency_graph`
- **Tree-sitter BSL**: 100% точный AST-парсинг (процедуры, функции, экспорты, регионы, переменные)
- **11 типов модулей**: FORM_MODULE, OBJECT_MODULE, MANAGER_MODULE, COMMAND_MODULE, COMMON_MODULE, RECORDSET_MODULE, SESSION_MODULE, APPLICATION_MODULE, MANAGED_APPLICATION_MODULE, EXTERNAL_CONNECTION_MODULE
- **25+ типов метаданных**: справочники, документы, регистры, обработки, отчёты и др.
- **Call graph**: визуализация зависимостей (INTERNAL, COMMON_MODULE, MANAGER, OBJECT_METHOD, PLATFORM, CONSTRUCTOR)
- **5 AI-провайдеров**: Gemini (free, 1,500/day), Groq (free), Ollama (local), xAI Grok, OpenRouter
- **Metadata XML**: парсинг форм, реквизитов, табличных частей, валидация Form.xml vs Module.bsl
- **Режимы**: bottom-up aggregation, incremental, watch mode, cache

#### Фаза 48: BSL Debugger

**Scope:** Перенос интерактивного отладчика BSL

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 48.1 | Скопировать `bsl-debugger/` → `tools/bsl-debugger/` | Весь каталог | Файлы на месте |
| 48.2 | `npm install` + `npm run build` | Node.js deps | Сборка успешна |
| 48.3 | Зарегистрировать в `.mcp.json` | `.mcp.json` | 10 debug tools доступны |
| 48.4 | Тест: запуск debug-сессии, breakpoint, step, variables | Ручной тест | Все 10 инструментов работают |
| 48.5 | Создать skill `bsl-debugger` | `.claude/skills/bsl-debugger/SKILL.md` | Триггеры: 'отладка BSL', 'debug 1С', 'breakpoint' |

**Зависимости:** Фаза 44
**Оценка:** ~3 часа

---

### Tier 3: Memory и AI-сервисы (Фазы 49-51)

**Цель:** Единая система памяти, LLM rotation, task management

#### Фаза 49: Unified Memory System

**Scope:** Memory Orchestrator + AI Memory + Vector Memory

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 49.1 | Перенести `memory-orchestrator/` → `src/memory/orchestrator/` | Python | Импорты работают |
| 49.2 | Перенести `ai-memory-system/` → `src/memory/ai_memory/` | Python | Подключение к TimescaleDB/Qdrant |
| 49.3 | Перенести `vector-memory-mcp/` → `src/memory/vector_memory/` | Python | MCP tools зарегистрированы |
| 49.4 | Перенести `skill-learning-mcp/` → `src/memory/skill_learning/` | Python | Skill capture работает |
| 49.5 | Адаптировать Qdrant клиент к общему | `src/memory/*/config.py` | Один клиент, разные коллекции |
| 49.6 | Унифицировать UnifiedID систему | `src/memory/orchestrator/unified_id.py` | `episodic:memory-type:id` формат |
| 49.7 | Интеграционный тест: federated search | `tests/integration/test_memory_unified.py` | Поиск по всем 4 системам |
| 49.8 | Зарегистрировать MCP tools (memory-ai, conversation-memory, vector-memory) | `.mcp.json` | 3 MCP сервера доступны |

**Зависимости:** Фаза 44, Qdrant running
**Оценка:** ~8 часов

#### Фаза 50: LLM Rotation Service

**Scope:** Мульти-провайдер LLM сервис с фоллбеком

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 50.1 | Перенести `shared/` → `src/shared/llm_rotation/` | Python | Импорты работают |
| 50.2 | Адаптировать к существующему config паттерну (pydantic-settings) | `src/shared/llm_rotation/config.py` | Конфиг из `.env` |
| 50.3 | Интегрировать с Z.AI proxy (уже в 1С-Framework) | `src/shared/llm_rotation/zai_proxy.py` | Z.AI доступен как провайдер |
| 50.4 | Тест: fallback цепочка Mistral → OpenRouter → Gemini → Ollama | `tests/test_llm_rotation.py` | При ошибке провайдера — автопереключение |
| 50.5 | MCP wrapper для доступа из Claude Code | `src/shared/llm_rotation/mcp.py` | Tool `llm_rotate` доступен |

**Зависимости:** Фаза 44
**Оценка:** ~4 часа

#### Фаза 51: Task Master + Development Pipeline

**Scope:** AI-управление задачами и CI/CD

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 51.1 | Оценить совместимость claude-task-master с существующим Task Protocol | Анализ | Документ сравнения |
| 51.2 | Перенести `claude-task-master/` → `infra/task-master/` (если совместим) ИЛИ извлечь полезные паттерны | Node.js | Запускается или паттерны извлечены |
| 51.3 | Перенести `development-pipeline/` → `infra/pipeline/` | Python | Artifact store работает |
| 51.4 | Интегрировать pipeline с существующими hooks (auto-git-save, code-verify) | Hooks config | Pipeline триггерится от hooks |
| 51.5 | Зарегистрировать task-master в `.mcp.json` | `.mcp.json` | MCP tool доступен |

**Зависимости:** Фазы 44, 49
**Оценка:** ~5 часов

---

### Tier 4: Расширения (Фазы 52-54)

**Цель:** LSP, fine-tuning, Docker-оркестрация

#### Фаза 52: Serena LSP Integration

**Scope:** LSP-агент для symbol-level code intelligence

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 52.1 | Скопировать `serena/` → `tools/serena/` | Весь каталог | Файлы на месте |
| 52.2 | Настроить venv и зависимости | `tools/serena/` | LSP сервер запускается |
| 52.3 | Зарегистрировать в `.mcp.json` | `.mcp.json` | Serena tools доступны |
| 52.4 | Настроить BSL Language Server через `bsl_language_server.py` | Конфиг | BSL symbols извлекаются |
| 52.5 | Тест: symbol extraction для BSL-модуля | Ручной тест | Процедуры/функции найдены |

**Зависимости:** Фаза 44
**Оценка:** ~4 часа

#### Фаза 53: BSL Fine-tuning

**Scope:** Инфраструктура для fine-tuning моделей на BSL

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 53.1 | Перенести `finetuning/` → `src/bsl/finetuning/` | Python, Notebooks | Файлы на месте |
| 53.2 | Адаптировать dataset extraction к новой структуре | `src/bsl/finetuning/extract.py` | Скрипт находит BSL-проекты |
| 53.3 | Проверить Colab notebook | `src/bsl/finetuning/notebooks/` | Notebook запускается |
| 53.4 | Документировать процесс fine-tuning | `docs/guides/bsl-finetuning.md` | Пошаговая инструкция |
| 53.5 | Создать skill `bsl-finetuning` | `.claude/skills/bsl-finetuning/SKILL.md` | Триггеры: 'fine-tuning BSL', 'обучение модели' |

**Зависимости:** Фаза 45
**Оценка:** ~3 часа

#### Фаза 54: Infrastructure (Lazy MCP + Docker + AST Grep)

**Scope:** Инфраструктурные компоненты

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 54.1 | Перенести `lazy-mcp/` → `infra/lazy-mcp/` | Python | Lazy proxy работает |
| 54.2 | Создать `.mcp/lazy-mcp.json` с 3 профилями | `.mcp/lazy-mcp.json` | pdf / bsl / full профили |
| 54.3 | Перенести `docker-mcp-pilot/` → `infra/docker-mcp/` | Docker, Bash | `docker compose config` валиден |
| 54.4 | Перенести `ast-grep-mcp/` → `tools/ast-grep-mcp/` | Python/Node.js | AST search работает |
| 54.5 | Обновить `docker/docker-compose.yml`: BSL services | Docker | Все сервисы стартуют |

**Зависимости:** Фазы 44-48
**Оценка:** ~5 часов

---

### Tier 5: Финализация (Фаза 55)

**Цель:** Интеграционное тестирование, документация, cleanup

#### Фаза 55: Integration & Cleanup

| Шаг | Действие | Файлы | Критерий приёмки |
|-----|----------|-------|-----------------|
| 55.1 | End-to-end тест: полный BSL workflow | `tests/e2e/test_bsl_workflow.py` | Index → Search → Document → Review → Debug |
| 55.2 | End-to-end тест: PDF + BSL cross-search | `tests/e2e/test_cross_search.py` | Поиск по PDF и BSL одновременно |
| 55.3 | Обновить CLAUDE.md: BSL секция | `CLAUDE.md` | BSL-инструменты документированы |
| 55.4 | Обновить MEMORY.md: BSL секция | `memory/MEMORY.md` | BSL-конфигурация записана |
| 55.5 | Обновить skill-router-config.json: BSL bundles | `.claude/skills/skill-router-config.json` | BSL-запросы роутятся к правильным скиллам |
| 55.6 | Создать `docs/architecture/bsl-integration.md` | Документация | Полная архитектура BSL-интеграции |
| 55.7 | Провести audit-docs для BSL компонентов | Скрипт | 0 undocumented BSL features |
| 55.8 | Performance benchmark: BSL search latency | Бенчмарк | <500ms для семантического поиска |
| 55.9 | Cleanup: удалить временные файлы, привести к code style | ruff, mypy | 0 lint errors в новых файлах |
| 55.10 | Git tag `v0.34.0-bsl-migration` | Git | Тег создан |

**Зависимости:** Все предыдущие фазы
**Оценка:** ~6 часа

---

## 5. Детальный план по компонентам

### 5.1 Auto-Documenter (Профиль #7) — Ключевой компонент

**Источник:** `D:\1C-Enterprise_Framework\autodocument\`
**Цель:** `D:\1С-Framework\tools\auto-documenter\`

#### Архитектура компонента

```
tools/auto-documenter/
├── mcp-start.js                    # Entry point (обновить пути)
├── package.json                    # npm deps
├── tsconfig.json                   # TypeScript config
├── src/
│   ├── index.ts                    # MCP server definition
│   ├── analyzer/
│   │   ├── bsl-treesitter-analyzer.ts    # Tree-sitter BSL parsing
│   │   ├── bsl-call-graph-analyzer.ts    # Call graph analysis
│   │   ├── structure-1c-analyzer.ts      # 1C metadata detection
│   │   ├── bsl-integration.ts            # Integration layer
│   │   └── index.ts                      # File analyzer router
│   ├── tools/
│   │   ├── registry.ts                   # Tool registry
│   │   ├── aggregator.ts                 # Bottom-up processor
│   │   ├── documentation-tool.ts         # generate_documentation
│   │   ├── testplan-tool.ts              # autotestplan
│   │   ├── review-tool.ts               # autoreview
│   │   ├── inline-docs-tool.ts           # generate_inline_docs
│   │   └── dependency-graph-tool.ts      # generate_dependency_graph
│   ├── providers/
│   │   ├── provider-factory.ts           # Provider instantiation
│   │   └── provider-rotation.ts          # 5-provider rotation
│   ├── metadata/
│   │   ├── metadata-parser.ts            # XML parsing
│   │   └── metadata-integration.ts       # Prompt enrichment
│   ├── prompts/
│   │   ├── bsl-context-prompts.ts        # BSL-specific context
│   │   └── bsl-review-prompts.ts         # 1C standards review
│   ├── cache/                            # AI response cache
│   ├── cli/                              # Standalone CLI
│   └── prompt-config.ts                  # Centralized prompts
├── build/                                # Compiled JS
└── docs/                                 # Component docs
```

#### Что адаптировать

| Файл | Изменение | Причина |
|------|-----------|---------|
| `mcp-start.js` | Обновить `cwd` и env пути | Новое расположение |
| `src/providers/provider-rotation.ts` | Добавить Z.AI как провайдер | Уже используется в 1С-Framework |
| `.mcp.json` | Добавить server entry с правильным cwd | Регистрация в Claude Code |
| `src/index.ts` | Проверить output directory logic | `calculate1COutputDir()` пути |

#### Что НЕ менять

- Tree-sitter парсер (самодостаточный)
- Tool registry и aggregator (стабильные)
- Prompt templates (BSL-специфичные, отлажены)
- CLI интерфейс (standalone usage)

### 5.2 BSL Semantic Search — Интеграция с существующим Qdrant

**Текущая конфигурация:**
- Коллекция: `bsl_code_v2`
- Embeddings: `nomic-embed-text` (768d)
- Индекс: 3,908 BSL модулей
- Backend: Qdrant + Neo4j

**Интеграция с 1С-Framework:**

```python
# src/bsl/semantic_search/config.py
from src.pdf_framework.config import get_settings

class BSLSearchSettings:
    """Конфигурация BSL поиска. Использует общий Qdrant."""
    qdrant_url: str = get_settings().vector_store.qdrant_url  # Общий URL
    collection_name: str = "bsl_code_v2"                       # Отдельная коллекция
    embedding_model: str = "nomic-embed-text"                   # Свой embedding
    embedding_dim: int = 768                                    # Свои размерности
```

**Ключевое решение:** BSL использует другую embedding модель (768d nomic vs 1024d E5). Коллекции изолированы — конфликтов нет.

### 5.3 Shared LLM Rotation — Унификация провайдеров

**Текущие провайдеры в 1C-Enterprise_Framework:**
1. Mistral AI (mistral-small-latest)
2. OpenRouter (llama-3.3-70b)
3. Gemini (gemini-2.0-flash)
4. Ollama Cloud
5. Ollama Local

**Текущие провайдеры в 1С-Framework:**
1. Claude Opus 4.6 (main LLM)
2. Claude Sonnet 4.5 (fast LLM, reranker, vision)
3. Z.AI proxy

**Решение:** LLM Rotation как fallback-слой. Claude остаётся primary, rotation service подключается для задач не требующих Claude (BSL documentation, embeddings, lightweight analysis).

---

## 6. Конфигурация и MCP

### 6.1 Обновлённый `.mcp.json`

```json
{
  "mcpServers": {
    "pdf-vector-graph": { "... существующий ..." },

    "auto-documenter": {
      "command": "node",
      "args": ["mcp-start.js"],
      "cwd": "D:\\1С-Framework\\tools\\auto-documenter",
      "env": {
        "NODE_OPTIONS": "--max-old-space-size=4096",
        "DEEP_REASONING_MODEL": "glm-5"
      },
      "timeout": 180000
    },

    "bsl-semantic-search": {
      "command": "D:\\1С-Framework\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.bsl.semantic_search.mcp"],
      "cwd": "D:\\1С-Framework"
    },

    "bsl-debugger": {
      "command": "node",
      "args": ["build/index.js"],
      "cwd": "D:\\1С-Framework\\tools\\bsl-debugger"
    },

    "bsl-platform-context": {
      "command": "D:\\1С-Framework\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.bsl.mcp_server.server"],
      "cwd": "D:\\1С-Framework"
    },

    "serena": {
      "command": "D:\\1С-Framework\\tools\\serena\\.venv\\Scripts\\python.exe",
      "args": ["-m", "serena"],
      "cwd": "D:\\1С-Framework\\tools\\serena"
    },

    "ast-grep-mcp": {
      "command": "node",
      "args": ["build/index.js"],
      "cwd": "D:\\1С-Framework\\tools\\ast-grep-mcp"
    }
  }
}
```

### 6.2 Lazy MCP профили

```json
{
  "profiles": {
    "pdf": {
      "description": "PDF документация и RAG",
      "servers": ["pdf-vector-graph"]
    },
    "bsl": {
      "description": "BSL/1C разработка",
      "servers": ["auto-documenter", "bsl-semantic-search", "bsl-debugger", "bsl-platform-context", "serena", "ast-grep-mcp"]
    },
    "full": {
      "description": "Все серверы",
      "servers": ["pdf-vector-graph", "auto-documenter", "bsl-semantic-search", "bsl-debugger", "bsl-platform-context", "serena", "ast-grep-mcp"]
    }
  }
}
```

### 6.3 Новые зависимости в `pyproject.toml`

```toml
[project.optional-dependencies]
bsl = [
    "qdrant-client>=1.12",       # Уже есть в основных deps
    "neo4j>=5.25",               # Уже в [neo4j]
    "fastmcp>=0.1",              # MCP для BSL search
]
memory = [
    "timescaledb>=0.1",          # AI Memory
    "qdrant-client>=1.12",
]
llm-rotation = [
    "mistralai>=1.0",
    "openai>=1.0",               # Уже есть
    "google-generativeai>=0.8",
]
```

---

## 7. Риски и зависимости

### 7.1 Технические риски

| Риск | Вероятность | Влияние | Митигация |
|------|------------|---------|-----------|
| **Конфликт Python-зависимостей** | Средняя | Высокое | Изолировать BSL deps в extras `[bsl]`, тестировать совместно |
| **Разные embedding модели** (768d vs 1024d) | Низкая | Низкое | Отдельные Qdrant коллекции, разные клиенты |
| **Node.js компоненты требуют отдельный runtime** | Низкая | Среднее | `tools/` директория с собственным `package.json` |
| **Tree-sitter WASM совместимость** | Средняя | Высокое | Зафиксировать версии в package.json, тестировать на Windows |
| **MCP timeout (auto-documenter 180s)** | Средняя | Среднее | Настроить timeout в `.mcp.json`, мониторить через hooks |
| **Qdrant memory pressure** (доп. коллекции) | Низкая | Среднее | Мониторить через `GET /metrics`, увеличить Docker memory limit |
| **TimescaleDB отсутствует в текущем docker-compose** | Высокая | Среднее | Добавить сервис или использовать SQLite fallback для AI Memory |
| **Neo4j конфликт портов** (17474 vs стандартный 7474) | Низкая | Низкое | Использовать нестандартные порты как в 1C-Enterprise |

### 7.2 Организационные риски

| Риск | Вероятность | Влияние | Митигация |
|------|------------|---------|-----------|
| **Scope creep** — миграция разрастается | Высокая | Высокое | Строгий tier-порядок, каждая фаза — отдельный коммит |
| **Устаревший код в источнике** | Средняя | Среднее | Ревью каждого компонента перед миграцией |
| **Потеря конфигурации** (.env, API keys) | Средняя | Высокое | Документировать все env переменные, `.env.example` |
| **Прерывание работающего 1С-Framework** | Низкая | Высокое | Все изменения в новых директориях, без модификации существующего кода до Tier 5 |

### 7.3 Граф зависимостей

```
Tier 1 (Фундамент)
  Фаза 44 ──────────────────────────┐
     │                               │
     ├── Фаза 45 (BSL Search)       │
     │      │                        │
Tier 2     │                        │
     ├── Фаза 46 (MCP 1C) ─────────┤
     ├── Фаза 47 (Auto-Doc) ───────┤
     ├── Фаза 48 (Debugger) ───────┤
     │                               │
Tier 3                               │
     ├── Фаза 49 (Memory) ──── Qdrant│
     ├── Фаза 50 (LLM Rotation)    │
     ├── Фаза 51 (Task+Pipeline) ──┤
     │                               │
Tier 4                               │
     ├── Фаза 52 (Serena) ─────────┤
     ├── Фаза 53 (Fine-tuning) ← Фаза 45
     ├── Фаза 54 (Infra) ← Все Tier 2
     │                               │
Tier 5                               │
     └── Фаза 55 (Integration) ← ВСЕ
```

---

## 8. Критерии приёмки

### 8.1 Per-Tier критерии

| Tier | Критерий | Метрика |
|------|----------|---------|
| **Tier 1** | BSL semantic search работает в 1С-Framework | Query latency <500ms, recall >0.8 |
| **Tier 2** | Все 3 Node.js MCP-сервера доступны из Claude Code | `mcp__auto-documenter__*`, `mcp__bsl-debugger__*`, `mcp__bsl-platform-context__*` |
| **Tier 3** | Unified memory federated search | Поиск по 4+ системам памяти |
| **Tier 4** | Serena BSL symbols + fine-tuning pipeline | Symbol extraction для .bsl файлов |
| **Tier 5** | E2E: PDF + BSL cross-search, все тесты зелёные | 0 failures в `pytest tests/` |

### 8.2 Общие критерии завершения

- [ ] Все 18 компонентов перенесены и работоспособны
- [ ] `.mcp.json` содержит все BSL MCP серверы
- [ ] Lazy MCP профили (pdf/bsl/full) работают
- [ ] CLAUDE.md обновлён с BSL секцией
- [ ] MEMORY.md обновлён с BSL конфигурацией
- [ ] Skill router распознаёт BSL-запросы
- [ ] 0 lint errors в новых файлах (ruff + mypy)
- [ ] Документация в `docs/architecture/bsl-integration.md`
- [ ] Git tag `v0.34.0-bsl-migration`
- [ ] Существующий функционал PDF Framework НЕ нарушен

---

## 9. Приложения

### 9.1 Полный список MCP серверов для миграции

| # | Сервер | Тип | Приоритет | Фаза |
|---|--------|-----|-----------|------|
| 1 | serena | Python (LSP) | HIGH | 52 |
| 2 | ast-grep-mcp | Node.js | MEDIUM | 54 |
| 3 | bsl-platform-context | Python | CRITICAL | 46 |
| 4 | 1c-docs-rag | Python | CRITICAL | 45 |
| 5 | memory-ai | Python | HIGH | 49 |
| 6 | bsl-semantic-search | Python | CRITICAL | 45 |
| 7 | **auto-documenter** | Node.js | **CRITICAL** | **47** |
| 8 | ripgrep | Binary | LOW | 54 |
| 9 | deep-code-reasoning | Python | MEDIUM | 51 |
| 10 | conversation-memory | Python | HIGH | 49 |
| 11 | task-master-ai | Node.js | HIGH | 51 |
| 12 | markitdown | Python | LOW | - |
| 13 | vector-memory | Python | MEDIUM | 49 |
| 14 | skill-learning | Python | MEDIUM | 49 |
| 15 | lazy-mcp | Python (proxy) | MEDIUM | 54 |

### 9.2 Env-переменные для миграции

```bash
# BSL Semantic Search
BSL_QDRANT_COLLECTION=bsl_code_v2
BSL_EMBEDDING_MODEL=nomic-embed-text
BSL_EMBEDDING_DIM=768

# Auto-Documenter
AUTODOC_PRIMARY_PROVIDER=gemini
GEMINI_API_KEY=...
GROQ_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434

# LLM Rotation
LLM_ROTATION_PRIMARY=mistral
MISTRAL_API_KEY=...
OPENROUTER_API_KEY=...

# AI Memory
TIMESCALE_URL=postgresql://...
MEMORY_QDRANT_COLLECTION=ai_memory

# Deep Code Reasoning
DEEP_REASONING_API_KEY=...
DEEP_REASONING_BASE_URL=https://api.z.ai/api/anthropic
DEEP_REASONING_MODEL=glm-5
```

### 9.3 Новые Skills для создания

| Skill | Триггеры | Фаза |
|-------|----------|------|
| `bsl-development` | 'BSL', '1С код', 'модуль 1С', 'процедура BSL' | 44 |
| `auto-documenter` | 'документация BSL', 'generate_documentation', 'autoreview', 'testplan' | 47 |
| `bsl-debugger` | 'отладка BSL', 'debug 1С', 'breakpoint', 'переменные отладки' | 48 |
| `bsl-finetuning` | 'fine-tuning BSL', 'обучение модели', 'LoRA BSL', 'Qwen BSL' | 53 |
| `memory-unified` | 'память', 'memory search', 'federated search', 'unified memory' | 49 |
| `llm-rotation` | 'ротация LLM', 'fallback провайдер', 'LLM rotation' | 50 |

### 9.4 Новые Hooks для создания

| Hook | Событие | Назначение | Фаза |
|------|---------|-----------|------|
| `bsl-tool-router.py` | PreToolUse | Роутинг BSL-запросов к правильным MCP tools | 44 |
| `bsl-doc-reminder.py` | PostToolUse:Write (*.bsl) | Напоминание запустить auto-documenter после изменения BSL | 47 |
| `memory-sync.py` | Stop | Синхронизация memory систем при завершении сессии | 49 |

### 9.5 Оценка трудозатрат

| Tier | Фазы | Часы (прибл.) | Описание |
|------|-------|---------------|----------|
| Tier 1 | 44-45 | ~10 | Фундамент + BSL Search |
| Tier 2 | 46-48 | ~12 | MCP 1C + Auto-Doc + Debugger |
| Tier 3 | 49-51 | ~17 | Memory + LLM Rotation + Task |
| Tier 4 | 52-54 | ~12 | Serena + Fine-tuning + Infra |
| Tier 5 | 55 | ~6 | Интеграция и cleanup |
| **ИТОГО** | **44-55** | **~57 часов** | 12 фаз, 18 компонентов |

### 9.6 Порядок параллельного выполнения

```
Неделя 1: Tier 1 (Фаза 44 → 45)
          ├─ Параллельно: создание структуры (44) + анализ зависимостей
          └─ Последовательно: BSL Search после структуры (45)

Неделя 2: Tier 2 (Фазы 46, 47, 48 — ПАРАЛЛЕЛЬНО)
          ├─ MCP 1C (46)
          ├─ Auto-Documenter (47)
          └─ BSL Debugger (48)

Неделя 3: Tier 3 (Фазы 49, 50 — параллельно, 51 — после)
          ├─ Memory (49) ─┐
          ├─ LLM Rot (50) ├─ Фаза 51 (Task+Pipeline)
          └───────────────┘

Неделя 4: Tier 4 (Фазы 52, 53, 54 — параллельно)
          ├─ Serena (52)
          ├─ Fine-tuning (53)
          └─ Infra (54)

Неделя 5: Tier 5 (Фаза 55 — последовательно)
          └─ Integration, testing, docs, cleanup
```

---

*Документ создан на основе полного анализа `D:\1C-Enterprise_Framework` (33+ MCP серверов, 18 ключевых компонентов) с фокусом на профиль lazy-mcp #7 (auto-documenter).*
