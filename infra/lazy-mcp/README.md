# Lazy-MCP - Dynamic MCP Server Loading

> 95% Token Savings through On-Demand Server Loading + Automatic Tool Selection

## Problem

Claude Code sees ALL tools from ALL MCP servers at once. With 20+ servers each having 5-20 tools, this means:
- **100k+ tokens** just for tool descriptions
- **Slower responses** due to context bloat
- **Higher costs** from unnecessary tokens

## Solution

Lazy-MCP exposes only **3 meta-tools** to Claude:

```
1. recommend_tools(task_description) - SMART automatic tool recommendation
2. get_tools_in_category(path) - Navigate categories
3. execute_tool(tool_path, args) - Execute any tool
```

**Result: ~100k tokens → ~5k tokens (95% reduction) + Automatic Selection**

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Claude Code                                 │
│                                                                 │
│   Sees only 2 tools:                                            │
│   - get_tools_in_category                                       │
│   - execute_tool                                                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Lazy-MCP Server                               │
│                                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│   │  Registry   │  │   Loader    │  │    LRU Pool (5 max)    ││
│   │  (YAML)     │  │  (dynamic)  │  │    Active Servers       ││
│   └─────────────┘  └─────────────┘  └─────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              MCP Servers (loaded on-demand)                     │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ast-grep  │ │1c-docs-  │ │unified-  │ │ serena   │  ...      │
│  │  -mcp    │ │   rag    │ │ memory   │ │          │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Usage Example

### Automatic Selection (Recommended)

```
User: "Analyze BSL code for procedures"

Claude:
1. recommend_tools("Analyze BSL code for procedures")
   → {
       "recommendations": [
         {"category": "1c-development", "suggested_tool": "/1c-development/ast-grep-mcp/ast_grep"}
       ],
       "quick_action": {"tool_path": "/1c-development/ast-grep-mcp/ast_grep"}
     }

2. execute_tool("/1c-development/ast-grep-mcp/ast_grep", {
     "pattern": "Процедура $NAME($$$PARAMS)",
     "language": "bsl"
   })
   → Results from ast-grep-mcp
```

### Manual Navigation (Alternative)

```
Claude:
1. get_tools_in_category("/")
   → ["1c-development", "documentation", "memory", ...]

2. get_tools_in_category("/1c-development")
   → ["ast-grep-mcp", "bsl-platform-context", ...]

3. get_tools_in_category("/1c-development/ast-grep-mcp")
   → [tool descriptions with inputSchema]

4. execute_tool("/1c-development/ast-grep-mcp/ast_grep", {...})
   → Results
```

## Installation

```bash
# Already installed in 1C-Enterprise Framework
cd D:\1C-Enterprise_Framework\lazy-mcp

# Dependencies (already installed)
.venv\Scripts\pip install -r requirements.txt
```

## Configuration

### MCP Profile

Use the lazy-mcp profile to start Claude Code:

```bash
claude --mcp-config .mcp/lazy-mcp.json
```

### Registry

Edit `config/registry.yaml` to add/remove servers:

```yaml
categories:
  1c-development:
    description: "1C Development Tools"
    servers:
      ast-grep-mcp:
        command: "python"
        args: ["path/to/main.py"]
        env:
          PYTHONIOENCODING: "utf-8"
        description: "AST analysis for BSL code"
        timeout: 60000
```

## Automatic Tool Selection

The `recommend_tools` feature uses a **hybrid approach**:

1. **1c-docs-rag search** (primary) - searches documentation for tool descriptions
2. **Static TASK_ROUTING** (fallback) - keyword-based category mapping

### Task Routing Map

| Category | Keywords | Typical Tasks |
|----------|----------|---------------|
| `1c-development` | BSL, 1С, процедура, функция, AST | Анализ BSL кода, API платформы |
| `documentation` | документация, docs, RAG | Поиск в документации |
| `memory` | память, memory, контекст | Сохранение/поиск контекста |
| `code-analysis` | символы, LSP, рефакторинг | Навигация по Python/JS/TS |
| `file-operations` | файл, grep, search | Поиск в файлах |
| `reasoning` | думай, think, step by step | Структурированный анализ |
| `web` | веб, HTTP, браузер | Веб-поиск, HTTP запросы |
| `utils` | zip, конвертация | Архивация, конвертация |

## Categories

