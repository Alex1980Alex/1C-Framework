/**
 * Generate Documentation Command
 * @module cli/commands/generate
 */
import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { FileAnalyzer } from '../../analyzer/index.js';
import { DocumentationTool } from '../../tools/documentation-tool.js';
import { createOutput } from '../utils/output.js';
import { getApiKey, getModel, validateProviderConfig } from '../utils/options.js';
// Phase 2 modules
import { createCache } from '../../cache/response-cache.js';
import { runIncremental } from '../../incremental/change-tracker.js';
import { WatchModeRunner } from '../../watch/file-watcher.js';
import { loadConfig } from '../../config/config-loader.js';
/**
 * Recursively get all files in a directory
 */
function getAllFiles(dirPath, arrayOfFiles = []) {
    try {
        const files = fs.readdirSync(dirPath);
        files.forEach((file) => {
            const fullPath = path.join(dirPath, file);
            try {
                if (fs.statSync(fullPath).isDirectory()) {
                    if (!file.startsWith('.') && file !== 'node_modules') {
                        getAllFiles(fullPath, arrayOfFiles);
                    }
                }
                else {
                    arrayOfFiles.push(fullPath);
                }
            }
            catch {
                // Skip files we can't access
            }
        });
    }
    catch {
        // Skip directories we can't access
    }
    return arrayOfFiles;
}
/**
 * Execute generate documentation command
 */
async function executeGenerate(targetPath, options, output) {
    const absolutePath = path.resolve(targetPath);
    // Load config file if specified or auto-detect
    const { config: fileConfig } = loadConfig(absolutePath, {
        provider: options.provider,
        model: options.model
    });
    // Merge CLI options with config file (CLI takes precedence)
    const mergedOptions = {
        ...options,
        cache: options.cache || fileConfig.cache?.enabled || false,
        cacheDir: options.cacheDir || fileConfig.cache?.directory,
        watch: options.watch || fileConfig.watch?.enabled || false,
        incremental: options.incremental || false
    };
    // Validate path exists
    if (!fs.existsSync(absolutePath)) {
        throw new Error(`Path does not exist: ${absolutePath}`);
    }
    const stats = fs.statSync(absolutePath);
    if (!stats.isDirectory()) {
        throw new Error(`Path is not a directory: ${absolutePath}`);
    }
    // Get API key and model
    const apiKey = getApiKey(mergedOptions.provider, mergedOptions.apiKey);
    const model = getModel(mergedOptions.provider, mergedOptions.model);
    // Validate provider config
    const validationError = validateProviderConfig(mergedOptions.provider, apiKey);
    if (validationError) {
        throw new Error(validationError);
    }
    output.header('Generating Documentation');
    output.info(`Path: ${absolutePath}`);
    output.info(`Provider: ${mergedOptions.provider}`);
    output.info(`Model: ${model}`);
    if (mergedOptions.cache)
        output.info('Cache: enabled');
    if (mergedOptions.incremental)
        output.info('Mode: incremental');
    if (mergedOptions.watch)
        output.info('Mode: watch');
    output.newline();
    // Set environment variables for provider rotation
    process.env.PRIMARY_PROVIDER = mergedOptions.provider;
    process.env.ENABLE_ROTATION = 'true';
    if (apiKey) {
        const envVarNames = {
            gemini: 'GEMINI_API_KEY',
            groq: 'GROQ_API_KEY',
            ollama: '',
            grok: 'XAI_API_KEY',
            openrouter: 'OPENROUTER_API_KEY'
        };
        const envVar = envVarNames[mergedOptions.provider];
        if (envVar) {
            process.env[envVar] = apiKey;
        }
    }
    // Initialize cache if enabled
    let cache = null;
    if (mergedOptions.cache) {
        const cacheDir = mergedOptions.cacheDir || path.join(absolutePath, '.autodoc-cache');
        cache = await createCache({ directory: cacheDir });
        output.debug(`Cache initialized at: ${cacheDir}`);
    }
    // Initialize tools
    const analyzer = new FileAnalyzer();
    const docTool = new DocumentationTool(apiKey, model, mergedOptions.update);
    // Core generation function
    const generateDocs = async (filesToProcess) => {
        // Get all files or use provided list
        output.info('Scanning directory...');
        const files = filesToProcess
            ? filesToProcess.map(f => path.join(absolutePath, f))
            : getAllFiles(absolutePath);
        output.debug(`Found ${files.length} files`);
        // Analyze files
        output.info('Analyzing files...');
        const analysisResult = await analyzer.analyzeFiles(absolutePath, files);
        if (analysisResult.analyzedFiles.length === 0) {
            output.warn('No code files found to document');
            return;
        }
        output.info(`Analyzing ${analysisResult.analyzedFiles.length} code files...`);
        // Generate documentation
        output.info('Generating documentation with AI...');
        const result = await docTool.generate(absolutePath, analysisResult, true);
        if (result.success) {
            output.success(`Documentation generated: ${result.outputPath}`);
            output.summary({
                'Files analyzed': analysisResult.analyzedFiles.length,
                'Files excluded': analysisResult.excludedFiles.length,
                'Output': result.outputPath,
                'Updated': result.isUpdate ? 'Yes' : 'No',
                ...(cache ? { 'Cache hits': cache.getStats().hits } : {})
            });
        }
        else {
            throw new Error(result.error || 'Failed to generate documentation');
        }
    };
    // Watch mode
    if (mergedOptions.watch) {
        output.info('Starting watch mode...');
        const watchRunner = new WatchModeRunner(absolutePath, {
            include: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.jsx', '**/*.bsl', '**/*.py'],
            exclude: ['**/node_modules/**', '**/dist/**', '**/.git/**'],
            debounceMs: 1000,
            recursive: true
        });
        await watchRunner.start(async (changedFiles) => {
            output.info(`\nFiles changed: ${changedFiles.join(', ')}`);
            await generateDocs(changedFiles);
        });
        // Keep process running
        process.on('SIGINT', () => {
            output.info('\nStopping watch mode...');
            watchRunner.stop();
            process.exit(0);
        });
        return; // Don't continue, watch mode runs indefinitely
    }
    // Incremental mode
    if (mergedOptions.incremental && !mergedOptions.force) {
        output.info('Running in incremental mode...');
        const result = await runIncremental(absolutePath, async (files) => {
            await generateDocs(files);
        }, { force: mergedOptions.force, verbose: mergedOptions.verbose });
        output.summary({
            'Files processed': result.processed,
            'Files skipped': result.skipped,
            'Changes detected': result.changes.length
        });
        return;
    }
    // Standard full generation
    await generateDocs();
}
/**
 * Create generate command
 */
export function createGenerateCommand() {
    const command = new Command('generate')
        .alias('doc')
        .alias('g')
        .description('Generate documentation for a directory')
        .argument('<path>', 'Directory path to document')
        .action(async (targetPath, options, cmd) => {
        const globalOpts = cmd.optsWithGlobals();
        const output = createOutput(globalOpts.verbose, globalOpts.quiet);
        try {
            await executeGenerate(targetPath, globalOpts, output);
        }
        catch (error) {
            output.error(error.message);
            process.exit(1);
        }
    });
    return command;
}
//# sourceMappingURL=generate.js.map