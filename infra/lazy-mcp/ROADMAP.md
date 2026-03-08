# Lazy-MCP: Детальная дорожная карта реализации

## Обзор проекта

**Цель:** Сократить потребление токенов MCP серверами с ~68k до ~3k (95% экономия)

**Подход:** Proxy-сервер, который экспонирует Claude только 2-3 meta-инструмента вместо сотен реальных инструментов

---

## Фаза 1: Архитектура и проектирование (30 мин)

### 1.1 Компоненты системы

```
lazy-mcp/
├── src/
│   ├── server.py          # MCP сервер (точка входа)
│   ├── registry.py         # Реестр MCP серверов и категорий
│   ├── loader.py           # Динамический загрузчик серверов
│   ├── executor.py         # Выполнение инструментов
│   └── tools/
│       ├── __init__.py
│       ├── get_tools.py    # Meta-tool: навигация
│       └── execute.py      # Meta-tool: выполнение
├── config/
│   ├── registry.yaml       # Конфигурация всех серверов
│   └── categories.yaml     # Иерархия категорий
├── tests/
│   ├── test_registry.py
│   ├── test_loader.py
│   └── test_integration.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

### 1.2 Поток данных

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLAUDE CODE                                   │
│  Видит только 2 инструмента:                                        │
│  • get_tools_in_category(path: str) → list[str]                     │
│  • execute_tool(tool_path: str, arguments: dict) → any              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LAZY-MCP PROXY                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Registry   │  │   Loader    │  │  Executor   │                 │
│  │  (config)   │  │  (spawn)    │  │  (call)     │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     REAL MCP SERVERS                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │  brave   │ │ serena   │ │ ast-grep │ │ docker   │ ...          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Структура категорий

```yaml
/
├── 1c-development/          # Разработка 1С
│   ├── ast-grep-mcp         # AST анализ BSL
│   ├── bsl-platform-context # API платформы
│   ├── bsl-semantic-search  # Семантический поиск
│   └── bsl-debugger         # Отладка
├── code-analysis/           # Анализ кода
│   ├── serena               # LSP Python/JS/TS
│   └── code-reasoning       # Пошаговый анализ
├── web-search/              # Веб поиск
│   ├── brave                # Brave Search
│   └── fetch                # HTTP fetch
├── file-operations/         # Файловые операции
│   ├── filesystem           # Файловая система
│   └── ripgrep              # Поиск в файлах
├── memory/                  # Память
│   ├── unified-memory       # Unified Memory
│   ├── memory-ai            # AI Memory
│   └── memory               # Knowledge Graph
├── documentation/           # Документация
│   ├── 1c-docs-rag          # RAG поиск
│   └── auto-documenter      # Генерация доков
└── reasoning/               # Рассуждения
    └── sequential-thinking  # Структурированное мышление
```

---

## Фаза 2: Реализация ядра (1.5 часа)

### 2.1 Registry - Реестр серверов (20 мин)

**Файл:** `src/registry.py`

**Функционал:**
- Загрузка конфигурации из YAML
- Построение иерархии категорий
- Маппинг tool_path → server_config
- Кеширование схем инструментов

**API:**
```python
class Registry:
    def get_categories(self, path: str = "/") -> list[str]
    def get_tools(self, category: str) -> list[ToolInfo]
    def get_server_config(self, tool_path: str) -> ServerConfig
    def get_tool_schema(self, tool_path: str) -> dict
```

### 2.2 Loader - Загрузчик серверов (30 мин)

**Файл:** `src/loader.py`

**Функционал:**
- Запуск MCP серверов по требованию
- Управление процессами (spawn/kill)
- Пул активных серверов (LRU cache)
- Healthcheck и переподключение

**API:**
```python
class ServerLoader:
    async def get_server(self, server_name: str) -> MCPClient
    async def ensure_running(self, server_name: str) -> bool
    async def shutdown_server(self, server_name: str) -> None
    async def list_active(self) -> list[str]
```

### 2.3 Executor - Исполнитель (20 мин)

**Файл:** `src/executor.py`

**Функционал:**
- Маршрутизация вызовов к серверам
- Сериализация/десериализация аргументов
- Обработка ошибок
- Логирование вызовов

**API:**
```python
class ToolExecutor:
    async def execute(self, tool_path: str, arguments: dict) -> Any
    async def get_tool_info(self, tool_path: str) -> ToolInfo
```

### 2.4 MCP Server - Точка входа (20 мин)

**Файл:** `src/server.py`

**Функционал:**
- FastMCP сервер
- 2 экспонируемых инструмента
- stdio транспорт
- Graceful shutdown

---

## Фаза 3: Meta-tools (30 мин)

### 3.1 get_tools_in_category

**Сигнатура:**
```python
@mcp.tool()
async def get_tools_in_category(path: str = "/") -> str:
    """
    Navigate through available tool categories.

    Args:
        path: Category path (e.g., "/", "/1c-development", "/web-search/brave")

    Returns:
        JSON list of subcategories or tools at this path

    Examples:
        get_tools_in_category("/") → ["1c-development", "web-search", ...]
        get_tools_in_category("/1c-development") → ["ast-grep-mcp", "bsl-platform-context", ...]
        get_tools_in_category("/1c-development/ast-grep-mcp") → [tool schemas...]
    """
