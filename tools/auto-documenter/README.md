# Autodocument MCP Server

An MCP (Model Context Protocol) server that automatically generates documentation for code repositories by analyzing directory structures and code files using AI providers.

## 🚀 Quick Links

- **[Documentation](docs/)** - Complete documentation in organized structure
- **[Quick Start Guide](docs/guides/FREE_TIER_SETUP.md)** - Set up with free providers
- **[Troubleshooting](docs/troubleshooting/README-RUN.md)** - Common issues and solutions
- **[Architecture](docs/architecture/)** - System design and internals

## ✨ Features

- **Smart Directory Analysis**: Recursively analyzes directories and files in a code repository
- **Git Integration**: Respects `.gitignore` patterns to skip ignored files
- **AI-Powered Documentation**: Supports multiple AI providers with automatic rotation
- **1C:Enterprise (BSL) Support**: Native support for 1C:Enterprise modules with tree-sitter parsing
  - Accurate procedure/function extraction
  - Export keyword detection
  - Russian language documentation
  - Module type detection (Forms, Objects, Managers)
  - Regions and comments analysis
- **Form.xml Validation**: Advanced validation for 1C:Enterprise forms
  - Cross-validation between Form.xml and Module.bsl
  - Missing/orphaned handler detection (control events + commands)
  - DataPath integrity checking
  - Form hierarchy validation
  - Conditional appearance validation
  - Quality scoring (0-100)
  - Best practice recommendations
  - **Automatic integration** - validation results included in documentation context
  - See [Form.xml Validation Guide](docs/features/FORM_XML_VALIDATION.md)
- **Test Plan Generation**: Automatically creates test plans with suitable test types, edge cases, and mock requirements
- **Code Review**: Performs senior developer-level code reviews focused on security, best practices, and improvements
- **Bottom-Up Approach**: Starts with leaf directories and works upward, creating a coherent documentation hierarchy
- **Provider Rotation**: Automatic failover between AI providers to minimize costs and maximize availability
- **Intelligent File Handling**:
  - Creates `documentation.md`, `testplan.md`, and `review.md` files at each directory level
  - Skips single-file directories but includes their content in parent outputs
  - Supports updating existing files
  - Creates fallback files for directories that exceed limits
- **Progress Reporting**: Provides detailed progress updates to prevent timeouts in long-running operations
- **Highly Configurable**: Customize file extensions, size limits, models, prompts, and more
- **Extensible Architecture**: Modular design makes it easy to add more auto-* tools in the future

## 💰 Cost Overview

| Configuration | Monthly Cost | Daily Capacity |
|---------------|--------------|----------------|
| **Free-only** (Gemini + Groq + Ollama) | **$0** | ~1,533 modules |
| **With Grok** (Gemini + Grok + Ollama) | $5-10 | Unlimited |
| **OpenRouter only** (legacy) | $60-150 | Unlimited |

**Recommendation:** Use the free-only configuration for zero-cost operation. See [Free Tier Setup Guide](docs/guides/FREE_TIER_SETUP.md).

## 🖥️ CLI Usage

Autodocument can be used as a standalone command-line tool without MCP integration.

### Quick Start

```bash
# Install globally
npm install -g autodocument

# Or run directly
npx autodoc generate ./src
```

### Commands

```bash
autodoc generate <path>       # Generate documentation
autodoc review <path>         # Generate code review
autodoc testplan <path>       # Generate test plan
autodoc inline <path>         # Generate inline docs (JSDoc/BSL)
autodoc info                  # Show system info
autodoc benchmark <path>      # Run performance benchmarks
autodoc browse <path>         # Browse documentation
autodoc diff <base> <target>  # Compare documentation versions
```

### Global Options

| Flag | Description |
|------|-------------|
| `-p, --provider <name>` | AI provider (gemini, groq, ollama, grok, openrouter) |
| `-m, --model <model>` | Model to use |
| `-k, --api-key <key>` | API key for provider |
| `-o, --output <path>` | Output directory |
| `-u, --update` | Update existing files |
| `--verbose` | Verbose output |
| `-q, --quiet` | Suppress non-essential output |
| `-r, --recursive` | Process recursively (default: true) |

