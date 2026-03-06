/**
 * Benchmark Reporter - Format and display benchmark results
 * @module benchmark/reporter
 */
import { BenchmarkResult, BenchmarkSuite } from './runner.js';
/**
 * Format a single benchmark result
 */
export declare function formatBenchmarkResult(result: BenchmarkResult): string;
/**
 * Format benchmark results as a table
 */
export declare function formatBenchmarkResults(results: BenchmarkResult[]): string;
/**
 * Format benchmark suite results
 */
export declare function formatSuiteResults(suite: BenchmarkSuite): string;
/**
 * Generate comprehensive benchmark report
 */
export declare function generateBenchmarkReport(suites: BenchmarkSuite[], metadata?: {
    environment?: string;
    timestamp?: Date;
    version?: string;
}): string;
/**
 * Generate markdown benchmark report
 */
export declare function generateMarkdownReport(suites: BenchmarkSuite[], metadata?: {
    environment?: string;
    timestamp?: Date;
    version?: string;
}): string;
/**
 * Generate JSON report
 */
export declare function generateJsonReport(suites: BenchmarkSuite[], metadata?: Record<string, any>): string;