```

### 3.2 execute_tool

**Сигнатура:**
```python
@mcp.tool()
async def execute_tool(tool_path: str, arguments: dict = {}) -> str:
    """
    Execute a tool from any MCP server.

    Args:
        tool_path: Full path to tool (e.g., "/1c-development/ast-grep-mcp/ast_grep")
        arguments: Tool arguments as JSON object

    Returns:
        Tool execution result

    Examples:
        execute_tool("/web-search/brave/brave_web_search", {"query": "MCP"})
        execute_tool("/1c-development/ast-grep-mcp/ast_grep", {"pattern": "Процедура $NAME"})
    """
```

---

## Фаза 4: Конфигурация (20 мин)

### 4.1 Registry YAML

**Файл:** `config/registry.yaml`

```yaml
categories:
  1c-development:
    description: "Инструменты разработки 1С:Предприятие"
    servers:
      ast-grep-mcp:
        command: "D:\\1C-Enterprise_Framework\\ast-grep-mcp\\.venv\\Scripts\\python.exe"
        args: ["D:\\1C-Enterprise_Framework\\ast-grep-mcp\\main.py"]
        env:
          PYTHONIOENCODING: "utf-8"
        description: "AST-анализ BSL кода"

      bsl-platform-context:
        command: "java"
        args: ["-jar", "D:\\1C-Enterprise_Framework\\mcp-servers\\mcp-bsl-context-0.3.1.jar"]
        description: "API платформы 1С"

  web-search:
    description: "Веб-поиск и HTTP"
    servers:
      brave:
        type: "docker-mcp"
        image: "mcp/brave-search"
        description: "Brave Search API"
```

### 4.2 MCP Profile

**Файл:** `.mcp/lazy-mcp.json`

```json
{
  "name": "Lazy-MCP Profile",
  "description": "95% экономия токенов через динамическую загрузку",
  "mcpServers": {
    "lazy-mcp": {
      "command": "python",
      "args": ["D:\\1C-Enterprise_Framework\\Проекты\\lazy-mcp\\src\\server.py"],
      "timeout": 60000
    }
  }
}
```

---

## Фаза 5: Тестирование (30 мин)

### 5.1 Unit тесты

- `test_registry.py` - загрузка конфига, навигация
- `test_loader.py` - запуск/остановка серверов
- `test_executor.py` - выполнение инструментов

### 5.2 Интеграционные тесты

- Запуск lazy-mcp → навигация → выполнение
- Тест с реальным ast-grep-mcp
- Тест с docker-mcp серверами

### 5.3 Проверка экономии токенов

```bash
# До (docker-mcp)
claude --mcp-config .mcp.json
# → ~100k токенов в контексте

# После (lazy-mcp)
claude --mcp-config .mcp/lazy-mcp.json
# → ~35k токенов (экономия 65k)
```

---

## Фаза 6: Интеграция (15 мин)

### 6.1 Создание профиля Claude Code

```json
{
  "$schema": "https://raw.githubusercontent.com/anthropics/claude-code/main/.mcp.schema.json",
  "name": "Lazy-MCP Profile",
  "mcpServers": {
    "lazy-mcp": { ... }
  }
}
```

### 6.2 Добавление в slash-command

```markdown
# /mcp-profile lazy-mcp
claude --mcp-config .mcp/lazy-mcp.json
```

---

## Временная оценка

| Фаза | Задача | Время |
|------|--------|-------|
| 1 | Архитектура | 30 мин |
| 2 | Ядро (registry, loader, executor) | 1.5 часа |
| 3 | Meta-tools | 30 мин |
| 4 | Конфигурация | 20 мин |
| 5 | Тестирование | 30 мин |
| 6 | Интеграция | 15 мин |
| **Итого** | | **~3.5 часа** |

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| MCP сервер не стартует | Средняя | Healthcheck + retry |
| Timeout при первом вызове | Высокая | Предзагрузка критичных серверов |
| Несовместимость docker-mcp | Низкая | Fallback на native серверы |
| Ошибки сериализации | Средняя | Строгая валидация JSON |

---

## Метрики успеха

1. **Токены:** 68k → 3k (95% экономия)
2. **Latency:** первый вызов <3s, последующие <500ms
3. **Reliability:** 99% успешных вызовов
4. **Coverage:** все серверы из .mcp.json доступны

---

## Следующие шаги после MVP

1. **Кеширование схем** - офлайн хранение tool schemas
2. **Keyword auto-detect** - автоматическое определение нужного сервера
3. **LRU pool** - ограничение активных серверов (max 5)
4. **Web UI** - дашборд активных серверов
5. **Metrics** - Prometheus метрики