| Category | Description | Servers |
|----------|-------------|---------|
| `1c-development` | 1C:Enterprise development | ast-grep-mcp, bsl-platform-context, bsl-semantic-search, bsl-debugger |
| `documentation` | Documentation & RAG | 1c-docs-rag, auto-documenter |
| `memory` | Memory systems | unified-memory, memory-ai, conversation-memory |
| `code-analysis` | LSP & code analysis | serena |
| `file-operations` | File operations | ripgrep, filesystem |
| `reasoning` | Structured thinking | sequential-thinking, code-reasoning |
| `web` | Web search & fetch | brave, fetch, puppeteer (docker-mcp) |
| `utils` | Utilities | zip, markitdown, docling |

## Technical Details

### LRU Pool
- Max 5 active servers at once
- Oldest server evicted when limit reached
- Servers stay active until evicted (fast subsequent calls)

### MCP Protocol
- JSON-RPC 2.0 over stdio
- Initialize → **notifications/initialized** → tools/list → tools/call
- Timeout: 10s per request

**Important**: The MCP protocol requires sending `notifications/initialized` after receiving the `initialize` response. Without this, some servers (like deep-code-reasoning) will not accept `tools/call` requests.

Reference: https://modelcontextprotocol.io/specification/basic/lifecycle

### Server Types
- **Local**: Python, Java, Node executables
- **NPX**: On-demand from npm registry
- **Docker-MCP**: Via docker-mcp gateway (requires Docker)
- **Bridge (HTTP)**: MCP-to-OpenAPI bridges (e.g., MCPO) - executes tools via HTTP instead of subprocess

## Files

```
lazy-mcp/
├── src/
│   ├── __init__.py
│   ├── registry.py      # Category/server configuration
│   ├── loader.py        # Dynamic server management
│   └── server.py        # MCP server entry point
├── config/
│   └── registry.yaml    # Server definitions
├── .venv/               # Python virtual environment
├── requirements.txt
├── start-lazy-mcp.bat
└── README.md
```

## Comparison

| Approach | Tools Visible | Tokens | Latency | Auto Selection |
|----------|---------------|--------|---------|----------------|
| All servers loaded | ~200 tools | ~100k | Instant | ❌ Manual |
| **Lazy-MCP** | 3 tools | ~5k | +1-3s first call | ✅ Automatic |

## Known Limitations

1. **First call latency**: 1-3 seconds to start server
2. **Docker-MCP servers**: Require docker-mcp gateway running
3. **NPX servers**: Require npm/npx installed

## Changelog

### v1.3.0 (2026-01-18)
- **Feature**: Added HTTP Bridge server support for MCPO integration
  - New server type `bridge` routes tool calls via HTTP POST instead of subprocess
  - Enables `Claude Code → Z.AI API → lazy-mcp → MCPO → MCP Servers` chain
  - Configuration in `registry.yaml`:
    ```yaml
    mcpo:
      type: "bridge"
      endpoints:
        base_url: "http://localhost:8765"
        filesystem: "/filesystem"
        ripgrep: "/ripgrep"
    ```
  - Location: `src/loader.py` - `BridgeServer` class, `execute_bridge_tool()`, `_register_bridge_server()`
  - Tested: `list_directory`, `read_text_file`, `search` work correctly through MCPO bridge

### v1.2.0 (2026-01-10)
- **Fix**: Added stderr drain thread to prevent stdout blocking
  - Root cause: MCP servers (especially FastMCP with Redis workers) write lots of debug info to stderr. When stderr buffer fills up (~64KB), the process blocks and cannot send responses to stdout, causing `tools/call` timeout.
  - Solution: Daemon thread continuously reads stderr in background, preventing buffer overflow
  - Location: `src/loader.py` - `drain_stderr()` function and `stderr_thread` field in `ActiveServer`
  - Tested: unified-memory now works correctly through lazy-mcp (save_memory, search_memory, etc.)

### v1.1.0 (2026-01-07)
- **Fix**: Added `notifications/initialized` to MCP protocol sequence
  - Root cause: Some MCP servers (deep-code-reasoning) require this notification before accepting `tools/call`
  - Location: `src/loader.py` lines 586-597
  - Reference: https://modelcontextprotocol.io/specification/basic/lifecycle

### v1.0.0 (2026-01-06)
- Initial release with 3 meta-tools
- Support for 40+ on-demand servers
- Automatic tool recommendation via 1c-docs-rag

## Version

- **Version**: 1.3.0
- **Date**: 2026-01-18
- **Author**: 1C-Enterprise Framework
