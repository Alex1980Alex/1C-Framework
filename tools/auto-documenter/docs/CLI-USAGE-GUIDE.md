# CLI Usage Guide - Auto-Documenter

> **Version:** 2.3.0
> **Date:** 2025-11-26

## Quick Start

```bash
# Install globally
npm install -g autodocument

# Or run from local build
node build/cli/index.js <command> [options]

# Shortcut alias
autodoc <command> [options]
```

## Commands

### generate - Generate Documentation

Generate `documentation.md` files for your codebase.

```bash
autodoc generate <path> [options]

# Aliases: doc, g

# Examples:
autodoc generate ./src
autodoc g ./src -p gemini
autodoc doc ./src --provider groq --model llama-3.3-70b-versatile
```

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--provider` | `-p` | AI provider (gemini, groq, ollama, grok, openrouter) | gemini |
| `--model` | `-m` | Model to use | Provider default |
| `--api-key` | `-k` | API key | From environment |
| `--update` | `-u` | Update existing files | false |
| `--verbose` | | Show detailed output | false |
| `--quiet` | `-q` | Suppress output | false |

### review - Code Review

Generate `review.md` files with code quality analysis.

```bash
autodoc review <path> [options]

# Alias: r

# Examples:
autodoc review ./src
autodoc r ./src -p groq
autodoc review ./src/components --update
```

### testplan - Test Plan Generation

Generate `testplan.md` files with test scenarios.

```bash
autodoc testplan <path> [options]

# Aliases: test, t

# Examples:
autodoc testplan ./src
autodoc test ./src -p ollama
autodoc t ./src/services --verbose
```

### inline - Inline Documentation

Generate inline documentation comments (JSDoc/TSDoc/BSL).

```bash
autodoc inline <path> [options]

# Alias: i

# Examples:
autodoc inline ./src
autodoc i ./src/utils
autodoc inline ./src --provider gemini --update
```

### info - System Information

Display system configuration and provider status.

```bash
autodoc info

# Shows:
# - Version
# - Available providers
# - Environment variables
# - Configuration status
```

### benchmark - Performance Benchmarks

Run performance benchmarks for analysis and providers.

```bash
autodoc benchmark <path> [options]

# Examples:
autodoc benchmark ./src                    # Analysis benchmark
autodoc benchmark ./src -t scalability     # Scalability test
autodoc benchmark -t provider -i 3         # Provider comparison
autodoc benchmark ./src -f markdown -o report.md
```

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--type` | `-t` | Benchmark type (analysis, scalability, provider, all) | analysis |
| `--iterations` | `-i` | Number of iterations | 3 |
| `--format` | `-f` | Output format (console, markdown, json) | console |
| `--output` | `-o` | Output file path | - |

### browse - Interactive Browser

Start interactive documentation browser.

```bash
autodoc browse <path> [options]

# Examples:
autodoc browse ./src
autodoc browse ./docs --port 3000
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--port` | Server port | 8080 |

### diff - Documentation Diff

Compare two versions of documentation and detect changes. Useful for CI/CD pipelines.

