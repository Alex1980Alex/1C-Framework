/**
 * Analysis Benchmark - Measure file analysis performance
 * @module benchmark/analysis-benchmark
 */
import { BenchmarkResult, BenchmarkSuite } from './runner.js';
/**
 * Analysis benchmark configuration
 */
export interface AnalysisBenchmarkConfig {
    /** Directory to analyze */
    targetPath: string;
    /** Number of iterations */
    iterations?: number;
    /** Include BSL analysis */
    includeBsl?: boolean;
    /** Maximum files to analyze */
    maxFiles?: number;
}
/**
 * Analysis benchmark results with additional metrics
 */
export type AnalysisBenchmarkResult = BenchmarkResult;
/**
 * Analysis Benchmark class
 */
export declare class AnalysisBenchmark {
    private runner;
    private analyzer;
    constructor();
    /**
     * Get all files in a directory recursively
     */
    private getAllFiles;
    /**
     * Calculate file statistics
     */
    private getFileStats;
    /**
     * Run file analysis benchmark
     */
    runAnalysisBenchmark(config: AnalysisBenchmarkConfig): Promise<AnalysisBenchmarkResult>;
    /**
     * Run benchmark suite for different directory sizes
     */
    runScalabilityBenchmark(basePath: string): Promise<BenchmarkSuite>;
    /**
     * Run language-specific benchmark
     */
    runLanguageBenchmark(targetPath: string): Promise<BenchmarkSuite>;
    /**
     * Get benchmark results
     */
    getResults(): BenchmarkResult[];
}
