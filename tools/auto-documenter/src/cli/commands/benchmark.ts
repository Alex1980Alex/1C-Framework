/**
 * Benchmark Command - Run performance benchmarks
 * @module cli/commands/benchmark
 */

import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { createOutput, Output } from '../utils/output.js';
import { version } from '../utils/version.js';
import {
  AnalysisBenchmark,
  ProviderBenchmark,
  formatBenchmarkResults,
  generateBenchmarkReport,
  generateMarkdownReport,
  generateJsonReport,
  BenchmarkSuite
} from '../../benchmark/index.js';

/**
 * Benchmark types
 */
type BenchmarkType = 'analysis' | 'provider' | 'scalability' | 'all';

/**
 * Output formats
 */
type OutputFormat = 'console' | 'markdown' | 'json';

/**
 * Benchmark command options
 */
interface BenchmarkOptions {
  type: BenchmarkType;
  format: OutputFormat;
  output?: string;
  iterations: number;
  maxFiles: number;
  verbose?: boolean;
  quiet?: boolean;
}

/**
 * Execute benchmark command
 */
async function executeBenchmark(
  targetPath: string,
  options: BenchmarkOptions,
  output: Output
): Promise<void> {
  const absolutePath = path.resolve(targetPath);

  // Validate path exists for analysis benchmarks
  if (options.type !== 'provider' && !fs.existsSync(absolutePath)) {
    throw new Error(`Path does not exist: ${absolutePath}`);
  }

  output.header('Running Performance Benchmarks');
  output.info(`Type: ${options.type}`);
  output.info(`Iterations: ${options.iterations}`);
  if (options.type !== 'provider') {
    output.info(`Path: ${absolutePath}`);
    output.info(`Max files: ${options.maxFiles}`);
  }
  output.newline();

  const suites: BenchmarkSuite[] = [];

  // Run analysis benchmarks
  if (options.type === 'analysis' || options.type === 'all') {
    output.info('Running analysis benchmarks...');
    const analysisBenchmark = new AnalysisBenchmark();

    try {
      const result = await analysisBenchmark.runAnalysisBenchmark({
        targetPath: absolutePath,
        iterations: options.iterations,
        maxFiles: options.maxFiles
      });

      suites.push({
        name: 'File Analysis',
        description: 'Measure file analysis performance',
        benchmarks: [],
        results: [result]
      });

      output.success('Analysis benchmark completed');
    } catch (error: any) {
      output.warn(`Analysis benchmark failed: ${error.message}`);
    }
  }

  // Run scalability benchmarks
  if (options.type === 'scalability' || options.type === 'all') {
    output.info('Running scalability benchmarks...');
    const analysisBenchmark = new AnalysisBenchmark();

    try {
      const suite = await analysisBenchmark.runScalabilityBenchmark(absolutePath);
      suites.push(suite);
      output.success('Scalability benchmark completed');
    } catch (error: any) {
      output.warn(`Scalability benchmark failed: ${error.message}`);
    }
  }

  // Run provider benchmarks
  if (options.type === 'provider' || options.type === 'all') {
    output.info('Running provider benchmarks...');
    const providerBenchmark = new ProviderBenchmark();

    try {
      const suite = await providerBenchmark.runComparisonBenchmark(
        'Document this code: function add(a, b) { return a + b; }',
        options.iterations
      );
      suites.push(suite);
      output.success('Provider benchmark completed');
    } catch (error: any) {
      output.warn(`Provider benchmark failed: ${error.message}`);
    }
  }

  // Generate report
  output.newline();
  output.header('Benchmark Results');

  const metadata = {
    version,
    timestamp: new Date(),
    environment: `${process.platform} ${process.arch}`
  };

  let report: string;

  switch (options.format) {
    case 'markdown':
      report = generateMarkdownReport(suites, metadata);
      break;
    case 'json':
      report = generateJsonReport(suites, metadata);
      break;
    default:
      report = generateBenchmarkReport(suites, metadata);
  }

  // Output report
  if (options.output) {
    const outputPath = path.resolve(options.output);
    const extension = options.format === 'json' ? '.json' : '.md';
    const finalPath = outputPath.endsWith(extension) ? outputPath : `${outputPath}${extension}`;

    fs.writeFileSync(finalPath, report);
    output.success(`Report saved to: ${finalPath}`);
  } else {
    console.log(report);
  }

  // Summary
  const allResults = suites.flatMap(s => s.results || []);
  const successful = allResults.filter(r => r.success).length;

  output.newline();
  output.summary({
    'Total benchmarks': allResults.length,
    'Successful': successful,
    'Failed': allResults.length - successful
  });
}

/**
 * Create benchmark command
 */
export function createBenchmarkCommand(): Command {
  const command = new Command('benchmark')
    .alias('bench')
    .alias('b')
    .description('Run performance benchmarks')
    .argument('[path]', 'Directory path for analysis benchmarks', '.')
    .option('-t, --type <type>', 'Benchmark type (analysis, provider, scalability, all)', 'analysis')
    .option('-f, --format <format>', 'Output format (console, markdown, json)', 'console')
    .option('-o, --output <path>', 'Save report to file')
    .option('-i, --iterations <n>', 'Number of iterations', '3')
    .option('--max-files <n>', 'Maximum files for analysis', '500')
    .action(async (targetPath: string, options: any, cmd: Command) => {
      const globalOpts = cmd.optsWithGlobals();
      const output = createOutput(globalOpts.verbose, globalOpts.quiet);

      const benchmarkOptions: BenchmarkOptions = {
        ...globalOpts,
        type: options.type as BenchmarkType,
        format: options.format as OutputFormat,
        output: options.output,
        iterations: parseInt(options.iterations, 10),
        maxFiles: parseInt(options.maxFiles, 10)
      };

      try {
        await executeBenchmark(targetPath, benchmarkOptions, output);
      } catch (error: any) {
        output.error(error.message);
        process.exit(1);
      }
    });

  return command;
}
