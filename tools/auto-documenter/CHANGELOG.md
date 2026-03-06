# Changelog

All notable changes to the autodocument project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0] - 2025-11-26

### Added - Productivity Features 🎉

**Phase 2: New Productivity Features** - значительные улучшения для больших проектов:

#### Watch Mode (`--watch`, `-w`)
```bash
autodoc generate ./src --watch
```
- **Автоматическая регенерация** при изменении файлов
- Debouncing (1 секунда по умолчанию)
- Поддержка glob-паттернов для фильтрации
- Рекурсивное отслеживание поддиректорий
- `FileWatcher` класс с EventEmitter API
- `WatchModeRunner` для интеграции с CLI

#### AI Response Caching (`--cache`)
```bash
autodoc generate ./src --cache
autodoc generate ./src --cache --cache-dir ./my-cache
```
- **Кэширование AI-ответов** по content hash
- TTL (24 часа по умолчанию)
- Статистика: hits, misses, hit ratio
- Автоочистка просроченных записей
- `ResponseCache` класс с полным API
- `withCache` HOF для оборачивания функций

#### Incremental Documentation (`--incremental`, `-i`)
```bash
autodoc generate ./src --incremental
autodoc generate ./src --incremental --force  # принудительная полная регенерация
```
- **Только изменённые файлы** обрабатываются
- Git-aware: отслеживание через git diff
- Hash-based: MD5 хеши для детекции изменений
- Файл состояния `.autodoc-state.json`
- `ChangeTracker` класс
- `runIncremental` функция для интеграции

#### Configuration Files (`--config`, `-c`)
```bash
autodoc generate ./src --config ./autodoc.config.yaml
```
- **YAML/JSON конфигурации**: `autodoc.config.yaml`, `autodoc.config.json`
- Наследование конфигураций (`extends`)
- Валидация схемы
- Автопоиск конфиг-файла в проекте
- Приоритет: CLI флаги > конфиг файл > defaults

**Пример конфигурации:**
```yaml
# autodoc.config.yaml
version: "1.0"
cli:
  provider: gemini
  verbose: true
cache:
  enabled: true
  directory: .autodoc-cache
  ttlSeconds: 86400
watch:
  enabled: false
  debounceMs: 1000
```

### Added - Error Handling Enhancement

**Система обработки ошибок:**

- **Иерархия ошибок** (`src/errors/index.ts`):
  - `AutodocError` - базовый класс
  - `ConfigurationError` - ошибки конфигурации
  - `FileSystemError` - файловые операции
  - `ProviderError` - AI провайдеры (с retryable флагом)
  - `ParserError` - парсинг кода
  - `ValidationError` - валидация данных
  - `TimeoutError` - таймауты

- **Retry Utilities** (`src/utils/retry.ts`):
  - `withRetry` - exponential backoff с jitter
  - `createProviderRetry` - специализированный retry для AI провайдеров
  - `RateLimiter` - token bucket алгоритм

### Added - E2E CLI Tests

**Полное покрытие CLI команд:**
- `tests/cli/review.test.ts`
- `tests/cli/testplan.test.ts`
- `tests/cli/inline.test.ts`
- `tests/cli/diff.test.ts`
- `tests/cli/browse.test.ts`
- `tests/cli/benchmark.test.ts`

### New CLI Options

| Флаг | Описание |
|------|----------|
| `-w, --watch` | Watch mode: регенерация при изменениях |
| `--cache` | Включить кэширование AI-ответов |
| `--cache-dir <path>` | Путь к директории кэша |
| `-i, --incremental` | Инкрементальный режим |
| `-f, --force` | Принудительная полная регенерация |
| `-c, --config <path>` | Путь к конфиг-файлу |

### Test Coverage

- **Total tests:** 1131 passing
- **New modules:** 6 (errors, retry, config-loader, file-watcher, response-cache, change-tracker)
- **New test files:** 12

### Dependencies

