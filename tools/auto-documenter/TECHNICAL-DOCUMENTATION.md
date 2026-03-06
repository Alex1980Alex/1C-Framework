# Autodocument - Техническая документация

> **Версия:** 2.4.0
> **Дата:** 2025-11-26
> **Тип:** MCP Server + CLI для автоматической документации кода

---

## Оглавление

1. [Обзор проекта](#1-обзор-проекта)
2. [Архитектура](#2-архитектура)
3. [MCP Server](#3-mcp-server)
4. [CLI интерфейс](#4-cli-интерфейс)
5. [Инструменты (Tools)](#5-инструменты-tools)
6. [Анализаторы кода](#6-анализаторы-кода)
7. [AI провайдеры](#7-ai-провайдеры)
8. [Система кэширования](#8-система-кэширования)
9. [Watch режим](#9-watch-режим)
10. [Инкрементальная обработка](#10-инкрементальная-обработка)
11. [Система учета затрат](#11-система-учета-затрат)
12. [Парсер метаданных 1C](#12-парсер-метаданных-1c)
13. [Конфигурация](#13-конфигурация)
14. [API Reference](#14-api-reference)

---

## 1. Обзор проекта

### 1.1 Назначение

**Autodocument** - это инструмент автоматической генерации документации кода с использованием AI. Работает как:
- **MCP Server** - для интеграции с Claude Code и другими MCP-клиентами
- **CLI утилита** - для использования из командной строки

### 1.2 Ключевые возможности

| Возможность | Описание |
|-------------|----------|
| **Документация кода** | Генерация markdown-документации для проектов |
| **Code Review** | AI-анализ кода с рекомендациями |
| **Test Plan** | Генерация планов тестирования |
| **Inline Docs** | JSDoc/TSDoc/BSL комментарии |
| **Documentation Diff** | Сравнение версий документации |
| **Native BSL Support** | 100% поддержка языка 1C:Enterprise |
| **Multi-Provider** | 5 AI провайдеров с ротацией |
| **Кэширование** | 90% экономия токенов |
| **Watch Mode** | Автообновление при изменениях |

### 1.3 Поддерживаемые языки

```
TypeScript (.ts, .tsx)  │  JavaScript (.js, .jsx)
Python (.py)            │  BSL/1C (.bsl, .os)
Java (.java)            │  C# (.cs)
Go (.go)                │  Rust (.rs)
```

### 1.4 Зависимости

```json
{
  "core": {
    "@modelcontextprotocol/sdk": "^1.19.1",
    "tree-sitter": "0.21.1",
    "tree-sitter-bsl": "^0.1.5",
    "openai": "^4.17.0"
  },
  "cli": {
    "commander": "^14.0.2",
    "chalk": "^5.6.2"
  },
  "utilities": {
    "diff": "^7.0.0",
    "xml2js": "^0.6.2",
    "js-yaml": "^4.1.1"
  }
}
```

---

## 2. Архитектура

### 2.1 Структура проекта

```
autodocument/
├── src/
│   ├── index.ts                 # MCP Server entry point
│   ├── analyzer/                # Анализаторы кода
│   │   ├── index.ts             # FileAnalyzer
│   │   └── bsl-treesitter-analyzer.ts  # BSL парсер
│   ├── benchmark/               # Производительность
│   ├── browser/                 # Doc browser server
│   ├── cache/                   # Кэширование ответов
│   │   └── response-cache.ts
│   ├── cli/                     # CLI интерфейс
│   │   ├── index.ts             # Entry point
│   │   ├── commands/            # Команды
│   │   │   ├── generate.ts      # autodoc generate
│   │   │   ├── review.ts        # autodoc review
│   │   │   ├── testplan.ts      # autodoc testplan
│   │   │   ├── inline.ts        # autodoc inline
│   │   │   ├── diff.ts          # autodoc diff
│   │   │   ├── info.ts          # autodoc info
│   │   │   ├── benchmark.ts     # autodoc benchmark
│   │   │   └── browse.ts        # autodoc browse
│   │   └── utils/               # Утилиты CLI
│   │       ├── options.ts       # Глобальные опции
│   │       ├── output.ts        # Форматирование вывода
│   │       └── version.ts       # Версия и баннер
│   ├── config/                  # Конфигурация
│   │   └── config-loader.ts     # Загрузчик конфигов
│   ├── cost/                    # Учет затрат
│   │   ├── cost-tracker.ts      # Трекер затрат
│   │   └── pricing-config.ts    # Цены провайдеров
│   ├── crawler/                 # Обход директорий
│   ├── documentation/           # Генерация документации
│   ├── errors/                  # Типы ошибок
│   ├── incremental/             # Инкрементальная обработка
│   │   └── change-tracker.ts    # Отслеживание изменений
│   ├── metadata/                # Метаданные 1C
│   │   ├── form-parser.ts       # Парсер Form.xml
│   │   ├── form-types.ts        # Типы форм
│   │   └── metadata-parser.ts   # Парсер метаданных
│   ├── openrouter/              # OpenRouter клиент
│   ├── prompts/                 # AI промпты
│   │   └── bsl-context-prompts.ts  # BSL-контексты
│   ├── providers/               # AI провайдеры
│   │   └── provider-rotation.ts # Ротация провайдеров
│   ├── tools/                   # MCP инструменты
│   │   ├── base-tool.ts         # Базовый класс
│   │   ├── registry.ts          # Реестр инструментов
│   │   ├── documentation-tool.ts
│   │   ├── review-tool.ts
│   │   ├── testplan-tool.ts
│   │   ├── inline-docs-tool.ts
│   │   ├── diff-tool.ts
│   │   └── diff-formatters.ts
│   ├── utils/                   # Общие утилиты
│   └── watch/                   # Watch mode
│       └── file-watcher.ts
├── tests/                       # Тесты (531+)
├── docs/                        # Документация
├── build/                       # Скомпилированный код
├── package.json
└── tsconfig.json
```

### 2.2 Потоки данных

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Client                              │
│                    (Claude Code, etc.)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP Protocol
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Server (index.ts)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   ToolRegistry                            │   │
│  │  ├── DocumentationTool    ├── TestPlanTool               │   │
│  │  ├── ReviewTool           └── InlineDocsTool             │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────────┐    ┌─────────────┐
│  FileAnalyzer │    │   ResponseCache  │    │  CostTracker │
│ ├── BSL AST   │    │ ├── SHA256 keys  │    │ ├── USD      │
│ └── TS/JS     │    │ └── TTL 24h      │    │ └── Tokens   │
└──────┬────────┘    └────────┬────────┘    └──────────────┘
       │                      │
       ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ProviderRotationManager                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Primary: Gemini → Fallback: Groq → Fallback: Ollama      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. MCP Server

### 3.1 Класс AutodocumentServer

**Файл:** `src/index.ts`

```typescript
class AutodocumentServer {
  private server: Server;
  private toolRegistry: ToolRegistry;

  constructor() {
    this.server = new Server({
      name: 'autodocument',
      version: '2.4.0',
    }, {
      capabilities: {
        tools: {},
      },
    });

    this.toolRegistry = new ToolRegistry();
    this.setupToolHandlers();
    this.setupErrorHandlers();
  }
}
```

### 3.2 Tool Handlers

```typescript
private setupToolHandlers(): void {
  // Список доступных инструментов
  this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: this.toolRegistry.getToolSchemas(),
  }));

  // Вызов инструмента
  this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const tool = this.toolRegistry.getTool(name);

    if (!tool) {
      throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`);
    }

    // Выполнение с progress callback
    const result = await tool.execute(args, (progress) => {
      this.server.notification({
        method: 'notifications/progress',
        params: { progress }
      });
    });

    return { content: [{ type: 'text', text: result }] };
  });
}
```

### 3.3 Доступные инструменты MCP

| Tool | Описание | Параметры |
|------|----------|-----------|
| `generate_documentation` | Генерация документации | `path`, `updateExisting` |
| `autoreview` | Code review | `path` |
| `autotestplan` | План тестирования | `path` |
| `generate_inline_docs` | Inline документация | `path`, `updateExisting` |

---

## 4. CLI интерфейс

### 4.1 Entry Point

**Файл:** `src/cli/index.ts`

```typescript
async function main(): Promise<void> {
  const program = new Command();

  program
    .name('autodoc')
    .description('Automatic code documentation generator')
    .version('2.4.0');

  // Глобальные опции
  setupGlobalOptions(program);

  // Команды
  program.addCommand(createGenerateCommand());
  program.addCommand(createReviewCommand());
  program.addCommand(createTestplanCommand());
  program.addCommand(createInlineCommand());
  program.addCommand(createInfoCommand());
  program.addCommand(createBenchmarkCommand());
  program.addCommand(createBrowseCommand());
  program.addCommand(createDiffCommand());

  await program.parseAsync(process.argv);
}
```

### 4.2 Команды

#### generate (doc, g)
```bash
autodoc generate <path> [options]
autodoc g src/

# Опции:
--provider <name>      # AI провайдер (gemini|groq|ollama|grok|openrouter)
--model <name>         # Модель AI
--api-key <key>        # API ключ
--update               # Обновить существующую документацию
--cache                # Включить кэширование
--watch                # Watch mode
--incremental          # Инкрементальная генерация
```

#### review (r)
```bash
autodoc review <path> [options]
autodoc r src/
```

#### testplan (test, t)
```bash
autodoc testplan <path> [options]
autodoc t src/
```

#### inline (i)
```bash
autodoc inline <path> [options]
```

#### diff (d, compare)
```bash
autodoc diff <base> <target> [options]

# Опции:
-f, --format <format>        # console|markdown|json|github
-o, --output <file>          # Сохранить в файл
-w, --ignore-whitespace      # Игнорировать пробелы
-b, --detect-breaking        # Обнаружение breaking changes
```

#### info
```bash
autodoc info                 # Информация о системе
```

#### benchmark
```bash
autodoc benchmark <path>     # Бенчмарк производительности
```

#### browse
```bash
autodoc browse <path>        # Запустить doc browser
```

### 4.3 Глобальные опции

```typescript
export interface CLIOptions {
  provider: Provider;        // AI провайдер
  model?: string;            // Модель
  apiKey?: string;           // API ключ
  verbose: boolean;          // Подробный вывод
  quiet: boolean;            // Тихий режим
  update: boolean;           // Обновлять существующее
  force: boolean;            // Принудительное выполнение
  cache: boolean;            // Кэширование
  cacheDir?: string;         // Директория кэша
  watch: boolean;            // Watch mode
  incremental: boolean;      // Инкрементальный режим
}

export type Provider = 'gemini' | 'groq' | 'ollama' | 'grok' | 'openrouter';
```

### 4.4 Модели по умолчанию

```typescript
export const DEFAULT_MODELS: Record<Provider, string> = {
  gemini: 'gemini-2.5-flash-latest',
  groq: 'llama-3.3-70b-versatile',
  ollama: 'deepseek-r1:14b',
  grok: 'grok-2-1212',
  openrouter: 'anthropic/claude-3.5-sonnet'
};
```

---

## 5. Инструменты (Tools)

### 5.1 Базовый класс BaseTool

**Файл:** `src/tools/base-tool.ts`

```typescript
export interface BaseToolConfig {
  apiKey?: string;
  model?: string;
  updateExisting?: boolean;
}

export interface AutoToolResult {
  success: boolean;
  outputPath: string;
  content: string;
  error?: string;
  isUpdate?: boolean;
  stats?: {
    filesProcessed: number;
    linesGenerated: number;
    tokensUsed?: number;
  };
}

export abstract class BaseTool<T extends BaseToolConfig> {
  abstract readonly name: string;
  abstract readonly description: string;
  protected readonly config: T;

  constructor(config: T) {
    this.config = config;
  }

  abstract generate(
    directoryPath: string,
    analysisResult: AnalysisResult,
    isTopLevel: boolean,
    childrenContent?: Array<{ path: string; content: string }>
  ): Promise<AutoToolResult>;

  protected abstract createFallbackContent(
    directoryPath: string,
    analysisResult: AnalysisResult
  ): string;

  protected formatResultSummary(result: AutoToolResult): string {
    if (result.success) {
      return `✅ ${this.name}: ${result.outputPath}`;
    }
    return `❌ ${this.name}: ${result.error}`;
  }
}
```

### 5.2 ToolRegistry

**Файл:** `src/tools/registry.ts`

```typescript
export class ToolRegistry {
  private tools: Map<string, BaseTool<any>> = new Map();

  constructor(apiKey?: string, model?: string) {
    this.registerTools(apiKey, model);
  }

  private registerTools(apiKey?: string, model?: string): void {
    this.registerTool(new DocumentationTool(apiKey, model));
    this.registerTool(new TestPlanTool(apiKey, model));
    this.registerTool(new ReviewTool(apiKey, model));
    this.registerTool(new InlineDocsTool(apiKey, model));
  }

  registerTool(tool: BaseTool<any>): void {
    this.tools.set(tool.name, tool);
  }

  getTool(name: string): BaseTool<any> | undefined {
    return this.tools.get(name);
  }

  hasTool(name: string): boolean {
    return this.tools.has(name);
  }

  getToolSchemas(): ToolSchema[] {
    return Array.from(this.tools.values()).map(tool => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema
    }));
  }

  getToolNames(): string[] {
    return Array.from(this.tools.keys());
  }
}
```

### 5.3 Diff Tool

**Файл:** `src/cli/commands/diff.ts`

```typescript
export interface DiffOptions {
  ignoreWhitespace: boolean;
  includeUnchanged: boolean;
  detectBreaking: boolean;
  includePatterns?: string[];
  excludePatterns?: string[];
}

// Форматы вывода: console, markdown, json, github
export type OutputFormat = 'console' | 'markdown' | 'json' | 'github';

// Результат сравнения
interface DiffResult {
  summary: {
    totalFiles: number;
    changedFiles: number;
    addedFiles: number;
    removedFiles: number;
    linesAdded: number;
    linesRemoved: number;
    breakingChanges: number;
  };
  files: FileDiff[];
}
```

---

## 6. Анализаторы кода

### 6.1 BSL Tree-sitter Analyzer

**Файл:** `src/analyzer/bsl-treesitter-analyzer.ts`

```typescript
export interface BSLAnalysisResult {
  procedures: BSLProcedure[];
  functions: BSLFunction[];
  variables: BSLVariable[];
  exports: string[];
  regions: BSLRegion[];
  comments: BSLComment[];
  imports: string[];
  moduleType?: BSLModuleType;
}

export class BSLTreesitterAnalyzer {
  private parser: TreeSitter.Parser | null = null;

  async initialize(): Promise<void> {
    const TreeSitter = await import('web-tree-sitter');
    await TreeSitter.default.init();

    const language = await loadBSLLanguage();
    this.parser = new TreeSitter.default.Parser();
    this.parser.setLanguage(language);
  }

  public analyze(code: string, filePath?: string): BSLAnalysisResult {
    if (!this.parser) {
      throw new Error('Parser not initialized');
    }

    const tree = this.parser.parse(code);
    const result: BSLAnalysisResult = {
      procedures: [],
      functions: [],
      variables: [],
      exports: [],
      regions: [],
      comments: [],
      imports: []
    };

    this.traverseTree(tree.rootNode, result);

    if (filePath) {
      result.moduleType = detectBSLModuleType(filePath);
    }

    return result;
  }
}
```

### 6.2 BSL Module Types

```typescript
export enum BSLModuleType {
  FORM = 'form',                           // Модуль формы
  OBJECT = 'object',                       // Модуль объекта
  MANAGER = 'manager',                     // Модуль менеджера
  COMMON = 'common',                       // Общий модуль
  COMMAND = 'command',                     // Модуль команды
  SESSION = 'session',                     // Модуль сеанса
  APPLICATION = 'application',             // Модуль приложения
  EXTERNAL_CONNECTION = 'external_connection',
  MANAGED_APPLICATION = 'managed_application',
  RECORDSET = 'recordset',                 // Модуль набора записей
  VALUE_MANAGER = 'value_manager',         // Модуль менеджера значений
  UNKNOWN = 'unknown'
}
```

### 6.3 Context-Aware Prompts для BSL

**Файл:** `src/prompts/bsl-context-prompts.ts`

```typescript
export function getBSLContextPrompt(filePath: string): string {
  const moduleType = detectBSLModuleType(filePath);

  switch (moduleType) {
    case BSLModuleType.FORM:
      return `
## Контекст: Модуль формы

**Особенности модуля формы:**
- Обработка событий формы (ПриОткрытии, ПриЗакрытии, ОбработкаОповещения)
- Управление элементами формы (Элементы.ИмяЭлемента)
- Работа с данными формы (ЭтотОбъект, Объект, Реквизиты)
- Клиент-серверное взаимодействие (&НаКлиенте, &НаСервере)

**При документировании учитывайте:**
1. Директивы компиляции (&НаКлиенте, &НаСервере, &НаСервереБезКонтекста)
2. Связь обработчиков с элементами формы
3. Передачу данных между клиентом и сервером
4. Оптимизацию серверных вызовов
`;

    case BSLModuleType.COMMON:
      return `
## Контекст: Общий модуль

**Особенности общего модуля:**
- Переиспользуемые процедуры и функции
- Экспортные методы (Экспорт)
- Глобальная доступность в конфигурации
- Возможные контексты выполнения

**При документировании учитывайте:**
1. Экспортные vs внутренние методы
2. Зависимости от других общих модулей
3. Контекст выполнения (Сервер, Клиент, ВнешнееСоединение)
4. Назначение модуля (служебный, прикладной, интеграционный)
`;

    // ... другие типы модулей
  }
}
```

---

## 7. AI провайдеры

### 7.1 Provider Rotation Manager

**Файл:** `src/providers/provider-rotation.ts`

```typescript
export interface RotationConfig {
  primaryProvider: Provider;
  fallbackProviders: Provider[];
  maxErrorsBeforeSwitch: number;
  cooldownMs: number;
  retryDelayMs: number;
}

export class ProviderRotationManager {
  private config: RotationConfig;
  private currentProviderIndex: number = 0;
  private providerErrors: Map<Provider, number> = new Map();
  private providerCooldowns: Map<Provider, number> = new Map();
  private costTracker: CostTracker;

  constructor(config: Partial<RotationConfig> = {}) {
    this.config = {
      primaryProvider: 'gemini',
      fallbackProviders: ['groq', 'ollama'],
      maxErrorsBeforeSwitch: 3,
      cooldownMs: 60000,      // 1 минута
      retryDelayMs: 1000,     // 1 секунда
      ...config
    };
    this.costTracker = new CostTracker();
  }

  getCurrentProvider(): Provider {
    const providers = [
      this.config.primaryProvider,
      ...this.config.fallbackProviders
    ];
    return providers[this.currentProviderIndex];
  }

  createClient(): OpenAI {
    const provider = this.getCurrentProvider();
    const apiKey = this.getApiKey(provider);
    const baseURL = this.getBaseURL(provider);

    return new OpenAI({
      apiKey,
      baseURL,
      timeout: 60000,
      maxRetries: 2
    });
  }

  recordSuccess(inputTokens?: number, outputTokens?: number): void {
    const provider = this.getCurrentProvider();
    this.providerErrors.set(provider, 0);

    if (inputTokens && outputTokens) {
      this.costTracker.recordRequest(
        provider,
        this.getModel(provider),
        inputTokens,
        outputTokens
      );
    }
  }

  recordError(error: string): void {
    const provider = this.getCurrentProvider();
    const currentErrors = (this.providerErrors.get(provider) || 0) + 1;
    this.providerErrors.set(provider, currentErrors);

    if (currentErrors >= this.config.maxErrorsBeforeSwitch) {
      this.switchToNextProvider();
    }
  }

  private switchToNextProvider(): void {
    const currentProvider = this.getCurrentProvider();
    this.providerCooldowns.set(currentProvider, Date.now());

    const totalProviders = 1 + this.config.fallbackProviders.length;
    this.currentProviderIndex =
      (this.currentProviderIndex + 1) % totalProviders;

    console.error(`Switching to provider: ${this.getCurrentProvider()}`);
  }
}
```

### 7.2 Конфигурация провайдеров

| Provider | Base URL | Free Tier | Модель по умолчанию |
|----------|----------|-----------|---------------------|
| Gemini | `https://generativelanguage.googleapis.com/v1beta` | 1500 req/day | gemini-2.5-flash-latest |
| Groq | `https://api.groq.com/openai/v1` | 500k tokens/day | llama-3.3-70b-versatile |
| Ollama | `http://localhost:11434/v1` | Unlimited (local) | deepseek-r1:14b |
| Grok | `https://api.x.ai/v1` | Нет | grok-2-1212 |
| OpenRouter | `https://openrouter.ai/api/v1` | Pay-as-you-go | claude-3.5-sonnet |

### 7.3 API Keys (Environment Variables)

```bash
export GEMINI_API_KEY=...
export GROQ_API_KEY=...
export XAI_API_KEY=...           # Grok
export OPENROUTER_API_KEY=...
# Ollama не требует ключа
```

---

## 8. Система кэширования

### 8.1 ResponseCache

**Файл:** `src/cache/response-cache.ts`

```typescript
export interface CacheConfig {
  directory: string;        // Директория кэша
  ttlSeconds: number;       // TTL (по умолчанию 24 часа)
  maxSizeMb: number;        // Максимальный размер (100 MB)
  enabled: boolean;         // Включен/выключен
}

export interface CacheEntry {
  hash: string;             // SHA256 хеш контента
  provider: string;         // AI провайдер
  model: string;            // Модель
  promptType: string;       // Тип промпта
  createdAt: number;        // Timestamp создания
  expiresAt: number;        // Timestamp истечения
  sizeBytes: number;        // Размер в байтах
  hits: number;             // Количество попаданий
}

export class ResponseCache {
  async get(key: string): Promise<string | null> {
    // Проверяет существование и TTL
    // Обновляет hit count
    // Возвращает кэшированный ответ или null
  }

  async set(
    key: string,
    response: string,
    provider: string,
    model: string,
    promptType: string
  ): Promise<void> {
    // Проверяет лимит размера
    // Удаляет старые записи при необходимости
    // Сохраняет ответ и метаданные
  }

  generateKey(
    content: string,
    provider: string,
    model: string,
    promptType: string
  ): string {
    // SHA256 хеш от нормализованного контента + параметров
    const data = JSON.stringify({
      content: this.normalizeContent(content),
      provider,
      model,
      promptType
    });
    return crypto.createHash('sha256').update(data).digest('hex');
  }
}
```

### 8.2 Cache Statistics

```typescript
export interface CacheStats {
  totalEntries: number;     // Всего записей
  totalSizeBytes: number;   // Общий размер
  hits: number;             // Попадания в кэш
  misses: number;           // Промахи
  hitRatio: number;         // Коэффициент попаданий (0-1)
  expiredEntries: number;   // Истекшие записи
  tokensSaved: number;      // Сэкономлено токенов (~response.length/4)
}
```

### 8.3 withCache Wrapper

```typescript
export function withCache<T extends (...args: any[]) => Promise<string>>(
  cache: ResponseCache,
  fn: T,
  options: {
    provider: string;
    model: string;
    promptType: string;
    getContentKey: (...args: Parameters<T>) => string;
  }
): T {
  return (async (...args: Parameters<T>): Promise<string> => {
    const contentKey = options.getContentKey(...args);
    const cacheKey = cache.generateKey(
      contentKey,
      options.provider,
      options.model,
      options.promptType
    );

    // Try cache first
    const cached = await cache.get(cacheKey);
    if (cached !== null) {
      return cached;
    }

    // Call original function
    const result = await fn(...args);

    // Store in cache
    await cache.set(cacheKey, result, options.provider, options.model, options.promptType);

    return result;
  }) as T;
}
```

---

## 9. Watch режим

### 9.1 FileWatcher

**Файл:** `src/watch/file-watcher.ts`

```typescript
export interface WatchOptions {
  include: string[];        // Glob паттерны для включения
  exclude: string[];        // Glob паттерны для исключения
  debounceMs: number;       // Задержка debounce (1000ms)
  recursive: boolean;       // Рекурсивно следить
  pollIntervalMs?: number;  // Интервал polling (500ms)
}

export const DEFAULT_WATCH_OPTIONS: WatchOptions = {
  include: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.bsl'],
  exclude: ['**/node_modules/**', '**/dist/**', '**/.git/**', '**/*.d.ts'],
  debounceMs: 1000,
  recursive: true,
  pollIntervalMs: 500
};

export class FileWatcher extends EventEmitter {
  start(): void {
    // Запускает fs.watch с рекурсией
    // Фильтрует по include/exclude
    // Debounce изменений
  }

  stop(): void {
    // Останавливает все watchers
    // Flush pending changes
  }

  // События
  on('change', (event: FileChangeEvent) => void);
  on('batch', (batch: FileChangeBatch) => void);
  on('error', (error: Error) => void);
  on('ready', () => void);
}
```

### 9.2 WatchModeRunner

```typescript
export class WatchModeRunner {
  async start(
    regenerate: (files: string[]) => Promise<void>
  ): Promise<void> {
    console.log(`🔍 Starting watch mode in: ${this.rootDir}`);
    console.log(`   Include: ${this.options.include.join(', ')}`);
    console.log(`   Exclude: ${this.options.exclude.join(', ')}`);
    console.log(`   Debounce: ${this.options.debounceMs}ms`);
    console.log(`   Press Ctrl+C to stop.`);

    this.watcher = createWatcher(this.rootDir, this.options, {
      onBatch: async (batch) => {
        console.log(`📝 Detected ${batch.files.length} changed file(s)`);
        await regenerate(batch.files);
        console.log(`✅ Documentation updated successfully.`);
      },
      onError: (error) => {
        console.error(`❌ Watch error: ${error.message}`);
      },
      onReady: () => {
        console.log(`✅ Watcher ready.`);
      }
    });
  }
}
```

---

## 10. Инкрементальная обработка

### 10.1 ChangeTracker

**Файл:** `src/incremental/change-tracker.ts`

```typescript
export interface TrackedFile {
  path: string;             // Относительный путь
  hash: string;             // MD5 хеш контента
  mtime: number;            // Время модификации
  size: number;             // Размер файла
  processedAt?: number;     // Когда обработан
}

export interface TrackingState {
  version: string;
  projectRoot: string;
  lastFullRun?: number;
  files: Record<string, TrackedFile>;
  gitCommit?: string;       // Хеш git коммита
}

export class ChangeTracker {
  async detectChanges(): Promise<FileChange[]> {
    // 1. Загружает предыдущее состояние
    // 2. Сканирует текущие файлы
    // 3. Сравнивает хеши
    // 4. Использует git diff если доступен
    // 5. Возвращает список изменений (added/modified/deleted)
  }

  async markProcessed(filePaths: string[]): Promise<void> {
    // Обновляет состояние для обработанных файлов
    // Сохраняет текущий git commit
  }

  async markAllProcessed(): Promise<void> {
    // Полное сканирование и сохранение состояния
  }
}
```

### 10.2 runIncremental

```typescript
export async function runIncremental(
  rootDir: string,
  processFiles: (files: string[]) => Promise<void>,
  options: IncrementalOptions = {}
): Promise<{
  processed: number;
  skipped: number;
  changes: FileChange[];
}> {
  const tracker = new ChangeTracker(rootDir);

  if (options.force) {
    // Полный прогон - сбрасываем состояние
    await tracker.reset();
    const files = await tracker.detectChanges();
    await processFiles(files.map(f => f.path));
    await tracker.markAllProcessed();
    return { processed: files.length, skipped: 0, changes: files };
  }

  // Инкрементальный прогон
  const changes = await tracker.detectChanges();
  const filesToProcess = changes
    .filter(c => c.status === 'added' || c.status === 'modified')
    .map(c => c.path);

  if (filesToProcess.length > 0) {
    await processFiles(filesToProcess);
    await tracker.markProcessed(filesToProcess);
  }

  return {
    processed: filesToProcess.length,
    skipped: totalFiles - filesToProcess.length,
    changes
  };
}
```

---

## 11. Система учета затрат

### 11.1 CostTracker

**Файл:** `src/cost/cost-tracker.ts`

```typescript
export interface RequestCost {
  timestamp: Date;
  provider: Provider;
  model: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: number;             // USD
  isFree: boolean;
}

export interface BudgetLimit {
  maxCost?: number;         // Максимум USD
  maxTokens?: number;       // Максимум токенов
  maxRequests?: number;     // Максимум запросов
  warningThreshold?: number; // Порог предупреждения (0-1)
}

export class CostTracker {
  recordRequest(
    provider: Provider,
    model: string,
    inputTokens: number,
    outputTokens: number
  ): RequestCost {
    const cost = calculateCost(provider, model, inputTokens, outputTokens);
    // Сохраняет в историю
    // Обновляет статистику по провайдеру
    return requestCost;
  }

  checkBudget(): BudgetStatus {
    // Проверяет лимиты
    // Возвращает exceeded/warningTriggered/message
  }

  printSummary(): void {
    // 💰 Cost Summary:
    // Total Requests: 42
    //   Free: 40 | Paid: 2
    // Total Tokens: 125,000
    // Total Cost: $0.02
    //
    // 📊 Per-Provider Breakdown:
    // GEMINI:
    //   Requests: 40
    //   Cost: $0.00 (FREE)
    //   Daily Limit: 40/1500 requests (2.7%)
  }

  exportToJSON(): string {
    // Экспорт всей статистики в JSON
  }
}
```

### 11.2 Цены провайдеров (pricing-config.ts)

```typescript
export interface ModelPricing {
  inputPer1MTokens: number;    // $ за 1M input токенов
  outputPer1MTokens: number;   // $ за 1M output токенов
  isFree: boolean;
}

export const PROVIDER_PRICING: Record<Provider, Record<string, ModelPricing>> = {
  gemini: {
    'gemini-2.5-flash-latest': {
      inputPer1MTokens: 0,
      outputPer1MTokens: 0,
      isFree: true
    }
  },
  groq: {
    'llama-3.3-70b-versatile': {
      inputPer1MTokens: 0,
      outputPer1MTokens: 0,
      isFree: true
    }
  },
  ollama: {
    '*': { inputPer1MTokens: 0, outputPer1MTokens: 0, isFree: true }
  },
  grok: {
    'grok-2-1212': {
      inputPer1MTokens: 2,
      outputPer1MTokens: 10,
      isFree: false
    }
  },
  openrouter: {
    'anthropic/claude-3.5-sonnet': {
      inputPer1MTokens: 3,
      outputPer1MTokens: 15,
      isFree: false
    }
  }
};
```

---

## 12. Парсер метаданных 1C

### 12.1 FormParser

**Файл:** `src/metadata/form-parser.ts`

```typescript
export interface IFormStructure {
  formName: string;
  xmlFilePath: string;
  formEvents: IFormEvent[];
  attributes: IFormAttribute[];
  controls: IFormControl[];
  rootControls: IFormControl[];
  allEvents: IFormEvent[];
  commands: IFormCommand[];
  conditionalAppearance: IConditionalAppearanceItem[];
}

export interface IFormControl {
  id: string;
  name: string;
  type: FormControlType;
  dataPath?: string;
  title?: ILocalizedTitle[];
  events: IFormEvent[];
  parent?: string;
  children: IFormControl[];
  width?: number;
  horizontalStretch?: boolean;
}

export class FormParser {
  async parseFormXML(xmlFilePath: string): Promise<IFormStructure> {
    // Парсит Form.xml с помощью xml2js
    // Извлекает структуру формы
    // Извлекает элементы управления (рекурсивно)
    // Извлекает события и обработчики
    // Извлекает команды
    // Извлекает условное оформление
  }

  generateSummary(formStructure: IFormStructure): string {
    // Генерирует markdown-описание формы
  }

  generateContextPrompt(formStructure: IFormStructure): string {
    // Генерирует контекст для LLM
    // Включает структуру элементов
    // Включает связи с обработчиками
  }
}
```

### 12.2 Form Control Types

```typescript
export type FormControlType =
  | 'InputField'
  | 'Button'
  | 'Table'
  | 'Group'
  | 'Pages'
  | 'Page'
  | 'CommandBar'
  | 'Label'
  | 'CheckBox'
  | 'RadioButton'
  | 'Picture'
  | 'HTMLDocumentField'
  | 'SpreadsheetDocumentField'
  | 'CalendarField'
  | 'ChartField'
  | 'FormattedDocumentField'
  | 'Unknown';

export const CONTROL_TYPE_MAP: Record<string, FormControlType> = {
  'InputField': 'InputField',
  'Button': 'Button',
  'Table': 'Table',
  'UsualGroup': 'Group',
  'Pages': 'Pages',
  'Page': 'Page',
  'CommandBar': 'CommandBar',
  'LabelField': 'Label',
  'CheckBoxField': 'CheckBox',
  // ...
};
```

### 12.3 Form Event Types

```typescript
export const EVENT_NAME_MAP: Record<string, FormEventType> = {
  'OnOpen': 'ПриОткрытии',
  'OnClose': 'ПриЗакрытии',
  'BeforeClose': 'ПередЗакрытием',
  'OnChange': 'ПриИзменении',
  'OnClick': 'Нажатие',
  'OnActivateRow': 'ПриАктивизацииСтроки',
  'OnStartChoice': 'НачалоВыбора',
  'OnChoiceProcessing': 'ОбработкаВыбора',
  'OnCreateAtServer': 'ПриСозданииНаСервере',
  // ...
};
```

---

## 13. Конфигурация

### 13.1 Config Loader

**Файл:** `src/config/config-loader.ts`

```typescript
export interface AutodocConfig {
  version?: string;
  extends?: string;           // Наследование от другого конфига
  cli?: CliConfig;
  docs?: DocsConfig;
  watch?: WatchConfig;
  cache?: CacheConfig;
  extensions?: string[];
  ignore?: string[];
  providers?: {
    gemini?: { model?: string; temperature?: number };
    groq?: { model?: string; temperature?: number };
    ollama?: { model?: string; baseUrl?: string };
    grok?: { model?: string; temperature?: number };
    openrouter?: { model?: string; temperature?: number };
  };
}

// Файлы конфигурации (в порядке приоритета)
export const CONFIG_FILES = [
  'autodoc.config.yaml',
  'autodoc.config.yml',
  'autodoc.config.json',
  '.autodocrc.yaml',
  '.autodocrc.yml',
  '.autodocrc.json',
  '.autodocrc'
];
```

### 13.2 Пример конфигурации

```yaml
# autodoc.config.yaml
version: "1.0"

cli:
  provider: gemini
  format: markdown
  verbose: false
  updateExisting: true

docs:
  outputFilename: documentation.md
  includePrivate: false
  language: ru

watch:
  include:
    - "src/**/*.ts"
    - "src/**/*.bsl"
  exclude:
    - "**/node_modules/**"
    - "**/dist/**"
  debounceMs: 1000

cache:
  enabled: true
  ttlSeconds: 86400

extensions:
  - .ts
  - .js
  - .bsl

ignore:
  - "**/node_modules/**"
  - "**/dist/**"
```

### 13.3 Иерархия конфигураций

```
1. CLI аргументы (высший приоритет)
      ↓
2. Environment variables
      ↓
3. Локальный autodoc.config.yaml
      ↓
4. Родительский конфиг (extends)
      ↓
5. DEFAULT_CONFIG (базовые значения)
```

---

## 14. API Reference

### 14.1 MCP Tools

#### generate_documentation

```typescript
{
  name: "generate_documentation",
  description: "Generate documentation for a directory",
  inputSchema: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "Directory path to document"
      },
      updateExisting: {
        type: "boolean",
        description: "Update existing documentation",
        default: true
      }
    },
    required: ["path"]
  }
}
```

#### autoreview

```typescript
{
  name: "autoreview",
  description: "Generate code review",
  inputSchema: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "Directory path to review"
      }
    },
    required: ["path"]
  }
}
```

#### autotestplan

```typescript
{
  name: "autotestplan",
  description: "Generate test plan",
  inputSchema: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "Directory path"
      }
    },
    required: ["path"]
  }
}
```

#### generate_inline_docs

```typescript
{
  name: "generate_inline_docs",
  description: "Generate inline documentation (JSDoc/TSDoc/BSL comments)",
  inputSchema: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "Directory path"
      },
      updateExisting: {
        type: "boolean",
        default: true
      }
    },
    required: ["path"]
  }
}
```

### 14.2 CLI Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `generate <path>` | `g`, `doc` | Генерация документации |
| `review <path>` | `r` | Code review |
| `testplan <path>` | `t`, `test` | План тестирования |
| `inline <path>` | `i` | Inline документация |
| `diff <base> <target>` | `d`, `compare` | Сравнение версий |
| `info` | - | Информация о системе |
| `benchmark <path>` | - | Бенчмарк |
| `browse <path>` | - | Doc browser |

### 14.3 Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | File not found |
| 4 | API error |
| 5 | Breaking changes detected (diff --detect-breaking) |

---

## Приложения

### A. Тестовое покрытие

```
Total Tests: 531+
├── analyzer/           # 50+ tests
├── cli/                # 40+ tests
├── cache/              # 30+ tests
├── cost/               # 25+ tests
├── metadata/           # 224 tests (Form.xml validation)
├── providers/          # 35+ tests
├── tools/              # 60+ tests
├── watch/              # 20+ tests
└── incremental/        # 30+ tests
```

### B. Производительность

| Операция | Время | Примечание |
|----------|-------|------------|
| BSL parsing (1000 строк) | ~50ms | Tree-sitter |
| Cache lookup | ~1ms | SHA256 key |
| Cache save | ~5ms | JSON + file |
| Full doc generation | 10-30s | Зависит от провайдера |
| Incremental update | 2-5s | Только измененные файлы |

### C. Лимиты

| Параметр | Значение |
|----------|----------|
| Max cache size | 100 MB |
| Cache TTL | 24 часа |
| Max concurrent requests | 3 |
| Request timeout | 60 секунд |
| Max retries per provider | 3 |
| Provider cooldown | 60 секунд |

---

**Документация сгенерирована:** 2025-11-26
**Версия проекта:** 2.4.0
**Автор документации:** Claude Code Analysis
