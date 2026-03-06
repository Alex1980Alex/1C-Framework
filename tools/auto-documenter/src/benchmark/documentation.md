# Benchmark Documentation

This directory contains modules for benchmarking different aspects of the application, including file analysis and AI provider performance. It also includes utilities for running benchmarks and reporting results.

## `analysis-benchmark.ts`

This module provides functionality to benchmark the performance of file analysis operations.

**Key Features:**

*   **`AnalysisBenchmarkConfig`**: Defines configuration options for analysis benchmarks, such as the target directory, number of iterations, and maximum files to analyze.
*   **`AnalysisBenchmarkResult`**: Extends `BenchmarkResult` to include analysis-specific metrics.
*   **`AnalysisBenchmark` Class**:
    *   Manages the benchmarking process for file analysis.
    *   `getAllFiles()`: Recursively finds all files within a given directory, with an option to limit the number of files.
    *   `getFileStats()`: Calculates total size, average size, and language distribution of files.
    *   `runAnalysisBenchmark()`: Executes a benchmark for analyzing files in a specified directory. It measures performance and includes file statistics in the results.
    *   `runScalabilityBenchmark()`: Runs analysis benchmarks on a directory with varying numbers of files to assess scalability.
    *   `runLanguageBenchmark()`: Compares analysis performance across different programming languages by benchmarking analysis on files grouped by their extensions.

## `index.ts`

This is the main entry point for the benchmarking module. It exports all the public components from the other files in the directory.

**Exports:**

*   `BenchmarkRunner`, `BenchmarkResult`, `BenchmarkSuite` from `./runner.js`.
*   `AnalysisBenchmark` from `./analysis-benchmark.js`.
*   `ProviderBenchmark` from `./provider-benchmark.js`.
*   `formatBenchmarkResults`, `generateBenchmarkReport`, `generateMarkdownReport`, `generateJsonReport` from `./reporter.js`.

## `provider-benchmark.ts`

This module is designed to benchmark the performance of various AI providers.

**Key Features:**

*   **`Provider`**: An enum-like type defining supported AI providers ('gemini', 'groq', 'ollama', 'grok', 'openrouter').
*   **`ProviderBenchmarkConfig`**: Configuration for provider benchmarks, including provider, model, API key, prompt, and iterations.
*   **`ProviderBenchmarkResult`**: Extends `BenchmarkResult` with provider-specific metrics like average response time and tokens per second.
*   **`ProviderBenchmark` Class**:
    *   Orchestrates the benchmarking of AI providers.
    *   `callProvider()`: A private method that acts as a dispatcher to call specific provider APIs.
    *   Includes private methods (`callGemini`, `callGroq`, `callOllama`, `callGrok`, `callOpenRouter`) for interacting with each provider's API.
    *   `runProviderBenchmark()`: Runs a benchmark for a single provider with a given configuration.
    *   `runComparisonBenchmark()`: Compares the performance of all configured providers using a specified prompt.
    *   `runLatencyBenchmark()`: Measures the latency of a specific provider across different prompt complexities.

## `reporter.ts`

This module contains utilities for formatting and generating reports from benchmark results.

**Key Features:**

*   **Formatting Functions**:
    *   `formatBytes()`: Converts byte counts into human-readable strings (e.g., KB, MB).
    *   `formatDuration()`: Converts milliseconds into human-readable time formats (e.g., ms, s, min).
*   **Reporting Functions**:
    *   `formatBenchmarkResult()`: Formats a single `BenchmarkResult` into a readable string.
    *   `formatBenchmarkResults()`: Formats an array of `BenchmarkResult` objects into a tabular summary.
    *   `formatSuiteResults()`: Formats the results of a `BenchmarkSuite`.
    *   `generateBenchmarkReport()`: Creates a comprehensive text-based report from multiple benchmark suites.
    *   `generateMarkdownReport()`: Generates a benchmark report in Markdown format.
    *   `generateJsonReport()`: Outputs benchmark results in JSON format.

## `runner.ts`

This module provides the core infrastructure for running benchmarks.

**Key Features:**

*   **Interfaces**:
    *   `BenchmarkResult`: Defines the structure for storing the outcome of a single benchmark run, including performance metrics, success status, and errors.
    *   `BenchmarkFn`: Represents the function to be benchmarked.
    *   `BenchmarkConfig`: Specifies the configuration for a single benchmark, including the function to run, setup/teardown logic, iterations, and timeouts.
    *   `BenchmarkSuite`: Represents a collection of related benchmarks.
*   **`BenchmarkRunner` Class**:
    *   Manages the execution of benchmarks and suites.
    *   `run()`: Executes a single benchmark according to its configuration, handling warmup, iterations, timing, memory usage, and teardown.
    *   `runSuite()`: Runs all benchmarks within a `BenchmarkSuite`.
    *   `getResults()`: Retrieves all recorded benchmark results.
    *   `clearResults()`: Resets the stored benchmark results.
    *   `compare()`: A static method to compare two `BenchmarkResult` objects and report differences.