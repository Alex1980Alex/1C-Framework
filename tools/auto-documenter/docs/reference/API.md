# Auto-Documenter API Reference

Complete API reference for the Auto-Documenter v2.2.0.

## Table of Contents

- [MCP Tools](#mcp-tools)
- [CLI Commands](#cli-commands)
- [Analyzers](#analyzers)
- [Providers](#providers)
- [Type Definitions](#type-definitions)

---

## MCP Tools

### generate_documentation

Generates comprehensive documentation for a directory.

```typescript
interface GenerateDocumentationParams {
  path: string;              // Directory path to analyze
  updateExisting?: boolean;  // Update existing docs (default: true)
  openRouterApiKey?: string; // API key (optional, uses env vars)
  model?: string;            // Model override (optional)
}

interface GenerateDocumentationResult {
  outputPath: string;        // Path to generated documentation.md
  success: boolean;          // Whether generation succeeded
  content: string;           // Generated documentation content
  error?: string;            // Error message if failed
  isUpdate: boolean;         // Whether this was an update
}
```

**Example:**
```typescript
const result = await mcp.call('generate_documentation', {
  path: '/path/to/project/src',
  updateExisting: true
});
```

---

### autotestplan

Generates test plans for code.

```typescript
interface AutoTestPlanParams {
  path: string;              // Directory path to analyze
  updateExisting?: boolean;  // Update existing plans (default: true)
  openRouterApiKey?: string; // API key (optional)
  model?: string;            // Model override (optional)
}

interface AutoTestPlanResult {
  outputPath: string;        // Path to generated testplan.md
  success: boolean;
  content: string;           // Generated test plan
  error?: string;
  isUpdate: boolean;
}
```

---

### autoreview

Generates code reviews with security focus.

```typescript
interface AutoReviewParams {
  path: string;              // Directory path to analyze
  updateExisting?: boolean;  // Update existing reviews (default: true)
  openRouterApiKey?: string; // API key (optional)
  model?: string;            // Model override (optional)
}

interface AutoReviewResult {
  outputPath: string;        // Path to generated review.md
  success: boolean;
  content: string;           // Generated review
  error?: string;
  isUpdate: boolean;
}
```

---

### generate_inline_docs

Generates inline documentation (JSDoc/TSDoc/BSL comments).

```typescript
interface GenerateInlineDocsParams {
  path: string;              // Directory path to process
  updateExisting?: boolean;  // Update existing docs (default: true)
  dryRun?: boolean;          // Preview without changes (default: false)
  openRouterApiKey?: string;
  model?: string;
}

interface InlineDocsResult {
  outputPath: string;        // Path to results JSON
  success: boolean;
  content: string;           // Summary
  filesProcessed: number;
  symbolsDocumented: number;
}
```

---

## CLI Commands

### generate (doc, g)

Generate documentation for a directory.

```bash
autodoc generate <path> [options]
autodoc doc <path>         # Alias
autodoc g <path>           # Short alias
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `-p, --provider <name>` | AI provider (gemini, groq, ollama, grok, openrouter) | gemini |
| `-m, --model <name>` | Model to use | Provider default |
| `-k, --api-key <key>` | API key | From env vars |
| `-u, --update` | Update existing docs | true |
| `-r, --recursive` | Process subdirectories | true |
| `-v, --verbose` | Verbose output | false |
| `-q, --quiet` | Minimal output | false |

---

### review

Generate code review with security analysis.

```bash
autodoc review <path> [options]
```

Same options as `generate`.

---

### testplan

Generate test plan.

```bash
autodoc testplan <path> [options]
```

Same options as `generate`.

---

### inline

Generate inline documentation comments.

```bash
autodoc inline <path> [options]
```

**Additional Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Preview changes without writing | false |

---

### info

Display tool information.

```bash
autodoc info
```

Shows:
- Available providers and their status
- Supported languages
- Available commands
- Environment variable status

---

### benchmark

Run performance benchmarks.

```bash
autodoc benchmark [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--type <type>` | Benchmark type (analysis, provider, all) | all |
| `--iterations <n>` | Number of iterations | 3 |
| `--output <format>` | Output format (console, json, markdown) | console |

---

### browse

Browse generated documentation.

```bash
autodoc browse <path> [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `-p, --port <port>` | Server port | 3000 |
| `--no-open` | Don't open browser | false |

---

## Analyzers

### FileAnalyzer

Main analyzer class for all file types.

```typescript
import { FileAnalyzer, AnalysisResult } from 'autodocument';

class FileAnalyzer {
  constructor();

  /**
   * Analyze a directory recursively
   */
  async analyzeDirectory(
    directoryPath: string,
    options?: AnalyzeOptions
  ): Promise<AnalysisResult>;

  /**
   * Analyze a single file
   */
  async analyzeFile(filePath: string): Promise<AnalyzedFile>;
}

interface AnalysisResult {
  analyzedFiles: AnalyzedFile[];
  totalFiles: number;
  totalLines: number;
  languages: Record<string, number>;
  structure: DirectoryStructure;
}

interface AnalyzedFile {
  path: string;
  content: string;
  language: string;
  lines: number;
  symbols?: Symbol[];
}
```

---

### TSCompilerAnalyzer

TypeScript/JavaScript AST-based analyzer using TypeScript Compiler API.

```typescript
import { TSCompilerAnalyzer, TSSymbol } from 'autodocument';

class TSCompilerAnalyzer {
  /**
   * Analyze source code and extract symbols
   * @param content Source code
   * @param fileName File name for language detection
   */
  analyze(content: string, fileName?: string): TSSymbol[];

  /**
   * Get only exported symbols
   */
  getExportedSymbols(content: string, fileName?: string): TSSymbol[];

  /**
   * Get symbols without JSDoc
   */
  getUndocumentedSymbols(content: string, fileName?: string): TSSymbol[];

  /**
   * Get exported symbols without JSDoc
   */
  getExportedUndocumentedSymbols(content: string, fileName?: string): TSSymbol[];
}

interface TSSymbol {
  name: string;
  type: 'function' | 'class' | 'interface' | 'type' | 'method' | 'property';
  code: string;
  lineNumber: number;
  endLineNumber: number;
  isExported: boolean;
  isAsync: boolean;
  hasJSDoc: boolean;
  parameters?: TSParameter[];
  returnType?: string;
  modifiers?: string[];
}

interface TSParameter {
  name: string;
  type?: string;
  isOptional: boolean;
  hasDefault: boolean;
}
```

**Example:**
```typescript
import { TSCompilerAnalyzer } from 'autodocument';

const analyzer = new TSCompilerAnalyzer();
const code = `
export function greet(name: string): string {
  return \`Hello, \${name}!\`;
}
`;

const symbols = analyzer.analyze(code, 'example.ts');
console.log(symbols);
// [{
//   name: 'greet',
//   type: 'function',
//   isExported: true,
//   parameters: [{ name: 'name', type: 'string', isOptional: false }],
//   returnType: 'string',
//   hasJSDoc: false,
//   ...
// }]
```

---

### BSLTreesitterAnalyzer

1C:Enterprise BSL code analyzer using tree-sitter.

```typescript
import { getBSLAnalyzer, BSLAnalysisResult } from 'autodocument';

const analyzer = await getBSLAnalyzer();

interface BSLCodeElement {
  type: BSLElementType;
  name: string;
  startLine: number;
  endLine: number;
  isExport: boolean;
  parameters?: BSLParameter[];
  body?: string;
}

enum BSLElementType {
  Procedure = 'procedure',
  Function = 'function',
  Variable = 'variable',
  Region = 'region',
  Comment = 'comment'
}

interface BSLAnalysisResult {
  elements: BSLCodeElement[];
  procedures: BSLCodeElement[];
  functions: BSLCodeElement[];
  exports: BSLCodeElement[];
  regions: BSLCodeElement[];
  hasErrors: boolean;
}
```

---

### Structure1CAnalyzer

Analyzes 1C:Enterprise configuration structure.

```typescript
import { analyze1CStructure, FilePathInfo } from 'autodocument';

function analyze1CStructure(filePath: string): FilePathInfo;

interface FilePathInfo {
  objectType: MetadataObjectType;
  objectName: string;
  moduleType: ModuleType;
  isCommonModule: boolean;
  subsystem?: string;
}

enum MetadataObjectType {
  Catalog = 'Catalog',
  Document = 'Document',
  DataProcessor = 'DataProcessor',
  Report = 'Report',
  InformationRegister = 'InformationRegister',
  AccumulationRegister = 'AccumulationRegister',
  CommonModule = 'CommonModule',
  // ... more types
}

enum ModuleType {
  ObjectModule = 'ObjectModule',
  ManagerModule = 'ManagerModule',
  FormModule = 'FormModule',
  CommandModule = 'CommandModule',
  CommonModule = 'CommonModule',
  // ... more types
}
```

---

## Providers

### Provider Configuration

```typescript
type Provider = 'gemini' | 'groq' | 'ollama' | 'grok' | 'openrouter';

const PROVIDERS: readonly Provider[] = [
  'gemini', 'groq', 'ollama', 'grok', 'openrouter'
];

const DEFAULT_MODELS: Record<Provider, string> = {
  gemini: 'gemini-2.5-flash-latest',
  groq: 'llama-3.3-70b-versatile',
  ollama: 'deepseek-r1:14b',
  grok: 'grok-2-1212',
  openrouter: 'anthropic/claude-3.5-sonnet'
};
```

### Environment Variables

| Provider | API Key Variable | Notes |
|----------|-----------------|-------|
| Gemini | `GEMINI_API_KEY` | Free tier: 1,500 req/day |
| Groq | `GROQ_API_KEY` | Free tier: 500k tokens/day |
| Ollama | - | Local, no API key needed |
| Grok | `XAI_API_KEY` | Paid only |
| OpenRouter | `OPENROUTER_API_KEY` | Pay-per-use |

### Global Options

| Variable | Description | Default |
|----------|-------------|---------|
| `PRIMARY_PROVIDER` | Default provider | gemini |
| `ENABLE_ROTATION` | Enable provider failover | true |

---

### OpenRouterClient

Main LLM client with provider rotation.

```typescript
import { OpenRouterClient } from 'autodocument';

class OpenRouterClient {
  constructor(
    apiKey?: string,
    model?: string,
    enableRotation?: boolean
  );

  /**
   * Generate content with automatic provider failover
   */
  async generateWithFallback(
    files: Array<{ path: string; content: string }>,
    systemPrompt: string,
    existingContent?: string,
    isUpdate?: boolean
  ): Promise<GenerationResult>;

  /**
   * Generate with custom prompt
   */
  async generateWithCustomPrompt(
    files: Array<{ path: string; content: string }>,
    prompt: string,
    existingContent?: string,
    isUpdate?: boolean,
    formatInstructions?: string
  ): Promise<GenerationResult>;
}

interface GenerationResult {
  content: string;
  successful: boolean;
  provider: string;
  model: string;
  error?: string;
  tokenUsage?: {
    input: number;
    output: number;
    total: number;
  };
}
```

---

## Type Definitions

### Core Types

```typescript
// Analysis types
interface AnalysisResult {
  analyzedFiles: AnalyzedFile[];
  totalFiles: number;
  totalLines: number;
  languages: Record<string, number>;
  structure: DirectoryStructure;
}

interface AnalyzedFile {
  path: string;
  content: string;
  language: string;
  lines: number;
  symbols?: Symbol[];
}

// Tool result types
interface AutoToolResult {
  outputPath: string;
  success: boolean;
  content: string;
  error?: string;
  isUpdate: boolean;
}

// Provider types
type Provider = 'gemini' | 'groq' | 'ollama' | 'grok' | 'openrouter';

interface GenerationResult {
  content: string;
  successful: boolean;
  provider: string;
  model: string;
  error?: string;
}
```

---

## See Also

- [CLI Usage Guide](../CLI-USAGE-GUIDE.md) - Detailed CLI documentation
- [Architecture](../architecture/README.md) - System design
- [BSL Development Guide](../guides/BSL_DEVELOPMENT_GUIDE.md) - 1C:Enterprise specifics
- [Form.xml Validation](../features/FORM_XML_VALIDATION.md) - Form validation feature

---

*Last updated: 2025-11-26*
*Version: 2.2.0*
