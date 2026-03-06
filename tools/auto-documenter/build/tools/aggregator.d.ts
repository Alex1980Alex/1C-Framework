import { BaseTool } from './base-tool.js';
/**
 * Result of the tool aggregation process
 */
export interface AggregationResult {
    /**
     * Total number of directories processed
     */
    totalDirectories: number;
    /**
     * Number of directories successfully processed
     */
    successfulGenerations: number;
    /**
     * Number of directories that failed processing
     */
    failedGenerations: number;
    /**
     * Number of directories with fallback files
     */
    fallbackFiles: number;
    /**
     * Number of directories that were updated
     */
    updatedGenerations: number;
    /**
     * Number of directories that were skipped (existing files when updateExisting is false)
     */
    skippedGenerations: number;
    /**
     * Errors encountered during the process
     */
    errors: Array<{
        directory: string;
        error: string;
    }>;
    /**
     * Number of retries performed
     */
    retriesPerformed?: number;
}
/**
 * Type definition for progress callback
 */
export type ProgressCallback = (directory: string, fileCount: number, currentIndex: number, totalDirectories: number) => void;
/**
 * Class for handling the bottom-up aggregation process for auto-* tools
 */
export declare class ToolAggregator {
    private rootPath;
    private updateExisting;
    private crawler;
    private analyzer;
    private tool;
    private outputDir;
    private config;
    private maxRetries;
    private retryDelayMs;
    /**
     * Creates a new tool aggregator
     * @param rootPath The root directory to process (source)
     * @param tool The tool to use for generating content
     * @param updateExisting Whether to update existing files
     * @param outputDir Optional output directory for generated files (preserves source structure)
     */
    constructor(rootPath: string, tool: BaseTool<any>, updateExisting?: boolean, outputDir?: string);
    /**
     * Maps a source directory path to the corresponding output directory path
     * @param sourcePath The source directory path
     * @returns The mapped output path
     */
    private getOutputPath;
    /**
     * Ensures the output directory exists
     * @param outputPath The output path to ensure exists
     */
    private ensureOutputDir;
    /**
     * Runs the full aggregation process with auto-retry for failed directories
     * @param progressCallback Optional callback for progress updates
     * @returns Results of the aggregation process
     */
    run(progressCallback?: ProgressCallback): Promise<AggregationResult>;
    /**
     * Retries processing for failed directories
     */
    private retryFailedDirectories;
    /**
     * Runs directories sequentially (original behavior)
     */
    private runSequential;
    /**
     * Runs directories in parallel by depth level
     */
    private runParallel;
    /**
     * Processes multiple directories in parallel with a concurrency limit
     */
    private processDirectoriesInParallel;
    /**
     * Processes a single directory
     */
    private processDirectory;
    /**
     * Generates content for a directory and updates the aggregation result
     * @param directoryPath Path to the directory
     * @param analysisResult Results of file analysis
     * @param isTopLevel Whether this is the top level directory
     * @param childContent Content from child directories
     * @param aggregationResult Aggregation result to update
     * @returns Generation result
     */
    private generateContent;
}
