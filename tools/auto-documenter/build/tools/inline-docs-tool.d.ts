import { BaseTool, BaseToolConfig, AutoToolResult } from './base-tool.js';
import { AnalysisResult } from '../analyzer/index.js';
/**
 * Configuration for inline documentation tool
 */
export interface InlineDocsToolConfig extends BaseToolConfig {
    systemPrompt: string;
    dryRun: boolean;
}
/**
 * Result of inline documentation generation for a single file
 */
export interface InlineDocsFileResult {
    filePath: string;
    success: boolean;
    symbolsDocumented: number;
    error?: string;
    changes?: Array<{
        symbolName: string;
        symbolType: 'function' | 'class' | 'interface' | 'type';
        documentation: string;
        lineNumber: number;
    }>;
}
/**
 * Tool for generating inline documentation (JSDoc/TSDoc/BSL comments)
 */
export declare class InlineDocsTool extends BaseTool<InlineDocsToolConfig> {
    readonly name = "generate_inline_docs";
    readonly description = "Generates inline documentation comments (JSDoc/TSDoc/BSL) for functions, classes, and interfaces";
    private openRouterClient;
    private dryRun;
    private tsAnalyzer;
    constructor(apiKey?: string, model?: string, updateExisting?: boolean, dryRun?: boolean);
    /**
     * Generate inline documentation for files
     * @param directoryPath Directory to process (source)
     * @param analysisResult Analysis result from file analyzer
     * @param isTopLevel Whether this is the top-level directory
     * @param childrenContent Content from child directories (unused for inline docs)
     * @param outputDir Optional output directory (if different from source)
     * @returns Result of inline documentation generation
     */
    generate(directoryPath: string, analysisResult: AnalysisResult, isTopLevel?: boolean, childrenContent?: Array<{
        path: string;
        content: string;
    }>, outputDir?: string): Promise<AutoToolResult>;
    /**
     * Create fallback content for inline documentation
     * Not applicable for inline docs since we modify files directly
     */
    createFallbackContent(directoryPath: string, analysisResult: AnalysisResult): Promise<string>;
    /**
     * Generate inline documentation for a single file
     * @param filePath Path to the source file
     * @param content File content
     * @param fileExt File extension
     * @param sourceDir Source directory (to calculate relative path)
     * @param outputDir Optional output directory (if different from source)
     * @returns Result of documentation generation
     */
    private generateForFile;
    /**
     * Extract symbols (functions, classes, interfaces) from code
     * @param content File content
     * @param fileExt File extension
     * @returns Array of symbols
     */
    private extractSymbols;
    /**
     * Extract symbols from TypeScript/JavaScript code using TypeScript Compiler API
     * Provides accurate AST-based parsing instead of regex
     * @param content File content
     * @param filePath File path for language detection
     * @returns Array of extracted symbols
     */
    private extractTSSymbols;
    /**
     * Extract symbols from BSL code with enhanced metadata
     * Extracts export status, directives, and parameters
     */
    private extractBSLSymbols;
    /**
     * Extract compilation directive from lines before procedure/function
     * @param content Full file content
     * @param matchIndex Index of procedure/function match
     * @param lineNumber Line number of procedure/function
     * @returns Directive string if found
     */
    private extractBSLDirective;
    /**
     * Parse BSL parameters string into structured format
     * @param paramsString Parameters string from procedure/function declaration
     * @returns Array of parameter info
     */
    private parseBSLParameters;
    /**
     * Extract BSL procedure body
     */
    private extractBSLProcedure;
    /**
     * Extract BSL function body
     */
    private extractBSLFunction;
    /**
     * Check if code already has documentation
     */
    private hasExistingDocumentation;
    /**
     * Apply documentation to file content
     */
    private applyDocumentation;
    /**
     * Check if file type is supported
     */
    private isSupportedFileType;
    /**
     * Strip markdown formatting from BSL documentation
     * LLMs sometimes return markdown despite instructions, this cleans it up
     * @param documentation Raw documentation from LLM
     * @param fileExt File extension
     * @returns Cleaned documentation with proper comment format
     */
    private cleanDocumentation;
    /**
     * Create summary of results
     */
    private createSummary;
}
