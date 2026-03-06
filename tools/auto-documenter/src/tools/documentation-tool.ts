import * as fs from 'fs';
import * as path from 'path';
import { AnalysisResult } from '../analyzer/index.js';
import { OpenRouterClient } from '../openrouter/client.js';
import { BaseTool, AutoToolResult, BaseToolConfig } from './base-tool.js';
import { getConfig } from '../config.js';
import { documentationPrompts, updateExistingContentPrompt, bslDocumentationPrompts, bslCrossReferencePrompt, bslCallGraphPrompt } from '../prompt-config.js';
import { getBSLContextPrompt, detectBSLModuleType, getModuleTypeDescription } from '../prompts/bsl-context-prompts.js';
import { enrichWithMetadata, generateMetadataContextPrompt, validateFormModules } from '../metadata/metadata-integration.js';
import { structure1CAnalyzer } from '../analyzer/structure-1c-analyzer.js';
import { getBSLCallGraphAnalyzer, ModuleCallGraph } from '../analyzer/bsl-call-graph-analyzer.js';

/**
 * Configuration for the documentation tool
 */
export interface DocumentationToolConfig extends BaseToolConfig {
  systemPrompt: string;
  topLevelPrompt: string;
  withChildrenPrompt: string;
}

/**
 * Tool for generating documentation
 */
export class DocumentationTool extends BaseTool<DocumentationToolConfig> {
  readonly name = 'generate_documentation';
  readonly description = 'Generates documentation for a code repository by recursively analyzing directories and files';
  
  private openRouterClient: OpenRouterClient;
  
  /**
   * Creates a new documentation tool
   * @param apiKey OpenRouter API key (optional)
   * @param model LLM model to use (optional)
   * @param updateExisting Whether to update existing files
   */
  constructor(apiKey?: string, model?: string, updateExisting?: boolean) {
    // Get default config
    const config = getConfig();
    
    // Create tool config
    const toolConfig: DocumentationToolConfig = {
      outputFilename: config.documentation.outputFilename,
      fallbackFilename: config.documentation.fallbackFilename,
      updateExisting: updateExisting !== undefined ? updateExisting : config.documentation.updateExisting,
      systemPrompt: documentationPrompts.systemPrompt,
      topLevelPrompt: documentationPrompts.topLevelPrompt,
      withChildrenPrompt: documentationPrompts.withChildrenPrompt
    };
    
    super(toolConfig);
    
    // Initialize OpenRouter client
    this.openRouterClient = new OpenRouterClient(apiKey, model, true);
  }
  
