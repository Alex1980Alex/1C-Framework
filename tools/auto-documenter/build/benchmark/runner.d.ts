/**
 * Benchmark Runner - Core benchmarking infrastructure
 * @module benchmark/runner
 */
/**
 * Result of a single benchmark run
 */
export interface BenchmarkResult {
    /** Benchmark name */
    name: string;
    /** Execution time in milliseconds */
    duration: number;
    /** Memory used in bytes */
    memoryUsed: number;
    /** Number of operations performed */
    operations: number;
    /** Operations per second */
    opsPerSecond: number;
    /** Additional metrics */
    metrics: Record<string, any>;
    /** Timestamp of the run */
    timestamp: Date;
    /** Whether the benchmark succeeded */
    success: boolean;
    /** Error message if failed */
    error?: string;
}
/**
 * Benchmark function signature
 */
export type BenchmarkFn = () => Promise<void> | void;
/**
 * Benchmark configuration
 */
export interface BenchmarkConfig {
    /** Benchmark name */
    name: string;
    /** Function to benchmark */
    fn: BenchmarkFn;
    /** Setup function (runs before benchmark) */
    setup?: () => Promise<void> | void;
    /** Teardown function (runs after benchmark) */
    teardown?: () => Promise<void> | void;
    /** Number of iterations */
    iterations?: number;
    /** Warmup iterations (not counted) */
    warmupIterations?: number;
    /** Timeout in milliseconds */
    timeout?: number;
}
/**
 * Suite of related benchmarks
 */
export interface BenchmarkSuite {
    /** Suite name */
    name: string;
    /** Suite description */
    description: string;
    /** Benchmarks in the suite */
    benchmarks: BenchmarkConfig[];
    /** Results after running */
    results?: BenchmarkResult[];
}
/**
 * Benchmark Runner class
 */
export declare class BenchmarkRunner {
    private results;
    /**
     * Run a single benchmark
     */
    run(config: BenchmarkConfig): Promise<BenchmarkResult>;
    /**
     * Run a suite of benchmarks
     */
    runSuite(suite: BenchmarkSuite): Promise<BenchmarkResult[]>;
    /**
     * Get all results
     */
    getResults(): BenchmarkResult[];
    /**
     * Clear results
     */
    clearResults(): void;
    /**
     * Compare two benchmark results
     */
    static compare(baseline: BenchmarkResult, current: BenchmarkResult): {
        durationChange: number;
        memoryChange: number;
        opsPerSecondChange: number;
        faster: boolean;
        lessMemory: boolean;
    };
}