**Added:**
- `js-yaml@^4.1.1` - YAML парсинг
- `minimatch@^10.1.1` - Glob matching
- `@types/js-yaml@^4.0.9` (dev)
- `@types/minimatch@^5.1.2` (dev)

---

## [2.2.0] - 2025-11-25

### Added - CLI Interface

**Standalone command-line tool** - use autodocument without Claude Code:

```bash
autodoc generate ./src        # Generate documentation
autodoc review ./src -p groq  # Code review
autodoc testplan ./src        # Test plan
autodoc inline ./src          # Inline docs
autodoc info                  # System info
```

#### CLI Features
- **5 commands**: generate, review, testplan, inline, info
- **Command aliases**: doc/g, r, test/t, i
- **5 AI providers**: Gemini, Groq, Ollama, Grok, OpenRouter
- **Global options**: -p/--provider, -m/--model, -k/--api-key, -u/--update, --verbose, -q/--quiet
- **Environment variable support**: GEMINI_API_KEY, GROQ_API_KEY, XAI_API_KEY, OPENROUTER_API_KEY
- **Provider rotation**: Automatic failover between providers
- **Colored output**: Progress indicators, success/error highlighting
- **Recursive processing**: Process entire directory trees (default: on)

#### CLI Structure
- src/cli/index.ts - Main entry point
- src/cli/commands/ - Command implementations (generate, review, testplan, inline, info)
- src/cli/utils/ - Options, output formatting, version

**Test Coverage:** 24 unit tests for CLI functionality

**Total tests:** 508 (was 486 in CLI release)

### Added - Performance Benchmarks

**Measure and compare documentation performance:**

```bash
autodoc benchmark ./src                    # Analysis benchmark
autodoc benchmark ./src -t scalability     # Scalability test
autodoc benchmark -t provider -i 3         # Provider comparison
autodoc benchmark ./src -f markdown -o report.md
```

#### Benchmark Features
- **BenchmarkRunner** - Core benchmarking infrastructure with warmup, iterations, timing
- **AnalysisBenchmark** - Measure file analysis performance, scalability testing
- **ProviderBenchmark** - Compare AI provider response times and throughput
- **Reporter** - Console tables, Markdown, and JSON output formats
- **CLI Command** - autodoc benchmark with -t/--type, -f/--format, -o/--output options

#### Benchmark Types
- **analysis** - File analysis performance (default)
- **scalability** - Test with different directory sizes
- **provider** - Compare AI provider performance
- **all** - Run all benchmarks

**Test Coverage:** 22 unit tests for benchmark system

**Total tests:** 508 (was 486)


---

## [2.0.0] - 2025-11-25

### Added - Form.xml Validation 🎉

#### Form Validation System (NEW in 2.0)

**Automatic validation for 1C:Enterprise forms** - integrated with documentation generation:

- **FormParser** (`src/metadata/form-parser.ts`)
  - Complete XML structure parsing
  - Control hierarchy extraction (InputField, Button, Table, Group)
  - Event bindings (OnChange, Click, StartChoice, etc.)
  - Form attributes and commands parsing
  - ConditionalAppearance items
  - Localized title extraction

- **FormValidator** (`src/metadata/form-validator.ts`)
  - Cross-validation Form.xml ↔ Module.bsl
  - Missing handler detection (control events + commands)
  - Orphaned handler detection (code without XML references)
  - Coverage metrics calculation
  - Unused controls identification

- **FormExtendedValidator** (`src/metadata/form-extended-validator.ts`)
  - DataPath integrity checking (Объект.Код, Объект.Товары.Количество)
  - Form hierarchy validation
  - Required handlers recommendations
  - Best practice suggestions
  - **Quality scoring system (0-100)**
  - ConditionalAppearance validation
  - Command handler validation

- **EventHandlerDetector** (`src/metadata/event-handler-detector.ts`)
  - Tree-sitter based handler detection in Module.bsl
  - Form-level events (ПриСозданииНаСервере, ПриОткрытии)
  - Control events (ПриИзменении, Нажатие)
  - Table events (ПриАктивизацииСтроки)
  - Command handlers
  - Exported procedure detection