  /**
   * Generates documentation for a directory
   * @param directoryPath Path to the source directory
   * @param analysisResult Results of file analysis
   * @param isTopLevel Whether this is the top level directory
   * @param childrenContent Documentation from child directories
   * @param outputDir Optional output directory (if different from source)
   * @returns Documentation generation result
   */
  public async generate(
    directoryPath: string,
    analysisResult: AnalysisResult,
    isTopLevel: boolean = false,
    childrenContent?: Array<{ path: string; content: string }>,
    outputDir?: string
  ): Promise<AutoToolResult> {
    // Use outputDir if provided, otherwise write to source directory
    const targetDir = outputDir || directoryPath;
    const docFilePath = path.join(targetDir, this.config.outputFilename);
    const existingDocumentation = this.readExistingFile(docFilePath);
    const isUpdate = existingDocumentation !== null;
    
    // Skip generation if the file exists and updateExisting is false
    if (isUpdate && !this.config.updateExisting) {
      console.error(`Skipping documentation for ${directoryPath} - File exists and updateExisting is false`);
      return {
        outputPath: docFilePath,
        success: true,
        content: existingDocumentation as string,
        isUpdate: false,
        skipped: true
      };
    }
    
    // Convert analyzed files to format expected by OpenRouterClient
    const files = analysisResult.analyzedFiles.map((file) => ({
      path: path.relative(directoryPath, file.path),
      content: file.content
    }));
    
    try {
      // Check if this is a BSL file - use Russian prompts for 1C code
      const isBSLFile = analysisResult.analyzedFiles.some(file => file.path.toLowerCase().endsWith('.bsl'));

      // Determine the appropriate system prompt based on context
      let systemPrompt: string;

      if (isBSLFile) {
        // Use Russian prompts for BSL/1C code
        if (isTopLevel) {
          systemPrompt = bslDocumentationPrompts.topLevelPrompt;
        } else if (childrenContent && childrenContent.length > 0) {
          systemPrompt = bslDocumentationPrompts.withChildrenPrompt;
        } else {
          systemPrompt = bslDocumentationPrompts.systemPrompt;
        }

        // Add cross-reference analysis prompt
        systemPrompt += bslCrossReferencePrompt;

        console.error(`[BSL] Using Russian prompts for ${path.basename(directoryPath)}`);
      } else {
        // Use English prompts for non-BSL code
        if (isTopLevel) {
          systemPrompt = this.config.topLevelPrompt;
        } else if (childrenContent && childrenContent.length > 0) {
          systemPrompt = this.config.withChildrenPrompt;
        } else {
          systemPrompt = this.config.systemPrompt;
        }
      }

      // Add BSL context-aware prompt for module type detection
      if (isBSLFile && analysisResult.analyzedFiles.length > 0) {
        // Get the first BSL file to detect module type
        const bslFile = analysisResult.analyzedFiles.find(file => file.path.toLowerCase().endsWith('.bsl'));
        if (bslFile) {
          const moduleType = detectBSLModuleType(bslFile.path);
          const moduleTypeDesc = getModuleTypeDescription(moduleType);
          const bslContextPrompt = getBSLContextPrompt(bslFile.path);

          // Add BSL context to system prompt
          systemPrompt += `\n\n=== КОНТЕКСТ BSL МОДУЛЯ ===\n`;
          systemPrompt += `Тип модуля: ${moduleTypeDesc}\n`;
          systemPrompt += `Путь: ${path.basename(directoryPath)}\n\n`;
          systemPrompt += bslContextPrompt;

          console.error(`[BSL Context] Detected ${moduleTypeDesc} for ${path.basename(directoryPath)}`);

          // Add 1C Structure Analyzer context
          try {
            if (structure1CAnalyzer.isConfigurationPath(bslFile.path)) {
              const structureInfo = structure1CAnalyzer.analyze(bslFile.path);
              const structureContext = structure1CAnalyzer.getContextInfo(structureInfo);

              systemPrompt += `\n\n=== СТРУКТУРА КОНФИГУРАЦИИ 1С ===\n`;
              systemPrompt += `Тип объекта метаданных: ${structureInfo.metadataTypeDescription}\n`;
              systemPrompt += `Имя объекта: ${structureInfo.objectName}\n`;
              systemPrompt += `Тип модуля: ${structureInfo.moduleTypeDescription}\n`;
              if (structureInfo.formName) {
                systemPrompt += `Форма: ${structureInfo.formName}\n`;
              }
              if (structureInfo.commandName) {
                systemPrompt += `Команда: ${structureInfo.commandName}\n`;
              }
              systemPrompt += `\n${structureContext}`;

              console.error(`[Structure1C] ${structureInfo.metadataTypeDescription}/${structureInfo.objectName} - ${structureInfo.moduleTypeDescription}`);
            }
          } catch (structureErr: any) {
            console.error(`[Structure1C] Failed to analyze structure:`, structureErr.message);
            // Continue without structure analysis - non-blocking error
          }

          // Analyze call graph for BSL module
          try {
            const callGraphAnalyzer = await getBSLCallGraphAnalyzer();
            const callGraph = await callGraphAnalyzer.analyzeCallGraph(bslFile.content, bslFile.path);

            // Add call graph context and formatting instructions to prompt
            const callGraphContext = callGraphAnalyzer.generateContextForLLM(callGraph);
            systemPrompt += `\n\n${callGraphContext}`;
            systemPrompt += `\n\n${bslCallGraphPrompt}`;

            console.error(`[CallGraph] Analyzed: ${callGraph.procedures.size} procedures/functions, ${callGraph.allCalls.length} calls, ${callGraph.usedCommonModules.size} common modules`);
          } catch (callGraphErr: any) {
            console.error(`[CallGraph] Failed to analyze call graph:`, callGraphErr.message);
            // Continue without call graph - non-blocking error
          }
        }
      }

      // Check for 1C metadata and enrich documentation context
      try {
        const metadataResult = await enrichWithMetadata(directoryPath, analysisResult);
        if (metadataResult) {
          // Run form validation if forms exist
          let formValidationResults;
          if (metadataResult.relatedFiles.formModules && metadataResult.relatedFiles.formModules.length > 0) {
            try {
              formValidationResults = await validateFormModules(metadataResult);
              console.error(`[FormValidation] Validated ${formValidationResults.size} forms`);
            } catch (validationErr: any) {
              console.error(`[FormValidation] Failed to validate forms:`, validationErr);
              // Continue without form validation - non-blocking error
            }
          }

          const metadataPrompt = generateMetadataContextPrompt(metadataResult, undefined, formValidationResults);
          systemPrompt += metadataPrompt;
          console.error(`[Metadata] Enriched with ${metadataResult.objectType} metadata for ${metadataResult.metadata.name}`);
        }
      } catch (err: any) {
        console.error(`[Metadata] Failed to enrich with metadata:`, err);
        // Continue without metadata - non-blocking error
      }

      // Add instruction about existing documentation
      if (existingDocumentation) {
        systemPrompt += ` ${updateExistingContentPrompt}`;
      }

      // CRITICAL: Add final Mermaid reminder for BSL files
      if (isBSLFile) {
        systemPrompt += `\n\n## ⚠️ ФИНАЛЬНОЕ НАПОМИНАНИЕ - MERMAID ДИАГРАММА\n\nЭТО ОБЯЗАТЕЛЬНОЕ ТРЕБОВАНИЕ! Документация БЕЗ Mermaid диаграммы считается НЕПОЛНОЙ!\n\nВ секции "Зависимости и интеграции" ОБЯЗАТЕЛЬНО добавьте:\n\n\`\`\`mermaid\ngraph TD\n    subgraph "Модуль"\n        A[Процедура]\n    end\n    subgraph "Зависимости"\n        B[(Справочник)]\n        C[Документ]\n    end\n    A -->|Чтение| B\n    A -->|Запись| C\n\`\`\`\n\nНЕ ИГНОРИРУЙТЕ ЭТО ТРЕБОВАНИЕ!`;
        console.error('[BSL] Added final Mermaid reminder to prompt');
      }

      // Generate documentation using OpenRouter
      const genResult = await this.openRouterClient.generateWithCustomPrompt(
        files,
        systemPrompt,
        existingDocumentation || undefined,
        isTopLevel,
        childrenContent
      );
      
      if (!genResult.successful) {
        return {
          outputPath: docFilePath,
          success: false,
          content: '',
          error: genResult.error || 'Unknown error during documentation generation',
          isUpdate
        };
      }
      
      // Ensure output directory exists (important when outputDir is different from source)
      await fs.promises.mkdir(targetDir, { recursive: true });

      // Write the generated documentation to file
      await fs.promises.writeFile(docFilePath, genResult.content, 'utf8');
      
      return {
        outputPath: docFilePath,
        success: true,
        content: genResult.content,
        isUpdate
      };
    } catch (error: any) {
      return {
        outputPath: docFilePath,
        success: false,
        content: '',
        error: `Error generating documentation: ${error.message}`,
        isUpdate
      };
    }
  }
  
