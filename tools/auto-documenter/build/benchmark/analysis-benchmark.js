/**
 * Analysis Benchmark - Measure file analysis performance
 * @module benchmark/analysis-benchmark
 */
import * as fs from 'fs';
import * as path from 'path';
import { BenchmarkRunner } from './runner.js';
import { FileAnalyzer } from '../analyzer/index.js';
/**
 * Analysis Benchmark class
 */
export class AnalysisBenchmark {
    constructor() {
        this.runner = new BenchmarkRunner();
        this.analyzer = new FileAnalyzer();
    }
    /**
     * Get all files in a directory recursively
     */
    getAllFiles(dirPath, maxFiles = Infinity) {
        const files = [];
        const traverse = (currentPath) => {
            if (files.length >= maxFiles)
                return;
            try {
                const entries = fs.readdirSync(currentPath);
                for (const entry of entries) {
                    if (files.length >= maxFiles)
                        break;
                    const fullPath = path.join(currentPath, entry);
                    try {
                        const stat = fs.statSync(fullPath);
                        if (stat.isDirectory()) {
                            if (!entry.startsWith('.') && entry !== 'node_modules') {
                                traverse(fullPath);
                            }
                        }
                        else {
                            files.push(fullPath);
                        }
                    }
                    catch {
                        // Skip inaccessible files
                    }
                }
            }
            catch {
                // Skip inaccessible directories
            }
        };
        traverse(dirPath);
        return files;
    }
    /**
     * Calculate file statistics
     */
    getFileStats(files) {
        let totalSize = 0;
        const languageBreakdown = {};
        for (const file of files) {
            try {
                const stat = fs.statSync(file);
                totalSize += stat.size;
                const ext = path.extname(file).toLowerCase();
                languageBreakdown[ext] = (languageBreakdown[ext] || 0) + 1;
            }
            catch {
                // Skip
            }
        }
        return {
            totalSize,
            avgSize: files.length > 0 ? totalSize / files.length : 0,
            languageBreakdown
        };
    }
    /**
     * Run file analysis benchmark
     */
    async runAnalysisBenchmark(config) {
        const { targetPath, iterations = 3, maxFiles = 1000 } = config;
        const absolutePath = path.resolve(targetPath);
        if (!fs.existsSync(absolutePath)) {
            throw new Error(`Path does not exist: ${absolutePath}`);
        }
        // Get files
        const files = this.getAllFiles(absolutePath, maxFiles);
        const fileStats = this.getFileStats(files);
        let analysisResult;
        const benchmarkConfig = {
            name: `File Analysis: ${path.basename(absolutePath)}`,
            fn: async () => {
                analysisResult = await this.analyzer.analyzeFiles(absolutePath, files);
            },
            iterations,
            warmupIterations: 1
        };
        const result = await this.runner.run(benchmarkConfig);
        // Enhance result with analysis-specific metrics
        const enhancedResult = {
            ...result,
            metrics: {
                ...result.metrics,
                filesAnalyzed: analysisResult?.analyzedFiles?.length || 0,
                filesPerSecond: (analysisResult?.analyzedFiles?.length || 0) / (result.duration / 1000),
                avgFileSize: fileStats.avgSize,
                totalSize: fileStats.totalSize,
                languageBreakdown: fileStats.languageBreakdown
            }
        };
        return enhancedResult;
    }
    /**
     * Run benchmark suite for different directory sizes
     */
    async runScalabilityBenchmark(basePath) {
        const suite = {
            name: 'Scalability Benchmark',
            description: 'Measure performance across different directory sizes',
            benchmarks: []
        };
        const sizes = [10, 50, 100, 500, 1000];
        const results = [];
        for (const maxFiles of sizes) {
            const result = await this.runAnalysisBenchmark({
                targetPath: basePath,
                maxFiles,
                iterations: 3
            });
            result.name = `Analysis (${maxFiles} files)`;
            results.push(result);
        }
        suite.results = results;
        return suite;
    }
    /**
     * Run language-specific benchmark
     */
    async runLanguageBenchmark(targetPath) {
        const suite = {
            name: 'Language Benchmark',
            description: 'Compare analysis performance across languages',
            benchmarks: []
        };
        const files = this.getAllFiles(targetPath);
        const byExtension = {};
        // Group files by extension
        for (const file of files) {
            const ext = path.extname(file).toLowerCase();
            if (!byExtension[ext]) {
                byExtension[ext] = [];
            }
            byExtension[ext].push(file);
        }
        const results = [];
        // Benchmark each language
        for (const [ext, extFiles] of Object.entries(byExtension)) {
            if (extFiles.length < 5)
                continue; // Skip if too few files
            const config = {
                name: `Language: ${ext || 'no-ext'}`,
                fn: async () => {
                    await this.analyzer.analyzeFiles(targetPath, extFiles.slice(0, 100));
                },
                iterations: 3,
                warmupIterations: 1
            };
            const result = await this.runner.run(config);
            result.metrics.fileCount = extFiles.length;
            results.push(result);
        }
        suite.results = results;
        return suite;
    }
    /**
     * Get benchmark results
     */
    getResults() {
        return this.runner.getResults();
    }
}
//# sourceMappingURL=analysis-benchmark.js.map