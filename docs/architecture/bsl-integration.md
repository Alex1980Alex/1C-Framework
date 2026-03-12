# BSL Integration Architecture

**Date:** 2026-03-08 | **Migration:** Phases 44-55 | **Source:** D:\1C-Enterprise_Framework

## Overview

BSL (Built-in Scripting Language) integration adds 1C:Enterprise development capabilities to the PDF Vector & Graph Framework. Migrated from standalone 1C-Enterprise_Framework project.

## Components

```
src/
  bsl/
    semantic_search/    # BSL code search (Qdrant, nomic embeddings)
    mcp_server/         # MCP server for BSL tools
    mcp_integration/    # 1C platform integration (.cfe extensions)
    sonar/              # SonarQube BSL analysis
    finetuning/         # Qwen2.5-Coder fine-tuning for BSL
  memory/
    ai_memory/          # Important messages with priorities
    vector_memory/      # Learned patterns (Qdrant + ONNX)
    skill_learning/     # Capture from tool use
    orchestrator/       # Unified memory API
  shared/
    llm_rotation/       # Multi-provider LLM with fallback

tools/
    auto-documenter/    # Node.js, 5 MCP tools, tree-sitter-bsl
    bsl-debugger/       # Node.js, 10 debug tools
    ast-grep-mcp/       # AST analysis for BSL
    bsl-semantic-diff/  # Semantic diff for BSL code
    mcp-jars/           # Java MCP servers (bsl-platform-context)
    serena/             # LSP for Python/JS/TS (30+ languages)

infra/
    lazy-mcp/           # On-demand MCP proxy (11 categories, 27 servers)
    docker-mcp/         # Docker MCP orchestration (POC)
```

## Qdrant Collections

| Collection | Dimensions | Model | Content |
|-----------|-----------|-------|---------|
| pdf_documents | 1024 | intfloat/multilingual-e5-large | PDF chunks |
| graph_embeddings | 1024 | intfloat/multilingual-e5-large | Entity/relation embeddings |
| bsl_code_v2 | 768 | nomic-embed-text | 3,908 BSL modules |
| ai_memory | 768 | nomic-embed-text | Important messages |
| learned_patterns | 768 | nomic-embed-text | Learned patterns |

## MCP Servers

| Server | Runtime | Tools | Profile |
|--------|---------|-------|---------|
| pdf-vector-graph | Python | 12 | .mcp/pdf.json |
| bsl-semantic-search | Python | 4 | .mcp/bsl.json |
| bsl-platform-context | Java | 5 | .mcp/bsl.json |
| auto-documenter | Node.js | 5 | .mcp/bsl.json |
| bsl-debugger | Node.js | 10 | .mcp/bsl.json |
| ast-grep-mcp | Python | 1 | .mcp/bsl.json |
| memory-ai | Python | 5 | .mcp/full.json |
| vector-memory | Python | 5 | .mcp/full.json |
| llm-rotation | Python | 5 | .mcp/full.json |
| lazy-mcp | Python | 3 | .mcp/lazy-mcp.json |
| serena | Python | 15+ | .mcp/full.json |
| edt-mcp | HTTP | 13+ | .mcp.json |

### bsl-debugger Configuration

**Требование:** OneScript 2.0+ в PATH или явный путь в конфигурации.

```json
{
  "bsl-debugger": {
    "command": "node",
    "args": ["D:\\1С-Framework\\tools\\bsl-debugger\\dist\\index.js"],
    "cwd": "D:\\1С-Framework\\tools\\bsl-debugger",
    "env": {
      "NODE_ENV": "production",
      "PATH": "C:\\Tools\\OneScript\\bin;${PATH}"
    },
    "timeout": 120000
  }
}
```

**Инструменты (10):**
- `bsl_analyze` — статический анализ (процедуры, функции, переменные)
- `bsl_debug_start` — создать сессию отладки
- `bsl_debug_stop` — завершить сессию
- `bsl_debug_breakpoints` — установить breakpoints (условные, hit count)
- `bsl_debug_step` — continue/stepOver/stepIn/stepOut/pause
- `bsl_debug_stack` — стек вызовов
- `bsl_debug_variables` — переменные (local/module/global)
- `bsl_debug_evaluate` — вычислить выражение
- `bsl_debug_sessions` — список активных сессий
- `bsl_execute` — быстрое выполнение без отладки

### edt-mcp Configuration

**Требование:** 1C:EDT с плагином EDT-MCP (port 8765).

```json
{
  "edt-mcp": {
    "command": "npx",
    "args": ["-y", "mcp-remote", "http://localhost:8765/mcp"],
    "timeout": 60000
  }
}
```

**Инструменты (13+):** list_projects, list_modules, get_module_structure, read_module_source, write_module_source, get_symbol_info, get_content_assist, go_to_definition, validate_query, search_in_code, get_project_errors, get_metadata_objects, find_references, rename_metadata_object, delete_metadata_object, get_form_screenshot, update_database, debug_launch.

## MCP Profiles

| Profile | Servers | Use Case |
|---------|---------|----------|
| pdf.json | pdf-vector-graph | PDF-only workflow |
| bsl.json | bsl-semantic-search, bsl-platform-context, serena | BSL development |
| full.json | All native servers | Full capabilities |
| lazy-mcp.json | lazy-mcp proxy | On-demand (saves ~95% tokens) |

## Lazy MCP Proxy

3 meta-tools expose 27 servers across 11 categories:

- **recommend_tools**(task) - category + server recommendation
- **get_tools_in_category**(path) - navigate hierarchy
- **execute_tool**(path, args) - load server on-demand + execute

Categories: 1c-development, documentation, memory, learning, file-operations, reasoning, web, utils, routing, browser, bridges.

## Routing

| Hook | Event | Purpose |
|------|-------|---------|
| bsl-tool-router.py | UserPromptSubmit | Routes BSL/1C queries to bsl-development |

| Name | Domain | Triggers |
|------|--------|----------|
| bsl-development | 1c | BSL, 1C code, module, procedure |
| 1c-doc-research | 1c | 1C documentation, platform API |
| memory-unified | memory | Memory search, context, recall |

## Data Flow

```
User Query (BSL)
  |
  v
bsl-tool-router.py (hook) -> activates bsl-development
  |
  v
MCP Server Selection:
  |- bsl-semantic-search -> Qdrant bsl_code_v2
  |- bsl-platform-context -> 1C Platform API
  |- ast-grep-mcp -> AST analysis
  |- auto-documenter -> Doc generation
  |- bsl-debugger -> Debug tools
  |
  v
Results -> Claude -> User
```
