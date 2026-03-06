/**
 * Benchmark Runner - Core benchmarking infrastructure
 * @module benchmark/runner
 */
/**
 * Benchmark Runner class
 */
export class BenchmarkRunner {
    constructor() {
        this.results = [];
    }
    /**
     * Run a single benchmark
     */
    async run(config) {
        const { name, fn, setup, teardown, iterations = 1, warmupIterations = 0, timeout = 300000 // 5 minutes default
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
        let error;
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
        }
        catch (e) {
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
        const result = {
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
    async runSuite(suite) {
        const results = [];
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
    getResults() {
        return [...this.results];
    }
    /**
     * Clear results
     */
    clearResults() {
        this.results = [];
    }
    /**
     * Compare two benchmark results
     */
    static compare(baseline, current) {
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
//# sourceMappingURL=runner.js.map