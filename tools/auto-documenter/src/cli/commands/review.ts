/**
 * Code Review Command
 * @module cli/commands/review
 */

import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { FileAnalyzer } from '../../analyzer/index.js';
import { ReviewTool } from '../../tools/review-tool.js';
import { createOutput, Output } from '../utils/output.js';
import { getApiKey, getModel, validateProviderConfig, CLIOptions, Provider } from '../utils/options.js';

/**
 * Recursively get all files in a directory
 */
function getAllFiles(dirPath: string, arrayOfFiles: string[] = []): string[] {
  try {
    const files = fs.readdirSync(dirPath);

    files.forEach((file) => {
      const fullPath = path.join(dirPath, file);
      try {
        if (fs.statSync(fullPath).isDirectory()) {
          if (!file.startsWith('.') && file !== 'node_modules') {
            getAllFiles(fullPath, arrayOfFiles);
          }
        } else {
          arrayOfFiles.push(fullPath);
        }
      } catch {
        // Skip files we can't access
      }
    });
  } catch {
    // Skip directories we can't access
  }

  return arrayOfFiles;
}

/**
 * Execute review command
 */
async function executeReview(targetPath: string, options: CLIOptions, output: Output): Promise<void> {
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

  output.header('Generating Code Review');
  output.info(`Path: ${absolutePath}`);
  output.info(`Provider: ${options.provider}`);
  output.info(`Model: ${model}`);
  output.newline();

  // Set environment variables for provider rotation
  process.env.PRIMARY_PROVIDER = options.provider;
  process.env.ENABLE_ROTATION = 'true';
  if (apiKey) {
    const envVarNames: Record<Provider, string> = {
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
  const reviewTool = new ReviewTool(apiKey, model, options.update);

  // Get all files
  output.info('Scanning directory...');
  const files = getAllFiles(absolutePath);
  output.debug(`Found ${files.length} files`);

  // Analyze files
  output.info('Analyzing files...');
  const analysisResult = await analyzer.analyzeFiles(absolutePath, files);

  if (analysisResult.analyzedFiles.length === 0) {
    output.warn('No code files found to review');
    return;
  }

  output.info(`Analyzing ${analysisResult.analyzedFiles.length} code files...`);

  // Generate review
  output.info('Generating code review with AI...');
  const result = await reviewTool.generate(absolutePath, analysisResult, true);

  if (result.success) {
    output.success(`Code review generated: ${result.outputPath}`);
    output.summary({
      'Files analyzed': analysisResult.analyzedFiles.length,
      'Files excluded': analysisResult.excludedFiles.length,
      'Output': result.outputPath,
      'Updated': result.isUpdate ? 'Yes' : 'No'
    });
  } else {
    throw new Error(result.error || 'Failed to generate code review');
  }
}

/**
 * Create review command
 */
export function createReviewCommand(): Command {
  const command = new Command('review')
    .alias('r')
    .description('Generate code review for a directory')
    .argument('<path>', 'Directory path to review')
    .action(async (targetPath: string, options: any, cmd: Command) => {
      const globalOpts = cmd.optsWithGlobals() as CLIOptions;
      const output = createOutput(globalOpts.verbose, globalOpts.quiet);

      try {
        await executeReview(targetPath, globalOpts, output);
      } catch (error: any) {
        output.error(error.message);
        process.exit(1);
      }
    });

  return command;
}