### Productivity Options (v2.4.0+)

| Flag | Description |
|------|-------------|
| `-w, --watch` | Watch mode: auto-regenerate on file changes |
| `--cache` | Enable AI response caching |
| `--cache-dir <path>` | Cache directory path |
| `-i, --incremental` | Incremental mode: only process changed files |
| `-f, --force` | Force full regeneration |
| `-c, --config <path>` | Path to configuration file |

### Examples

```bash
# Basic documentation generation
autodoc generate ./src -p gemini

# Watch mode - auto-regenerate on changes
autodoc generate ./src --watch

# Incremental mode - only changed files
autodoc generate ./src --incremental

# With caching for faster repeat runs
autodoc generate ./src --cache

# Use configuration file
autodoc generate ./src --config ./autodoc.config.yaml

# Combined productivity features
autodoc generate ./src --incremental --cache --verbose
```

### Configuration File

Create `autodoc.config.yaml` in your project:

```yaml
version: "1.0"
cli:
  provider: gemini
  verbose: true
  updateExisting: true
cache:
  enabled: true
  directory: .autodoc-cache
  ttlSeconds: 86400
watch:
  enabled: false
  debounceMs: 1000
  include:
    - "**/*.ts"
    - "**/*.bsl"
  exclude:
    - "**/node_modules/**"
```

## 📦 Installation

### Prerequisites

