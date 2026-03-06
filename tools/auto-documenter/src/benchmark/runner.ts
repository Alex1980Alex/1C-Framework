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
export class BenchmarkRunner {
  private results: BenchmarkResult[] = [];

  /**
   * Run a single benchmark
   */
  async run(config: BenchmarkConfig): Promise<BenchmarkResult> {
    const {
      name,
      fn,
      setup,
      teardown,
      iterations = 1,
      warmupIterations = 0,
      timeout = 300000 // 5 minutes default
    } = config;

    // Setup
    if (setup) {
      await setup();
    }

    // Warmup runs
    for (let i = 0; i < warmupIterations; i++) {
      await fn();
    }

    // Force garbage collection if available
    if (global.gc) {
      global.gc();
    }

    const startMemory = process.memoryUsage().heapUsed;
    const startTime = performance.now();

    let success = true;
    let error: string | undefined;

    try {
      // Actual benchmark runs
      for (let i = 0; i < iterations; i++) {
        const iterStart = performance.now();
        await fn();
        const iterDuration = performance.now() - iterStart;

        // Check timeout
        if (iterDuration > timeout) {
          throw new Error(`Benchmark timeout: ${iterDuration}ms > ${timeout}ms`);
        }
      }
    } catch (e: any) {
      success = false;
      error = e.message;
    }

    const endTime = performance.now();
    const endMemory = process.memoryUsage().heapUsed;

    // Teardown
    if (teardown) {
      await teardown();
    }

    const duration = endTime - startTime;
    const memoryUsed = Math.max(0, endMemory - startMemory);
    const opsPerSecond = iterations / (duration / 1000);

    const result: BenchmarkResult = {
      name,
      duration,
      memoryUsed,
      operations: iterations,
      opsPerSecond,
      metrics: {
        avgDuration: duration / iterations,
        minMemory: startMemory,
        maxMemory: endMemory
      },
      timestamp: new Date(),
      success,
      error
    };

    this.results.push(result);
    return result;
  }

  /**
   * Run a suite of benchmarks
   */
  async runSuite(suite: BenchmarkSuite): Promise<BenchmarkResult[]> {
    const results: BenchmarkResult[] = [];

    for (const benchmark of suite.benchmarks) {
      const result = await this.run(benchmark);
      results.push(result);
    }

    suite.results = results;
    return results;
  }

  /**
   * Get all results
   */
  getResults(): BenchmarkResult[] {
    return [...this.results];
  }

  /**
   * Clear results
   */
  clearResults(): void {
    this.results = [];
  }

  /**
   * Compare two benchmark results
   */
  static compare(baseline: BenchmarkResult, current: BenchmarkResult): {
    durationChange: number;
    memoryChange: number;
    opsPerSecondChange: number;
    faster: boolean;
    lessMemory: boolean;
  } {
    const durationChange = ((current.duration - baseline.duration) / baseline.duration) * 100;
    const memoryChange = ((current.memoryUsed - baseline.memoryUsed) / (baseline.memoryUsed || 1)) * 100;
    const opsPerSecondChange = ((current.opsPerSecond - baseline.opsPerSecond) / baseline.opsPerSecond) * 100;

    return {
      durationChange,
      memoryChange,
      opsPerSecondChange,
      faster: current.duration < baseline.duration,
      lessMemory: current.memoryUsed < baseline.memoryUsed
    };
  }
}
