# Фаза 44: Инфраструктура миграции

**Tier:** 1 — Фундамент
**Статус:** TODO
**Зависимости:** Нет (первая фаза)
**Оценка:** ~4 часа
**Блокирует:** Все остальные фазы (44 → 45-55)

---

## Цель

Подготовить структуру директорий, зависимости, MCP-конфигурацию, hooks и skills для приёма BSL-компонентов из `D:\1C-Enterprise_Framework`.

---

## Целевая структура

```
D:\1С-Framework\
├── src/
│   ├── pdf_framework/          # [БЕЗ ИЗМЕНЕНИЙ]
│   ├── api/                    # [БЕЗ ИЗМЕНЕНИЙ]
│   ├── cli/                    # [БЕЗ ИЗМЕНЕНИЙ]
│   ├── mcp_server/             # [БЕЗ ИЗМЕНЕНИЙ]
│   ├── ui/                     # [БЕЗ ИЗМЕНЕНИЙ]
│   ├── workers/                # [БЕЗ ИЗМЕНЕНИЙ]
│   │
│   ├── bsl/                    # [СОЗДАТЬ] BSL-инструментарий
│   │   ├── __init__.py
│   │   ├── semantic_search/    # Фаза 45
│   │   ├── sonar/              # Фаза 45
│   │   ├── mcp_integration/    # Фаза 46
│   │   ├── mcp_server/         # Фаза 46
│   │   └── finetuning/         # Фаза 53
│   │
│   ├── memory/                 # [СОЗДАТЬ] Unified Memory
│   │   ├── __init__.py
│   │   ├── orchestrator/       # Фаза 49
│   │   ├── ai_memory/          # Фаза 49
│   │   ├── vector_memory/      # Фаза 49
│   │   └── skill_learning/     # Фаза 49
│   │
│   └── shared/                 # [СОЗДАТЬ] Общие сервисы
│       ├── __init__.py
│       └── llm_rotation/       # Фаза 50
│
├── tools/                      # [СОЗДАТЬ] Node.js инструменты
│   ├── package.json            # Общий для tools/
│   ├── auto-documenter/        # Фаза 47
│   ├── bsl-debugger/           # Фаза 48
│   ├── ast-grep-mcp/           # Фаза 54
│   ├── serena/                 # Фаза 52
│   └── mcp-jars/               # Java JAR файлы (bsl-platform-context)
│
├── infra/                      # [СОЗДАТЬ] Инфраструктура
│   ├── lazy-mcp/               # Фаза 54
│   ├── docker-mcp/             # Фаза 54
│   └── pipeline/               # Фаза 51
│
├── .mcp/                       # [СОЗДАТЬ] MCP профили
│   ├── pdf.json
│   ├── bsl.json
│   ├── full.json
│   └── lazy-mcp.json
│
└── scripts/
    └── claude.bat              # [СОЗДАТЬ] Launcher с профилями
```

---

## Шаги

### 44.1 Создать структуру директорий

```bash
# Python пакеты
mkdir -p src/bsl src/memory src/shared
touch src/bsl/__init__.py src/memory/__init__.py src/shared/__init__.py

# Node.js инструменты
mkdir -p tools/mcp-jars

# Инфраструктура
mkdir -p infra

# MCP профили
mkdir -p .mcp

# Скрипты
mkdir -p scripts
```

**Критерий:** Все директории существуют, `__init__.py` на месте.

### 44.2 Обновить pyproject.toml

Добавить extras для BSL, Memory и LLM Rotation:

```toml
[project.optional-dependencies]
# ... существующие extras ...

bsl = [
    "qdrant-client>=1.12",       # Уже в основных deps — дублирование допустимо
    "neo4j>=5.25",               # Уже в [neo4j]
    "fastmcp>=0.1",              # MCP server для BSL search
    "nomic[local]>=3.0",         # Embeddings для BSL (nomic-embed-text, 768d)
]

memory = [
    "qdrant-client>=1.12",
    "google-generativeai>=0.8",  # Google Gemini embeddings для vector-memory
]

llm-rotation = [
    "mistralai>=1.0",            # Mistral AI provider
    "openai>=1.0",               # Уже есть — OpenRouter тоже через openai SDK
    "google-generativeai>=0.8",  # Gemini provider
]

# Mega-extra для всего
all-bsl = [
    "pdf-framework[bsl,memory,llm-rotation]",
]
```

**Критерий:** `pip install -e ".[bsl]"` проходит без ошибок.
**Файл:** `pyproject.toml`

### 44.3 Создать MCP профили

