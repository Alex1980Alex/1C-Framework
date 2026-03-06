import * as path from 'path';
import * as fs from 'fs';
import { BaseTool, BaseToolConfig, AutoToolResult } from './base-tool.js';
import { AnalysisResult } from '../analyzer/index.js';
import { OpenRouterClient } from '../openrouter/client.js';
import { getBSLCallGraphAnalyzer, ModuleCallGraph } from '../analyzer/bsl-call-graph-analyzer.js';

/**
 * Configuration for the dependency graph tool
 */
interface DependencyGraphConfig extends BaseToolConfig {
  outputFilename: string;
  fallbackFilename: string;
  updateExisting: boolean;
}

/**
 * Represents a dependency extracted from BSL code
 */
interface BslDependency {
  type: 'module' | 'catalog' | 'document' | 'register' | 'processing' | 'report' | 'enum' | 'constant' | 'external';
  name: string;
  russianName?: string;
  usageCount: number;
  usageType: 'read' | 'write' | 'call' | 'reference';
  methods?: string[];  // Specific methods called on this dependency
}

/**
 * Represents a procedure/function in BSL code
 */
interface BslProcedure {
  name: string;
  type: 'procedure' | 'function';
  isExport: boolean;
  lineNumber: number;
}

/**
 * Results of BSL static analysis
 */
interface BslAnalysisResult {
  moduleName: string;
  procedures: BslProcedure[];
  dependencies: BslDependency[];
  internalCalls: string[];
}

/**
 * Tool for generating dependency graphs for BSL/1C code
 * Uses hybrid approach: static analysis + LLM for formatting
 */
export class DependencyGraphTool extends BaseTool<DependencyGraphConfig> {
  readonly name = 'generate_dependency_graph';
  readonly description = 'Generates Mermaid dependency graphs for BSL/1C code using hybrid analysis (static extraction + LLM formatting)';

  private openRouterClient: OpenRouterClient;

  constructor(apiKey?: string, model?: string) {
    super({
      outputFilename: 'dependencies.md',
      fallbackFilename: 'dependencies-fallback.md',
      updateExisting: true,
    });

    // Initialize OpenRouter client with rotation enabled
    this.openRouterClient = new OpenRouterClient(apiKey, model, true);
  }

  /**
   * Recursively find all BSL files in a directory
   * @param dirPath Directory to search (source directory)
   * @returns Array of BSL file paths with their content
   */
  private findBslFilesRecursively(dirPath: string): Array<{ path: string; content: string; extension: string }> {
    const bslFiles: Array<{ path: string; content: string; extension: string }> = [];

    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);

