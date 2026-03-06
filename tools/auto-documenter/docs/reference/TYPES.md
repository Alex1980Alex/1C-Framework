# Types Reference

Complete TypeScript type definitions for Auto-Documenter.

## Core Types

### Analysis Types

```typescript
/**
 * Result of directory analysis
 */
interface AnalysisResult {
  /** List of analyzed files */
  analyzedFiles: AnalyzedFile[];
  /** Total file count */
  totalFiles: number;
  /** Total line count */
  totalLines: number;
  /** Language breakdown { language: fileCount } */
  languages: Record<string, number>;
  /** Directory structure tree */
  structure: DirectoryStructure;
}

/**
 * Single analyzed file
 */
interface AnalyzedFile {
  /** Absolute file path */
  path: string;
  /** File content */
  content: string;
  /** Detected language */
  language: string;
  /** Line count */
  lines: number;
  /** Extracted symbols (optional) */
  symbols?: Symbol[];
}

/**
 * Directory structure node
 */
interface DirectoryStructure {
  name: string;
  type: 'file' | 'directory';
  children?: DirectoryStructure[];
  language?: string;
  lines?: number;
}
```

---

### TypeScript Analyzer Types

```typescript
/**
 * Symbol extracted from TypeScript/JavaScript code
 */
interface TSSymbol {
  /** Symbol name */
  name: string;
  /** Symbol type */
  type: 'function' | 'class' | 'interface' | 'type' | 'method' | 'property';
  /** Full source code */
  code: string;
  /** Start line (1-indexed) */
  lineNumber: number;
  /** End line (1-indexed) */
  endLineNumber: number;
  /** Has export modifier */
  isExported: boolean;
  /** Has async modifier */
  isAsync: boolean;
  /** Has JSDoc comment */
  hasJSDoc: boolean;
  /** Function/method parameters */
  parameters?: TSParameter[];
  /** Return type annotation */
  returnType?: string;
  /** All modifiers */
  modifiers?: string[];
}

/**
 * Function/method parameter
 */
interface TSParameter {
  /** Parameter name */
  name: string;
  /** Type annotation */
  type?: string;
  /** Has ? modifier */
  isOptional: boolean;
  /** Has default value */
  hasDefault: boolean;
}
```

---

### BSL Analyzer Types

```typescript
/**
 * BSL element type
 */
enum BSLElementType {
  Procedure = 'procedure',
  Function = 'function',
  Variable = 'variable',
  Region = 'region',
  Comment = 'comment'
}

/**
 * BSL code element
 */
interface BSLCodeElement {
  /** Element type */
  type: BSLElementType;
  /** Element name */
  name: string;
  /** Start line */
  startLine: number;
  /** End line */
  endLine: number;
  /** Has Экспорт/Export keyword */
  isExport: boolean;
  /** Parameters for procedures/functions */
  parameters?: BSLParameter[];
  /** Full body code */
  body?: string;
}

/**
 * BSL parameter
 */
interface BSLParameter {
  /** Parameter name */
  name: string;
  /** Has Знач/Val keyword */
  byValue: boolean;
  /** Default value expression */
  defaultValue?: string;
}

/**
 * BSL analysis result
 */
interface BSLAnalysisResult {
  /** All found elements */
  elements: BSLCodeElement[];
  /** Procedures only */
  procedures: BSLCodeElement[];
  /** Functions only */
  functions: BSLCodeElement[];
  /** Exported elements */
  exports: BSLCodeElement[];
  /** Region blocks */
  regions: BSLCodeElement[];
  /** Parser encountered errors */
  hasErrors: boolean;
}
```

---

### 1C Structure Types

```typescript
/**
 * Metadata object type
 */
enum MetadataObjectType {
  Catalog = 'Catalog',
  Document = 'Document',
  DataProcessor = 'DataProcessor',
  Report = 'Report',
  InformationRegister = 'InformationRegister',
  AccumulationRegister = 'AccumulationRegister',
  AccountingRegister = 'AccountingRegister',
  CalculationRegister = 'CalculationRegister',
  CommonModule = 'CommonModule',
  SessionParameter = 'SessionParameter',
  Role = 'Role',
  ExchangePlan = 'ExchangePlan',
  Constant = 'Constant',
  Enum = 'Enum',
  ChartOfCharacteristicTypes = 'ChartOfCharacteristicTypes',
  ChartOfAccounts = 'ChartOfAccounts',
  ChartOfCalculationTypes = 'ChartOfCalculationTypes',
  Task = 'Task',
  BusinessProcess = 'BusinessProcess',
  Unknown = 'Unknown'
}

/**
 * Module type
 */
enum ModuleType {
  ObjectModule = 'ObjectModule',
  ManagerModule = 'ManagerModule',
  FormModule = 'FormModule',
  CommandModule = 'CommandModule',
  CommonModule = 'CommonModule',
  RecordSetModule = 'RecordSetModule',
  ValueManagerModule = 'ValueManagerModule',
  SessionModule = 'SessionModule',
  ExternalConnectionModule = 'ExternalConnectionModule',
  ManagedApplicationModule = 'ManagedApplicationModule',
  OrdinaryApplicationModule = 'OrdinaryApplicationModule',
  Unknown = 'Unknown'
}

/**
 * Parsed file path information
 */
interface FilePathInfo {
  /** Metadata object type */
  objectType: MetadataObjectType;
  /** Object name (e.g., "Товары") */
  objectName: string;
  /** Module type */
  moduleType: ModuleType;
  /** Is common module */
  isCommonModule: boolean;
  /** Parent subsystem (if any) */
  subsystem?: string;
}
```

