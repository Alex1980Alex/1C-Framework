/**
 * Test Plan Generation Command
 * @module cli/commands/testplan
 */
import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { FileAnalyzer } from '../../analyzer/index.js';
import { TestPlanTool } from '../../tools/testplan-tool.js';
import { createOutput } from '../utils/output.js';
import { getApiKey, getModel, validateProviderConfig } from '../utils/options.js';
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
 * Execute testplan command
 */
async function executeTestplan(targetPath, options, output) {
    const absolutePath = path.resolve(targetPath);
    // Validate path exists
    if (!fs.existsSync(absolutePath)) {
        throw new Error(`Path does not exist: ${absolutePath}`);
    }
    const stats = fs.statSync(absolutePath);
    if (!stats.isDirectory()) {
        throw new Error(`Path is not a directory: ${absolutePath}`);
    }
    // Get API key and model
    const apiKey = getApiKey(options.provider, options.apiKey);
    const model = getModel(options.provider, options.model);
    // Validate provider config
    const validationError = validateProviderConfig(options.provider, apiKey);
    if (validationError) {
        throw new Error(validationError);
    }
    output.header('Generating Test Plan');
    output.info(`Path: ${absolutePath}`);
    output.info(`Provider: ${options.provider}`);
    output.info(`Model: ${model}`);
    output.newline();
    // Set environment variables for provider rotation
    process.env.PRIMARY_PROVIDER = options.provider;
    process.env.ENABLE_ROTATION = 'true';
    if (apiKey) {
        const envVarNames = {
            gemini: 'GEMINI_API_KEY',
            groq: 'GROQ_API_KEY',
            ollama: '',
            grok: 'XAI_API_KEY',
            openrouter: 'OPENROUTER_API_KEY'
        };
        const envVar = envVarNames[options.provider];
        if (envVar) {
            process.env[envVar] = apiKey;
        }
    }
    // Initialize tools
    const analyzer = new FileAnalyzer();
    const testplanTool = new TestPlanTool(apiKey, model, options.update);
    // Get all files
    output.info('Scanning directory...');
    const files = getAllFiles(absolutePath);
    output.debug(`Found ${files.length} files`);
    // Analyze files
    output.info('Analyzing files...');
    const analysisResult = await analyzer.analyzeFiles(absolutePath, files);
    if (analysisResult.analyzedFiles.length === 0) {
        output.warn('No code files found for test planning');
        return;
    }
    output.info(`Analyzing ${analysisResult.analyzedFiles.length} code files...`);
    // Generate test plan
    output.info('Generating test plan with AI...');
    const result = await testplanTool.generate(absolutePath, analysisResult, true);
    if (result.success) {
        output.success(`Test plan generated: ${result.outputPath}`);
        output.summary({
            'Files analyzed': analysisResult.analyzedFiles.length,
            'Files excluded': analysisResult.excludedFiles.length,
            'Output': result.outputPath,
            'Updated': result.isUpdate ? 'Yes' : 'No'
        });
    }
    else {
        throw new Error(result.error || 'Failed to generate test plan');
    }
}
/**
 * Create testplan command
 */
export function createTestplanCommand() {
    const command = new Command('testplan')
        .alias('test')
        .alias('t')
        .description('Generate test plan for a directory')
        .argument('<path>', 'Directory path for test planning')
        .action(async (targetPath, options, cmd) => {
        const globalOpts = cmd.optsWithGlobals();
        const output = createOutput(globalOpts.verbose, globalOpts.quiet);
        try {
            await executeTestplan(targetPath, globalOpts, output);
        }
        catch (error) {
            output.error(error.message);
            process.exit(1);
        }
    });
    return command;
}
//# sourceMappingURL=testplan.js.map