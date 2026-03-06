/**
 * Benchmark Reporter - Format and display benchmark results
 * @module benchmark/reporter
 */

import { BenchmarkResult, BenchmarkSuite } from './runner.js';

/**
 * Format bytes to human-readable string
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

/**
 * Format duration to human-readable string
 */
function formatDuration(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(2)} μs`;
  if (ms < 1000) return `${ms.toFixed(2)} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)} s`;
  return `${(ms / 60000).toFixed(2)} min`;
}

/**
 * Format a single benchmark result
 */
export function formatBenchmarkResult(result: BenchmarkResult): string {
  const lines: string[] = [];

  const status = result.success ? '✓' : '✗';
  lines.push(`${status} ${result.name}`);
  lines.push(`  Duration: ${formatDuration(result.duration)}`);
  lines.push(`  Memory: ${formatBytes(result.memoryUsed)}`);
  lines.push(`  Ops/sec: ${result.opsPerSecond.toFixed(2)}`);

  if (result.metrics) {
    for (const [key, value] of Object.entries(result.metrics)) {
      if (typeof value === 'number') {
        if (key.includes('Duration') || key.includes('Time')) {
          lines.push(`  ${key}: ${formatDuration(value)}`);
        } else if (key.includes('Memory') || key.includes('Size')) {
          lines.push(`  ${key}: ${formatBytes(value)}`);
        } else {
          lines.push(`  ${key}: ${value.toFixed(2)}`);
        }
      } else if (key === 'languageBreakdown' && typeof value === 'object') {
        lines.push(`  Languages:`);
        for (const [lang, count] of Object.entries(value as Record<string, number>)) {
          lines.push(`    ${lang || 'no-ext'}: ${count}`);
        }
      } else if (Array.isArray(value) && key === 'errors' && value.length > 0) {
        lines.push(`  Errors: ${value.length}`);
        for (const error of value.slice(0, 3)) {
          lines.push(`    - ${error}`);
        }
      }
    }
  }

  if (result.error) {
    lines.push(`  Error: ${result.error}`);
  }

  return lines.join('\n');
}

/**
 * Format benchmark results as a table
 */
export function formatBenchmarkResults(results: BenchmarkResult[]): string {
  if (results.length === 0) return 'No results';

  const lines: string[] = [];

  // Header
  lines.push('┌─────────────────────────────────────────────────────────────────────┐');
  lines.push('│                       BENCHMARK RESULTS                            │');
  lines.push('├─────────────────────────────────────────────────────────────────────┤');

  // Column headers
  lines.push('│ Name                          │ Duration    │ Memory    │ Ops/s    │');
  lines.push('├───────────────────────────────┼─────────────┼───────────┼──────────┤');

  // Results
  for (const result of results) {
    const name = result.name.slice(0, 29).padEnd(29);
    const duration = formatDuration(result.duration).padStart(11);
    const memory = formatBytes(result.memoryUsed).padStart(9);
    const ops = result.opsPerSecond.toFixed(2).padStart(8);
    const status = result.success ? ' ' : '!';

    lines.push(`│${status}${name} │ ${duration} │ ${memory} │ ${ops} │`);
  }

  lines.push('└─────────────────────────────────────────────────────────────────────┘');

  // Summary
  const successful = results.filter(r => r.success).length;
  const totalDuration = results.reduce((sum, r) => sum + r.duration, 0);
  const avgDuration = totalDuration / results.length;

  lines.push('');
  lines.push(`Summary: ${successful}/${results.length} passed`);
  lines.push(`Total time: ${formatDuration(totalDuration)}`);
  lines.push(`Average: ${formatDuration(avgDuration)}`);

  return lines.join('\n');
}

/**
 * Format benchmark suite results
 */
export function formatSuiteResults(suite: BenchmarkSuite): string {
  const lines: string[] = [];

  lines.push('═'.repeat(70));
  lines.push(`  ${suite.name}`);
  lines.push(`  ${suite.description}`);
  lines.push('═'.repeat(70));
  lines.push('');

  if (suite.results && suite.results.length > 0) {
    lines.push(formatBenchmarkResults(suite.results));
  } else {
    lines.push('No results available');
  }

  return lines.join('\n');
}

/**
 * Generate comprehensive benchmark report
 */
export function generateBenchmarkReport(
  suites: BenchmarkSuite[],
  metadata?: {
    environment?: string;
    timestamp?: Date;
    version?: string;
  }
): string {
  const lines: string[] = [];

  // Header
  lines.push('╔══════════════════════════════════════════════════════════════════════╗');
  lines.push('║                    AUTODOCUMENT BENCHMARK REPORT                     ║');
  lines.push('╚══════════════════════════════════════════════════════════════════════╝');
  lines.push('');

  // Metadata
  if (metadata) {
    lines.push('Environment Information:');
    if (metadata.version) lines.push(`  Version: ${metadata.version}`);
    if (metadata.environment) lines.push(`  Environment: ${metadata.environment}`);
    if (metadata.timestamp) lines.push(`  Timestamp: ${metadata.timestamp.toISOString()}`);
    lines.push(`  Node.js: ${process.version}`);
    lines.push(`  Platform: ${process.platform} ${process.arch}`);
    lines.push('');
  }

  // Suites
  for (const suite of suites) {
    lines.push(formatSuiteResults(suite));
    lines.push('');
  }

  // Overall summary
  const allResults = suites.flatMap(s => s.results || []);
  const totalSuccessful = allResults.filter(r => r.success).length;
  const totalDuration = allResults.reduce((sum, r) => sum + r.duration, 0);

  lines.push('─'.repeat(70));
  lines.push('OVERALL SUMMARY');
  lines.push('─'.repeat(70));
  lines.push(`Total benchmarks: ${allResults.length}`);
  lines.push(`Successful: ${totalSuccessful}`);
  lines.push(`Failed: ${allResults.length - totalSuccessful}`);
  lines.push(`Total time: ${formatDuration(totalDuration)}`);
  lines.push('');

  return lines.join('\n');
}

/**
 * Generate markdown benchmark report
 */
export function generateMarkdownReport(
  suites: BenchmarkSuite[],
  metadata?: {
    environment?: string;
    timestamp?: Date;
    version?: string;
  }
): string {
  const lines: string[] = [];

  lines.push('# Autodocument Benchmark Report');
  lines.push('');

  // Metadata
  if (metadata) {
    lines.push('## Environment');
    lines.push('');
    lines.push('| Property | Value |');
    lines.push('|----------|-------|');
    if (metadata.version) lines.push(`| Version | ${metadata.version} |`);
    if (metadata.timestamp) lines.push(`| Timestamp | ${metadata.timestamp.toISOString()} |`);
    lines.push(`| Node.js | ${process.version} |`);
    lines.push(`| Platform | ${process.platform} ${process.arch} |`);
    lines.push('');
  }

  // Suites
  for (const suite of suites) {
    lines.push(`## ${suite.name}`);
    lines.push('');
    lines.push(suite.description);
    lines.push('');

    if (suite.results && suite.results.length > 0) {
      lines.push('| Benchmark | Duration | Memory | Ops/s | Status |');
      lines.push('|-----------|----------|--------|-------|--------|');

      for (const result of suite.results) {
        const status = result.success ? '✅' : '❌';
        lines.push(
          `| ${result.name} | ${formatDuration(result.duration)} | ${formatBytes(result.memoryUsed)} | ${result.opsPerSecond.toFixed(2)} | ${status} |`
        );
      }
      lines.push('');
    }
  }

  // Summary
  const allResults = suites.flatMap(s => s.results || []);
  const successful = allResults.filter(r => r.success).length;

  lines.push('## Summary');
  lines.push('');
  lines.push(`- **Total benchmarks:** ${allResults.length}`);
  lines.push(`- **Successful:** ${successful}`);
  lines.push(`- **Failed:** ${allResults.length - successful}`);
  lines.push('');

  return lines.join('\n');
}

/**
 * Generate JSON report
 */
export function generateJsonReport(
  suites: BenchmarkSuite[],
  metadata?: Record<string, any>
): string {
  const report = {
    metadata: {
      ...metadata,
      nodeVersion: process.version,
      platform: process.platform,
      arch: process.arch,
      generatedAt: new Date().toISOString()
    },
    suites: suites.map(suite => ({
      name: suite.name,
      description: suite.description,
      results: suite.results?.map(r => ({
        name: r.name,
        duration: r.duration,
        memoryUsed: r.memoryUsed,
        opsPerSecond: r.opsPerSecond,
        metrics: r.metrics,
        success: r.success,
        error: r.error
      }))
    })),
    summary: {
      totalBenchmarks: suites.flatMap(s => s.results || []).length,
      successful: suites.flatMap(s => s.results || []).filter(r => r.success).length,
      totalDuration: suites.flatMap(s => s.results || []).reduce((sum, r) => sum + r.duration, 0)
    }
  };

  return JSON.stringify(report, null, 2);
}
