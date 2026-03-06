import { AnalysisResult } from '../analyzer/index.js';
/**
 * Base interface for all auto-* tool configurations
 */
export interface BaseToolConfig {
    outputFilename: string;
    fallbackFilename: string;
    updateExisting: boolean;
}
/**
 * Base interface for all auto-* tool results
 */
export interface AutoToolResult {
    /**
     * Path to the generated file
     */
    outputPath: string;
    /**
     * Whether generation was successful
     */
    success: boolean;
    /**
     * Content of the generated file
     */
    content: string;
    /**
     * Error message if generation failed
     */
    error?: string;
    /**
     * Whether this was a fresh generation or an update
     */
    isUpdate: boolean;
    /**
     * Whether generation was skipped (for existing files when updateExisting is false)
     */
    skipped?: boolean;
}
/**
 * Abstract base class for all auto-* tools
 */
export declare abstract class BaseTool<T extends BaseToolConfig> {
    /**
     * The name of the tool (used for registration)
     */
    abstract readonly name: string;
    /**
     * The description of the tool
     */
    abstract readonly description: string;
    /**
     * The configuration for the tool
     */
    protected config: T;
    constructor(config: T);
    /**
     * Get the output filename for this tool
     */
    getOutputFilename(): string;
    /**
     * Get the fallback filename for this tool
     */
    getFallbackFilename(): string;
    /**
     * Abstract method to generate content for a directory
     * @param directoryPath Path to the source directory
     * @param analysisResult Results of file analysis
     * @param isTopLevel Whether this is the top level directory
     * @param childrenContent Content from child directories
     * @param outputDir Optional output directory (if different from source)
     */
    abstract generate(directoryPath: string, analysisResult: AnalysisResult, isTopLevel: boolean, childrenContent?: Array<{
        path: string;
        content: string;
    }>, outputDir?: string): Promise<AutoToolResult>;
    /**
     * Abstract method to create fallback content for directories that exceed limits
     */
    abstract createFallbackContent(directoryPath: string, analysisResult: AnalysisResult): Promise<string>;
    /**
     * Get the input schema for the tool
     */
    getInputSchema(): any;
    /**
     * Format the aggregation result for display
     */
    formatResultSummary(result: any): string;
}