- **Automatic Integration**
  - Validation runs automatically during `generate_documentation`
  - Results included in LLM context for enhanced documentation
  - **Non-blocking errors** - validation failures don't stop documentation
  - Graceful degradation

**Test Coverage:** 224 unit tests covering all validation scenarios

**Usage:**
```typescript
// Automatic - triggered when Form.xml detected
generate_documentation({ path: "path/to/catalog/forms" })

// Validation results appear in LLM context:
// === ВАЛИДАЦИЯ ФОРМ ===
// Форма: ФормаЭлемента
// Оценка качества: 85/100
// Отсутствующие обработчики: 2
// - КодПриИзменении (InputField)
// - СохранитьНажатие (Button)
```

### Added - BSL Support 🎉

#### Core BSL Features
- **BSL Tree-sitter Analyzer** (`src/analyzer/bsl-treesitter-analyzer.ts`)
  - 100% accurate AST-based parsing of BSL code
  - Procedure and function extraction with parameters
  - Export keyword detection (Экспорт/Export)
  - Region analysis (#Область/#Region)
  - Comment extraction and preservation
  - Code statistics (lines of code, comment lines)
  - Support for Russian and English keywords

- **BSL Integration** (`src/analyzer/bsl-integration.ts`)
  - Markdown formatting for BSL analysis results
  - Module statistics generation
  - Export/internal method categorization
  - Empty file filtering
  - Complexity estimation

- **Russian Language Prompts** (`src/prompts/inline-docs-prompts.ts`)
  - Native Russian documentation generation
  - BSL-specific documentation format
  - Parameter and return value documentation
  - Usage examples in Russian
  - 1C:Enterprise terminology

- **Context-Aware Prompts** (`src/prompts/bsl-context-prompts.ts`) - **589 lines**
  - Module type detection from file path
  - Specialized prompts for 11 module types
  - Context-specific documentation guidelines
  - Best practices for each module type

#### Module Type Detection & Context-Aware Documentation

**11 module types with specialized prompts:**
- **Forms** (Формы) - UI event handlers, form initialization, data validation
- **Objects** (Модули объектов) - Business logic, before/after event handlers
- **Managers** (Модули менеджеров) - API and utilities, query generation
- **Common Modules** (Общие модули) - Shared functionality, reusable code
- **Commands** (Модули команд) - User actions, data processing
- **Session/Application** - Lifecycle management
- **External Connection** - Integration points
- **Managed Application** - Client-side logic
- **RecordSet** - Data manipulation
- **Value Manager** - Computed values

#### Configuration
- Added `.bsl` extension to supported file types
- BSL-optimized default settings
- Russian language documentation support

### Changed

#### Provider Rotation
- Enhanced provider rotation system
- Support for 5 AI providers:
  - Google Gemini (free, 1500 req/day)
  - Groq (free, 500k tokens/day)
  - Ollama (local, unlimited)
  - xAI Grok (paid, advanced)
  - OpenRouter (paid, fallback)

#### Documentation
- Updated README.md with BSL Quick Start section
- Added comprehensive BSL examples
- Documented BSL-specific features
- Added Russian language documentation guidelines

### Technical Details

#### Dependencies
- `tree-sitter-bsl@^0.1.5` - BSL grammar for tree-sitter
- `web-tree-sitter@^0.20.8` - Tree-sitter runtime

#### Architecture Improvements
- Modular analyzer design
- Singleton pattern for analyzer reuse
- Async initialization
- Error handling for missing WASM files

### Migration Guide

#### For Existing Users

**No breaking changes** - existing functionality fully preserved:
- TypeScript/JavaScript documentation works as before
- Python, Java, C++, etc. support unchanged
- Configuration compatibility maintained

**New BSL capabilities** work out of the box:
```json
{
  "mcpServers": {
    "auto-documenter": {
      "command": "node",
      "args": ["D:\\path\\to\\autodocument\\build\\index.js"],
      "env": {
        "ENABLE_ROTATION": "true",
        "PRIMARY_PROVIDER": "gemini",
        "GEMINI_API_KEY": "your-key"
      }
    }
  }
}
```

#### For BSL Projects

**Quick start:**
```bash
# Document 1C configuration
generate_documentation({
  "path": "D:/1C-Config/src/Configuration"
})

# Generate test plans
autotestplan({
  "path": "D:/1C-Config/src/DataProcessors"
})

# Review code
autoreview({
  "path": "D:/1C-Config/src/CommonModules"
})
```

### Added - 1C Structure Analyzer 🎉

#### Structure Analysis System (NEW in 2.0)

**Automatic detection and analysis of 1C:Enterprise configuration structure:**

- **Structure1CAnalyzer** (`src/analyzer/structure-1c-analyzer.ts`)
  - Path-based metadata object detection (Catalogs, Documents, Registers, etc.)
  - Module type detection (ObjectModule, ManagerModule, FormModule, etc.)
  - Support for 19 metadata object types
  - Support for 10 module types
  - Both English and Russian folder name support
  - Structural context generation for LLM prompts
  - Documentation guidance based on metadata/module type

- **Integrated with DocumentationTool**
  - Automatic structure detection for BSL files
  - Enriched prompts with metadata type information
  - Context-aware documentation guidance
  - Non-blocking errors - analysis failures don't stop documentation

**Usage:**
```typescript
import { structure1CAnalyzer } from './analyzer/structure-1c-analyzer.js';

// Analyze file path
const info = structure1CAnalyzer.analyze('/path/to/Catalogs/Товары/Ext/ObjectModule.bsl');
console.log(info.metadataType);      // 'Catalog'
console.log(info.objectName);         // 'Товары'
console.log(info.moduleType);         // 'ObjectModule'

// Get context for documentation
const context = structure1CAnalyzer.getContextInfo(info);
```

**Test Coverage:** 74 unit tests covering all metadata and module types

### Test Coverage Summary

- **Total tests:** 462 passing
- **Unit tests:** documentation-tool, review-tool, testplan-tool, mcp-server
- **Integration tests:** e2e, directory-processing, provider-rotation
- **BSL tests:** bsl-treesitter-analyzer, bsl-integration
- **Form validation tests:** form-parser, form-validator, form-extended-validator, event-handler-detector
- **Structure analyzer tests:** structure-1c-analyzer

### Known Issues

- None - all planned features for v2.0.0 implemented and tested

### Performance

- BSL parsing: ~0.1-0.5ms per file (tree-sitter)
- Zero-cost for non-BSL projects
- Lazy initialization of BSL analyzer

### Documentation

- **README.md** - Updated with BSL Quick Start
- **docs/guides/** - Configuration guides
- **docs/architecture/** - Technical documentation

---

## [1.0.0] - 2025-11-15

### Added

#### Initial Release Features
- MCP server implementation
- Directory traversal and analysis
- Git integration with .gitignore support
- Multi-language code documentation
- Test plan generation
- Code review functionality
- Bottom-up documentation approach

#### Supported Languages
- TypeScript (.ts, .tsx)
- JavaScript (.js, .jsx)
- Python (.py)
- Java (.java)
- C/C++ (.c, .cpp)
- C# (.cs)
- PHP (.php)
- Ruby (.rb)
- Go (.go)
- Rust (.rs)

#### AI Providers
- OpenRouter integration
- Multiple model support
- Configurable API endpoints

#### Tools
- `generate_documentation` - Creates documentation.md files
- `autotestplan` - Generates testplan.md files
- `autoreview` - Creates review.md files
- `generate_inline_docs` - Generates JSDoc/TSDoc comments

#### Configuration
- Environment variable configuration
- File size and count limits
- Custom prompt configuration
- Model selection

#### Output Files
- documentation.md - Comprehensive code documentation
- testplan.md - Test plans with edge cases
- review.md - Senior developer-level code reviews
- Fallback files for oversized directories

### Architecture
- Modular design
- Provider abstraction
- Tool registry system
- Centralized prompt management

---

## Release Notes

### Version 2.0.0 Highlights

**🎯 Major Feature #1: Form.xml Validation System**

Revolutionary validation for 1C:Enterprise forms:
- **Cross-validation** Form.xml ↔ Module.bsl (100% automated)
- **Quality scoring** 0-100 based on handler coverage and best practices
- **Automatic integration** - results included in documentation context
- **224 unit tests** ensuring production-ready reliability
- **Non-blocking** - validation failures don't stop documentation
- **Comprehensive checks:** missing handlers, orphaned code, DataPath integrity, commands, conditional appearance

**🎯 Major Feature #2: Native 1C:Enterprise (BSL) Support**

First-class support for 1C:Enterprise BSL modules:
- 100% accurate parsing using tree-sitter AST
- **Context-aware prompts** for 11 module types (589 lines)
- Russian language documentation
- Export detection and API documentation
- Module type awareness (Forms, Objects, Managers, etc.)
- Region and comment analysis

**🆓 Free-Tier Ready**

Default configuration now uses free providers:
- Google Gemini (1,500 req/day free)
- Groq (500k tokens/day free)
- Ollama (local, unlimited)

**Monthly cost: $0** for most projects!

**📊 Production Ready**

- Used in production for 1C:Enterprise projects
- Handles large codebases (100+ modules)
- Respects .gitignore patterns
- Smart directory processing
- Incremental documentation updates

### Upgrade Path

**From 1.0.0 to 2.0.0:**

1. Pull latest changes: `git pull`
2. Install dependencies: `npm install`
3. Rebuild: `npm run build`
4. Update configuration (optional) - add BSL-specific settings
5. Restart MCP server

**No manual migration required** - all features are backward compatible.

---

## Future Roadmap

### Completed in v2.0.0
- [x] Context-aware prompts for BSL module types ✅
- [x] Event handler detection ✅
- [x] Form.xml validation system ✅
- [x] 1C Structure Analyzer for metadata object detection ✅
- [x] Tool unit tests (documentation-tool, review-tool, testplan-tool) ✅
- [x] Integration tests (e2e, directory-processing, provider-rotation) ✅

### Completed in v2.2.0
- [x] CLI interface for standalone usage ✅
- [x] Performance benchmarks ✅
- [x] Interactive documentation browser ✅
- [x] Inline Docs Tool (generate inline comments for BSL) ✅

### Completed in v2.4.0
- [x] Watch mode for automatic regeneration ✅
- [x] AI response caching system ✅
- [x] Incremental documentation (git-aware) ✅
- [x] Configuration file support (YAML/JSON) ✅
- [x] Enhanced error handling system ✅
- [x] E2E tests for all CLI commands ✅
- [x] Test coverage > 1100 tests ✅

### v2.5.x Planned
- [ ] Cache integration for review/testplan/inline commands
- [ ] Parallel file processing
- [ ] Performance metrics dashboard

### Planned for v3.0.0
- [ ] Documentation diff tool
- [ ] Documentation quality metrics
- [ ] Export to different formats (HTML, PDF)
- [ ] Multi-file refactoring suggestions

### Planned for v4.0.0
- [ ] Real-time documentation updates
- [ ] Integration with 1C:Enterprise Designer
- [ ] Collaborative documentation features

---

## Links

- **Repository**: https://github.com/PARS-DOE/autodocument
- **Documentation**: [docs/](docs/)
- **Issues**: https://github.com/PARS-DOE/autodocument/issues
- **MCP Specification**: https://code.claude.com/docs/en/mcp

---

**Legend:**
- 🎉 Major feature
- ✨ Enhancement
- 🐛 Bug fix
- 📚 Documentation
- ⚡ Performance
- 🔧 Configuration
- 🔒 Security