#### `.mcp/pdf.json` — только PDF RAG

```json
{
  "$schema": "https://raw.githubusercontent.com/anthropics/claude-code/main/.mcp.schema.json",
  "mcpServers": {
    "pdf-vector-graph": {
      "command": "D:\\1С-Framework\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "D:\\1С-Framework"
    }
  }
}
```

#### `.mcp/bsl.json` — BSL разработка (6 серверов)

```json
{
  "$schema": "https://raw.githubusercontent.com/anthropics/claude-code/main/.mcp.schema.json",
  "mcpServers": {
    "auto-documenter": {
      "command": "node",
      "args": ["mcp-start.js"],
      "cwd": "D:\\1С-Framework\\tools\\auto-documenter",
      "env": {
        "NODE_OPTIONS": "--max-old-space-size=4096",
        "DEEP_REASONING_API_KEY": "${DEEP_REASONING_API_KEY}",
        "DEEP_REASONING_BASE_URL": "https://api.z.ai/api/anthropic",
        "DEEP_REASONING_MODEL": "glm-5"
      },
      "timeout": 180000
    },
    "bsl-semantic-search": {
      "command": "D:\\1С-Framework\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.bsl.semantic_search.mcp"],
      "cwd": "D:\\1С-Framework",
      "env": { "PYTHONIOENCODING": "utf-8" },
      "timeout": 60000
    },
    "bsl-debugger": {
      "command": "node",
      "args": ["dist/index.js"],
      "cwd": "D:\\1С-Framework\\tools\\bsl-debugger",
      "env": { "NODE_ENV": "production" },
      "timeout": 60000
    },
    "bsl-platform-context": {
      "command": "java",
      "args": ["-Dfile.encoding=UTF-8", "-jar",
               "D:\\1С-Framework\\tools\\mcp-jars\\mcp-bsl-context-0.3.1.jar",
               "--platform-path", "C:\\Program Files\\1cv8\\8.3.27.1859",
               "--verbose"],
      "env": { "JAVA_HOME": "C:\\Program Files\\Zulu\\zulu-17" },
      "timeout": 30000
    },
    "serena": {
      "command": "D:\\1С-Framework\\tools\\serena\\.venv\\Scripts\\serena.exe",
      "args": ["start-mcp-server", "--context", "ide-assistant"],
      "cwd": "D:\\1С-Framework\\tools\\serena",
      "timeout": 180000
    },
    "ast-grep-mcp": {
      "command": "D:\\1С-Framework\\tools\\ast-grep-mcp\\.venv\\Scripts\\python.exe",
      "args": ["main.py"],
      "cwd": "D:\\1С-Framework\\tools\\ast-grep-mcp",
      "env": { "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1" },
      "timeout": 60000
    }
  }
}
```

#### `.mcp/full.json` — PDF + BSL + Memory

Объединение pdf.json + bsl.json + memory серверы (memory-ai, vector-memory, unified-memory, conversation-memory, task-master-ai, deep-code-reasoning).

**Критерий:** `claude --strict-mcp-config --mcp-config ".mcp/bsl.json"` запускается.

### 44.4 Обновить `.mcp.json` (основной)

Добавить BSL серверы в основной `.mcp.json` проекта:

```json
{
  "mcpServers": {
    "pdf-vector-graph": { "...существующий..." },
    "auto-documenter": { "...из bsl.json..." },
    "bsl-semantic-search": { "...из bsl.json..." },
    "bsl-debugger": { "...из bsl.json..." },
    "bsl-platform-context": { "...из bsl.json..." }
  }
}
```

**Критерий:** Все серверы видны при `claude --mcp-config .mcp.json`.

### 44.5 Создать tools/package.json

```json
{
  "name": "1c-framework-tools",
  "version": "1.0.0",
  "private": true,
  "description": "Node.js MCP tools for 1C-Framework",
  "workspaces": [
    "auto-documenter",
    "bsl-debugger",
    "ast-grep-mcp"
  ],
  "scripts": {
    "build:all": "npm run build --workspaces",
    "build:autodoc": "cd auto-documenter && npm run build",
    "build:debugger": "cd bsl-debugger && npm run build"
  }
}
```

**Критерий:** `npm install` в `tools/` проходит (после переноса компонентов в Tier 2).

### 44.6 Обновить docker-compose.yml

Добавить BSL-специфичные сервисы (опционально):