- Node.js (v16 or newer)
- **Optional but recommended:** Free API keys (see [guides](docs/guides/))
  - [Google Gemini](https://ai.google.dev/) - Free, 1,500 req/day
  - [Groq](https://console.groq.com/) - Free, 500k tokens/day
  - [Ollama](https://ollama.com/) - Local, unlimited
- **Legacy option:** [OpenRouter API key](https://openrouter.ai/) - Paid

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/PARS-DOE/autodocument.git
cd autodocument

# Install dependencies
npm install

# Build the project
npm run build
```

## 🎯 Supported AI Providers

The system supports multiple AI providers with automatic rotation:

1. **Google Gemini** (Primary, Free) - 1,500 requests/day, fast and capable
2. **Groq** (Free) - 500,000 tokens/day, very fast inference
3. **Ollama** (Local, Free) - Unlimited, runs on your machine
4. **xAI Grok** (Paid) - Advanced reasoning, real-time knowledge
5. **OpenRouter** (Paid, Fallback) - Access to all models, last resort

**Provider Rotation:** The system automatically switches providers on errors or limits, ensuring uninterrupted operation. See [Architecture](docs/architecture/ROTATION_IMPLEMENTATION.md) for details.

## ⚙️ Configuration

Configure autodocument using environment variables in your MCP configuration file.

### Provider Rotation Configuration

**Free Tier (Recommended):**
```json
{
  "mcpServers": {
    "auto-documenter": {
      "command": "node",
      "args": ["D:\\path\\to\\autodocument\\build\\index.js"],
      "env": {
        "ENABLE_ROTATION": "true",
        "PRIMARY_PROVIDER": "gemini",
        "GEMINI_API_KEY": "your-gemini-key",
        "GROQ_API_KEY": "your-groq-key"
      }
    }
  }
}
```

**Legacy OpenRouter:**
```json
{
  "env": {
    "ENABLE_ROTATION": "false",
    "OPENROUTER_API_KEY": "your-openrouter-key"
  }
}
```

### Environment Variables

**Provider Configuration:**
- `ENABLE_ROTATION`: Enable provider rotation (default: false)
- `PRIMARY_PROVIDER`: Main provider (gemini, groq, ollama, grok, openrouter)
- `GEMINI_API_KEY`: Google Gemini API key
- `GROQ_API_KEY`: Groq API key
- `GROK_API_KEY`: xAI Grok API key
- `OPENROUTER_API_KEY`: OpenRouter API key (fallback)
- `OLLAMA_MODEL`: Ollama model name (e.g., qwen2.5-coder:14b)

**Legacy Options:**
- `OPENROUTER_MODEL`: Model to use (default: `anthropic/claude-3-7-sonnet`)

**Processing Limits:**
- `MAX_FILE_SIZE_KB`: Maximum file size in KB (default: 100)
- `MAX_FILES_PER_DIR`: Maximum number of files per directory (default: 20)

**Detailed configuration guide:** See [docs/guides/](docs/guides/) for complete setup instructions.

## 🎯 BSL Quick Start

### Documenting 1C:Enterprise (BSL) Projects

Autodocument has native support for 1C:Enterprise modules written in BSL (Built-in Script Language).

#### Quick Example

**Generate documentation for a 1C configuration:**

```typescript
// In Claude Code or any MCP client
{
  "tool": "generate_documentation",
  "arguments": {
    "path": "D:/1C-Projects/MyConfiguration/src"
  }
}
```

**What gets analyzed:**
- ✅ **Процедуры** (Procedures) - with parameters and export detection
- ✅ **Функции** (Functions) - with return types and parameters
- ✅ **Экспорт** (Export) - automatically detects public API
- ✅ **Области** (#Область/#Region) - code organization blocks
- ✅ **Комментарии** - existing documentation
- ✅ **Типы модулей** - Forms, Objects, Managers, etc.

#### Example BSL Module

**Input file:** `Справочники.Контрагенты/Ext/ManagerModule.bsl`

```bsl
#Область ПрограммныйИнтерфейс

// Создает новый элемент справочника Контрагенты
//
// Параметры:
//   Наименование - Строка - наименование контрагента
//   ИНН - Строка - ИНН контрагента
//
// Возвращаемое значение:
//   СправочникСсылка.Контрагенты - созданный элемент
//
Функция СоздатьКонтрагента(Наименование, ИНН) Экспорт
    НовыйЭлемент = Справочники.Контрагенты.СоздатьЭлемент();
    НовыйЭлемент.Наименование = Наименование;
    НовыйЭлемент.ИНН = ИНН;
    НовыйЭлемент.Записать();
    Возврат НовыйЭлемент.Ссылка;
КонецФункции

#КонецОбласти
```

**Generated documentation.md:**

```markdown
# Справочники.Контрагенты - Модуль менеджера

## Обзор
Модуль менеджера справочника Контрагенты, содержащий программный интерфейс для работы с контрагентами.

## Экспортные функции

### СоздатьКонтрагента(Наименование, ИНН) ➜ СправочникСсылка.Контрагенты
Создает новый элемент справочника Контрагенты с указанными параметрами.

**Параметры:**
- `Наименование` (Строка) - наименование контрагента
- `ИНН` (Строка) - ИНН контрагента

**Возвращает:** Ссылку на созданный элемент справочника

**Пример использования:**
```bsl
Контрагент = Справочники.Контрагенты.СоздатьКонтрагента("ООО Ромашка", "1234567890");
```

## Статистика модуля
- Всего функций: 1
- Экспортных: 1
- Внутренних: 0
- Строк кода: 12
```

#### BSL-Specific Features

**Tree-sitter AST Parsing:**
- 100% accurate procedure/function extraction
- Correct parameter parsing with defaults
- Export keyword detection in any position
- Handles Russian and English keywords

**Russian Language Support:**
- Documentation generated in Russian
- Proper terminology for 1C:Enterprise
- Respects 1C naming conventions

**Module Type Detection:**
- Forms (`Форма`) - UI event handlers
- Objects (`Модуль объекта`) - business logic
- Managers (`Модуль менеджера`) - API and helpers
- Common modules (`Общий модуль`) - shared utilities

**Configuration Options:**

```json
{
  "env": {
    "ENABLE_ROTATION": "true",
    "PRIMARY_PROVIDER": "gemini",
    "GEMINI_API_KEY": "your-key",
    "MAX_FILE_SIZE_KB": "200",  // BSL files can be larger
    "MAX_FILES_PER_DIR": "30"    // 1C modules often have many files
  }
}
```

#### Common Use Cases

**1. Document entire 1C configuration:**
```bash
generate_documentation({
  "path": "D:/1C-Config/src/Configuration",
  "updateExisting": false
})
```

**2. Generate test plans for BSL modules:**
```bash
autotestplan({
  "path": "D:/1C-Config/src/DataProcessors/МояОбработка"
})
```

**3. Review BSL code quality:**
```bash
autoreview({
  "path": "D:/1C-Config/src/CommonModules"
})
```

#### Tips for BSL Documentation

1. **Use Russian comments** - autodocument preserves and enhances them
2. **Mark exports** - use `Экспорт` keyword for public API
3. **Organize with regions** - `#Область` helps structure documentation
4. **Include examples** - add usage examples in comments
5. **Document parameters** - specify types and constraints

### 🆕 Advanced 1C Features (v2.5.0)

#### Auto Output Directory for 1C Configurations

For 1C configurations, documentation is automatically saved to `/docs` instead of alongside source files:

```
# Input:
path: .../251118_GKSTCPLK-1872/src/

# Output (automatic):
docs: .../251118_GKSTCPLK-1872/docs/
      ├── CommonModules/
      │   └── documentation.md
      ├── Catalogs/
      │   └── documentation.md
      └── documentation.md
```

**How it works:**
- Automatically detects 1C configurations by path patterns and file structure
- Creates `/docs` at the same level as `/src`
- Preserves directory structure from source

#### Call Graph Analysis

BSL modules are analyzed for call chains and dependencies:

```markdown
### Цепочки вызовов
```
ГлавнаяПроцедура()
├── ПодготовитьДанные()
│   └── ПроверитьПараметры()
├── ВыполнитьОбработку()
│   ├── ОбщийМодуль.Функция()
│   └── ЗаписатьРезультат()
└── ОповеститьПользователя()
```
```

**Features:**
- Entry points detection (exported procedures/functions)
- Internal and external call classification
- Common module dependency tracking
- Configuration object relationships (Catalogs, Documents, Registers)

#### Inline Documentation (BSL Comments)

Generate inline comments directly in BSL code following 1C standards:

```bash
autodoc inline ./src/CommonModules
```

**Result:**
```bsl
// Получает основные данные контрагента для заполнения документов
//
// Параметры:
//   Контрагент - СправочникСсылка.Контрагенты - Ссылка на контрагента
//   ДатаПолучения - Дата - Дата актуальности данных
//
// Возвращаемое значение:
//   Структура - Ключи: ИНН, КПП, НаименованиеПолное
//
Функция ПолучитьДанныеКонтрагента(Контрагент, ДатаПолучения = Неопределено) Экспорт
```

See [CHANGELOG-1C-FEATURES.md](docs/CHANGELOG-1C-FEATURES.md) for complete documentation.

## Using with Roo or Cline

Roo Code and Cline are AI assistants that support the Model Context Protocol (MCP), which allows them to use external tools like autodocument.

### Setup for Roo/Cline

1. **Clone and build the repository** (follow the Installation Steps above)

2. **Configure the MCP server**:

   #### For Roo:

   In the MCP Servers menu, Edit the MCP Settings and add the autodocument configuration using the full path to where you cloned the repository:

   Add the autodocument configuration using the full path to where you cloned the repository:
   ```json
   {
     "mcpServers": {
       "autodocument": {
         "command": "node",
         "args": ["/path/to/autodocument/build/index.js"],
         "env": {
           "OPENROUTER_API_KEY": "your-api-key-here"
         },
         "disabled": false,
         "alwaysAllow": []
       }
     }
   }
   ```

   #### For Claude Desktop App:
   Edit the Claude desktop app configuration file at:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

   Add the autodocument configuration using the full path to where you cloned the repository:
   ```json
   {
     "mcpServers": {
       "autodocument": {
         "command": "node",
         "args": ["/path/to/autodocument/build/index.js"],
         "env": {
           "OPENROUTER_API_KEY": "your-api-key-here"
         },
         "disabled": false,
         "alwaysAllow": []
       }
     }
   }
   ```

3. **Important:** Make sure to use absolute paths to the build/index.js file in your cloned repository

4. **Restart Roo/Cline or the Claude desktop app**

4. **Use the tool**:
   In a conversation with Roo or Claude, you can now ask it to generate documentation or test plans for your code repository:
   ```
   Please generate documentation for my project at /path/to/my/project
   ```
   
   Or for test plans:
   ```
   Please create a test plan for my project at /path/to/my/project
   ```
   
   Or for code reviews:
   ```
   Please review the code in my project at /path/to/my/project
   ```

## How It Works

The autodocument server works using a bottom-up approach:

1. **Discovery**: Scans the target directory recursively, respecting `.gitignore` rules
2. **Smart Directory Processing**: 
   - Identifies directories with multiple code files or subdirectories
   - Skips single-file directories but includes their content in parent documentation
3. **File Analysis**: Analyzes code files, filtering by extension and size
4. **Documentation Generation**: For each qualifying directory:
   - Reads code files
   - Sends code to OpenRouter API with optimized prompts
   - Creates a `documentation.md` file (or updates existing one)
5. **Aggregation**: As it moves up the directory tree:
   - Processes each parent directory
   - Includes documentation from child directories
   - Creates a comprehensive overview at each level

## 🏗️ Architecture

The project follows a modular architecture with provider rotation:

```
MCP Server (stdio)
    ↓
Provider Rotation Manager
    ↓
├─→ Gemini (free, 1500/day)
├─→ Groq (free, 500k tokens/day)
├─→ Ollama (local, unlimited)
├─→ Grok (paid, advanced reasoning)
└─→ OpenRouter (paid, fallback)
    ↓
Documentation Tools
├─→ generate_documentation
├─→ autotestplan
└─→ autoreview
```

**Key Components:**
- **Core**: Configuration management and MCP server implementation
- **Crawler**: Directory traversal and file discovery with gitignore support
- **Analyzer**: Code file analysis and filtering
- **Provider System**: Multi-provider AI integration with automatic rotation
- **Documentation**: Orchestration of the documentation generation process
- **Tools**: Extensible system for auto-* operations (documentation, test plans, reviews)
- **Prompts**: Centralized prompt management for easy customization

**See also:** [Architecture Documentation](docs/architecture/) for detailed technical information.

## Example Usage

### Command Line

```bash
# Navigate to your cloned repository
cd path/to/cloned/autodocument

# Set your API key (or configure in environment variables)
export OPENROUTER_API_KEY=your-api-key-here

# Run documentation generation on a project
node build/index.js /path/to/your/project
```

### Programmatic Usage

```javascript
const { spawn } = require('child_process');
const path = require('path');

// Path to your project
const projectPath = '/path/to/your/project';

// Your OpenRouter API key
const apiKey = 'your-api-key-here';

// Create a JSON command to simulate an MCP tool call
const toolCallCommand = JSON.stringify({
  jsonrpc: '2.0',
  method: 'call_tool',
  params: {
    name: 'generate_documentation',
    arguments: {
      path: projectPath,
      openRouterApiKey: apiKey
    }
  },
  id: 1
});

// Start the server process - use the full path to your cloned repository
const serverProcess = spawn('node', ['/path/to/autodocument/build/index.js'], {
  env: {
    ...process.env,
    OPENROUTER_API_KEY: apiKey
  }
});

// Send the tool command
serverProcess.stdin.write(toolCallCommand + '\n');

// Handle server output and errors
// ...
```

## Customizing Prompts

You can easily customize the prompts used by the tools by editing the `src/prompt-config.ts` file. This allows you to:

- Adjust the tone and style of generated content
- Add specific instructions for your project's needs
- Modify how existing content is updated

The prompt configuration is separated from the tool implementation, making it easy to experiment with different prompts without changing the code.

## Available Tools

### generate_documentation

Generates comprehensive documentation for a code repository:
```
{
  "path": "/path/to/your/project",
  "openRouterApiKey": "your-api-key-here", // Optional
  "model": "anthropic/claude-3-7-sonnet", // Optional
  "updateExisting": true // Optional, defaults to true
}
```

### autotestplan

Generates test plans for functions and components in a code repository:
```
{
  "path": "/path/to/your/project",
  "openRouterApiKey": "your-api-key-here", // Optional
  "model": "anthropic/claude-3-7-sonnet", // Optional
  "updateExisting": true // Optional, defaults to true
}
```

### autoreview

Generates a senior developer-level code review for a repository:
```
{
  "path": "/path/to/your/project",
  "openRouterApiKey": "your-api-key-here", // Optional
  "model": "anthropic/claude-3-7-sonnet", // Optional
  "updateExisting": true // Optional, defaults to true
}
```

## Output Files

The server creates several types of output files:

### documentation.md

Contains comprehensive documentation of the code in a directory, including:
- Purpose of the code
- Key functions and classes
- Relationships between files
- Integration with child components

### testplan.md

Contains detailed test plans for code in a directory, including:
- Appropriate test types (unit, integration, e2e) for each function
- Common edge cases to test
- Dependency mocking requirements
- Integration testing strategies

### review.md

Contains senior developer-level code review feedback, including:
- Security issues and vulnerabilities
- Best practice violations
- Potential bugs or architectural concerns
- Opportunities for refactoring
- Practical, constructive feedback (not nitpicking style issues)

### Fallback Files

Created when a directory exceeds size or file count limits:
- `undocumented.md` - For documentation generation
- `untested.md` - For test plan generation
- `review-skipped.md` - For code review generation

These files contain:
- Reason for skipping processing
- List of files that were analyzed and excluded
- Instructions on how to fix (increase limits or manually create content)

## 🔧 Troubleshooting

For detailed troubleshooting, see [Troubleshooting Guide](docs/troubleshooting/README-RUN.md).

### Common Issues

**"OpenRouter API key is required"**
- Set `ENABLE_ROTATION=true` to use free providers
- Or get a free Gemini API key: https://ai.google.dev/

**Provider errors or limits exceeded**
- System automatically switches to next provider
- Check logs for current provider being used
- Verify API keys are valid

**Server won't start**
- Ensure Node.js is installed: `node --version`
- Rebuild if needed: `npm run build`
- Check MCP server status in Claude Code

**TypeScript compilation errors**
- Known issue with gitignore.ts
- Workaround: `npx tsc --skipLibCheck`

For complete troubleshooting guide with all issues and solutions, see [docs/troubleshooting/](docs/troubleshooting/).

## License

CC0-1.0 License - This work is dedicated to the public domain under CC0 by the United States Department of Energy

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development

See [Development Documentation](docs/development/) for:
- Code quality guidelines
- Known issues and technical debt
- Improvement roadmap
- Architecture details

### Adding New Tools

The architecture is designed to make it easy to add new auto-* tools:

1. Create a new class that extends `BaseTool` in the `src/tools` directory
2. Define the prompts in `src/prompt-config.ts`
3. Register the tool in the `ToolRegistry`

See the existing tools for examples of how to implement new functionality.

## 📚 Documentation

Complete documentation is available in the [docs/](docs/) directory:

- **[Architecture](docs/architecture/)** - System design and provider rotation
- **[Guides](docs/guides/)** - Setup and usage instructions
- **[Reference](docs/reference/)** - API reference (planned)
- **[Troubleshooting](docs/troubleshooting/)** - Common issues and solutions
- **[Development](docs/development/)** - Technical documentation for contributors

## 🔗 Related Projects

- [Model Context Protocol](https://code.claude.com/docs/en/mcp) - MCP specification
- [Claude Code](https://claude.com/code) - AI-powered IDE
- [OpenRouter](https://openrouter.ai/) - Unified AI API
- [Google Gemini](https://ai.google.dev/) - Free AI API
- [Groq](https://console.groq.com/) - Fast inference
- [Ollama](https://ollama.com/) - Local LLMs