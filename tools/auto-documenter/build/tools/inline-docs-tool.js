import * as fs from 'fs';
import * as path from 'path';
import { BaseTool } from './base-tool.js';
import { OpenRouterClient } from '../openrouter/client.js';
import { TSCompilerAnalyzer } from '../analyzer/ts-compiler-analyzer.js';
import { structure1CAnalyzer } from '../analyzer/structure-1c-analyzer.js';
import { inlineDocsPrompts, getInlineDocsPrompt, formatCodeContext, getBSLContextPrompt } from '../prompts/inline-docs-prompts.js';
/**
 * Tool for generating inline documentation (JSDoc/TSDoc/BSL comments)
 */
export class InlineDocsTool extends BaseTool {
    constructor(apiKey, model, updateExisting, dryRun = false) {
        const toolConfig = {
            outputFilename: 'inline-docs-result.json',
            fallbackFilename: 'inline-docs-result.json',
            updateExisting: updateExisting !== undefined ? updateExisting : true,
            systemPrompt: inlineDocsPrompts.jsdoc,
            dryRun,
        };
        super(toolConfig);
        this.name = 'generate_inline_docs';
        this.description = 'Generates inline documentation comments (JSDoc/TSDoc/BSL) for functions, classes, and interfaces';
        this.openRouterClient = new OpenRouterClient(apiKey, model, true);
        this.dryRun = dryRun;
        this.tsAnalyzer = new TSCompilerAnalyzer();
    }
    /**
     * Generate inline documentation for files
     * @param directoryPath Directory to process (source)
     * @param analysisResult Analysis result from file analyzer
     * @param isTopLevel Whether this is the top-level directory
     * @param childrenContent Content from child directories (unused for inline docs)
     * @param outputDir Optional output directory (if different from source)
     * @returns Result of inline documentation generation
     */
    async generate(directoryPath, analysisResult, isTopLevel = false, childrenContent, outputDir) {
        // Use outputDir if provided, otherwise write to source directory
        const targetDir = outputDir || directoryPath;
        const results = [];
        let totalSymbolsDocumented = 0;
        let totalFilesProcessed = 0;
        let totalErrors = 0;
        console.error(`\n📝 Generating inline documentation for ${directoryPath}...`);
        // Process each file in the analysis result
        for (const file of analysisResult.analyzedFiles) {
            const fileExt = path.extname(file.path);
            // Only process supported file types
            if (!this.isSupportedFileType(fileExt)) {
                continue;
            }
            try {
                console.error(`  Processing ${file.path}...`);
                const result = await this.generateForFile(file.path, file.content, fileExt, directoryPath, outputDir);
                results.push(result);
                totalFilesProcessed++;
                if (result.success) {
                    totalSymbolsDocumented += result.symbolsDocumented;
                    console.error(`    ✅ Documented ${result.symbolsDocumented} symbols`);
                }
                else {
                    totalErrors++;
                    console.error(`    ❌ Error: ${result.error}`);
                }
            }
            catch (error) {
                totalErrors++;
                results.push({
                    filePath: file.path,
                    success: false,
                    symbolsDocumented: 0,
                    error: error.message,
                });
                console.error(`    ❌ Error: ${error.message}`);
            }
        }
        // Create summary
        const summary = this.createSummary(results, totalFilesProcessed, totalSymbolsDocumented, totalErrors);
        // Ensure output directory exists (important when outputDir is different from source)
        await fs.promises.mkdir(targetDir, { recursive: true });
        // Write results to JSON file
        const resultPath = path.join(targetDir, this.config.outputFilename);
        await fs.promises.writeFile(resultPath, JSON.stringify({ summary, results }, null, 2), 'utf8');
        return {
            outputPath: resultPath,
            success: totalErrors === 0,
            content: summary,
            error: totalErrors > 0 ? `${totalErrors} errors occurred during generation` : undefined,
            isUpdate: false,
        };
    }
    /**
     * Create fallback content for inline documentation
     * Not applicable for inline docs since we modify files directly
     */
    async createFallbackContent(directoryPath, analysisResult) {
        return `Inline documentation generation fallback for ${directoryPath}`;
    }
    /**
     * Generate inline documentation for a single file
     * @param filePath Path to the source file
     * @param content File content
     * @param fileExt File extension
     * @param sourceDir Source directory (to calculate relative path)
     * @param outputDir Optional output directory (if different from source)
     * @returns Result of documentation generation
     */
    async generateForFile(filePath, content, fileExt, sourceDir, outputDir) {
        // Get 1C structure info for BSL files
        let structureInfo = null;
        if (fileExt === '.bsl' && structure1CAnalyzer.isConfigurationPath(filePath)) {
            structureInfo = structure1CAnalyzer.analyze(filePath);
        }
        // Extract symbols from file using TypeScript Compiler API for TS/JS
        const symbols = this.extractSymbols(content, fileExt, filePath);
        if (symbols.length === 0) {
            return {
                filePath,
                success: true,
                symbolsDocumented: 0,
            };
        }
        const changes = [];
        // Generate documentation for each symbol
        for (const symbol of symbols) {
            try {
                let prompt;
                // Use context-aware prompt for BSL files
                if (fileExt === '.bsl') {
                    const bslSymbol = symbol;
                    const symbolInfo = {
                        name: bslSymbol.name,
                        isExport: bslSymbol.isExport || false,
                        isFunction: bslSymbol.isFunction || false,
                        parameters: bslSymbol.parameters || [],
                        directive: bslSymbol.directive,
                    };
                    prompt = getBSLContextPrompt(structureInfo?.moduleType, structureInfo?.metadataType, symbolInfo);
                    // Add structure context to prompt
                    if (structureInfo) {
                        const structureContext = structure1CAnalyzer.getContextInfo(structureInfo);
                        prompt = `${prompt}\n\n${structureContext}`;
                    }
                }
                else {
                    prompt = getInlineDocsPrompt(fileExt, symbol.type);
                }
                const codeContext = formatCodeContext(symbol.code, filePath, symbol.name);
                // Check if symbol already has documentation
                const hasExistingDocs = this.hasExistingDocumentation(symbol.code, fileExt);
                if (hasExistingDocs && !this.config.updateExisting) {
                    console.error(`      ⏭️  Skipping ${symbol.name} (already documented)`);
                    continue;
                }
                // Generate documentation using LLM
                const genResult = await this.openRouterClient.generateWithCustomPrompt([{ path: filePath, content: symbol.code }], prompt, hasExistingDocs ? symbol.code : undefined, false, undefined);
                if (!genResult.successful) {
                    throw new Error(genResult.error || 'Failed to generate documentation');
                }
                // Clean documentation (strip markdown for BSL files)
                const cleanedDoc = this.cleanDocumentation(genResult.content, fileExt);
                // Log export status for BSL
                const exportMark = symbol.isExport ? ' [EXPORT]' : '';
                changes.push({
                    symbolName: symbol.name,
                    symbolType: symbol.type,
                    documentation: cleanedDoc,
                    lineNumber: symbol.lineNumber,
                });
                console.error(`      ✅ ${symbol.name}${exportMark} (${symbol.type})`);
            }
            catch (error) {
                console.error(`      ❌ ${symbol.name}: ${error.message}`);
            }
        }
        // Apply changes to file if not in dry-run mode
        if (!this.dryRun && changes.length > 0) {
            const newContent = this.applyDocumentation(content, changes, fileExt);
            // Calculate target path: use outputDir if provided, otherwise modify source
            let targetPath = filePath;
            if (outputDir && sourceDir) {
                // Calculate relative path from source directory
                const relativePath = path.relative(sourceDir, filePath);
                targetPath = path.join(outputDir, relativePath);
                // Ensure target directory exists
                await fs.promises.mkdir(path.dirname(targetPath), { recursive: true });
            }
            await fs.promises.writeFile(targetPath, newContent, 'utf8');
            console.error(`    📄 Written to: ${targetPath}`);
        }
        return {
            filePath,
            success: true,
            symbolsDocumented: changes.length,
            changes,
        };
    }
    /**
     * Extract symbols (functions, classes, interfaces) from code
     * @param content File content
     * @param fileExt File extension
     * @returns Array of symbols
     */
    extractSymbols(content, fileExt, filePath) {
        const symbols = [];
        if (fileExt === '.bsl') {
            return this.extractBSLSymbols(content);
        }
        else if (['.ts', '.tsx', '.js', '.jsx'].includes(fileExt)) {
            return this.extractTSSymbols(content, filePath);
        }
        return symbols;
    }
    /**
     * Extract symbols from TypeScript/JavaScript code using TypeScript Compiler API
     * Provides accurate AST-based parsing instead of regex
     * @param content File content
     * @param filePath File path for language detection
     * @returns Array of extracted symbols
     */
    extractTSSymbols(content, filePath) {
        // Use TypeScript Compiler API for accurate parsing
        const tsSymbols = this.tsAnalyzer.getExportedSymbols(content, filePath || 'file.ts');
        // Convert TSSymbol to the expected format
        return tsSymbols
            .filter(s => ['function', 'class', 'interface', 'type'].includes(s.type))
            .map(s => ({
            name: s.name,
            type: s.type,
            code: s.code,
            lineNumber: s.lineNumber,
        }));
    }
    /**
     * Extract symbols from BSL code with enhanced metadata
     * Extracts export status, directives, and parameters
     */
    extractBSLSymbols(content) {
        const symbols = [];
        const lines = content.split('\n');
        // Enhanced regex to capture the full procedure/function declaration
        // Matches: [Directive] Procedure/Function Name(Params) [Export]
        const procedureRegex = /(?:Процедура|Procedure)\s+([а-яА-ЯёЁa-zA-Z_][а-яА-ЯёЁa-zA-Z0-9_]*)\s*\(([^)]*)\)\s*(Экспорт|Export)?/gi;
        const functionRegex = /(?:Функция|Function)\s+([а-яА-ЯёЁa-zA-Z_][а-яА-ЯёЁa-zA-Z0-9_]*)\s*\(([^)]*)\)\s*(Экспорт|Export)?/gi;
        let match;
        // Extract procedures
        while ((match = procedureRegex.exec(content)) !== null) {
            const lineNumber = content.substring(0, match.index).split('\n').length;
            const code = this.extractBSLProcedure(content, match.index);
            const directive = this.extractBSLDirective(content, match.index, lineNumber);
            const parameters = this.parseBSLParameters(match[2]);
            const isExport = !!match[3];
            symbols.push({
                name: match[1],
                type: 'function',
                code,
                lineNumber,
                isExport,
                isFunction: false,
                parameters,
                directive,
            });
        }
        // Extract functions
        while ((match = functionRegex.exec(content)) !== null) {
            const lineNumber = content.substring(0, match.index).split('\n').length;
            const code = this.extractBSLFunction(content, match.index);
            const directive = this.extractBSLDirective(content, match.index, lineNumber);
            const parameters = this.parseBSLParameters(match[2]);
            const isExport = !!match[3];
            symbols.push({
                name: match[1],
                type: 'function',
                code,
                lineNumber,
                isExport,
                isFunction: true,
                parameters,
                directive,
            });
        }
        return symbols;
    }
    /**
     * Extract compilation directive from lines before procedure/function
     * @param content Full file content
     * @param matchIndex Index of procedure/function match
     * @param lineNumber Line number of procedure/function
     * @returns Directive string if found
     */
    extractBSLDirective(content, matchIndex, lineNumber) {
        const lines = content.split('\n');
        // Look at the line before the procedure/function for directive
        if (lineNumber > 1) {
            const prevLine = lines[lineNumber - 2].trim();
            // Match directives: Order matters - longer patterns first to avoid partial matches
            // &НаКлиентеНаСервереБезКонтекста before &НаКлиенте, etc.
            const directiveMatch = prevLine.match(/^&(НаКлиентеНаСервереБезКонтекста|НаКлиентеНаСервере|НаСервереБезКонтекста|НаСервере|НаКлиенте|AtClientAtServerNoContext|AtClientAtServer|AtServerNoContext|AtServer|AtClient)/i);
            if (directiveMatch) {
                return `&${directiveMatch[1]}`;
            }
        }
        return undefined;
    }
    /**
     * Parse BSL parameters string into structured format
     * @param paramsString Parameters string from procedure/function declaration
     * @returns Array of parameter info
     */
    parseBSLParameters(paramsString) {
        const params = [];
        if (!paramsString || paramsString.trim() === '') {
            return params;
        }
        // Split by comma, handling nested structures
        const paramParts = paramsString.split(',');
        for (const part of paramParts) {
            const trimmed = part.trim();
            if (!trimmed)
                continue;
            // Match parameter: [Знач] ИмяПараметра [= ЗначениеПоУмолчанию]
            const paramMatch = trimmed.match(/^(?:Знач\s+|Val\s+)?([а-яА-ЯёЁa-zA-Z_][а-яА-ЯёЁa-zA-Z0-9_]*)(?:\s*=\s*(.+))?$/i);
            if (paramMatch) {
                params.push({
                    name: paramMatch[1],
                    hasDefault: !!paramMatch[2],
                });
            }
        }
        return params;
    }
    // Note: TypeScript body extraction methods removed - now using TSCompilerAnalyzer
    /**
     * Extract BSL procedure body
     */
    extractBSLProcedure(content, startIndex) {
        const endRegex = /(?:КонецПроцедуры|EndProcedure)/gi;
        const match = endRegex.exec(content.substring(startIndex));
        if (!match) {
            return content.substring(startIndex);
        }
        return content.substring(startIndex, startIndex + match.index + match[0].length);
    }
    /**
     * Extract BSL function body
     */
    extractBSLFunction(content, startIndex) {
        const endRegex = /(?:КонецФункции|EndFunction)/gi;
        const match = endRegex.exec(content.substring(startIndex));
        if (!match) {
            return content.substring(startIndex);
        }
        return content.substring(startIndex, startIndex + match.index + match[0].length);
    }
    /**
     * Check if code already has documentation
     */
    hasExistingDocumentation(code, fileExt) {
        if (fileExt === '.bsl') {
            // Check for BSL comments (// or //)
            const lines = code.split('\n');
            for (let i = 0; i < Math.min(5, lines.length); i++) {
                if (lines[i].trim().startsWith('//')) {
                    return true;
                }
            }
            return false;
        }
        else {
            // Check for JSDoc comments (/** */)
            return /\/\*\*[\s\S]*?\*\//.test(code);
        }
    }
    /**
     * Apply documentation to file content
     */
    applyDocumentation(content, changes, fileExt) {
        const lines = content.split('\n');
        // Sort changes by line number in reverse order (to maintain line numbers)
        const sortedChanges = [...changes].sort((a, b) => b.lineNumber - a.lineNumber);
        for (const change of sortedChanges) {
            const docLines = change.documentation.split('\n');
            // Insert documentation before the symbol
            lines.splice(change.lineNumber - 1, 0, ...docLines);
        }
        return lines.join('\n');
    }
    /**
     * Check if file type is supported
     */
    isSupportedFileType(fileExt) {
        return ['.ts', '.tsx', '.js', '.jsx', '.bsl'].includes(fileExt);
    }
    /**
     * Strip markdown formatting from BSL documentation
     * LLMs sometimes return markdown despite instructions, this cleans it up
     * @param documentation Raw documentation from LLM
     * @param fileExt File extension
     * @returns Cleaned documentation with proper comment format
     */
    cleanDocumentation(documentation, fileExt) {
        if (fileExt !== '.bsl') {
            return documentation; // Only clean BSL documentation
        }
        let cleaned = documentation;
        // Remove markdown code blocks ```bsl ... ```
        cleaned = cleaned.replace(/```(?:bsl|1c)?\s*\n?/gi, '');
        cleaned = cleaned.replace(/```\s*$/gm, '');
        // Remove markdown headers # ## ###
        cleaned = cleaned.replace(/^#+\s*/gm, '// ');
        // Remove markdown bold **text** -> text
        cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
        // Remove markdown italic *text* or _text_ -> text
        cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');
        cleaned = cleaned.replace(/_([^_]+)_/g, '$1');
        // Remove markdown inline code `code` -> code
        cleaned = cleaned.replace(/`([^`]+)`/g, '$1');
        // Ensure each non-empty line starts with //
        const lines = cleaned.split('\n');
        const cleanedLines = lines.map(line => {
            const trimmed = line.trim();
            if (trimmed === '')
                return '//';
            if (!trimmed.startsWith('//')) {
                return '// ' + trimmed;
            }
            return line;
        });
        return cleanedLines.join('\n');
    }
    /**
     * Create summary of results
     */
    createSummary(results, totalFiles, totalSymbols, totalErrors) {
        const summary = `
📝 Inline Documentation Generation Summary

Files processed: ${totalFiles}
Symbols documented: ${totalSymbols}
Errors: ${totalErrors}

Status: ${totalErrors === 0 ? '✅ Success' : '⚠️  Completed with errors'}

${this.dryRun ? '⚠️  DRY RUN MODE - No files were modified\n' : ''}
`.trim();
        return summary;
    }
}
//# sourceMappingURL=inline-docs-tool.js.map