```yaml
# В docker/docker-compose.yml
services:
  # ... существующие сервисы ...

  # TimescaleDB для AI Memory (Фаза 49)
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    ports:
      - "5433:5432"  # Другой порт чтобы не конфликтовать с pgvector
    environment:
      POSTGRES_DB: ai_memory
      POSTGRES_USER: memory
      POSTGRES_PASSWORD: ${TIMESCALE_PASSWORD:-memory_pass}
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "1.0"
    profiles:
      - memory  # Активировать: docker compose --profile memory up

volumes:
  timescaledb_data:
```

**Критерий:** `docker compose config` валиден.

### 44.7 Создать skill `bsl-development`

**Файл:** `.claude/skills/bsl-development/SKILL.md`

```markdown
# BSL Development — разработка на 1С:Предприятие

## Обзор
Скилл для работы с кодом на языке BSL (Built-in Scripting Language)
платформы 1С:Предприятие 8.3.27.

## Триггеры
- 'BSL', '1С код', 'модуль 1С', 'процедура BSL'
- 'конфигурация 1С', 'справочник', 'документ 1С', 'регистр'
- 'модуль объекта', 'модуль формы', 'общий модуль'

## Доступные MCP-инструменты

| Инструмент | MCP сервер | Назначение |
|-----------|-----------|-----------|
| Семантический поиск | `bsl-semantic-search` | Поиск похожего кода (3,908 модулей) |
| Автодокументация | `auto-documenter` | generate_documentation, autoreview, autotestplan |
| Отладка | `bsl-debugger` | breakpoints, step, variables, evaluate |
| API платформы | `bsl-platform-context` | Типы, методы, свойства 1С:8.3.27 |
| AST-анализ | `ast-grep-mcp` | Tree-sitter парсинг BSL |
| LSP | `serena` | Symbol extraction, рефакторинг |

## Workflow
1. Анализ: `ast-grep-mcp` или `serena` для AST/symbols
2. Поиск: `bsl-semantic-search` для похожего кода
3. Контекст: `bsl-platform-context` для API платформы
4. Документация: `auto-documenter` для генерации docs
5. Качество: `autoreview` для code review по стандартам 1С
6. Отладка: `bsl-debugger` при необходимости
```

**Критерий:** Skill router распознаёт BSL-запросы и рекомендует `bsl-development`.

### 44.8 Создать hook `bsl-tool-router.py`

**Файл:** `.claude/hooks/bsl-tool-router.py`
**Событие:** PreToolUse
**Назначение:** При работе с `.bsl` файлами или BSL-запросах — рекомендовать правильные MCP tools.

```python
#!/usr/bin/env python3
"""BSL Tool Router — направляет BSL-задачи к правильным MCP tools."""
import sys
import json

def main():
    raw = sys.stdin.buffer.read().decode("utf-8")
    hook_input = json.loads(raw)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Детектим работу с BSL файлами
    bsl_signals = []

    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
    if file_path and file_path.endswith(".bsl"):
        bsl_signals.append("BSL file detected")

    command = tool_input.get("command", "")
    if any(kw in command.lower() for kw in [".bsl", "1c-enterprise", "bsl-semantic"]):
        bsl_signals.append("BSL command detected")

    result = {"decision": "approve"}

    if bsl_signals:
        result["message"] = (
            f"[BSL-ROUTER] {', '.join(bsl_signals)}. "
            "Доступные инструменты: "
            "mcp__bsl-semantic-search (поиск кода), "
            "mcp__auto-documenter (документация), "
            "mcp__bsl-debugger (отладка), "
            "mcp__bsl-platform-context (API 1С)"
        )

    print(json.dumps(result))

if __name__ == "__main__":
    main()
```

**Критерий:** Hook срабатывает при работе с `.bsl` файлами.

### 44.9 Создать scripts/claude.bat

