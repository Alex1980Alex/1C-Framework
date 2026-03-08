"""
Lazy-MCP Server - Main Entry Point

MCP сервер с динамической загрузкой инструментов.
Экспонирует только 2 meta-инструмента для Claude:
1. get_tools_in_category - навигация по категориям
2. execute_tool - выполнение инструментов
"""

import asyncio
import json
import sys
import os
import logging
from pathlib import Path
from typing import Any, Optional

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from registry import Registry
from loader import ServerLoader
from tool_interceptor import get_interceptor, intercept_tool_call, ToolCategory

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("lazy-mcp")

# Глобальные объекты
registry: Registry = None
loader: ServerLoader = None
server = Server("lazy-mcp")


def log_stderr(message: str) -> None:
    """Логирование в stderr для отладки"""
    print(message, file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════════════
# Task-to-Category Routing Map (для автоматического выбора)
# ═══════════════════════════════════════════════════════════════════════════════
TASK_ROUTING = {
    "1c-development": {
        "keywords": ["BSL", "1С", "1C", "процедура", "функция", "модуль", "конфигурация",
                     "справочник", "документ", "регистр", "СправочникМенеджер", "ДокументОбъект",
                     "analyze BSL", "parse 1C", "AST", "syntax tree"],
        "tasks": ["анализ BSL кода", "поиск процедур/функций", "API платформы 1С",
                  "семантический поиск по коду", "отладка BSL"]
    },
    "documentation": {
        "keywords": ["документация", "docs", "RAG", "поиск правил", "best practices",
                     "автодокументирование", "generate docs", "search documentation"],
        "tasks": ["поиск в документации", "генерация документации", "правила разработки"]
    },
    "memory": {
        "keywords": ["память", "memory", "контекст", "история", "запомни", "вспомни",
                     "save context", "remember", "recall", "knowledge graph"],
        "tasks": ["сохранение контекста", "поиск в истории", "knowledge management"]
    },
    "code-analysis": {
        "keywords": ["символы", "symbols", "LSP", "рефакторинг", "навигация",
                     "Python", "JavaScript", "TypeScript", "find references", "go to definition"],
        "tasks": ["анализ Python/JS/TS кода", "поиск символов", "навигация по коду"]
    },
    "file-operations": {
        "keywords": ["файл", "file", "поиск", "grep", "search", "read", "write",
                     "directory", "папка", "содержимое"],
        "tasks": ["поиск в файлах", "чтение/запись файлов", "операции с директориями"]
    },
    "reasoning": {
        "keywords": ["думай", "think", "анализируй", "рассуждение", "step by step",
                     "пошагово", "сложная задача", "branching", "complex problem"],
        "tasks": ["структурированное мышление", "пошаговый анализ", "сложные задачи"]
    },
    "web": {
        "keywords": ["веб", "web", "HTTP", "API", "search", "интернет", "браузер",
                     "fetch", "puppeteer", "scrape"],
        "tasks": ["веб-поиск", "HTTP запросы", "браузерная автоматизация"]
    },
    "utils": {
        "keywords": ["zip", "архив", "конвертация", "markdown", "convert", "docling"],
        "tasks": ["архивация", "конвертация форматов"]
    }
}


def recommend_categories(task_description: str) -> list[dict]:
    """Рекомендовать категории на основе описания задачи"""
    task_lower = task_description.lower()
    recommendations = []

    for category, info in TASK_ROUTING.items():
        score = 0
        matched_keywords = []

        for keyword in info["keywords"]:
            if keyword.lower() in task_lower:
                score += 1
                matched_keywords.append(keyword)

        if score > 0:
            recommendations.append({
                "category": category,
                "score": score,
                "matched_keywords": matched_keywords,
                "typical_tasks": info["tasks"],
                "path": f"/{category}"
            })

    # Сортируем по релевантности
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return recommendations


@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    Возвращает 3 meta-инструмента.
    Это ключ к экономии токенов + автоматический выбор!
    """
    return [
        Tool(
            name="recommend_tools",
            description="""🎯 SMART TOOL RECOMMENDATION - Use this FIRST to automatically find the right tools!

Analyzes your task description and recommends the best category/server/tool path.

WHEN TO USE:
- You have a task but don't know which tool to use
- You want automatic routing to the right MCP server
- Before manually navigating with get_tools_in_category

TASK ROUTING MAP:
┌─────────────────┬──────────────────────────────────────────────────────────┐
│ CATEGORY        │ USE FOR TASKS                                            │
├─────────────────┼──────────────────────────────────────────────────────────┤
│ 1c-development  │ BSL код, процедуры, функции, API платформы 1С           │
│ documentation   │ Поиск документации, генерация docs, правила              │
│ memory          │ Сохранить/вспомнить контекст, история сессий             │
│ code-analysis   │ Python/JS/TS символы, LSP, рефакторинг                   │
│ file-operations │ Поиск файлов, grep, чтение/запись                        │
│ reasoning       │ Сложные задачи, пошаговый анализ, think step-by-step    │
│ web             │ Веб-поиск, HTTP, браузерная автоматизация                │
│ utils           │ ZIP архивы, конвертация документов                       │
└─────────────────┴──────────────────────────────────────────────────────────┘

Example:
- recommend_tools("найди все процедуры в BSL файле")
  → {"recommended": "/1c-development/ast-grep-mcp", "tool": "ast_grep"}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Describe what you want to do (in any language)"
                    }
                },
                "required": ["task_description"]
            }
        ),
        Tool(
            name="get_tools_in_category",
            description="""📂 Navigate tool categories - use after recommend_tools or when you know the category.

Path structure:
- "/" → All categories with descriptions
- "/category" → Servers in category
- "/category/server" → Tool list with inputSchema

QUICK REFERENCE:
/1c-development     → ast-grep-mcp, bsl-platform-context, bsl-semantic-search
/documentation      → 1c-docs-rag, auto-documenter
/memory             → unified-memory, memory-ai, conversation-memory
/code-analysis      → serena (LSP)
/file-operations    → ripgrep, filesystem
/reasoning          → sequential-thinking, code-reasoning
/web                → brave, fetch, puppeteer (docker-mcp)
/utils              → zip, markitdown, docling""",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Category path: '/', '/category', or '/category/server'",
                        "default": "/"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="execute_tool",
            description="""⚡ Execute any tool dynamically - servers load on-demand.

Path format: /category/server/tool_name

COMMON PATTERNS:
┌─────────────────────────────────────────────────────────────────────────────┐
│ BSL Analysis:                                                               │
│   /1c-development/ast-grep-mcp/ast_grep                                    │
│   {"pattern": "Процедура $NAME($$$PARAMS)", "language": "bsl"}             │
├─────────────────────────────────────────────────────────────────────────────┤
│ Documentation Search:                                                       │
│   /documentation/1c-docs-rag/search_docs                                   │
│   {"query": "правила документирования BSL"}                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Memory Operations:                                                          │
│   /memory/unified-memory/search_memory                                     │
│   {"query": "последняя задача"}                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ File Search:                                                                │
│   /file-operations/ripgrep/search                                          │
│   {"pattern": "TODO", "path": "."}                                          │
└─────────────────────────────────────────────────────────────────────────────┘""",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_path": {
                        "type": "string",
                        "description": "Full path: /category/server/tool_name"
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Tool arguments (check get_tools_in_category for schema)",
                        "default": {}
                    }
                },
                "required": ["tool_path"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Обработчик вызовов инструментов"""
    log_stderr(f"[lazy-mcp] Tool call: {name} with args: {arguments}")

    try:
        if name == "recommend_tools":
            result = await handle_recommend_tools(arguments)
        elif name == "get_tools_in_category":
            result = await handle_get_tools(arguments)
        elif name == "execute_tool":
            result = await handle_execute_tool(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]

    except Exception as e:
        logger.error(f"Error in {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)}, ensure_ascii=False)
        )]


async def handle_recommend_tools(arguments: dict) -> dict[str, Any]:
    """
    Обработчик recommend_tools - умная рекомендация через 1c-docs-rag.

    Использует RAG поиск по документации для нахождения релевантных инструментов.
    Fallback на статический TASK_ROUTING если 1c-docs-rag недоступен.
    """
    task_description = arguments.get("task_description", "")

    if not task_description:
        return {
            "error": "task_description is required",
            "hint": "Опишите задачу, например: 'найди все процедуры в BSL коде'"
        }

    log_stderr(f"[lazy-mcp] Analyzing task: {task_description}")

    result = {
        "task": task_description,
        "source": "hybrid",  # static + docs-rag
        "recommendations": []
    }

    # ═══════════════════════════════════════════════════════════════════
    # 1. Поиск в 1c-docs-rag (ОСНОВНОЙ источник)
    # ═══════════════════════════════════════════════════════════════════
    docs_recommendations = []
    try:
        # Пытаемся получить рекомендации из 1c-docs-rag
        docs_server = await loader.get_server("1c-docs-rag")
        if docs_server:
            search_result = await loader.execute_tool(
                "1c-docs-rag",
                "search_docs",
                {
                    "query": f"MCP инструмент tool {task_description}",
                    "limit": 5,
                    "search_type": "hybrid"
                }
            )

            # Парсим результаты поиска
            if search_result and (not isinstance(search_result, dict) or "error" not in search_result):
                log_stderr(f"[lazy-mcp] Got docs results: {type(search_result)}")
                docs_recommendations = parse_docs_recommendations(search_result, task_description)
                result["source"] = "1c-docs-rag"

    except Exception as e:
        log_stderr(f"[lazy-mcp] 1c-docs-rag search failed: {e}, using fallback")

    # ═══════════════════════════════════════════════════════════════════
    # 2. Статический TASK_ROUTING (fallback или дополнение)
    # ═══════════════════════════════════════════════════════════════════
    static_recommendations = recommend_categories(task_description)

    # ═══════════════════════════════════════════════════════════════════
    # 3. Объединение результатов
    # ═══════════════════════════════════════════════════════════════════

    # Добавляем рекомендации из документации (если есть)
    for doc_rec in docs_recommendations[:2]:
        result["recommendations"].append({
            "source": "1c-docs-rag",
            "type": "documentation",
            "title": doc_rec.get("title", ""),
            "relevance": doc_rec.get("relevance", 0),
            "doc_id": doc_rec.get("doc_id", ""),
            "suggested_tools": doc_rec.get("tools", []),
            "hint": doc_rec.get("hint", "")
        })

    # Добавляем статические рекомендации
    for rec in static_recommendations[:3]:
        category = rec["category"]
        servers = registry.get_servers_in_category(category) if registry else []

        rec_entry = {
            "source": "task_routing",
            "type": "category",
            "category": category,
            "relevance_score": rec["score"],
            "matched_keywords": rec["matched_keywords"],
            "typical_tasks": rec["typical_tasks"],
            "path": rec["path"],
            "servers": servers
        }

        # Подсказки по инструментам
        suggested = get_suggested_tool(category)
        if suggested:
            rec_entry["suggested_tool"] = suggested

        result["recommendations"].append(rec_entry)

    # ═══════════════════════════════════════════════════════════════════
    # 4. Quick Action - если уверены в рекомендации
    # ═══════════════════════════════════════════════════════════════════
    if result["recommendations"]:
        top = result["recommendations"][0]
        if top.get("type") == "documentation" and top.get("suggested_tools"):
            tool = top["suggested_tools"][0]
            result["quick_action"] = {
                "message": f"📚 Найдена документация: {top.get('title', '')}",
                "tool_path": tool.get("path", ""),
                "example": tool.get("example", "")
            }
        elif top.get("type") == "category" and top.get("relevance_score", 0) >= 2:
            result["quick_action"] = {
                "message": f"🎯 Рекомендую категорию '{top['category']}'",
                "tool_path": top.get("suggested_tool", {}).get("path", ""),
                "hint": top.get("suggested_tool", {}).get("hint", "")
            }

    return result


def parse_docs_recommendations(search_result: Any, task: str) -> list[dict]:
    """Парсинг результатов поиска из 1c-docs-rag"""
    recommendations = []

    # Результат может быть строкой или объектом
    if isinstance(search_result, str):
        # Парсим markdown-like результат
        lines = search_result.split('\n')
        current_doc = {}

        for line in lines:
            if line.startswith('## '):
                if current_doc:
                    recommendations.append(current_doc)
                current_doc = {"title": line[3:].strip(), "tools": []}
            elif 'AST-GREP' in line.upper() or 'ast_grep' in line:
                current_doc.setdefault("tools", []).append({
                    "path": "/1c-development/ast-grep-mcp/ast_grep",
                    "name": "ast_grep",
                    "example": "pattern='Процедура $NAME', language='bsl'"
                })
            elif 'RIPGREP' in line.upper() or 'ripgrep' in line.lower():
                current_doc.setdefault("tools", []).append({
                    "path": "/file-operations/ripgrep/search",
                    "name": "search"
                })
            elif 'docs-rag' in line.lower() or 'search_docs' in line:
                current_doc.setdefault("tools", []).append({
                    "path": "/documentation/1c-docs-rag/search_docs",
                    "name": "search_docs"
                })
            elif '🆔 ID:' in line:
                current_doc["doc_id"] = line.split('`')[1] if '`' in line else ""
            elif 'Релевантность:' in line:
                try:
                    current_doc["relevance"] = float(line.split(':')[1].split()[0])
                except:
                    pass

        if current_doc:
            recommendations.append(current_doc)

    return recommendations


def get_suggested_tool(category: str) -> Optional[dict]:
    """Получить подсказку по инструменту для категории"""
    suggestions = {
        "1c-development": {
            "path": "/1c-development/ast-grep-mcp/ast_grep",
            "hint": "Для поиска процедур: pattern='Процедура $NAME($$$PARAMS)', language='bsl'"
        },
        "documentation": {
            "path": "/documentation/1c-docs-rag/search_docs",
            "hint": "query='ваш поисковый запрос'"
        },
        "memory": {
            "path": "/memory/unified-memory/search_memory",
            "hint": "query='что искать в памяти'"
        },
        "file-operations": {
            "path": "/file-operations/ripgrep/search",
            "hint": "pattern='regex', path='.'"
        },
        "reasoning": {
            "path": "/reasoning/sequential-thinking/sequentialthinking",
            "hint": "thought='первый шаг анализа', thoughtNumber=1, totalThoughts=5"
        },
        "code-analysis": {
            "path": "/code-analysis/serena/find_symbol",
            "hint": "name_path='ClassName/method_name'"
        },
        "web": {
            "path": "/web/brave/brave_web_search",
            "hint": "query='поисковый запрос'"
        }
    }
    return suggestions.get(category)


async def handle_get_tools(arguments: dict) -> dict[str, Any]:
    """
    Обработчик get_tools_in_category.

    Навигация по иерархии:
    / → категории
    /category → серверы
    /category/server → инструменты (с загрузкой сервера)
    """
    path = arguments.get("path", "/").strip()
    if not path:
        path = "/"

    log_stderr(f"[lazy-mcp] Navigating to: {path}")

    # Получаем информацию о пути
    info = registry.get_category_info(path)

    if "error" in info:
        return info

    # Если это уровень сервера - загружаем и получаем реальные инструменты
    if info.get("type") == "tools":
        parts = path.strip('/').split('/')
        if len(parts) >= 2:
            server_name = parts[1]
            server = await loader.get_server(server_name)

            if server and server.tools:
                # Форматируем инструменты для отображения
                tools_info = []
                for tool in server.tools:
                    tools_info.append({
                        "name": tool.get("name", "unknown"),
                        "description": tool.get("description", "")[:200] + "..." if len(tool.get("description", "")) > 200 else tool.get("description", ""),
                        "full_path": f"{path}/{tool.get('name', 'unknown')}"
                    })
                info["items"] = tools_info
                info["tools_count"] = len(tools_info)

    return info


async def handle_execute_tool(arguments: dict) -> Any:
    """
    Обработчик execute_tool с интеграцией MCP Tool Interceptor.

    Парсит путь, классифицирует инструмент по категории A/B/C,
    и маршрутизирует через Z.AI или выполняет напрямую.

    Маршрутизация:
    - Category A (100% Z.AI): Детерминированные операции
    - Category B (Z.AI + валидация): Требуют проверки Claude
    - Category C (Claude): Сложный reasoning, архитектура

    Returns:
        Результат выполнения или инструкция для Claude
    """
    tool_path = arguments.get("tool_path", "")
    tool_args = arguments.get("arguments", {})
    use_interceptor = arguments.get("use_interceptor", True)  # Можно отключить

    if not tool_path:
        return {"error": "tool_path is required"}

    log_stderr(f"[lazy-mcp] Executing: {tool_path} with args: {tool_args}")

    # Парсим путь
    category, server_name, tool_name = registry.find_server_by_path(tool_path)

    if not server_name:
        return {"error": f"Invalid tool path: {tool_path}. Use /category/server/tool format."}

    if not tool_name:
        # Если не указан tool - показать доступные
        server = await loader.get_server(server_name)
        if server and server.tools:
            return {
                "message": f"No tool specified. Available tools in {server_name}:",
                "tools": [t.get("name") for t in server.tools]
            }
        return {"error": f"Could not load server: {server_name}"}

    # ═══════════════════════════════════════════════════════════════════════════
    # MCP Tool Interceptor Integration
    # ═══════════════════════════════════════════════════════════════════════════
    if use_interceptor:
        try:
            interceptor = get_interceptor()

            # Классифицируем инструмент
            tool_category = interceptor.classify_tool(server_name, tool_name)
            log_stderr(
                f"[lazy-mcp] Tool {server_name}/{tool_name} -> "
                f"Category {tool_category.value.upper()}"
            )

            # Для Category A/B - пробуем через интерцептор
            if tool_category in (ToolCategory.A, ToolCategory.B):
                # Передаём callback для прямого выполнения как fallback
                async def direct_execute(srv, tl, args):
                    return await loader.execute_tool(srv, tl, args)

                intercept_result = await intercept_tool_call(
                    server_name, tool_name, tool_args,
                    execute_direct=direct_execute
                )

                if intercept_result.intercepted:
                    # Успешный перехват
                    if intercept_result.error:
                        log_stderr(
                            f"[lazy-mcp] Interceptor warning: {intercept_result.error}, "
                            f"but result available via {intercept_result.provider}"
                        )

                    # Для Category B добавляем метаданные о валидации
                    if tool_category == ToolCategory.B and isinstance(intercept_result.result, dict):
                        if intercept_result.result.get("needs_validation"):
                            return {
                                "zai_result": intercept_result.result.get("zai_result"),
                                "validation_required": True,
                                "validation_prompt": intercept_result.result.get("validation_prompt"),
                                "routing": {
                                    "category": tool_category.value,
                                    "provider": intercept_result.provider,
                                    "latency_ms": intercept_result.latency_ms
                                }
                            }

                    return {
                        "result": intercept_result.result,
                        "routing": {
                            "category": tool_category.value,
                            "provider": intercept_result.provider,
                            "latency_ms": intercept_result.latency_ms
                        }
                    }

            # Category C или неперехваченный - прямое выполнение
            log_stderr(f"[lazy-mcp] Direct execution for Category {tool_category.value.upper()}")

        except Exception as e:
            log_stderr(f"[lazy-mcp] Interceptor error: {e}, falling back to direct execution")

    # ═══════════════════════════════════════════════════════════════════════════
    # Direct Execution (fallback или Category C)
    # ═══════════════════════════════════════════════════════════════════════════
    result = await loader.execute_tool(server_name, tool_name, tool_args)
    return result


async def main():
    """Точка входа"""
    global registry, loader

    log_stderr("[lazy-mcp] Starting Lazy-MCP Server...")

    # Определяем путь к конфигурации (приоритет: env > default)
    env_config = os.environ.get('LAZY_MCP_CONFIG')
    if env_config:
        config_path = Path(env_config)
        log_stderr(f"[lazy-mcp] Using config from LAZY_MCP_CONFIG: {config_path}")
    else:
        config_path = Path(__file__).parent.parent / "config" / "registry.yaml"
        log_stderr(f"[lazy-mcp] Using default config: {config_path}")

    if not config_path.exists():
        log_stderr(f"[lazy-mcp] ERROR: Config not found: {config_path}")
        log_stderr("[lazy-mcp] Creating default config...")
        # Создаем конфиг по умолчанию если нет
        config_path.parent.mkdir(parents=True, exist_ok=True)
        create_default_config(config_path)

    # Инициализация
    registry = Registry(config_path)
    loader = ServerLoader(registry, max_active=5)

    log_stderr(f"[lazy-mcp] Loaded {len(registry.servers)} servers in {len(registry.categories)} categories")
    log_stderr("[lazy-mcp] Ready. Exposing 3 meta-tools: recommend_tools, get_tools_in_category, execute_tool")

    # Запуск сервера
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def create_default_config(path: Path) -> None:
    """Создать конфигурацию по умолчанию"""
    default_config = """# Lazy-MCP Registry Configuration
# Иерархия категорий и серверов

categories:
  1c-development:
    description: "Инструменты разработки 1С:Предприятие"
    servers:
      ast-grep-mcp:
        command: "D:\\\\1С-Framework\\\\ast-grep-mcp\\\\.venv\\\\Scripts\\\\python.exe"
        args: ["D:\\\\1С-Framework\\\\ast-grep-mcp\\\\main.py"]
        env:
          PYTHONIOENCODING: "utf-8"
        description: "AST-анализ BSL кода (100% надёжность)"

      bsl-platform-context:
        command: "java"
        args: ["-jar", "D:\\\\1С-Framework\\\\mcp-servers\\\\mcp-bsl-context-0.3.1.jar", "--platform-path", "C:\\\\Program Files\\\\1cv8\\\\8.3.27.1859\\\\bin"]
        env:
          JAVA_HOME: "C:\\\\Program Files\\\\Zulu\\\\zulu-17"
        description: "API платформы 1С - типы, методы, свойства"

  documentation:
    description: "Поиск и генерация документации"
    servers:
      1c-docs-rag:
        command: "python"
        args: ["D:\\\\1С-Framework\\\\scripts\\\\docs-mcp\\\\mcp_server.py"]
        env:
          PYTHONIOENCODING: "utf-8"
          DOCS_ROOT: "D:/1C-Enterprise_Framework/docs"
        description: "RAG поиск по документации (Hybrid FTS5 + Semantic)"

  memory:
    description: "Системы памяти и контекста"
    servers:
      unified-memory:
        command: "C:\\\\Users\\\\AlexT\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\Python313\\\\python.exe"
        args: ["D:\\\\1С-Framework\\\\unified-memory-mcp\\\\server.py"]
        env:
          ANTHROPIC_DB_PATH: "D:/1C-Enterprise_Framework/cache/mcp_database.db"
        description: "Unified Memory System (6 backends)"

  file-operations:
    description: "Операции с файлами и поиск"
    servers:
      ripgrep:
        command: "npx"
        args: ["-y", "mcp-ripgrep"]
        description: "Продвинутый поиск по файлам (rg)"
        type: "npx"

  code-analysis:
    description: "Анализ и рассуждения о коде"
    servers:
      serena:
        command: "D:\\\\1С-Framework\\\\serena\\\\.venv\\\\Scripts\\\\serena.exe"
        args: ["start-mcp-server", "--context", "ide-assistant"]
        timeout: 180000
        description: "LSP для Python/JS/TS"

  reasoning:
    description: "Структурированное мышление"
    servers:
      sequential-thinking:
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-sequential-thinking"]
        description: "Пошаговое структурированное мышление"
        type: "npx"
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(default_config)


if __name__ == "__main__":
    asyncio.run(main())