```bash
autodoc diff <base> <target> [options]

# Aliases: d, compare

# Examples:
autodoc diff ./docs-v1 ./docs-v2                    # Compare directories
autodoc diff old.md new.md                          # Compare files
autodoc diff ./before ./after -f markdown -o report.md
autodoc diff ./base ./current -f github             # GitHub Actions format
```

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--format` | `-f` | Output format (console, markdown, json, github) | console |
| `--output` | `-o` | Save output to file | - |
| `--ignore-whitespace` | `-w` | Ignore whitespace changes | false |
| `--include-unchanged` | | Include unchanged files in report | false |
| `--detect-breaking` | `-b` | Detect breaking changes | true |
| `--include` | `-i` | File patterns to include | `**/*.md` |
| `--exclude` | `-e` | File patterns to exclude | `node_modules` |

**Output Formats:**
| Format | Description | Use Case |
|--------|-------------|----------|
| `console` | Colored terminal output | Local development |
| `markdown` | Structured markdown report | Documentation |
| `json` | Machine-readable JSON | Programmatic processing |
| `github` | GitHub Actions annotations | CI/CD pipelines |

**Breaking Changes Detection:**
The tool automatically detects potentially breaking changes:
- Removed API documentation sections
- Removed export statements
- Changes to parameter/return documentation
- Removed public function documentation

## AI Providers

### Gemini (Default)

Free tier: 1,500 requests/day

```bash
# Set API key
export GEMINI_API_KEY=your-key

# Usage
autodoc generate ./src -p gemini
autodoc generate ./src -p gemini -m gemini-2.5-pro-latest
```

### Groq

Free tier: 500,000 tokens/day

```bash
# Set API key
export GROQ_API_KEY=your-key

# Usage
autodoc generate ./src -p groq
autodoc generate ./src -p groq -m mixtral-8x7b-32768
```

### Ollama (Local)

Unlimited, no API key required.

```bash
# Ensure Ollama is running
ollama serve

# Usage
autodoc generate ./src -p ollama
autodoc generate ./src -p ollama -m deepseek-r1:14b
```

### Grok (xAI)

Paid tier.

```bash
# Set API key
export XAI_API_KEY=your-key

# Usage
autodoc generate ./src -p grok
```

### OpenRouter

Paid tier, multiple model access.

```bash
# Set API key
export OPENROUTER_API_KEY=your-key

# Usage
autodoc generate ./src -p openrouter
autodoc generate ./src -p openrouter -m anthropic/claude-3.5-sonnet
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | For Gemini |
| `GROQ_API_KEY` | Groq API key | For Groq |
| `XAI_API_KEY` | xAI/Grok API key | For Grok |
| `OPENROUTER_API_KEY` | OpenRouter API key | For OpenRouter |
| `ENABLE_ROTATION` | Enable provider rotation | Optional |
| `PRIMARY_PROVIDER` | Default provider | Optional |

## Provider Rotation

Enable automatic failover between providers:

```bash
export ENABLE_ROTATION=true
export PRIMARY_PROVIDER=gemini
export GEMINI_API_KEY=your-key
export GROQ_API_KEY=your-key

# Will try gemini first, fall back to groq on failure
autodoc generate ./src
```

## Examples

### Document TypeScript Project

```bash
# Generate documentation for entire project
autodoc generate ./src

# Update existing documentation
autodoc generate ./src --update

# Use specific provider
autodoc generate ./src -p groq -m llama-3.3-70b-versatile
```

### Document 1C:Enterprise (BSL) Project

```bash
# Document configuration
autodoc generate ./src/Configuration -p gemini

# Generate test plan
autodoc testplan ./src/CommonModules

# Code review
autodoc review ./src/DataProcessors
```

### Generate All Documentation

```bash
# Full documentation generation
autodoc generate ./src
autodoc testplan ./src
autodoc review ./src
```

### Performance Testing

```bash
# Run analysis benchmark
autodoc benchmark ./src

# Compare providers
autodoc benchmark -t provider -i 5

# Generate markdown report
autodoc benchmark ./src -f markdown -o benchmark-report.md
```

## Output Files

| Command | Output File |
|---------|-------------|
| generate | `documentation.md` |
| review | `review.md` |
| testplan | `testplan.md` |
| inline | Modifies source files |
| benchmark | Console or specified file |
| diff | Console or specified file |

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/docs-check.yml
name: Documentation Check

on:
  pull_request:
    paths:
      - 'docs/**'
      - 'src/**'

jobs:
  check-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install autodocument
        run: npm install -g autodocument

      - name: Generate documentation
        run: autodoc generate ./src -p gemini
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}

      - name: Compare with baseline
        run: |
          autodoc diff ./docs-baseline ./docs -f github
        continue-on-error: true

      - name: Save diff report
        run: autodoc diff ./docs-baseline ./docs -f markdown -o diff-report.md

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: documentation-diff
          path: diff-report.md
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for breaking documentation changes
autodoc diff docs-baseline docs -f json | jq '.summary.breakingChanges'
BREAKING=$(autodoc diff docs-baseline docs -f json | jq '.summary.breakingChanges')

if [ "$BREAKING" -gt 0 ]; then
  echo "⚠️ Warning: $BREAKING breaking documentation changes detected"
  autodoc diff docs-baseline docs -f console
  read -p "Continue with commit? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi
```

## Troubleshooting

### API Key Issues

```bash
# Verify API key is set
echo $GEMINI_API_KEY

# Use explicit key
autodoc generate ./src -k your-api-key
```

### Provider Unavailable

```bash
# Try different provider
autodoc generate ./src -p groq

# Or use local Ollama
ollama serve
autodoc generate ./src -p ollama
```

### Large Codebase

```bash
# Process specific directory
autodoc generate ./src/components

# Use faster model
autodoc generate ./src -p groq -m llama-3.1-8b-instant
```

## Support

- **Issues:** https://github.com/PARS-DOE/autodocument/issues
- **Documentation:** See `docs/` directory