        if (entry.isDirectory()) {
          // Recursively search subdirectories
          bslFiles.push(...this.findBslFilesRecursively(fullPath));
        } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.bsl')) {
          // Read BSL file content
          try {
            const content = fs.readFileSync(fullPath, 'utf8');
            bslFiles.push({ path: fullPath, content, extension: '.bsl' });
          } catch (readError) {
            console.error(`[DependencyGraph] Error reading file ${fullPath}:`, readError);
          }
        }
      }
    } catch (error) {
      console.error(`[DependencyGraph] Error scanning directory ${dirPath}:`, error);
    }

    return bslFiles;
  }

  /**
   * Extract dependencies from BSL code using regex patterns
   */
  private extractDependencies(code: string, fileName: string): BslAnalysisResult {
    const result: BslAnalysisResult = {
      moduleName: path.basename(fileName, '.bsl'),
      procedures: [],
      dependencies: [],
      internalCalls: [],
    };

    // Extract procedures and functions
    const lines = code.split('\n');

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const procMatch = line.match(/^\s*(Процедура|Функция|Procedure|Function)\s+([А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z0-9_]*)\s*\(/i);
      if (procMatch) {
        const isExport = line.toLowerCase().includes('экспорт') || line.toLowerCase().includes('export');
        result.procedures.push({
          name: procMatch[2],
          type: procMatch[1].toLowerCase().startsWith('проц') || procMatch[1].toLowerCase() === 'procedure' ? 'procedure' : 'function',
          isExport,
          lineNumber: i + 1,
        });
      }
    }

    // Extract module calls (ОбщийМодуль.Метод)
    // Note: \w doesn't match Cyrillic, so we use explicit character class
    const cyrillicId = '[А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z0-9_]*';
    const moduleCallRegex = new RegExp(`(${cyrillicId})\\s*\\.\\s*(${cyrillicId})\\s*\\(`, 'g');
    const moduleCalls = new Map<string, { count: number; methods: Set<string> }>();
    let match;

    while ((match = moduleCallRegex.exec(code)) !== null) {
      const moduleName = match[1];
      const methodName = match[2];

      // Skip known non-module prefixes
      const skipPrefixes = ['Элементы', 'Объект', 'ЭтотОбъект', 'Форма', 'Items', 'Object', 'ThisObject', 'Form'];
      if (skipPrefixes.some(p => moduleName.toLowerCase() === p.toLowerCase())) continue;

      if (!moduleCalls.has(moduleName)) {
        moduleCalls.set(moduleName, { count: 0, methods: new Set() });
      }
      const entry = moduleCalls.get(moduleName)!;
      entry.count++;
      entry.methods.add(methodName);
    }

    // Convert module calls to dependencies
    for (const [moduleName, data] of moduleCalls) {
      let type: BslDependency['type'] = 'module';
      let usageType: BslDependency['usageType'] = 'call';

      if (moduleName.startsWith('Справочник') || moduleName.startsWith('Catalog')) {
        type = 'catalog';
        usageType = 'reference';
      } else if (moduleName.startsWith('Документ') || moduleName.startsWith('Document')) {
        type = 'document';
        usageType = 'reference';
      } else if (moduleName.startsWith('Регистр') || moduleName.startsWith('Register')) {
        type = 'register';
        usageType = 'read';
      } else if (moduleName.startsWith('Обработк') || moduleName.startsWith('DataProcessor')) {
        type = 'processing';
        usageType = 'call';
      } else if (moduleName.startsWith('Отчет') || moduleName.startsWith('Report')) {
        type = 'report';
        usageType = 'call';
      } else if (moduleName.startsWith('Перечислен') || moduleName.startsWith('Enum')) {
        type = 'enum';
        usageType = 'reference';
      } else if (moduleName.startsWith('Константа') || moduleName.startsWith('Constant')) {
        type = 'constant';
        usageType = 'read';
      }

      result.dependencies.push({
        type,
        name: moduleName,
        usageCount: data.count,
        usageType,
        methods: Array.from(data.methods),
      });
    }

    // Extract catalog/document references (Справочники.Товары, Документы.Заказ)
    const metadataRegex = new RegExp(`(Справочники|Документы|РегистрыСведений|РегистрыНакопления|Обработки|Отчеты|Перечисления|Константы|Catalogs|Documents|InformationRegisters|AccumulationRegisters|DataProcessors|Reports|Enums|Constants)\\s*\\.\\s*(${cyrillicId})`, 'g');
    const metadataRefs = new Map<string, number>();

    while ((match = metadataRegex.exec(code)) !== null) {
      const fullRef = `${match[1]}.${match[2]}`;
      metadataRefs.set(fullRef, (metadataRefs.get(fullRef) || 0) + 1);
    }

    for (const [ref, count] of metadataRefs) {
      const [prefix, name] = ref.split('.');
      let type: BslDependency['type'] = 'external';

      if (prefix.includes('Справочник') || prefix.includes('Catalog')) type = 'catalog';
      else if (prefix.includes('Документ') || prefix.includes('Document')) type = 'document';
      else if (prefix.includes('Регистр') || prefix.includes('Register')) type = 'register';
      else if (prefix.includes('Обработк') || prefix.includes('DataProcessor')) type = 'processing';
      else if (prefix.includes('Отчет') || prefix.includes('Report')) type = 'report';
      else if (prefix.includes('Перечислен') || prefix.includes('Enum')) type = 'enum';
      else if (prefix.includes('Константа') || prefix.includes('Constant')) type = 'constant';

      // Check if not already added
      const existing = result.dependencies.find(d => d.name === name && d.type === type);
      if (!existing) {
        result.dependencies.push({
          type,
          name,
          russianName: name,
          usageCount: count,
          usageType: 'reference',
        });
      }
    }

    // Extract internal procedure calls
    const internalCallRegex = new RegExp(`(${cyrillicId})\\s*\\(`, 'g');
    const internalCalls = new Set<string>();
    const procNames = new Set(result.procedures.map(p => p.name.toLowerCase()));

    while ((match = internalCallRegex.exec(code)) !== null) {
      const callName = match[1];
      const keywords = ['Если', 'Пока', 'Для', 'Возврат', 'Новый', 'If', 'While', 'For', 'Return', 'New'];
      if (!keywords.includes(callName) && procNames.has(callName.toLowerCase())) {
        internalCalls.add(callName);
      }
    }

    result.internalCalls = Array.from(internalCalls);

    return result;
  }

  /**
   * Generate Mermaid diagram using LLM
   */
  private async generateMermaidWithLLM(analysis: BslAnalysisResult): Promise<string> {
    // Prepare structured data for LLM
    const dependencyData = {
      moduleName: analysis.moduleName,
      procedures: analysis.procedures.map(p => ({
        name: p.name,
        type: p.type,
        exported: p.isExport,
      })),
      externalDependencies: analysis.dependencies.map(d => ({
        type: d.type,
        name: d.name,
        usageCount: d.usageCount,
        usageType: d.usageType,
        methods: d.methods || [],  // Specific methods called
      })),
      internalCalls: analysis.internalCalls,
    };

    const systemPrompt = `Ты эксперт по созданию Mermaid диаграмм для визуализации зависимостей в коде 1С:Предприятие.
Твоя задача - создать понятную и информативную диаграмму на основе данных статического анализа.
Отвечай ТОЛЬКО кодом Mermaid без дополнительных пояснений.`;

    const userPrompt = `Создай Mermaid диаграмму зависимостей для модуля 1С на основе следующих данных:

## Данные анализа

\`\`\`json
${JSON.stringify(dependencyData, null, 2)}
\`\`\`

## Требования к диаграмме

1. Используй \`graph TD\` (сверху вниз)
2. Группируй элементы в subgraph по типам:
   - "Модуль" - центральный модуль и его процедуры/функции
   - "Справочники" - type: catalog
   - "Документы" - type: document
   - "Регистры" - type: register
   - "Общие модули" - type: module
   - "Обработки" - type: processing
   - "Перечисления" - type: enum
3. Используй разные формы узлов:
   - \`[Прямоугольник]\` для модулей и процедур
   - \`[(База данных)]\` для справочников/регистров
   - \`{{Ромб}}\` для документов
   - \`([Скруглённый])\` для функций
4. КРИТИЧЕСКИ ВАЖНО - формат ID узлов (ID ОБЯЗАТЕЛЬНО должен содержать префикс типа!):
   - ID узла = "Тип_Имя" (НЕ просто "Имя"!)
   - Модуль: \`Модуль_ФормаПринятыеТС_by["Модуль ФормаПринятыеТС_by"]\` (НЕ \`ФормаПринятыеТС_by["..."]\`)
   - Процедура: \`Процедура_ПриОткрытии["Процедура ПриОткрытии"]\` (НЕ \`ПриОткрытии["..."]\`)
   - Функция: \`Функция_ПолучитьДанные(["Функция ПолучитьДанные"])\`
   - Документ: \`Документ_гкс_Взвешивание{{Документ гкс_Взвешивание}}\`
   - Справочник: \`Справочник_Номенклатура[(Справочник Номенклатура)]\`
   - Перечисление: \`Перечисление_ТипыВзвешивания[[Перечисление ТипыВзвешивания]]\`
   - Общий модуль: \`Модуль_ОбщегоНазначения["Модуль ОбщегоНазначения"]\`
   ЗАПРЕЩЕНО использовать ID без префикса типа! Пример НЕПРАВИЛЬНО: \`ПриОткрытии["Процедура ПриОткрытии"]\`
5. КРИТИЧЕСКИ ВАЖНО - стрелки ОБЯЗАТЕЛЬНО с методами:
   - ВСЕГДА бери методы из поля "methods" в JSON данных
   - Формат стрелки: \`Процедура_Имя -->|Метод1, Метод2| Модуль_Имя\`
   - ПРИМЕР: если в JSON есть {"name": "ОбщегоНазначения", "methods": ["СообщитьПользователю", "ЗначениеРеквизитаОбъекта"]}
     то стрелка: \`Процедура_Печать -->|СообщитьПользователю, ЗначениеРеквизитаОбъекта| Модуль_ОбщегоНазначения\`
   - Если methods пустой, используй usageType: \`-->|вызов|\`, \`-->|ссылка|\`
   - ЗАПРЕЩЕНО делать стрелки без меток! НЕПРАВИЛЬНО: \`A --> B\`. ПРАВИЛЬНО: \`A -->|метод| B\`
6. Используй русские названия
7. Если зависимостей нет - покажи только центральный модуль

## ВАЖНО: Верни ТОЛЬКО код Mermaid

\`\`\`mermaid
graph TD
    ...
\`\`\``;

    try {
      // Create a "file" containing the analysis data for the LLM
      const analysisFile = {
        path: 'analysis.json',
        content: userPrompt
      };

      const response = await this.openRouterClient.generateWithCustomPrompt(
        [analysisFile],
        systemPrompt
      );

      // Check if generation was successful
      if (!response.successful || !response.content) {
        console.error('[DependencyGraph] LLM generation failed:', response.error);
        return this.generateSimpleMermaid(analysis);
      }

      // Extract mermaid code from response content
      const mermaidMatch = response.content.match(/```mermaid\s*([\s\S]*?)```/);
      if (mermaidMatch) {
        return this.fixMermaidNodeIds(mermaidMatch[1].trim());
      }

      // If no code block, try to use the whole response (clean any remaining fences)
      if (response.content.includes('graph ')) {
        // Remove any stray code fences
        let cleaned = response.content.trim();
        cleaned = cleaned.replace(/^```(?:mermaid)?\s*/gm, '');
        cleaned = cleaned.replace(/```\s*$/gm, '');
        return this.fixMermaidNodeIds(cleaned.trim());
      }

      // Fallback to simple diagram
      return this.generateSimpleMermaid(analysis);
    } catch (error) {
      console.error('[DependencyGraph] LLM error, falling back to simple diagram:', error);
      return this.generateSimpleMermaid(analysis);
    }
  }

  /**
   * Find all BSL files in a directory
   */
  private async findBslFilesInDirectory(dirPath: string): Promise<string[]> {
    const bslFiles: string[] = [];

    const scanDir = async (dir: string) => {
      try {
        const entries = await fs.promises.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
          const fullPath = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            await scanDir(fullPath);
          } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.bsl')) {
            bslFiles.push(fullPath);
          }
        }
      } catch (err) {
        // Skip inaccessible directories
      }
    };

    await scanDir(dirPath);
    return bslFiles;
  }

  /**
   * Fix Mermaid node IDs to match their labels
   * Rule: ID = label with spaces/special chars replaced by underscores
   * Converts: `A(["Функция ДобавитьКомандыОтчетов"])` -> `Функция_ДобавитьКомандыОтчетов(["Функция ДобавитьКомандыОтчетов"])`
   */
  private fixMermaidNodeIds(mermaidCode: string): string {
    // Pattern to match node definitions with various shapes:
    // ID["Label"], ID(["Label"]), ID{{Label}}, ID[(Label)], ID[[Label]], ID([Label])
    const nodePatterns = [
      /^(\s*)([a-zA-Zа-яА-ЯёЁ0-9_]+)\["([^"]+)"\]/gm,           // ID["Label"]
      /^(\s*)([a-zA-Zа-яА-ЯёЁ0-9_]+)\(\["([^"]+)"\]\)/gm,       // ID(["Label"])
      /^(\s*)([a-zA-Zа-яА-ЯёЁ0-9_]+)\{\{([^}]+)\}\}/gm,         // ID{{Label}}
      /^(\s*)([a-zA-Zа-яА-ЯёЁ0-9_]+)\[\(([^)]+)\)\]/gm,         // ID[(Label)]
      /^(\s*)([a-zA-Zа-яА-ЯёЁ0-9_]+)\[\[([^\]]+)\]\]/gm,        // ID[[Label]]
      /^(\s*)([a-zA-Zа-яА-ЯёЁ0-9_]+)\(\[([^\]]+)\]\)/gm,        // ID([Label]) - alternative
      /^(\s*)([a-zA-Zа-яА-ЯёЁ0-9_]+)\(\(([^)]+)\)\)/gm,         // ID((Label))
    ];

    const idMapping = new Map<string, string>(); // oldId -> newId

    // Helper to create ID from label
    const makeId = (label: string) => label.replace(/[^a-zA-Zа-яА-ЯёЁ0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');

    // Find all nodes and create ID mapping
    for (const pattern of nodePatterns) {
      pattern.lastIndex = 0;
      let match;

      while ((match = pattern.exec(mermaidCode)) !== null) {
        const oldId = match[2];
        const label = match[3].trim();

        // Skip subgraph definitions and keywords
        if (['subgraph', 'end', 'graph', 'TD', 'LR', 'TB', 'RL'].includes(oldId)) {
          continue;
        }

        // Generate correct ID from label
        const correctId = makeId(label);

        // If ID doesn't match, add to mapping
        if (oldId !== correctId && correctId.length > 0) {
          // Only add if not already mapped (avoid conflicts)
          if (!idMapping.has(oldId)) {
            idMapping.set(oldId, correctId);
          }
        }
      }
    }

    // If no fixes needed, return original
    if (idMapping.size === 0) {
      return mermaidCode;
    }

    // Sort mappings by oldId length (longest first) to avoid partial replacements
    const sortedMappings = Array.from(idMapping.entries()).sort((a, b) => b[0].length - a[0].length);

    // Replace all occurrences of old IDs with new IDs
    let fixedCode = mermaidCode;
    for (const [oldId, newId] of sortedMappings) {
      // Replace ID in node definitions and in arrow references
      // Use word boundary to avoid partial replacements
      const idRegex = new RegExp(`\\b${oldId}\\b`, 'g');
      fixedCode = fixedCode.replace(idRegex, newId);
    }

    // Fix malformed arrow labels: A --> B["call |Method1, Method2|"] -> A -->|Method1, Method2| B
    // Pattern: --> NodeId["type |methods|"] should be -->|methods| NodeId
    fixedCode = fixedCode.replace(
      /-->\s*([a-zA-Zа-яА-ЯёЁ0-9_]+)\["(?:call|reference|read|write)\s*\|([^|]+)\|"\]/g,
      '-->|$2| $1'
    );

    // Also fix: --> NodeId["type"] to -->|type| NodeId (for simple types without methods)
    fixedCode = fixedCode.replace(
      /-->\s*([a-zA-Zа-яА-ЯёЁ0-9_]+)\["(call|reference|read|write)"\]/g,
      '-->|$2| $1'
    );

    return fixedCode;
  }

  /**
   * Generate simple Mermaid diagram without LLM (fallback)
   */
  private generateSimpleMermaid(analysis: BslAnalysisResult): string {
    const lines: string[] = ['graph TD'];

    // Helper to create full ID from label (replace spaces with underscores)
    const makeId = (label: string) => label.replace(/[^a-zA-Zа-яА-ЯёЁ0-9]/g, '_').replace(/_+/g, '_');

    // Add module subgraph with procedures/functions
    const moduleLabel = `Модуль ${analysis.moduleName}`;
    const moduleId = makeId(moduleLabel);
    lines.push(`    subgraph module["Модуль"]`);
    lines.push(`        ${moduleId}["${moduleLabel}"]`);

    // Add procedures/functions with explicit labels (ID = label with underscores)
    if (analysis.procedures && analysis.procedures.length > 0) {
      for (const proc of analysis.procedures) {
        const typeLabel = proc.type === 'function' ? 'Функция' : 'Процедура';
        const exportLabel = proc.isExport ? ' Экспорт' : '';
        const label = `${typeLabel} ${proc.name}${exportLabel}`;
        const procId = makeId(label);

        // Use different shapes: rounded for functions, rectangle for procedures
        const shape = proc.type === 'function'
          ? `(["${label}"])`
          : `["${label}"]`;

        lines.push(`        ${procId}${shape}`);
      }
    }
    lines.push('    end');

    // Group dependencies by type
    const byType = new Map<string, BslDependency[]>();
    for (const dep of analysis.dependencies) {
      if (!byType.has(dep.type)) byType.set(dep.type, []);
      byType.get(dep.type)!.push(dep);
    }

    // Type labels in Russian
    const typeLabels: Record<string, string> = {
      'module': 'Общие модули',
      'catalog': 'Справочники',
      'document': 'Документы',
      'register': 'Регистры',
      'processing': 'Обработки',
      'report': 'Отчеты',
      'enum': 'Перечисления',
      'constant': 'Константы',
      'external': 'Внешние',
    };

    // Type prefixes for labels
    const typePrefixes: Record<string, string> = {
      'module': 'Модуль',
      'catalog': 'Справочник',
      'document': 'Документ',
      'register': 'Регистр',
      'processing': 'Обработка',
      'report': 'Отчет',
      'enum': 'Перечисление',
      'constant': 'Константа',
      'external': '',
    };

    // Add subgraphs for each dependency type (ID = full label with underscores)
    for (const [type, deps] of byType) {
      if (deps.length === 0) continue;

      const label = typeLabels[type] || type;
      lines.push(`    subgraph ${type}["${label}"]`);

      for (const dep of deps) {
        const prefix = typePrefixes[type] || '';
        const depLabel = prefix ? `${prefix} ${dep.name}` : dep.name;
        const depId = makeId(depLabel);

        // Choose shape based on type
        let shape = `["${depLabel}"]`;
        if (type === 'catalog' || type === 'register') shape = `[(${depLabel})]`;
        else if (type === 'document') shape = `{{${depLabel}}}`;
        else if (type === 'enum') shape = `(["${depLabel}"])`;

        lines.push(`        ${depId}${shape}`);
      }

      lines.push('    end');
    }

    // Add connections from module to dependencies (showing methods if available)
    for (const [type, deps] of byType) {
      for (const dep of deps) {
        const prefix = typePrefixes[type] || '';
        const depLabel = prefix ? `${prefix} ${dep.name}` : dep.name;
        const depId = makeId(depLabel);

        // Show methods if available, otherwise show usage type
        let edgeLabel: string;
        if (dep.methods && dep.methods.length > 0) {
          // Limit to first 3 methods to keep diagram readable
          const displayMethods = dep.methods.slice(0, 3);
          edgeLabel = displayMethods.join(', ');
          if (dep.methods.length > 3) {
            edgeLabel += '...';
          }
        } else {
          edgeLabel = dep.usageType === 'read' ? 'чтение' :
                      dep.usageType === 'write' ? 'запись' :
                      dep.usageType === 'call' ? 'вызов' : 'ссылка';
        }
        lines.push(`    ${moduleId} -->|${edgeLabel}| ${depId}`);
      }
    }

    return lines.join('\n');
  }

  /**
   * Generate dependency graph for a directory
   */
  async generate(
    directoryPath: string,
    analysisResult: AnalysisResult,
    isTopLevel: boolean,
    childrenContent?: Array<{ path: string; content: string }>,
    outputDir?: string
  ): Promise<AutoToolResult> {
    const effectiveOutputDir = outputDir || directoryPath;
    const outputPath = path.join(effectiveOutputDir, this.config.outputFilename);

    // Check if file exists and updateExisting is false
    if (!this.config.updateExisting && fs.existsSync(outputPath)) {
      return {
        outputPath,
        success: true,
        content: '',
        isUpdate: false,
        skipped: true,
      };
    }

    try {
      // Collect all BSL files from analyzedFiles
      let bslFiles = analysisResult.analyzedFiles.filter(f =>
        f.path.toLowerCase().endsWith('.bsl')
      );

      // If no BSL files in analysisResult, search recursively in source directory
      if (bslFiles.length === 0) {
        console.error(`[DependencyGraph] No BSL files in analysisResult, searching recursively in ${directoryPath}`);
        bslFiles = this.findBslFilesRecursively(directoryPath);
        console.error(`[DependencyGraph] Found ${bslFiles.length} BSL files recursively`);
      }

      if (bslFiles.length === 0) {
        // No BSL files found even with recursive search, create minimal output
        const content = `# Граф зависимостей\n\nBSL файлы не найдены в директории.\n`;
        await fs.promises.mkdir(effectiveOutputDir, { recursive: true });
        await fs.promises.writeFile(outputPath, content, 'utf8');

        return {
          outputPath,
          success: true,
          content,
          isUpdate: fs.existsSync(outputPath),
        };
      }

      // Analyze all BSL files
      const allAnalysis: BslAnalysisResult[] = [];

      for (const file of bslFiles) {
        const code = file.content || '';
        if (code.trim()) {
          const analysis = this.extractDependencies(code, file.path);
          allAnalysis.push(analysis);
        }
      }

      // Merge analysis results
      const mergedAnalysis: BslAnalysisResult = {
        moduleName: path.basename(directoryPath),
        procedures: [],
        dependencies: [],
        internalCalls: [],
      };

      const depMap = new Map<string, BslDependency>();

      for (const analysis of allAnalysis) {
        mergedAnalysis.procedures.push(...analysis.procedures);
        mergedAnalysis.internalCalls.push(...analysis.internalCalls);

        for (const dep of analysis.dependencies) {
          const key = `${dep.type}:${dep.name}`;
          if (depMap.has(key)) {
            const existing = depMap.get(key)!;
            existing.usageCount += dep.usageCount;
            // Merge methods arrays, keeping unique values
            if (dep.methods && dep.methods.length > 0) {
              const existingMethods = new Set(existing.methods || []);
              for (const method of dep.methods) {
                existingMethods.add(method);
              }
              existing.methods = Array.from(existingMethods);
            }
          } else {
            depMap.set(key, { ...dep, methods: dep.methods ? [...dep.methods] : [] });
          }
        }
      }

      mergedAnalysis.dependencies = Array.from(depMap.values());
      mergedAnalysis.internalCalls = [...new Set(mergedAnalysis.internalCalls)];

      // Generate Mermaid diagram
      let mermaidCode: string;

      if (mergedAnalysis.dependencies.length > 0 || mergedAnalysis.procedures.length > 0) {
        console.error(`[DependencyGraph] Generating diagram for ${directoryPath} with ${mergedAnalysis.dependencies.length} dependencies`);
        mermaidCode = await this.generateMermaidWithLLM(mergedAnalysis);
      } else {
        mermaidCode = `graph TD\n    A["${mergedAnalysis.moduleName}"]\n    A -->|нет зависимостей| A`;
      }

      // Generate procedure call graph (analyze ALL BSL files and merge)
      let callGraphSection = '';
      try {
        const callGraphAnalyzer = await getBSLCallGraphAnalyzer();
        const bslFilePaths = await this.findBslFilesInDirectory(directoryPath);
        console.error(`[DependencyGraph] Found ${bslFilePaths.length} BSL files for call graph in ${directoryPath}`);

        if (bslFilePaths.length > 0) {
          // Analyze ALL BSL files and merge call graphs
          const mergedCallGraph: ModuleCallGraph = {
            filePath: directoryPath,
            procedures: new Map(),
            allCalls: [],
            internalCalls: [],
            externalCalls: [],
            configObjectCalls: [],
            entryPoints: [],
            usedCommonModules: new Set(),
            usedConfigObjects: new Map()
          };

          // Collect all procedure names first (needed for internal call detection)
          const allProcedureNames = new Set<string>();

          for (const bslFile of bslFilePaths) {
            try {
              const bslContent = await fs.promises.readFile(bslFile, 'utf8');
              const callGraph = await callGraphAnalyzer.analyzeCallGraph(bslContent, bslFile);

              // Collect procedure names
              for (const [name, _] of callGraph.procedures) {
                allProcedureNames.add(name.toLowerCase());
              }
            } catch (fileErr) {
              console.error(`[DependencyGraph] Error reading ${bslFile}:`, fileErr);
            }
          }

          // Now analyze and merge with knowledge of all procedure names
          for (const bslFile of bslFilePaths) {
            try {
              const bslContent = await fs.promises.readFile(bslFile, 'utf8');
              const callGraph = await callGraphAnalyzer.analyzeCallGraph(bslContent, bslFile);
              console.error(`[DependencyGraph] Call graph for ${path.basename(bslFile)} has ${callGraph.procedures.size} procedures`);

              // Merge procedures
              for (const [name, procInfo] of callGraph.procedures) {
                if (!mergedCallGraph.procedures.has(name)) {
                  mergedCallGraph.procedures.set(name, procInfo);
                }
              }

              // Merge entry points
              for (const ep of callGraph.entryPoints) {
                if (!mergedCallGraph.entryPoints.includes(ep)) {
                  mergedCallGraph.entryPoints.push(ep);
                }
              }

              // Merge calls
              mergedCallGraph.allCalls.push(...callGraph.allCalls);
              mergedCallGraph.internalCalls.push(...callGraph.internalCalls);
              mergedCallGraph.externalCalls.push(...callGraph.externalCalls);
              mergedCallGraph.configObjectCalls.push(...callGraph.configObjectCalls);

              // Merge used common modules
              for (const mod of callGraph.usedCommonModules) {
                mergedCallGraph.usedCommonModules.add(mod);
              }

              // Merge used config objects
              for (const [category, objects] of callGraph.usedConfigObjects) {
                if (!mergedCallGraph.usedConfigObjects.has(category)) {
                  mergedCallGraph.usedConfigObjects.set(category, new Set());
                }
                for (const obj of objects) {
                  mergedCallGraph.usedConfigObjects.get(category)!.add(obj);
                }
              }
            } catch (fileErr) {
              console.error(`[DependencyGraph] Error analyzing ${bslFile}:`, fileErr);
            }
          }

          console.error(`[DependencyGraph] Merged call graph has ${mergedCallGraph.procedures.size} procedures, ${mergedCallGraph.internalCalls.length} internal calls`);

          if (mergedCallGraph.procedures.size > 0) {
            const callGraphMermaid = callGraphAnalyzer.generateCallGraphMermaid(mergedCallGraph, mergedAnalysis.moduleName);
            const totalCalls = Array.from(mergedCallGraph.procedures.values())
              .reduce((sum, p) => sum + p.internalCalls.length, 0);

            callGraphSection = `

## Граф вызовов процедур

Показывает какие процедуры/функции вызывают друг друга внутри модуля.

\`\`\`mermaid
${callGraphMermaid}
\`\`\`

### Легенда
- \`[Прямоугольник]\` — процедура
- \`([Скруглённый])\` — функция
- **Экспортные** — точки входа (вызываются извне)
- **Внутренние** — вспомогательные (вызываются только внутри модуля)
- **Стрелки** — направление вызова (A → B означает "A вызывает B")

### Статистика вызовов
- Всего внутренних вызовов: ${totalCalls}
- Точек входа: ${mergedCallGraph.entryPoints.length}
- Процедур найдено: ${mergedCallGraph.procedures.size}
- Процедуры: ${Array.from(mergedCallGraph.procedures.keys()).slice(0, 10).join(', ')}${mergedCallGraph.procedures.size > 10 ? '...' : ''}
`;
          }
        }
      } catch (callGraphErr: any) {
        console.error(`[DependencyGraph] CallGraph analysis failed:`, callGraphErr.message);
      }

      // Create markdown content
      const content = `# Граф зависимостей: ${mergedAnalysis.moduleName}

## Диаграмма

\`\`\`mermaid
${mermaidCode}
\`\`\`

## Статистика

- **Процедур/функций:** ${mergedAnalysis.procedures.length}
- **Экспортируемых:** ${mergedAnalysis.procedures.filter(p => p.isExport).length}
- **Внешних зависимостей:** ${mergedAnalysis.dependencies.length}
- **Внутренних вызовов:** ${mergedAnalysis.internalCalls.length}

## Детали зависимостей

| Тип | Имя | Использований | Тип использования | Методы |
|-----|-----|---------------|-------------------|--------|
${mergedAnalysis.dependencies.map(d =>
  `| ${d.type} | ${d.name} | ${d.usageCount} | ${d.usageType} | ${d.methods && d.methods.length > 0 ? d.methods.slice(0, 5).join(', ') + (d.methods.length > 5 ? '...' : '') : '-'} |`
).join('\n')}
${callGraphSection}
---
*Сгенерировано автоматически: ${new Date().toISOString()}*
`;

      // Write file
      await fs.promises.mkdir(effectiveOutputDir, { recursive: true });
      await fs.promises.writeFile(outputPath, content, 'utf8');

      return {
        outputPath,
        success: true,
        content,
        isUpdate: fs.existsSync(outputPath),
      };
    } catch (error: any) {
      console.error(`[DependencyGraph] Error:`, error);
      return {
        outputPath,
        success: false,
        content: '',
        error: error.message,
        isUpdate: false,
      };
    }
  }

  /**
   * Create fallback content for directories that exceed limits
   */
  async createFallbackContent(
    directoryPath: string,
    analysisResult: AnalysisResult
  ): Promise<string> {
    return `# Граф зависимостей: ${path.basename(directoryPath)}

> ⚠️ Директория содержит слишком много файлов для полного анализа.

## Файлы в директории

${analysisResult.analyzedFiles.map(f => `- ${path.basename(f.path)}`).join('\n')}

---
*Требуется ручной анализ*
`;
  }

  /**
   * Override input schema for this tool
   */
  getInputSchema(): any {
    return {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the directory with BSL files to analyze',
        },
        outputDir: {
          type: 'string',
          description: 'Output directory for generated dependency graphs (optional)',
        },
        updateExisting: {
          type: 'boolean',
          description: 'Whether to update existing dependency files (default: true)',
        },
      },
      required: ['path'],
    };
  }
}
