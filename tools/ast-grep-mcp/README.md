# ast-grep MCP Server

An experimental [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that provides AI assistants with powerful structural code search capabilities using [ast-grep](https://ast-grep.github.io/).

## Overview

This MCP server enables AI assistants (like Cursor, Claude Desktop, etc.) to search and analyze codebases using Abstract Syntax Tree (AST) pattern matching rather than simple text-based search. By leveraging ast-grep's structural search capabilities, AI can:

- Find code patterns based on syntax structure, not just text matching
- Search for specific programming constructs (functions, classes, imports, etc.)
- Write and test complex search rules using YAML configuration
- Debug and visualize AST structures for better pattern development

## 🆕 BSL/1C:Enterprise Support (v2.0)

This fork adds **native support for BSL (1C:Enterprise language)** with a pure Python parser:

### Key Features for BSL:
- ✅ **No external dependencies** - Pure Python regex-based parsing
- ✅ **No EINVAL errors** - Works with Cyrillic file paths on Windows
- ✅ **Multi-encoding support** - UTF-8, UTF-8-BOM, CP1251, CP866, Latin-1
- ✅ **Result caching** - Up to 100 files cached for performance
- ✅ **Full BSL syntax** - Procedures, functions, variables, exports

### BSL-specific search types:
| Type | Description | Example Pattern |
|------|-------------|-----------------|
| `procedures` | Find all procedures | `Процедура $NAME($$$ARGS)` |
| `functions` | Find all functions | `Функция $NAME($$$ARGS)` |
| `variables` | Find variable declarations | `Перем $NAME` |
| `exports` | Find exported methods only | `Функция $NAME($$$ARGS) Экспорт` |
| `text` | Free-text search in code | Any regex pattern |
| `auto` | Auto-detect from pattern | (default) |

### BSL Usage Example:
```python
# Find all functions in BSL files
mcp__ast-grep-mcp__ast_grep(
    pattern="Функция $NAME($$$ARGS)",
    path="src/CommonModules",
    language="bsl",
    bsl_type="functions"
)

# Find only exported procedures
mcp__ast-grep-mcp__ast_grep(
    pattern="Процедура $NAME($$$ARGS)",
    path="src/",
    language="bsl",
    export_only=True
)
```

## Prerequisites

1. **Install ast-grep**: Follow [ast-grep installation guide](https://ast-grep.github.io/guide/quick-start.html#installation)
   ```bash
   # macOS
   brew install ast-grep
   nix-shell -p ast-grep
   cargo install ast-grep --locked
   ```

2. **Install uv**: Python package manager
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **MCP-compatible client**: Such as Cursor, Claude Desktop, or other MCP clients

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/ast-grep/ast-grep-mcp.git
   cd ast-grep-mcp
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Verify ast-grep installation:
   ```bash
   ast-grep --version
   ```

## Running with `uvx`

You can run the server directly from GitHub using `uvx`:

```bash
uvx --from git+https://github.com/ast-grep/ast-grep-mcp ast-grep-server
```

This is useful for quickly trying out the server without cloning the repository.

## Configuration

### For Cursor

Add to your MCP settings (usually in `.cursor-mcp/settings.json`):

```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ast-grep-mcp", "run", "main.py"],
      "env": {}
    }
  }
}
```

### For Claude Desktop

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ast-grep-mcp", "run", "main.py"],
      "env": {}
    }
  }
}
```

### For Claude Code (Windows with BSL support)

Recommended configuration for Windows with Cyrillic path support:

```json
{
  "mcpServers": {
    "ast-grep-mcp": {
      "command": "D:\\path\\to\\ast-grep-mcp\\.venv\\Scripts\\python.exe",
      "args": ["D:\\path\\to\\ast-grep-mcp\\main.py"],
      "cwd": "D:\\path\\to\\ast-grep-mcp",
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1"
      },
      "timeout": 60000
    }
  }
}
```

**Key points for Windows:**
- Use Python directly from `.venv` (not `uv run`)
- Set `PYTHONIOENCODING=utf-8` for Cyrillic path support
- Set `PYTHONUTF8=1` for consistent UTF-8 handling
- Increase timeout for large codebases (60000ms = 1 minute)

### Custom ast-grep Configuration

The MCP server supports using a custom `sgconfig.yaml` file to configure ast-grep behavior.
See the [ast-grep configuration documentation](https://ast-grep.github.io/guide/project/project-config.html) for details on the config file format.

You can provide the config file in two ways (in order of precedence):

1. **Command-line argument**: `--config /path/to/sgconfig.yaml`
2. **Environment variable**: `AST_GREP_CONFIG=/path/to/sgconfig.yaml`

## Usage

This repository includes comprehensive ast-grep rule documentation in [ast-grep.mdc](https://github.com/ast-grep/ast-grep-mcp/blob/main/ast-grep.mdc). The documentation covers all aspects of writing effective ast-grep rules, from simple patterns to complex multi-condition searches.

You can add it to your cursor rule or Claude.md, and attach it when you need AI agent to create ast-grep rule for you.

The prompt will ask LLM to use MCP to create, verify and improve the rule it creates.

## Features

The server provides five main tools for code analysis:

### 🔍 `dump_syntax_tree`
Visualize the Abstract Syntax Tree structure of code snippets. Essential for understanding how to write effective search patterns.

**Use cases:**
- Debug why a pattern isn't matching
- Understand the AST structure of target code
- Learn ast-grep pattern syntax

### 🧪 `test_match_code_rule`
Test ast-grep YAML rules against code snippets before applying them to larger codebases.

**Use cases:**
- Validate rules work as expected
- Iterate on rule development
- Debug complex matching logic

### 🎯 `find_code`
Search codebases using simple ast-grep patterns for straightforward structural matches.

**Parameters:**
- `max_results`: Limit number of complete matches returned (default: unlimited)
- `output_format`: Choose between `"text"` (default, ~75% fewer tokens) or `"json"` (full metadata)

**Text Output Format:**
```
Found 2 matches:

path/to/file.py:10-15
def example_function():
    # function body
    return result

path/to/file.py:20-22
def another_function():
    pass
```

**Use cases:**
- Find function calls with specific patterns
- Locate variable declarations
- Search for simple code constructs

### 🚀 `find_code_by_rule`
Advanced codebase search using complex YAML rules that can express sophisticated matching criteria.

**Parameters:**
- `max_results`: Limit number of complete matches returned (default: unlimited)
- `output_format`: Choose between `"text"` (default, ~75% fewer tokens) or `"json"` (full metadata)

**Use cases:**
- Find nested code structures
- Search with relational constraints (inside, has, precedes, follows)
- Complex multi-condition searches

### 🆕 `ast_grep`
**Universal search tool** that combines all capabilities with enhanced BSL/1C support.

**Parameters:**
- `pattern`: AST pattern to search for (e.g., `Функция $NAME($$$ARGS)`)
- `path`: File or directory to search in
- `language`: Target language (auto-detected if not specified)
- `mode`: Operation mode (`search`, `replace`, `count`)
- `bsl_type`: BSL-specific search type (`auto`, `procedures`, `functions`, `variables`, `exports`, `text`)
- `export_only`: For BSL - search only exported methods
- `head_limit`: Limit output to first N matches (default: 100)
- `glob`: Filter files by pattern (e.g., `*.bsl`)
- `context`: Lines of context around matches

**Use cases:**
- Search BSL/1C:Enterprise code with native parsing
- Cross-language code search with unified interface
- Batch analysis of large codebases

**Example:**
```python
# Find all BSL functions across a project
ast_grep(
    pattern="Функция $NAME($$$ARGS)",
    path="D:/Projects/MyConfig/src",
    language="bsl",
    bsl_type="functions",
    head_limit=50
)
```


## Usage Examples

### Basic Pattern Search

Use Query:

> Find all console.log statements

AI will generate rules like:

```yaml
id: find-console-logs
language: javascript
rule:
  pattern: console.log($$$)
```

### Complex Rule Example

User Query:
> Find async functions that use await

AI will generate rules like:

```yaml
id: async-with-await
language: javascript
rule:
  all:
    - kind: function_declaration
    - has:
        pattern: async
    - has:
        pattern: await $EXPR
        stopBy: end
```

## Supported Languages

ast-grep supports many programming languages including:
- JavaScript/TypeScript
- Python
- Rust
- Go
- Java
- C/C++
- C#
- **BSL/1C:Enterprise** (native pure-Python parser) 🆕
- And many more...

For a complete list of built-in supported languages, see the [ast-grep language support documentation](https://ast-grep.github.io/reference/languages.html).

You can also add support for custom languages through the `sgconfig.yaml` configuration file. See the [custom language guide](https://ast-grep.github.io/guide/project/project-config.html#languagecustomlanguage) for details.

### BSL/1C Language Notes

BSL files (`.bsl`) are parsed using a built-in pure Python adapter that:
- Does **not** require external ast-grep CLI for BSL
- Handles Windows paths with Cyrillic characters
- Supports multiple encodings (UTF-8, CP1251, etc.)
- Uses regex-based parsing for procedures, functions, variables

This makes BSL analysis work reliably on Windows without EINVAL subprocess errors.

## Troubleshooting

### Common Issues

1. **"Command not found" errors**: Ensure ast-grep is installed and in your PATH
2. **No matches found**: Try adding `stopBy: end` to relational rules
3. **Pattern not matching**: Use `dump_syntax_tree` to understand the AST structure
4. **Permission errors**: Ensure the server has read access to target directories

### BSL-specific Issues

1. **EINVAL errors on Windows**: This is fixed in v2.0 with pure Python BSL parsing
2. **Encoding issues**: The adapter tries UTF-8, UTF-8-BOM, CP1251, CP866, Latin-1 automatically
3. **Long paths on Windows**: Use short paths or enable long path support in Windows
4. **Cyrillic in paths**: Fully supported with PYTHONIOENCODING=utf-8 environment variable

## Contributing

This is an experimental project. Issues and pull requests are welcome!

## Related Projects

- [ast-grep](https://ast-grep.github.io/) - The core structural search tool
- [Model Context Protocol](https://modelcontextprotocol.io/) - The protocol this server implements
- [FastMCP](https://github.com/pydantic/fastmcp) - The Python MCP framework used

[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/ast-grep-ast-grep-mcp-badge.png)](https://mseep.ai/app/ast-grep-ast-grep-mcp)
