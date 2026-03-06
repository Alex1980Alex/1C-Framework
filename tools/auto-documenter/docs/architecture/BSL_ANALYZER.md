# BSL Analyzer Architecture

Technical documentation for the 1C:Enterprise Business Script Language (BSL) analyzer implementation in Auto-Documenter v2.0.0.

## Overview

The BSL analyzer is a comprehensive code analysis system built on tree-sitter for accurate parsing of 1C:Enterprise code. It provides:

- **AST-based parsing** - Syntax-aware analysis using tree-sitter-bsl
- **Module type detection** - 11 distinct 1C:Enterprise module types
- **Context generation** - Module-specific prompt templates
- **Bilingual support** - English and Russian (Cyrillic) paths
- **Export detection** - Public API identification
- **Region extraction** - Code organization analysis

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   MCP Tool Layer                         │
│  (generate_documentation, autotestplan, autoreview)     │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│                Documentation Aggregator                  │
│        (src/tools/aggregator.ts)                        │
│  • Bottom-up directory processing                        │
│  • File filtering (shouldDocument)                       │
│  • Multi-file aggregation                               │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│              File Analyzer (FileAnalyzer)                │
│        (src/analyzer/index.ts)                          │
│  • Language detection                                    │
│  • Parser selection                                      │
│  • Code statistics                                       │
└──────────┬─────────────────────┬────────────────────────┘
           │                     │
    ┌──────↓────────┐     ┌─────↓─────────┐
    │  BSL Analyzer  │     │ Other Parsers │
    │   (BSL-only)   │     │ (JS, TS, Py)  │
    └──────┬─────────┘     └───────────────┘
           │
           ↓
┌─────────────────────────────────────────────────────────┐
│           BSL Tree-sitter Analyzer                       │
│   (src/analyzer/bsl-treesitter-analyzer.ts)             │
│  • Tree-sitter parsing                                   │
│  • Procedure/function extraction                         │
│  • Parameter analysis                                    │
│  • Region detection                                      │
│  • Export keyword detection                              │
│  • Variable extraction                                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│            BSL Context Prompts                           │
│     (src/prompts/bsl-context-prompts.ts)                │
│  • Module type detection (11 types)                      │
│  • Context-aware prompt generation                       │
│  • Russian/English bilingual support                     │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. BSL Tree-sitter Analyzer
**File:** `src/analyzer/bsl-treesitter-analyzer.ts`

**Purpose:** Parse BSL code using tree-sitter grammar and extract structural information.

**Key Methods:**

```typescript
class BSLTreesitterAnalyzer {
  /**
   * Parses BSL code and extracts all analysis data
   * @returns LanguageAnalysis with procedures, functions, variables, etc.
   */
  analyze(code: string, filePath: string): LanguageAnalysis

  /**
   * Extracts procedure/function definitions from AST
   * @returns Array of function objects with name, params, isExported
   */
  extractProceduresAndFunctions(rootNode: Parser.SyntaxNode): Array<{
    name: string
    params: Array<{name: string, hasDefault: boolean}>
    isExported: boolean
    lineNumber: number
  }>

  /**
   * Detects if function/procedure is exported
   * @returns true if "Экспорт" or "Export" keyword found
   */
  isExported(node: Parser.SyntaxNode): boolean

  /**
   * Extracts #Область/#Region blocks
   * @returns Array of region names and line ranges
   */
  extractRegions(rootNode: Parser.SyntaxNode): Array<{
    name: string
    startLine: number
    endLine: number
  }>
}
```

**Tree-sitter Node Types:**

| Node Type | BSL Construct | Extraction Logic |
|-----------|---------------|------------------|
| `sub_declaration` | Процедура | Name, parameters, Экспорт keyword |
| `func_declaration` | Функция | Name, parameters, return value, Экспорт |
| `var_statement` | Перем | Variable declarations |
| `preprocessor_region` | #Область | Region name, line range |
| `identifier` | Variable names | Context-dependent extraction |

