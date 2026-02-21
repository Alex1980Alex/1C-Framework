---
name: langchain-mcp-tools
description: >
  MCP (Model Context Protocol) в LangChain: MultiServerMCPClient, транспорты (stdio, HTTP, SSE),
  tools/resources/prompts, interceptors, progress callbacks, elicitation, stateful sessions.
  Триггеры: 'MCP langchain', 'langchain-mcp-adapters', 'MultiServerMCPClient',
  'MCP tools langchain', 'MCP transport', 'stdio transport', 'streamable-http',
  'MCP interceptor', 'tool interceptor', 'MCP resources', 'MCP prompts',
  'MCP elicitation', 'MCP progress', 'MCP session', 'MCP client langchain'.
  НЕ для MCP Server фреймворка — используй pdf-knowledge.
  НЕ для Claude Code MCP — используй claude-code-cli-interactive.
---

# MCP (Model Context Protocol) в LangChain

## Установка

```bash
pip install langchain-mcp-adapters
```

---

## Транспорты

### stdio (локальный процесс)

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

async with MultiServerMCPClient({
    "math": {
        "transport": "stdio",
        "command": "python",
        "args": ["math_server.py"]
    },
    "weather": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-weather"]
    }
}) as client:
    tools = client.get_tools()
    agent = create_agent(model="gpt-4.1", tools=tools)
    result = agent.invoke({"messages": [...]})
```

### HTTP / streamable-http (удалённый сервер)

```python
async with MultiServerMCPClient({
    "remote_api": {
        "transport": "streamable_http",
        "url": "https://api.example.com/mcp",
        "headers": {"Authorization": "Bearer TOKEN"}
    }
}) as client:
    tools = client.get_tools()
```

### SSE (legacy streaming)

```python
async with MultiServerMCPClient({
    "sse_server": {
        "transport": "sse",
        "url": "http://localhost:3000/sse"
    }
}) as client:
    tools = client.get_tools()
```

---

## Capabilities

### Tools (инструменты)

```python
tools = client.get_tools()  # LangChain-совместимые tools
# Автоматически конвертируются из MCP → @tool формат
```

### Resources (ресурсы)

```python
resources = await client.list_resources("server_name")
content = await client.read_resource("server_name", "file:///path/to/doc.txt")
# Возвращает Blob объекты
```

### Prompts (шаблоны промптов)

```python
prompts = await client.list_prompts("server_name")
messages = await client.get_prompt("server_name", "summarize", {"text": "..."})
# Возвращает список messages
```

---

## Interceptors (middleware для MCP)

### Инъекция контекста

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

def inject_user_context(request, next_handler):
    """Add user_id to every tool call."""
    request.arguments["user_id"] = "current_user_123"
    return next_handler(request)

async with MultiServerMCPClient({
    "api": {
        "transport": "stdio",
        "command": "python",
        "args": ["server.py"],
        "interceptors": [inject_user_context]
    }
}) as client:
    tools = client.get_tools()
```

### Store access (persistence)

```python
def store_interceptor(request, next_handler):
    """Save tool results to store."""
    result = next_handler(request)
    store.put(("tool_results",), request.name, {
        "args": request.arguments,
        "result": result
    })
    return result
```

### Authorization

```python
def auth_interceptor(request, next_handler):
    """Block unauthorized tool calls."""
    user_role = get_current_role()
    if request.name == "delete_data" and user_role != "admin":
        raise PermissionError("Admin only")
    return next_handler(request)
```

### Rate limiting

```python
import time

call_times = {}
def rate_limit_interceptor(request, next_handler):
    """Limit to 10 calls per minute per tool."""
    now = time.time()
    key = request.name
    times = call_times.setdefault(key, [])
    times = [t for t in times if now - t < 60]
    if len(times) >= 10:
        raise Exception(f"Rate limit exceeded for {key}")
    times.append(now)
    call_times[key] = times
    return next_handler(request)
```

### Command-based flow control

```python
from langgraph.types import Command

def routing_interceptor(request, next_handler):
    """Route based on tool result."""
    result = next_handler(request)
    if "escalate" in str(result):
        return Command(goto="human_review", update={"tool_result": result})
    return result
```

---

## Progress Callbacks

```python
def on_progress(progress):
    """Real-time progress from MCP server."""
    print(f"Progress: {progress.percentage}% - {progress.message}")

async with MultiServerMCPClient({
    "server": {
        "transport": "stdio",
        "command": "python",
        "args": ["server.py"],
        "progress_callback": on_progress
    }
}) as client:
    tools = client.get_tools()
```

---

## Elicitation (интерактивный ввод)

```python
def elicitation_handler(request):
    """Handle MCP server's request for user input."""
    if request.type == "confirm":
        return input(f"{request.message} (y/n): ") == "y"
    elif request.type == "text":
        return input(f"{request.message}: ")

async with MultiServerMCPClient({
    "server": {
        "transport": "stdio",
        "command": "python",
        "args": ["server.py"],
        "elicitation_handler": elicitation_handler
    }
}) as client:
    tools = client.get_tools()
```

---

## Stateful Sessions

```python
# Именованные сессии для persistent connections
session = client.session("data_analysis")
# Все вызовы через session сохраняют контекст MCP-сервера
result = await session.call_tool("query", {"sql": "SELECT ..."})
```

---

## Интеграция с create_agent

```python
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

async with MultiServerMCPClient({
    "filesystem": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "github": {
        "transport": "streamable_http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer TOKEN"}
    }
}) as client:
    agent = create_agent(
        model="gpt-4.1",
        tools=client.get_tools(),
        system_prompt="You have access to filesystem and GitHub."
    )

    result = agent.invoke({
        "messages": [{"role": "user", "content": "List files in /tmp"}]
    })
```

---

**Источники:** Lang Chain/Расширенное использование/Протокол контекста модели (MCP).md
