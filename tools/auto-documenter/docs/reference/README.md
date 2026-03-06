# API Reference

Complete API reference documentation for Auto-Documenter.

## Quick Links

- **[Full API Reference](./API.md)** - Complete API documentation
- **[Providers Reference](./PROVIDERS.md)** - Provider configuration details
- **[Types Reference](./TYPES.md)** - TypeScript type definitions

## Overview

### MCP Tools

| Tool | Description | Alias |
|------|-------------|-------|
| `generate_documentation` | Generate project documentation | - |
| `autotestplan` | Generate test plans | - |
| `autoreview` | Generate code reviews | - |
| `generate_inline_docs` | Generate JSDoc/TSDoc/BSL comments | - |

### CLI Commands

| Command | Description | Aliases |
|---------|-------------|---------|
| `generate` | Generate documentation | `doc`, `g` |
| `review` | Generate code review | - |
| `testplan` | Generate test plan | - |
| `inline` | Generate inline docs | - |
| `info` | Show tool information | - |
| `benchmark` | Run benchmarks | - |
| `browse` | Browse generated docs | - |

### Analyzers

| Analyzer | Language | Technology |
|----------|----------|------------|
| `TSCompilerAnalyzer` | TypeScript/JavaScript | TypeScript Compiler API |
| `BSLTreesitterAnalyzer` | BSL (1C:Enterprise) | tree-sitter-bsl |
| `Structure1CAnalyzer` | 1C Configuration | Path analysis |
| `FileAnalyzer` | Multi-language | Combined |

### Providers

| Provider | API Key Variable | Free Tier |
|----------|------------------|-----------|
| Gemini | `GEMINI_API_KEY` | 1,500 req/day |
| Groq | `GROQ_API_KEY` | 500k tokens/day |
| Ollama | - (local) | Unlimited |
| Grok | `XAI_API_KEY` | No |
| OpenRouter | `OPENROUTER_API_KEY` | No |

## Getting Started

### Basic Usage (MCP)

```typescript
// Generate documentation
const result = await mcp.call('generate_documentation', {
  path: '/path/to/project'
});
```

### Basic Usage (CLI)

```bash
# Generate documentation
autodoc generate ./src --provider gemini

# Generate with all features
autodoc generate ./src -p groq -u -r -v
```

### Programmatic Usage

```typescript
import { FileAnalyzer, TSCompilerAnalyzer } from 'autodocument';

// Analyze files
const analyzer = new FileAnalyzer();
const result = await analyzer.analyzeDirectory('./src');

// Analyze TypeScript
const tsAnalyzer = new TSCompilerAnalyzer();
const symbols = tsAnalyzer.getExportedSymbols(code, 'file.ts');
```

## Related Documentation

- **[CLI Usage Guide](../CLI-USAGE-GUIDE.md)** - Detailed CLI instructions
- **[Architecture](../architecture/README.md)** - System design
- **[Features](../features/README.md)** - Feature documentation
- **[Guides](../guides/README.md)** - How-to guides

---

*Version: 2.2.0 | Updated: 2025-11-26*