**Example AST Structure:**

```
program
  ├── preprocessor_region (#Область ПрограммныйИнтерфейс)
  │   └── func_declaration
  │       ├── identifier (ПолучитьСумму)
  │       ├── param_list
  │       │   ├── identifier (Число1)
  │       │   └── identifier (Число2)
  │       ├── export_keyword (Экспорт)
  │       └── statements
  └── preprocessor_endregion (#КонецОбласти)
```

**Statistics Collected:**

```typescript
interface CodeStatistics {
  totalLines: number        // All lines including empty
  codeLines: number        // Lines with actual code
  commentLines: number     // Lines with // or /* comments
  blankLines: number       // Empty lines
  functions: number        // Total function count
  procedures: number       // Total procedure count
  exportedCount: number    // Functions/procedures with Экспорт
  variables: number        // Variable declarations
  regions: number         // #Область blocks
}
```

### 2. BSL Context Prompts
**File:** `src/prompts/bsl-context-prompts.ts`

**Purpose:** Detect BSL module type and generate context-specific documentation prompts.

**Module Type Detection Algorithm:**

```typescript
function detectBSLModuleType(filePath: string): BSLModuleType {
  const lowerPath = filePath.toLowerCase()

  // Check file-name-based patterns first (most specific)
  if (lowerPath.includes('managedapplicationmodule.bsl'))
    return MANAGED_APPLICATION
  if (lowerPath.includes('applicationmodule.bsl'))
    return APPLICATION
  if (lowerPath.includes('externalconnectionmodule.bsl'))
    return EXTERNAL_CONNECTION
  if (lowerPath.includes('sessionmodule.bsl'))
    return SESSION
  if (lowerPath.includes('recordsetmodule.bsl'))
    return RECORDSET
  if (lowerPath.includes('valuemanagermodule.bsl'))
    return VALUE_MANAGER

  // Check directory-based patterns (bilingual support)
  if (matchesPath(lowerPath, ['/forms/', '\\forms\\', '/формы/', '\\формы\\']))
    if (matchesPath(lowerPath, ['/ext/form/module.bsl']))
      return FORM

  if (matchesPath(lowerPath, ['objectmodule.bsl']))
    return OBJECT

  if (matchesPath(lowerPath, ['managermodule.bsl']))
    return MANAGER

  if (matchesPath(lowerPath, ['/commands/', '\\commands\\', '/команды/', '\\команды\\']))
    if (matchesPath(lowerPath, ['commandmodule.bsl']))
      return COMMAND

  if (matchesPath(lowerPath, ['/commonmodules/', '\\commonmodules\\',
                               '/общиемодули/', '\\общиемодули\\']))
    return COMMON

  return UNKNOWN
}
```

