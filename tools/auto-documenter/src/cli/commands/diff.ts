/**
 * Documentation Diff Command
 * Compare two versions of documentation and generate diff report
 * @module cli/commands/diff
 */

import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { DiffTool, DiffOptions } from '../../tools/diff-tool.js';
import { getFormatter, OutputFormat } from '../../tools/diff-formatters.js';
import { createOutput, Output } from '../utils/output.js';
import { CLIOptions } from '../utils/options.js';

/**
 * Diff command specific options
 */
interface DiffCLIOptions extends CLIOptions {
  /** Output format */
  format: OutputFormat;
  /** Output file path */
  output?: string;
  /** Ignore whitespace changes */
  ignoreWhitespace: boolean;
  /** Include unchanged files */
  includeUnchanged: boolean;
  /** Detect breaking changes */
  detectBreaking: boolean;
  /** File patterns to include */
  include?: string[];
  /** File patterns to exclude */
  exclude?: string[];
}

/**
 * Execute diff command
 */
async function executeDiff(
  basePath: string,
  targetPath: string,
  options: DiffCLIOptions,
  output: Output
): Promise<void> {
  const absoluteBase = path.resolve(basePath);
  const absoluteTarget = path.resolve(targetPath);

  // Validate paths exist
  if (!fs.existsSync(absoluteBase)) {
    throw new Error(`Base path does not exist: ${absoluteBase}`);
  }

  if (!fs.existsSync(absoluteTarget)) {
    throw new Error(`Target path does not exist: ${absoluteTarget}`);
  }

  output.header('Documentation Diff');
  output.info(`Base: ${absoluteBase}`);
  output.info(`Target: ${absoluteTarget}`);
  output.info(`Format: ${options.format}`);
  output.newline();

  // Create diff options
  const diffOptions: DiffOptions = {
    ignoreWhitespace: options.ignoreWhitespace,
    includeUnchanged: options.includeUnchanged,
    detectBreaking: options.detectBreaking,
    includePatterns: options.include,
    excludePatterns: options.exclude,
  };

  // Initialize diff tool
  const diffTool = new DiffTool(diffOptions);

  // Determine if comparing files or directories
  const baseStats = fs.statSync(absoluteBase);
  const targetStats = fs.statSync(absoluteTarget);

  if (baseStats.isFile() && targetStats.isFile()) {
    output.info('Comparing files...');
  } else if (baseStats.isDirectory() && targetStats.isDirectory()) {
    output.info('Comparing directories...');
  } else {
    throw new Error('Cannot compare file with directory. Both paths must be of the same type.');
  }

  // Perform diff
  const result = baseStats.isFile()
    ? await diffTool.compareFiles(absoluteBase, absoluteTarget)
    : await diffTool.compareDirectories(absoluteBase, absoluteTarget);

  // Format output
  const formatter = getFormatter(options.format);
  const formattedOutput = formatter.format(result);

  // Handle output
  if (options.output) {
    const outputPath = path.resolve(options.output);
    await fs.promises.writeFile(outputPath, formattedOutput, 'utf-8');
    output.success(`Diff report saved to: ${outputPath}`);
  } else if (options.format === 'console') {
    // Print directly to console
    console.log(formattedOutput);
  } else {
    // Print raw format output (JSON or Markdown)
    console.log(formattedOutput);
  }

  // Summary for console
  if (!options.quiet && options.format === 'console') {
    output.newline();
    output.summary({
      'Files Compared': result.summary.totalFiles,
      'Files Changed': result.summary.changedFiles,
      'Files Added': result.summary.addedFiles,
      'Files Removed': result.summary.removedFiles,
      'Lines Added': `+${result.summary.linesAdded}`,
      'Lines Removed': `-${result.summary.linesRemoved}`,
      'Breaking Changes': result.summary.breakingChanges,
    });
  }

  // Exit with error code if breaking changes detected and detectBreaking is enabled
  if (options.detectBreaking && result.summary.breakingChanges > 0) {
    output.warn(
      `⚠️  ${result.summary.breakingChanges} breaking change(s) detected!`
    );
    process.exit(1);
  }
}

/**
 * Create diff command
 */
export function createDiffCommand(): Command {
  const command = new Command('diff')
    .alias('d')
    .alias('compare')
    .description('Compare two versions of documentation')
    .argument('<base>', 'Base path (old version) - file or directory')
    .argument('<target>', 'Target path (new version) - file or directory')
    .option(
      '-f, --format <format>',
      'Output format: console, markdown, json, github',
      'console'
    )
    .option('-o, --output <file>', 'Save output to file')
    .option('-w, --ignore-whitespace', 'Ignore whitespace changes', false)
    .option('-u, --include-unchanged', 'Include unchanged files in report', false)
    .option('-b, --detect-breaking', 'Detect and flag breaking changes', true)
    .option(
      '-i, --include <patterns...>',
      'File patterns to include (e.g., "*.md" "*.txt")'
    )
    .option(
      '-e, --exclude <patterns...>',
      'File patterns to exclude (e.g., "**/node_modules/**")'
    )
    .action(
      async (
        basePath: string,
        targetPath: string,
        localOpts: any,
        cmd: Command
      ) => {
        const globalOpts = cmd.optsWithGlobals() as DiffCLIOptions;
        const mergedOpts: DiffCLIOptions = {
          ...globalOpts,
          ...localOpts,
        };
        const output = createOutput(mergedOpts.verbose, mergedOpts.quiet);

        try {
          await executeDiff(basePath, targetPath, mergedOpts, output);
        } catch (error: any) {
          output.error(error.message);
          process.exit(1);
        }
      }
    );

  return command;
}