```bat
@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:menu
cls
echo +======================================================+
echo |        1C-Framework - Claude Code MCP Profiles         |
echo +======================================================+
echo |  1. pdf      - PDF RAG (~15k tokens)                  |
echo |  2. bsl      - 1C Development (~25k tokens)           |
echo |  3. full     - PDF + BSL + Memory (~45k tokens)       |
echo |  4. lazy-mcp - Auto-select (~5k tokens)               |
echo +------------------------------------------------------+
echo |  c. Continue last session (--continue)                 |
echo |  r. Resume session (--resume)                          |
echo |  0. Exit                                               |
echo +======================================================+
echo.

set /p choice="Select profile [1-4, c, r, 0]: "

if "%choice%"=="1" set "profile=pdf"
if "%choice%"=="2" set "profile=bsl"
if "%choice%"=="3" set "profile=full"
if "%choice%"=="4" set "profile=lazy-mcp"
if "%choice%"=="0" exit /b 0

if "%choice%"=="c" (
    set /p cprofile="Profile to continue [1-4]: "
    if "!cprofile!"=="1" set "profile=pdf"
    if "!cprofile!"=="2" set "profile=bsl"
    if "!cprofile!"=="3" set "profile=full"
    if "!cprofile!"=="4" set "profile=lazy-mcp"
    set "extra=--continue"
    goto run
)

if "%choice%"=="r" (
    set /p rprofile="Profile to resume [1-4]: "
    if "!rprofile!"=="1" set "profile=pdf"
    if "!rprofile!"=="2" set "profile=bsl"
    if "!rprofile!"=="3" set "profile=full"
    if "!rprofile!"=="4" set "profile=lazy-mcp"
    set "extra=--resume"
    goto run
)

if not defined profile (
    echo Invalid choice.
    timeout /t 2 >nul
    goto menu
)

:run
echo.
echo Starting Claude Code with profile: %profile%
claude --strict-mcp-config --mcp-config "D:\1С-Framework\.mcp\%profile%.json" %extra% %*
```

**Критерий:** `scripts\claude.bat` запускает Claude Code с выбранным профилем.

### 44.10 Обновить .env.example

Добавить BSL-специфичные переменные:

```bash
# === BSL Development (Phase 44+) ===

# BSL Semantic Search
BSL_QDRANT_COLLECTION=bsl_code_v2
BSL_EMBEDDING_MODEL=nomic-embed-text
BSL_EMBEDDING_DIM=768

# Auto-Documenter (Z.AI GLM-5)
DEEP_REASONING_API_KEY=
DEEP_REASONING_BASE_URL=https://api.z.ai/api/anthropic
DEEP_REASONING_MODEL=glm-5

# Auto-Documenter (AI providers)
AUTODOC_PRIMARY_PROVIDER=gemini
GEMINI_API_KEY=
GROQ_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434

# LLM Rotation
LLM_ROTATION_PRIMARY=mistral
MISTRAL_API_KEY=
OPENROUTER_API_KEY=

# Google Gemini Embeddings (vector-memory)
GOOGLE_API_KEY=
GOOGLE_EMBEDDING_MODEL=text-embedding-004

# AI Memory (TimescaleDB)
TIMESCALE_URL=postgresql://memory:memory_pass@localhost:5433/ai_memory

# Java (bsl-platform-context)
JAVA_HOME=C:\Program Files\Zulu\zulu-17

# BSL Platform
BSL_PLATFORM_PATH=C:\Program Files\1cv8\8.3.27.1859
```

---

## Обновление конфигурации

### skill-router-config.json

Добавить bundle `bsl-dev`:

```json
{
  "name": "bsl-dev",
  "keywords": ["BSL", "1С код", "модуль 1С", "процедура", "функция BSL",
               "конфигурация 1С", "справочник", "документ 1С", "регистр",
               "модуль объекта", "общий модуль", "отладка BSL", "debug 1С"],
  "skills": ["bsl-development"],
  "priority": 8
}
```

### settings.json (hooks)

Добавить `bsl-tool-router.py`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "command": "D:/1С-Framework/.venv/Scripts/python.exe D:/1С-Framework/.claude/hooks/bsl-tool-router.py"
      }
    ]
  }
}
```

---

## Чеклист завершения

- [ ] Директории `src/bsl/`, `src/memory/`, `src/shared/` созданы с `__init__.py`
- [ ] Директории `tools/`, `infra/`, `.mcp/` созданы
- [ ] `pyproject.toml` обновлён: extras `[bsl]`, `[memory]`, `[llm-rotation]`
- [ ] `pip install -e ".[bsl]"` проходит
- [ ] `.mcp/pdf.json`, `.mcp/bsl.json`, `.mcp/full.json` созданы
- [ ] `claude --strict-mcp-config --mcp-config ".mcp/pdf.json"` работает
- [ ] `tools/package.json` создан
- [ ] `docker-compose.yml` обновлён (TimescaleDB в profile `memory`)
- [ ] Skill `bsl-development/SKILL.md` создан
- [ ] Hook `bsl-tool-router.py` создан и зарегистрирован
- [ ] `scripts/claude.bat` создан и работает
- [ ] `.env.example` обновлён с BSL переменными
- [ ] `skill-router-config.json` обновлён с bundle `bsl-dev`
- [ ] Git commit: `feat: Phase 44 — BSL migration infrastructure`