**Detection Priority:**
1. **File-name specific** (highest) - ManagedApplicationModule, ApplicationModule, etc.
2. **Directory + filename combo** - Forms/*/Module.bsl, Commands/*/CommandModule.bsl
3. **Filename only** - ObjectModule.bsl, ManagerModule.bsl
4. **Directory only** (lowest) - CommonModules/*

**Critical Fix (v2.0.0):** Reordered `ManagedApplicationModule` check before `ApplicationModule` to prevent substring matching bug (since "managedapplicationmodule" contains "applicationmodule").

**Russian Path Support:**

| English Path | Russian Path | Module Type |
|--------------|--------------|-------------|
| `/Forms/*/Ext/Form/Module.bsl` | `/Формы/*/Ext/Form/Module.bsl` | FORM |
| `/Commands/*/Ext/CommandModule.bsl` | `/Команды/*/Ext/CommandModule.bsl` | COMMAND |
| `/CommonModules/*.bsl` | `/ОбщиеМодули/*.bsl` | COMMON |

Both Windows (`\`) and Unix (`/`) path separators supported.

**Context Prompt Template:**

```typescript
interface ModuleContext {
  moduleName: string       // e.g. "МОДУЛЬ ФОРМЫ"
  purpose: string          // Primary purpose description
  focusAreas: string[]    // What to document (events, queries, etc.)
  conventions: string[]   // 1C-specific naming/patterns
  commonPatterns: string[] // Typical code patterns for this module
}

function getBSLContextPrompt(filePath: string): string {
  const moduleType = detectBSLModuleType(filePath)
  const context = MODULE_CONTEXTS[moduleType]

  return `
## ${context.moduleName}

**Основное назначение:** ${context.purpose}

**Фокус документации:**
${context.focusAreas.map(area => `- ${area}`).join('\n')}

**Соглашения 1C:**
${context.conventions.map(conv => `- ${conv}`).join('\n')}

**Типичные паттерны:**
${context.commonPatterns.map(pattern => `- ${pattern}`).join('\n')}
`
}
```

### 3. Documentation Aggregator
**File:** `src/tools/aggregator.ts`

**Purpose:** Process directories bottom-up, aggregating documentation from child to parent.

**Bottom-Up Algorithm:**

```typescript
async function processDirectoryRecursive(dirPath: string): Promise<void> {
  const entries = await fs.readdir(dirPath, { withFileTypes: true })

  // Step 1: Process all subdirectories first (depth-first)
  for (const entry of entries) {
    if (entry.isDirectory() && !isIgnored(entry.name)) {
      await processDirectoryRecursive(path.join(dirPath, entry.name))
    }
  }

  // Step 2: Collect code files in current directory
  const codeFiles = entries.filter(e =>
    e.isFile() && isCodeFile(e.name) && !isIgnored(e.name)
  )

  const hasSubdirectories = entries.some(e =>
    e.isDirectory() && !isIgnored(e.name)
  )

  // Step 3: Check if directory should be documented
  if (!shouldDocument(dirPath, codeFiles, hasSubdirectories)) {
    return // Skip single-file directories without subdirectories
  }

  // Step 4: Analyze each code file
  const analyses: FileAnalysis[] = []
  for (const file of codeFiles) {
    const analysis = await analyzeFile(path.join(dirPath, file.name))
    analyses.push(analysis)
  }

  // Step 5: Aggregate and generate documentation
  const documentation = await generateAggregatedDocumentation(analyses)

  // Step 6: Write documentation.md
  await fs.writeFile(
    path.join(dirPath, 'documentation.md'),
    documentation
  )
}
```

**shouldDocument Logic:**

```typescript
function shouldDocument(
  dirPath: string,
  codeFiles: string[],
  hasSubdirectories: boolean
): boolean {
  // Minimum file requirement
  if (codeFiles.length < 1) return false

  // Skip single-file directories UNLESS they have subdirectories
  if (codeFiles.length === 1 && !hasSubdirectories) return false

  // Skip ignored patterns (.git, node_modules, etc.)
  if (isIgnoredPath(dirPath)) return false

  return true
}
```

**Design Rationale:** Single-file directories are self-contained and don't need aggregated documentation. For individual file docs, use `generate_inline_docs` tool instead.

### 4. File Analyzer
**File:** `src/analyzer/index.ts`

**Purpose:** Main entry point for file analysis, routing to appropriate parser.

**Language Detection:**

```typescript
function detectLanguage(filePath: string): Language {
  const ext = path.extname(filePath).toLowerCase()

  const LANGUAGE_MAP: Record<string, Language> = {
    '.bsl': 'bsl',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.py': 'python',
    '.java': 'java',
    '.go': 'go'
    // ... more languages
  }

  return LANGUAGE_MAP[ext] || 'unknown'
}
```

**Parser Selection:**

```typescript
async function analyzeFile(filePath: string): Promise<FileAnalysis> {
  const language = detectLanguage(filePath)
  const code = await fs.readFile(filePath, 'utf-8')

  let analysis: LanguageAnalysis

  switch (language) {
    case 'bsl':
      // Use BSL tree-sitter analyzer
      const bslAnalyzer = new BSLTreesitterAnalyzer()
      analysis = await bslAnalyzer.analyze(code, filePath)
      break

    case 'javascript':
    case 'typescript':
      // Use JavaScript/TypeScript parser
      analysis = await jstsAnalyzer.analyze(code, filePath)
      break

    default:
      // Fallback to simple regex-based analysis
      analysis = await simpleAnalyzer.analyze(code, filePath)
  }

  // Add BSL-specific context if applicable
  if (language === 'bsl') {
    analysis.moduleContext = getBSLContextPrompt(filePath)
    analysis.moduleType = detectBSLModuleType(filePath)
  }

  return {
    filePath,
    language,
    analysis
  }
}
```

## Data Flow

### Documentation Generation Flow

```
1. User calls generate_documentation tool
   Input: { path: "/src/Catalogs/Товары" }
   ↓
2. Aggregator starts bottom-up traversal
   Discovers: Forms/ФормаЭлемента/Ext/Form/Module.bsl
              Ext/ObjectModule.bsl
              Ext/ManagerModule.bsl
   ↓
3. FileAnalyzer detects language
   Forms/.../Module.bsl → "bsl"
   ObjectModule.bsl → "bsl"
   ManagerModule.bsl → "bsl"
   ↓
4. BSLTreesitterAnalyzer parses each file
   Extracts:
   - Functions: [ПриСозданииНаСервере, СохранитьИЗакрыть, ...]
   - Parameters: [{name: "Отказ"}, {name: "СтандартнаяОбработка"}]
   - Exports: [true, false, true]
   - Regions: ["ОбработчикиСобытийФормы", "ОбработчикиКомандФормы"]
   ↓
5. detectBSLModuleType identifies module type
   Forms/.../Module.bsl → FORM
   ObjectModule.bsl → OBJECT
   ManagerModule.bsl → MANAGER
   ↓
6. getBSLContextPrompt generates context
   FORM → "Focus: Event handlers, UI logic"
   OBJECT → "Focus: Business logic, validation"
   MANAGER → "Focus: CRUD operations, queries"
   ↓
7. Provider generates documentation with context
   Uses: Gemini/Groq/Ollama with BSL-specific prompt
   Output: Markdown documentation with Russian terms
   ↓
8. Aggregator writes documentation.md
   /src/Catalogs/Товары/documentation.md created
   ↓
9. Returns result to user
   Output: { success: true, filesProcessed: 3 }
```

### Inline Documentation Flow

```
1. User calls generate_inline_docs tool
   Input: { path: "/src/CommonModules/Utilities.bsl" }
   ↓
2. BSLTreesitterAnalyzer parses file
   Extracts: Functions with line numbers
   ↓
3. For each exported function:
   a) Generate JSDoc-style comment using AI
   b) Insert comment before function declaration
   c) Preserve original code
   ↓
4. Write modified file back to disk
   ↓
5. Return JSON result with changes
   Output: { symbolsDocumented: 5, changes: [...] }
```

## Key Algorithms

### 1. Export Detection Algorithm

```typescript
function isExported(node: Parser.SyntaxNode): boolean {
  // Check all child nodes for export keyword
  for (let i = 0; i < node.childCount; i++) {
    const child = node.child(i)

    // Check for "Экспорт" or "Export" keyword
    if (child?.type === 'export_keyword') return true

    // Check text content (fallback for grammar variations)
    const text = child?.text?.toLowerCase()
    if (text === 'экспорт' || text === 'export') return true
  }

  // Check siblings (export keyword may be after parameter list)
  let sibling = node.nextSibling
  while (sibling && sibling.startIndex < node.endIndex + 50) {
    if (sibling.type === 'export_keyword') return true
    if (sibling.text?.toLowerCase() === 'экспорт') return true
    if (sibling.text?.toLowerCase() === 'export') return true
    sibling = sibling.nextSibling
  }

  return false
}
```

**Why this approach:**
- Tree-sitter grammar may parse `Экспорт` differently in different contexts
- Keyword can appear after function name or after parameter list
- Must support both Russian (`Экспорт`) and English (`Export`)
- Need fallback to text matching for grammar edge cases

### 2. Region Extraction Algorithm

```typescript
function extractRegions(rootNode: Parser.SyntaxNode): Region[] {
  const regions: Region[] = []
  const stack: RegionStart[] = [] // Track nested regions

  function traverse(node: Parser.SyntaxNode) {
    // Check for region start
    if (node.type === 'preprocessor_region' ||
        node.text?.match(/^#(Область|Region|область|region)/)) {

      const name = extractRegionName(node.text)
      stack.push({
        name,
        startLine: node.startPosition.row + 1
      })
    }

    // Check for region end
    if (node.type === 'preprocessor_endregion' ||
        node.text?.match(/^#(КонецОбласти|EndRegion|конецобласти|endregion)/)) {

      if (stack.length > 0) {
        const start = stack.pop()
        regions.push({
          name: start.name,
          startLine: start.startLine,
          endLine: node.endPosition.row + 1
        })
      }
    }

    // Recurse to children
    for (let i = 0; i < node.childCount; i++) {
      traverse(node.child(i)!)
    }
  }

  traverse(rootNode)
  return regions
}
```

**Features:**
- Supports nested regions (using stack)
- Handles both Russian and English syntax
- Case-insensitive matching
- Extracts region names from preprocessor directives

### 3. Module Type String Matching

**Problem:** Substring matching can cause false positives.

**Example Bug (Fixed in v2.0.0):**
```typescript
// WRONG ORDER (bug)
if (path.includes('applicationmodule.bsl'))
  return APPLICATION
if (path.includes('managedapplicationmodule.bsl'))
  return MANAGED_APPLICATION

// "managedapplicationmodule" contains "applicationmodule"
// So it incorrectly matched APPLICATION first!
```

**Correct Order:**
```typescript
// RIGHT ORDER (fixed)
if (path.includes('managedapplicationmodule.bsl'))
  return MANAGED_APPLICATION  // Check more specific first
if (path.includes('applicationmodule.bsl'))
  return APPLICATION          // Then check general pattern
```

**Rule:** Always check longer/more-specific substrings before shorter/general ones.

## Testing Strategy

### Unit Tests (76 total)

**bsl-treesitter-analyzer.test.ts** (35 tests)
- Singleton pattern tests
- Empty file handling
- Procedure/function extraction
- Parameter parsing
- Export detection
- Region extraction
- Variable declarations
- Code statistics
- Real-world code patterns
- Error handling

**bsl-context-prompts.test.ts** (41 tests)
- Module type detection (11 types × multiple paths)
- Russian folder name support
- Bilingual path variations
- Edge cases (mixed Cyrillic/Latin)
- Context prompt generation
- Unknown module handling

### Integration Tests

**test-mcp-tools/** directory:
- Multi-file BSL project structure
- Real module type mix (Manager, Form, Test)
- Tools tested: generate_documentation, autotestplan, autoreview, generate_inline_docs
- Validates end-to-end workflow

### Test Coverage

```
src/analyzer/bsl-treesitter-analyzer.ts
  ✓ Core parsing logic              100%
  ✓ Export detection                100%
  ✓ Region extraction               100%
  ✓ Statistics calculation          100%

src/prompts/bsl-context-prompts.ts
  ✓ Module type detection           100%
  ✓ Russian path support            100%
  ✓ Context generation              100%

src/analyzer/index.ts (BSL paths)
  ✓ Language detection              100%
  ✓ Parser selection                100%
  ⚠ File I/O error handling          75%

src/tools/aggregator.ts (BSL files)
  ✓ Bottom-up processing            90%
  ⚠ Provider error handling          60%
```

## Performance Characteristics

### Parsing Performance

| File Size | Lines | Parse Time | Memory |
|-----------|-------|------------|--------|
| Small | <500 | <10ms | 2MB |
| Medium | 500-2000 | 10-50ms | 5MB |
| Large | 2000-5000 | 50-200ms | 15MB |
| Very Large | 5000+ | 200-500ms | 30MB+ |

**Tree-sitter advantages:**
- Incremental parsing (fast re-parsing after edits)
- Error-tolerant (handles syntactically incorrect code)
- Low memory overhead
- Consistent O(n) parsing time

### Directory Processing Performance

**Example project:**
```
src/Catalogs/
├── Товары/ (15 files)
├── Контрагенты/ (12 files)
└── Договоры/ (8 files)
Total: 35 BSL files
```

**Processing time breakdown:**
```
File analysis:         35 files × 20ms = 700ms
AI documentation:      10 dirs × 3s = 30s
File I/O:             100ms
Total:                ~31s
```

**Bottleneck:** AI provider latency (95% of time)
**Optimization:** Provider rotation minimizes cost, not time

## Error Handling

### Parse Errors

Tree-sitter is error-tolerant:
```typescript
// Even with syntax errors, partial AST is available
const code = `
Функция НеЗакрытаяФункция()
  Возврат 123
// Missing КонецФункции
`

// Still extracts function name and return statement
const analysis = analyzer.analyze(code, 'test.bsl')
// analysis.functions = [{ name: 'НеЗакрытаяФункция', ... }]
```

### Module Type Detection Fallback

```typescript
const moduleType = detectBSLModuleType(filePath)

if (moduleType === BSLModuleType.UNKNOWN) {
  // Fallback to generic BSL context
  return getGenericBSLContext()
}
```

### Provider Errors

Handled by provider rotation system:
```typescript
try {
  return await geminiProvider.generate(prompt)
} catch (error) {
  // Automatic fallback to next provider
  return await groqProvider.generate(prompt)
}
```

## Configuration

### BSL-Specific Settings

No special configuration required - BSL support is automatic based on file extension.

**Optional:** Customize prompts by editing `src/prompts/bsl-context-prompts.ts`.

### Environment Variables

Standard Auto-Documenter environment variables apply:
- `GEMINI_API_KEY` - Google Gemini (free tier)
- `GROQ_API_KEY` - Groq (free tier)
- `OLLAMA_BASE_URL` - Local Ollama
- `ENABLE_ROTATION=true` - Enable provider rotation

## Future Enhancements

### v2.1.0 (Planned)

**1. Metadata Analyzer**
- Parse 1C metadata XML files
- Document forms, tables, attributes
- Cross-reference metadata with code

**2. Event Handler Detection**
- Automatically identify form/document event handlers
- Link events to platform documentation
- Validate event handler signatures

**3. Enhanced Region Support**
- Better nested region handling
- Region-based documentation sections
- Statistics per region

### v2.2.0 (Planned)

**4. Query Analysis**
- Parse 1C query language
- Validate query syntax
- Performance recommendations

**5. Cross-Module Dependency Analysis**
- Trace function calls between modules
- Generate call graphs
- Identify unused code

## Related Documentation

- **User Guide:** [BSL Development Guide](../guides/BSL_DEVELOPMENT_GUIDE.md)
- **Development:** [BSL Tree-sitter Integration](../development/BSL_TREESITTER.md)
- **Troubleshooting:** [BSL Issues](../troubleshooting/BSL_ISSUES.md)

## References

- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [1C:Enterprise Documentation](https://its.1c.ru/)
- [BSL Language Server](https://github.com/1c-syntax/bsl-language-server)

---

**Last Updated:** 2025-11-24
**Version:** 2.0.0
**Author:** Auto-Documenter Team
