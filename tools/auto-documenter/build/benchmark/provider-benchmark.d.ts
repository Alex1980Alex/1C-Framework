/**
 * Provider Benchmark - Measure AI provider performance
 * @module benchmark/provider-benchmark
 */
import { BenchmarkResult, BenchmarkSuite } from './runner.js';
/**
 * Provider types
 */
export type Provider = 'gemini' | 'groq' | 'ollama' | 'grok' | 'openrouter';
/**
 * Provider benchmark configuration
 */
export interface ProviderBenchmarkConfig {
    /** Provider to benchmark */
    provider: Provider;
    /** Model to use */
    model?: string;
    /** API key (if required) */
    apiKey?: string;
    /** Number of iterations */
    iterations?: number;
    /** Prompt to use */
    prompt?: string;
    /** Maximum tokens in response */
    maxTokens?: number;
}
/**
 * Provider benchmark result with additional metrics
 */
export type ProviderBenchmarkResult = BenchmarkResult;
/**
 * Provider Benchmark class
 */
export declare class ProviderBenchmark {
    private runner;
    constructor();
    /**
     * Make API call to provider
     */
    private callProvider;
    /**
     * Call Gemini API
     */
    private callGemini;
    /**
     * Call Groq API
     */
    private callGroq;
    /**
     * Call Ollama API
     */
    private callOllama;
    /**
     * Call Grok API
     */
    private callGrok;
    /**
     * Call OpenRouter API
     */
    private callOpenRouter;
    /**
     * Run provider benchmark
     */
    runProviderBenchmark(config: ProviderBenchmarkConfig): Promise<ProviderBenchmarkResult>;
    /**
     * Run comparison benchmark across all available providers
     */
    runComparisonBenchmark(prompt?: string, iterations?: number): Promise<BenchmarkSuite>;
    /**
     * Run latency benchmark with different prompt sizes
     */
    runLatencyBenchmark(provider: Provider): Promise<BenchmarkSuite>;
    /**
     * Get benchmark results
     */
    getResults(): BenchmarkResult[];
}
