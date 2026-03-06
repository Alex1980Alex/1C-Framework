# CLI Command Documentation

This document provides an overview of the available commands for the CLI tool.

## Commands

### `benchmark` (alias: `bench`, `b`)

Runs performance benchmarks for various aspects of the tool.

*   **Arguments**:
    *   `[path]`: The directory path for analysis benchmarks. Defaults to the current directory.
*   **Options**:
    *   `-t, --type <type>`: The type of benchmark to run. Options: `analysis`, `provider`, `scalability`, `all`. Defaults to `analysis`.
    *   `-f, --format <format>`: The output format for the benchmark report. Options: `console`, `markdown`, `json`. Defaults to `console`.
    *   `-o, --output <path>`: Path to save the report file.
    *   `-i, --iterations <n>`: Number of iterations for benchmarks. Defaults to `3`.
    *   `--max-files <n>`: Maximum number of files to consider for analysis benchmarks. Defaults to `500`.
    *   `--verbose`: Enable verbose output.
    *   `-q, --quiet`: Enable quiet mode.

### `browse` (alias: `serve`, `view`)

Starts an interactive documentation browser server.

*   **Arguments**:
    *   `[path]`: The directory containing documentation files. Defaults to the current directory.
*   **Options**:
    *   `-p, --port <number>`: The port number for the server. Defaults to `3000`.
    *   `-H, --host <host>`: The host to bind the server to. Defaults to `localhost`.
    *   `--no-open`: Prevents the browser from automatically opening.
    *   `--verbose`: Enable verbose output.
    *   `-q, --quiet`: Enable quiet mode.

### `diff` (alias: `d`, `compare`)

Compares two versions of documentation and generates a diff report.

*   **Arguments**:
    *   `<base>`: The base path (old version) of the documentation to compare (file or directory).
    *   `<target>`: The target path (new version) of the documentation to compare (file or directory).
*   **Options**:
    *   `-f, --format <format>`: The output format for the diff report. Options: `console`, `markdown`, `json`, `github`. Defaults to `console`.
    *   `-o, --output <file>`: Path to save the diff report.
    *   `-w, --ignore-whitespace`: Ignores whitespace changes during comparison.
    *   `-u, --include-unchanged`: Includes unchanged files in the report.
    *   `-b, --detect-breaking`: Detects and flags breaking changes. Defaults to `true`.
    *   `-i, --include <patterns...>`: File patterns to include in the comparison.
    *   `-e, --exclude <patterns...>`: File patterns to exclude from the comparison.
    *   `--verbose`: Enable verbose output.
    *   `-q, --quiet`: Enable quiet mode.

### `generate` (alias: `doc`, `g`)

Generates documentation for a given directory.

*   **Arguments**:
    *   `<path>`: The directory path to document.
*   **Options**:
    *   `-p, --provider <name>`: The AI provider to use (e.g., `gemini`, `groq`, `ollama`).
    *   `-m, --model <name>`: The specific model to use with the provider.
    *   `-k, --api-key <key>`: The API key for the AI provider.
    *   `-u, --update`: Updates existing documentation files.
    *   `-r, --recursive`: Processes directories recursively. Defaults to `true`.
    *   `--verbose`: Enable verbose output.
    *   `-q, --quiet`: Enable quiet mode.
    *   `--cache`: Enable response caching.
    *   `--cache-dir <directory>`: Directory for the cache.
    *   `--watch`: Enable watch mode to automatically regenerate docs on file changes.
    *   `--incremental`: Run documentation generation incrementally, only processing changed files.
    *   `--force`: Force full regeneration even in incremental mode.

### `info`

Displays system information, provider status, supported languages, available commands, global options, and examples.

*   **Options**:
    *   `--verbose`: Enable verbose output.
    *   `-q, --quiet`: Enable quiet mode.

### `inline` (alias: `i`)

Generates inline documentation (e.g., JSDoc, TSDoc, BSL comments) for code files.

*   **Arguments**:
    *   `<path>`: The directory path for generating inline documentation.
*   **Options**:
    *   `-p, --provider <name>`: The AI provider to use.
    *   `-m, --model <name>`: The specific model to use.
    *   `-k, --api-key <key>`: The API key for the AI provider.
    *   `-u, --update`: Updates existing inline documentation.
    *   `--verbose`: Enable verbose output.
    *   `-q, --quiet`: Enable quiet mode.

### `review` (alias: `r`)

Generates a code review for a given directory.

*   **Arguments**:
    *   `<path>`: The directory path to review.
*   **Options**:
    *   `-p, --provider <name>`: The AI provider to use.
    *   `-m, --model <name>`: The specific model to use.
    *   `-k, --api-key <key>`: The API key for the AI provider.
    *   `-u, --update`: Updates existing review files.
    *   `--verbose`: Enable verbose output.
    *   `-q, --quiet`: Enable quiet mode.

### `testplan` (alias: `test`, `t`)

Generates a test plan for a given directory.

*   **Arguments**:
    *   `<path>`: The directory path for test planning.
*   **Options**:
    *   `-p, --provider <name>`: The AI provider to use.
    *   `-m, --model <name>`: The specific model to use.
    *   `-k, --api-key <key>`: The API key for the AI provider.
    *   `-u, --update`: Updates existing test plan files.
    *   `--verbose`: Enable verbose output.
    *   `-q, --quiet`: Enable quiet mode.

## Global Options

These options can be applied to most commands:

*   `-p, --provider <name>`: AI provider (e.g., `gemini`, `groq`, `ollama`, `grok`, `openrouter`).
*   `-m, --model <name>`: Model to use.
*   `-k, --api-key <key>`: API key for the provider.
*   `-u, --update`: Update existing files.
*   `-r, --recursive`: Process recursively (default: `true`).
*   `--verbose`: Enable verbose output.
*   `-q, --quiet`: Enable quiet mode.

## Environment Variables

*   `GEMINI_API_KEY`: Google Gemini API key.
*   `GROQ_API_KEY`: Groq API key.
*   `XAI_API_KEY`: xAI Grok API key.
*   `OPENROUTER_API_KEY`: OpenRouter API key.
*   `PRIMARY_PROVIDER`: Default provider to use.
*   `ENABLE_ROTATION`: Enable provider rotation.