  /**
   * Creates fallback content for directories that exceed limits
   * @param directoryPath Path to the directory
   * @param analysisResult Analysis result with limitation information
   * @returns Content for the fallback file
   */
  public async createFallbackContent(
    directoryPath: string,
    analysisResult: AnalysisResult
  ): Promise<string> {
    const dirName = path.basename(directoryPath);
    
    let content = `# ${dirName} - Documentation Skipped\n\n`;
    
    if (analysisResult.limited && analysisResult.limitReason) {
      content += `## Reason\n\n${analysisResult.limitReason}\n\n`;
    }
    
    if (analysisResult.analyzedFiles.length > 0) {
      content += `## Analyzed Files\n\n`;
      for (const file of analysisResult.analyzedFiles) {
        content += `- \`${path.relative(directoryPath, file.path)}\`\n`;
      }
      content += '\n';
    }
    
    if (analysisResult.excludedFiles.length > 0) {
      content += `## Excluded Files\n\n`;
      for (const file of analysisResult.excludedFiles) {
        content += `- \`${path.relative(directoryPath, file.path)}\`: ${file.reason}\n`;
      }
      content += '\n';
    }
    
    content += `## How to Fix\n\n`;
    content += `You can manually document this directory by replacing this file with a proper documentation.md file.\n`;
    content += `Alternatively, you can increase the file limits in the tool configuration and run again.\n`;
    
    return content;
  }
  
  /**
   * Reads an existing file if it exists
   * @param filePath Path to the file
   * @returns Content of the file or null if it doesn't exist
   */
  private readExistingFile(filePath: string): string | null {
    try {
      if (fs.existsSync(filePath)) {
        return fs.readFileSync(filePath, 'utf8');
      }
      return null;
    } catch (error) {
      console.error(`Error reading existing file at ${filePath}:`, error);
      return null;
    }
  }
}