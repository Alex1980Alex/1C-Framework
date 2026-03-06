import * as path from 'path';
import * as fs from 'fs';
import { DirectoryCrawler } from '../crawler/index.js';
import { FileAnalyzer } from '../analyzer/index.js';
import { getConfig } from '../config.js';
/**
 * Helper function to create a delay
 */
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
/**
 * Class for handling the bottom-up aggregation process for auto-* tools
 */
export class ToolAggregator {
    /**
     * Creates a new tool aggregator
     * @param rootPath The root directory to process (source)
     * @param tool The tool to use for generating content
     * @param updateExisting Whether to update existing files
     * @param outputDir Optional output directory for generated files (preserves source structure)
     */
    constructor(rootPath, tool, updateExisting = true, outputDir) {
        this.rootPath = rootPath;
        this.updateExisting = updateExisting;
        this.config = getConfig();
        // Auto-retry configuration
        this.maxRetries = 2;
        this.retryDelayMs = 5000;
        this.crawler = new DirectoryCrawler(rootPath, { respectGitignore: true });
        this.analyzer = new FileAnalyzer();
        this.tool = tool;
        this.outputDir = outputDir;
        // Read retry config from environment
        if (process.env.MAX_RETRIES) {
            this.maxRetries = parseInt(process.env.MAX_RETRIES, 10);
        }
        if (process.env.RETRY_DELAY_MS) {
            this.retryDelayMs = parseInt(process.env.RETRY_DELAY_MS, 10);
        }
    }
    /**
     * Maps a source directory path to the corresponding output directory path
     * @param sourcePath The source directory path
     * @returns The mapped output path
     */
    getOutputPath(sourcePath) {
        if (!this.outputDir) {
            return sourcePath;
        }
        const relativePath = path.relative(this.rootPath, sourcePath);
        return path.join(this.outputDir, relativePath);
    }
    /**
     * Ensures the output directory exists
     * @param outputPath The output path to ensure exists
     */
    async ensureOutputDir(outputPath) {
        const dir = path.dirname(outputPath);
        await fs.promises.mkdir(dir, { recursive: true });
    }
    /**
     * Runs the full aggregation process with auto-retry for failed directories
     * @param progressCallback Optional callback for progress updates
     * @returns Results of the aggregation process
     */
    async run(progressCallback) {
        const result = {
            totalDirectories: 0,
            successfulGenerations: 0,
            failedGenerations: 0,
            fallbackFiles: 0,
            updatedGenerations: 0,
            skippedGenerations: 0,
            errors: [],
            retriesPerformed: 0
        };
        try {
            // Check if parallel processing is enabled
            const parallelEnabled = this.config.parallelProcessing.enabled;
            const maxConcurrency = this.config.parallelProcessing.maxConcurrency;
            const requestDelayMs = this.config.parallelProcessing.requestDelayMs;
            if (parallelEnabled) {
                console.error(`Parallel processing enabled (max concurrency: ${maxConcurrency}, delay: ${requestDelayMs}ms)`);
                await this.runParallel(result, progressCallback, maxConcurrency, requestDelayMs);
            }
            else {
                console.error('Sequential processing mode');
                await this.runSequential(result, progressCallback);
            }
            // Auto-retry failed directories
            if (result.errors.length > 0 && this.maxRetries > 0) {
                await this.retryFailedDirectories(result, progressCallback);
            }
            return result;
        }
        catch (error) {
            console.error('Error during aggregation:', error);
            result.errors.push({
                directory: this.rootPath,
                error: `Global error: ${error.message}`
            });
            return result;
        }
    }
    /**
     * Retries processing for failed directories
     */
    async retryFailedDirectories(result, progressCallback) {
        for (let retry = 1; retry <= this.maxRetries; retry++) {
            const failedDirs = result.errors.map(e => e.directory);
            if (failedDirs.length === 0) {
                console.error('✅ All directories processed successfully!');
                break;
            }
            console.error(`\n🔄 Retry ${retry}/${this.maxRetries}: Retrying ${failedDirs.length} failed directories...`);
            console.error(`   Waiting ${this.retryDelayMs}ms before retry...`);
            await sleep(this.retryDelayMs);
            // Clear errors for this retry round
            const previousErrors = [...result.errors];
            result.errors = [];
            result.failedGenerations = 0;
            // Process failed directories one by one
            for (let i = 0; i < failedDirs.length; i++) {
                const dir = failedDirs[i];
                console.error(`   Retrying [${i + 1}/${failedDirs.length}]: ${path.basename(dir)}`);
                await this.processDirectory(dir, result, progressCallback, i + 1, failedDirs.length);
                // Small delay between retries to avoid rate limits
                if (i < failedDirs.length - 1) {
                    await sleep(this.config.parallelProcessing.requestDelayMs || 2000);
                }
            }
            result.retriesPerformed = retry;
            // Check if all retries succeeded
            if (result.errors.length === 0) {
                console.error(`✅ All ${failedDirs.length} directories succeeded on retry ${retry}!`);
                break;
            }
            else {
                console.error(`⚠️ Retry ${retry}: ${result.errors.length} directories still failing`);
            }
        }
        if (result.errors.length > 0) {
            console.error(`\n❌ After ${this.maxRetries} retries, ${result.errors.length} directories still failed:`);
            for (const err of result.errors) {
                console.error(`   - ${path.basename(err.directory)}: ${err.error}`);
            }
        }
    }
    /**
     * Runs directories sequentially (original behavior)
     */
    async runSequential(result, progressCallback) {
        // Create a bottom-up processing order
        const directories = await this.crawler.createBottomUpOrder();
        result.totalDirectories = directories.length;
        // Process each directory in bottom-up order
        for (let i = 0; i < directories.length; i++) {
            await this.processDirectory(directories[i], result, progressCallback, i + 1, directories.length);
        }
        return result;
    }
    /**
     * Runs directories in parallel by depth level
     */
    async runParallel(result, progressCallback, maxConcurrency = 5, requestDelayMs = 2000) {
        // Get directories grouped by depth level (deepest first)
        const directoriesByLevel = await this.crawler.createBottomUpOrderByLevel();
        // Calculate total directories for progress reporting
        let totalDirectories = 0;
        for (const level of directoriesByLevel) {
            totalDirectories += level.length;
        }
        result.totalDirectories = totalDirectories;
        console.error(`Processing ${totalDirectories} directories in ${directoriesByLevel.length} levels`);
        // Track progress across all levels
        let processedCount = 0;
        // Process each level sequentially (children before parents)
        for (let levelIndex = 0; levelIndex < directoriesByLevel.length; levelIndex++) {
            const dirsAtLevel = directoriesByLevel[levelIndex];
            console.error(`\n=== Processing level ${levelIndex + 1}/${directoriesByLevel.length} (${dirsAtLevel.length} directories) ===`);
            // Process directories at this level in parallel with concurrency limit
            await this.processDirectoriesInParallel(dirsAtLevel, result, progressCallback, processedCount, totalDirectories, maxConcurrency, requestDelayMs);
            processedCount += dirsAtLevel.length;
        }
        return result;
    }
    /**
     * Processes multiple directories in parallel with a concurrency limit
     */
    async processDirectoriesInParallel(directories, result, progressCallback, baseIndex, totalDirectories, maxConcurrency, requestDelayMs = 2000) {
        // Split directories into chunks based on maxConcurrency
        const chunks = [];
        for (let i = 0; i < directories.length; i += maxConcurrency) {
            chunks.push(directories.slice(i, i + maxConcurrency));
        }
        let processedInLevel = 0;
        // Process each chunk in parallel
        for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex++) {
            const chunk = chunks[chunkIndex];
            const startTime = Date.now();
            console.error(`Processing batch ${chunkIndex + 1}/${chunks.length} (${chunk.length} directories)...`);
            // Process all directories in this chunk simultaneously
            await Promise.all(chunk.map(async (directoryPath, indexInChunk) => {
                const globalIndex = baseIndex + processedInLevel + indexInChunk + 1;
                await this.processDirectory(directoryPath, result, progressCallback, globalIndex, totalDirectories);
            }));
            processedInLevel += chunk.length;
            const elapsed = Date.now() - startTime;
            console.error(`Batch ${chunkIndex + 1}/${chunks.length} completed in ${elapsed}ms`);
            // Add delay between batches to avoid rate limiting (except after last batch)
            if (chunkIndex < chunks.length - 1 && requestDelayMs > 0) {
                console.error(`Waiting ${requestDelayMs}ms before next batch to avoid rate limiting...`);
                await sleep(requestDelayMs);
            }
        }
    }
    /**
     * Processes a single directory
     */
    async processDirectory(directoryPath, result, progressCallback, currentIndex, totalDirectories) {
        console.error(`Processing directory: ${directoryPath}`);
        // Get all code files in the directory
        const files = this.crawler.getCodeFiles(directoryPath);
        // Report progress if callback is provided
        if (progressCallback) {
            progressCallback(path.relative(this.rootPath, directoryPath) || '.', files.length, currentIndex, totalDirectories);
        }
        // Check if directory has subdirectories
        const hasSubdirectories = this.crawler.hasSubdirectories(directoryPath);
        // Check if directory should be processed
        if (!this.analyzer.shouldDocument(directoryPath, files, hasSubdirectories)) {
            console.error(`Skipping directory ${directoryPath} - Not enough code files to process or skipped due to rules`);
            // If this is a single-file directory, it will be included in its parent's processing
            return;
        }
        // Get content from subdirectories and single-file directories that weren't processed
        const subdirContent = this.crawler.getSubdirectoryDocs(directoryPath);
        // Get single-file subdirectories' content to include in this directory's processing
        const singleFileContent = this.crawler.getSingleFileSubdirectories(directoryPath);
        // Check if this is a directory with no code files but with subdirectories
        if (files.length === 0 && hasSubdirectories) {
            console.error(`Processing directory ${directoryPath} - No code files, but contains subdirectories with content`);
        }
        // Analyze files (might be empty if directory only has subdirectories)
        const analysisResult = await this.analyzer.analyzeFiles(directoryPath, files);
        // Check if files are too large or too many
        if (analysisResult.limited) {
            console.error(`Directory ${directoryPath} exceeds limits: ${analysisResult.limitReason}`);
            const fallbackContent = await this.tool.createFallbackContent(directoryPath, analysisResult);
            // Get fallback filename from tool's public method
            const fallbackFilename = this.tool.getFallbackFilename();
            const outputDir = this.getOutputPath(directoryPath);
            await this.ensureOutputDir(path.join(outputDir, fallbackFilename));
            const fallbackPath = path.join(outputDir, fallbackFilename);
            await fs.promises.writeFile(fallbackPath, fallbackContent, 'utf8');
            result.fallbackFiles++;
            return;
        }
        // Get all content from child directories (subdirectories and single-file directories)
        const allChildContent = [...subdirContent];
        // Add content from single-file subdirectories
        if (singleFileContent.length > 0) {
            allChildContent.push(...singleFileContent);
        }
        // Generate content
        const isTopLevel = directoryPath === this.rootPath;
        const genResult = await this.generateContent(directoryPath, analysisResult, isTopLevel, allChildContent, result);
        if (genResult.skipped) {
            result.skippedGenerations++;
            console.error(`Skipped existing content for ${directoryPath} (updateExisting=false)`);
        }
        else if (genResult.isUpdate) {
            result.updatedGenerations++;
        }
    }
    /**
     * Generates content for a directory and updates the aggregation result
     * @param directoryPath Path to the directory
     * @param analysisResult Results of file analysis
     * @param isTopLevel Whether this is the top level directory
     * @param childContent Content from child directories
     * @param aggregationResult Aggregation result to update
     * @returns Generation result
     */
    async generateContent(directoryPath, analysisResult, isTopLevel, childContent, aggregationResult) {
        try {
            // Calculate output directory (may be different from source if outputDir is set)
            const outputDir = this.getOutputPath(directoryPath);
            const genResult = await this.tool.generate(directoryPath, analysisResult, isTopLevel, childContent, outputDir);
            if (genResult.success) {
                console.error(`Successfully ${genResult.isUpdate ? 'updated' : 'generated'} content for ${directoryPath}`);
                aggregationResult.successfulGenerations++;
            }
            else {
                console.error(`Failed to generate content for ${directoryPath}:`, genResult.error);
                aggregationResult.failedGenerations++;
                aggregationResult.errors.push({
                    directory: directoryPath,
                    error: genResult.error || 'Unknown error'
                });
            }
            return genResult;
        }
        catch (error) {
            console.error(`Error generating content for ${directoryPath}:`, error);
            aggregationResult.failedGenerations++;
            aggregationResult.errors.push({
                directory: directoryPath,
                error: error.message
            });
            // Use outputDir for the output path
            const outputDir = this.getOutputPath(directoryPath);
            return {
                outputPath: path.join(outputDir, this.tool.getOutputFilename()),
                success: false,
                content: '',
                error: error.message,
                isUpdate: false
            };
        }
    }
}
//# sourceMappingURL=aggregator.js.map