---

### Tool Types

```typescript
/**
 * Base tool result
 */
interface AutoToolResult {
  /** Path to output file */
  outputPath: string;
  /** Whether operation succeeded */
  success: boolean;
  /** Generated content */
  content: string;
  /** Error message if failed */
  error?: string;
  /** Whether this was an update */
  isUpdate: boolean;
}

/**
 * Inline docs file result
 */
interface InlineDocsFileResult {
  /** File path */
  filePath: string;
  /** Whether documentation succeeded */
  success: boolean;
  /** Number of symbols documented */
  symbolsDocumented: number;
  /** Error message if failed */
  error?: string;
  /** Individual symbol changes */
  changes?: Array<{
    symbolName: string;
    symbolType: 'function' | 'class' | 'interface' | 'type';
    documentation: string;
    lineNumber: number;
  }>;
}
```

---

### Provider Types

```typescript
/**
 * Supported AI providers
 */
type Provider = 'gemini' | 'groq' | 'ollama' | 'grok' | 'openrouter';

/**
 * Provider array (immutable)
 */
const PROVIDERS: readonly Provider[] = [
  'gemini', 'groq', 'ollama', 'grok', 'openrouter'
] as const;

/**
 * Default models per provider
 */
const DEFAULT_MODELS: Record<Provider, string> = {
  gemini: 'gemini-2.5-flash-latest',
  groq: 'llama-3.3-70b-versatile',
  ollama: 'deepseek-r1:14b',
  grok: 'grok-2-1212',
  openrouter: 'anthropic/claude-3.5-sonnet'
};

/**
 * Generation result from LLM
 */
interface GenerationResult {
  /** Generated content */
  content: string;
  /** Whether generation succeeded */
  successful: boolean;
  /** Provider used */
  provider: string;
  /** Model used */
  model: string;
  /** Error message if failed */
  error?: string;
  /** Token usage statistics */
  tokenUsage?: {
    input: number;
    output: number;
    total: number;
  };
}
```

---

### CLI Types

```typescript
/**
 * CLI command options
 */
interface CommandOptions {
  /** AI provider to use */
  provider?: Provider;
  /** Model to use */
  model?: string;
  /** API key override */
  apiKey?: string;
  /** Update existing files */
  update?: boolean;
  /** Process recursively */
  recursive?: boolean;
  /** Verbose output */
  verbose?: boolean;
  /** Minimal output */
  quiet?: boolean;
}

/**
 * Inline docs specific options
 */
interface InlineDocsOptions extends CommandOptions {
  /** Preview without writing */
  dryRun?: boolean;
}

/**
 * Benchmark options
 */
interface BenchmarkOptions {
  /** Benchmark type */
  type?: 'analysis' | 'provider' | 'all';
  /** Number of iterations */
  iterations?: number;
  /** Output format */
  output?: 'console' | 'json' | 'markdown';
}
```

---

### Benchmark Types

```typescript
/**
 * Benchmark result
 */
interface BenchmarkResult {
  /** Benchmark name */
  name: string;
  /** Average duration in ms */
  averageDuration: number;
  /** Min duration */
  minDuration: number;
  /** Max duration */
  maxDuration: number;
  /** Standard deviation */
  stdDev: number;
  /** Number of iterations */
  iterations: number;
  /** Individual run times */
  samples: number[];
  /** Additional metrics */
  metadata?: Record<string, any>;
}

/**
 * Benchmark suite
 */
interface BenchmarkSuite {
  /** Suite name */
  name: string;
  /** Individual results */
  results: BenchmarkResult[];
  /** Total duration */
  totalDuration: number;
  /** Timestamp */
  timestamp: string;
}
```

---

### Form Validation Types

```typescript
/**
 * Form.xml validation result
 */
interface FormValidationResult {
  /** Form is valid */
  isValid: boolean;
  /** Overall quality score (0-100) */
  score: number;
  /** Validation errors */
  errors: ValidationIssue[];
  /** Warnings */
  warnings: ValidationIssue[];
  /** Form metadata */
  metadata: FormMetadata;
}

/**
 * Validation issue
 */
interface ValidationIssue {
  /** Issue code */
  code: string;
  /** Human-readable message */
  message: string;
  /** Severity level */
  severity: 'error' | 'warning' | 'info';
  /** Location in file */
  location?: {
    line: number;
    column: number;
  };
  /** Fix suggestion */
  suggestion?: string;
}

/**
 * Form metadata
 */
interface FormMetadata {
  /** Form name */
  name: string;
  /** Form type */
  type: 'managed' | 'regular';
  /** Element count */
  elementCount: number;
  /** Command count */
  commandCount: number;
  /** Has module */
  hasModule: boolean;
}
```

---

## Type Guards

```typescript
/**
 * Check if value is a valid provider
 */
function isProvider(value: string): value is Provider {
  return PROVIDERS.includes(value as Provider);
}

/**
 * Check if symbol is a function
 */
function isFunction(symbol: TSSymbol): boolean {
  return symbol.type === 'function';
}

/**
 * Check if result is successful
 */
function isSuccessful(result: AutoToolResult): boolean {
  return result.success && !result.error;
}
```

---

## Utility Types

```typescript
/**
 * Make all properties optional recursively
 */
type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

/**
 * Extract function parameters type
 */
type FunctionParams<T extends (...args: any[]) => any> = T extends (...args: infer P) => any ? P : never;

/**
 * Provider configuration
 */
type ProviderConfig = {
  [K in Provider]: {
    apiKey?: string;
    model?: string;
    enabled: boolean;
  };
};
```

---

*Last updated: 2025-11-26*
