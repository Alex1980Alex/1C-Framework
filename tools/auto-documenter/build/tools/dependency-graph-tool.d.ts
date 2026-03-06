import { BaseTool, BaseToolConfig, AutoToolResult } from './base-tool.js';
import { AnalysisResult } from '../analyzer/index.js';
/**
 * Configuration for the dependency graph tool
 */
interface DependencyGraphConfig extends BaseToolConfig {
    outputFilename: string;
    fallbackFilename: string;
    updateExisting: boolean;
}
/**
 * Tool for generating dependency graphs for BSL/1C code
 * Uses hybrid approach: static analysis + LLM for formatting
 */
export declare class DependencyGraphTool extends BaseTool<DependencyGraphConfig> {
    readonly name = "generate_dependency_graph";
    readonly description = "Generates Mermaid dependency graphs for BSL/1C code using hybrid analysis (static extraction + LLM formatting)";
    private openRouterClient;
    constructor(apiKey?: string, model?: string);
    /**
     * Recursively find all BSL files in a directory
     * @param dirPath Directory to search (source directory)
     * @returns Array of BSL file paths with their content
     */
    private findBslFilesRecursively;
    /**
     * Extract dependencies from BSL code using regex patterns
     */
    private extractDependencies;
    /**
     * Generate Mermaid diagram using LLM
     */
    private generateMermaidWithLLM;
    /**
     * Find all BSL files in a directory
     */
    private findBslFilesInDirectory;
    /**
     * Fix Mermaid node IDs to match their labels
     * Rule: ID = label with spaces/special chars replaced by underscores
     * Converts: `A(["Функция ДобавитьКомандыОтчетов"])` -> `Функция_ДобавитьКомандыОтчетов(["Функция ДобавитьКомандыОтчетов"])`
     */
    private fixMermaidNodeIds;
    /**
     * Generate simple Mermaid diagram without LLM (fallback)
     */
    private generateSimpleMermaid;
    /**
     * Generate dependency graph for a directory
     */
    generate(directoryPath: string, analysisResult: AnalysisResult, isTopLevel: boolean, childrenContent?: Array<{
        path: string;
        content: string;
    }>, outputDir?: string): Promise<AutoToolResult>;
    /**
     * Create fallback content for directories that exceed limits
     */
    createFallbackContent(directoryPath: string, analysisResult: AnalysisResult): Promise<string>;
    /**
     * Override input schema for this tool
     */
    getInputSchema(): any;
}
export {};
