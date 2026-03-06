# Autodocument MCP Server Documentation

This document provides a comprehensive overview of the Autodocument MCP server, explaining its architecture, functionality, and configuration.

## Table of Contents

*   [1. Overview](#1-overview)
*   [2. Architecture](#2-architecture)
    *   [2.1. Core Components](#21-core-components)
    *   [2.2. File Structure](#22-file-structure)
*   [3. Configuration](#3-configuration)
    *   [3.1. `config.ts`](#31-configts)
    *   [3.2. `prompt-config.ts`](#32-prompt-configts)
*   [4. Core Functionality](#4-core-functionality)
    *   [4.1. `index.ts`](#41-indexts)
    *   [4.2. Tools](#42-tools)
        *   [4.2.1. Documentation Generation](#421-documentation-generation)
        *   [4.2.2. Code Review](#422-code-review)
        *   [4.2.3. Test Plan Generation](#423-test-plan-generation)
        *   [4.2.4. Diff Tool](#424-diff-tool)
        *   [4.2.5. Inline Documentation](#425-inline-documentation)
    *   [4.3. Analysis](#43-analysis)
        *   [4.3.1. TypeScript/JavaScript Analysis (`ts-compiler-analyzer.ts`)](#431-typescriptjavascript-analysis-ts-compiler-analyzerts)
        *   [4.3.2. 1C:Enterprise (BSL) Analysis (`bsl-treesitter-analyzer.ts`, `bsl-integration.ts`)](#432-1centerprise-bsl-analysis-bsl-treesitter-analyzer-ts-bsl-integration-ts)
        *   [4.3.3. 1C Structure Analysis (`structure-1c-analyzer.ts`)](#433-1c-structure-analysis-structure-1c-analyzer-ts)
        *   [4.3.4. Metadata Analysis (`metadata-parser.ts`, `form-parser.ts`, etc.)](#434-metadata-analysis-metadata-parser-ts-form-parser-ts-etc)
    *   [4.4. Watch Mode (`watch/`)](#44-watch-mode-watch)
    *   [4.5. Benchmarking (`benchmark/`)](#45-benchmarking-benchmark)
    *   [4.6. Caching (`cache/`)](#46-caching-cache)
    *   [4.7. CLI Interface (`cli/`)](#47-cli-interface-cli)
*   [5. AI Provider Integration](#5-ai-provider-integration)
    *   [5.1. OpenRouter Client (`openrouter/client.ts`)](#51-openrouter-client-openrouterclientts)
    *   [5.2. Provider Rotation (`providers/provider-rotation.ts`)](#52-provider-rotation-providersprovider-rotationts)
    *   [5.3. Local LLM Configuration (`providers/local-llm-config.ts`)](#53-local-llm-configuration-providerslocal-llm-configts)
*   [6. Error Handling (`errors/`)](#6-error-handling-errors)
*   [7. Utilities (`utils/`)](#7-utilities-utils)

---

## 1. Overview

The Autodocument MCP server is a command-line tool designed to automate the process of generating and managing code documentation, code reviews, and test plans. It leverages Large Language Models (LLMs) through various AI providers to analyze code and produce human-readable output in Markdown format. The server operates as a Model Context Protocol (MCP) server, allowing for integration with other tools and systems.

## 2. Architecture

The Autodocument server follows a modular architecture, separating concerns into distinct components for configuration, analysis, tool execution, provider integration, and utilities.

### 2.1. Core Components

*   **MCP Server (`index.ts`):** The main entry point that sets up and runs the MCP server, handling requests for various tools.
*   **Configuration (`config.ts`, `prompt-config.ts`):** Manages application settings, including AI provider details, file processing limits, and documentation output preferences. Prompts are also defined here to guide LLM behavior.
*   **Tools (`tools/`):** Implements specific automation tasks such as documentation generation, code review, test plan creation, diffing, and inline documentation.
*   **Analysis (`analyzer/`):** Contains modules for parsing and analyzing different types of code (TypeScript, JavaScript, BSL, 1C Metadata) to extract relevant information for LLMs.
*   **Crawling (`crawler/`):** Responsible for traversing the file system, identifying relevant files and directories, and respecting configurations like `.gitignore`.
*   **Provider Integration (`openrouter/`, `providers/`):** Handles communication with AI LLM providers, including specific client implementations and logic for provider rotation and cost tracking.
*   **Watch Mode (`watch/`):** Enables automatic regeneration of documentation when file changes are detected.
*   **Benchmarking (`benchmark/`):** Provides tools for performance testing of analysis and AI provider operations.
*   **Caching (`cache/`):** Implements a response cache to reduce LLM token usage and speed up repeated operations.
*   **CLI Interface (`cli/`):** Provides a user-friendly command-line interface for interacting with the Autodocument server.
*   **Error Handling (`errors/`):** Defines custom error types for robust error management.
*   **Utilities (`utils/`):** Contains reusable helper functions for tasks like retries, file system operations, and output formatting.

### 2.2. File Structure

The project is organized into the following top-level directories within `src/`:

*   `analyzer/`: Code analysis modules for various languages and formats.
*   `benchmark/`: Tools for performance benchmarking.
*   `browser/`: Code for the documentation browser interface.
*   `cache/`: Response caching mechanism.
*   `cli/`: Command-line interface implementation.
*   `config/`: Configuration loading and management.
*   `cost/`: Cost tracking for AI provider usage.
*   `crawler/`: File system traversal utilities.
*   `errors/`: Custom error definitions.
*   `documentation/`: Core documentation generation logic.
*   `incremental/`: Logic for incremental documentation updates.
*   `metadata/`: Specific analysis for 1C:Enterprise metadata.
*   `openrouter/`: Client for interacting with OpenRouter and other AI providers.
*   `providers/`: Abstractions and configurations for AI providers.
*   `prompts/`: Prompt templates for LLM interactions.
*   `tools/`: Implementations of various automation tools (documentation, review, etc.).
*   `watch/`: File watching and automatic regeneration logic.
*   `utils/`: General utility functions.

## 3. Configuration

Configuration is managed through `config.ts` and `prompt-config.ts`, allowing customization of the server's behavior.

### 3.1. `config.ts`

*   **`AutodocumentConfig` Interface:** Defines the structure for all configuration settings.
*   **`defaultConfig`:** Provides default values for all configuration parameters.
*   **`getConfig()` Function:** Loads configuration by merging default values with environment variables and optional overrides.
    *   **`openRouter`:** Settings for the AI provider, including API key, model, base URL, temperature, and max tokens.
    *   **`fileProcessing`:** Parameters for analyzing code files, such as supported extensions, maximum file size, and maximum files per directory.
    *   **`documentation`:** Settings for outputting documentation, including filenames and whether to update existing files.

### 3.2. `prompt-config.ts`

This file centralizes prompt templates used by various tools, allowing for easy customization of LLM behavior without modifying core code.

*   **`documentationPrompts`:** Contains prompts for generating documentation, with variations for system prompts, top-level directories, and directories with subdirectories.
*   **`testPlanPrompts`:** Provides prompts for generating test plans, similarly tailored for different contexts.
*   **`codeReviewPrompts`:** Offers prompts for generating code reviews, focusing on security, best practices, and potential bugs.
*   **`updateExistingContentPrompt`:** A specific prompt used when updating existing documentation to guide the LLM in reviewing and modifying current content.

## 4. Core Functionality

### 4.1. `index.ts`

*   **MCP Server Setup:** Initializes and runs the MCP server using `@modelcontextprotocol/sdk`.
*   **Tool Registration:** Registers available tools (`ListToolsRequestSchema`, `CallToolRequestSchema`) with the MCP server.
*   **Tool Execution:** Handles incoming tool calls, validates arguments, and invokes the appropriate tool logic via the `ToolRegistry` and `ToolAggregator`.
*   **Configuration Loading:** Loads the application configuration using `getConfig()`.
*   **Error Handling:** Sets up global error handlers for MCP errors and process signals.

### 4.2. Tools

The `tools/` directory contains implementations for various automated development tasks.

#### 4.2.1. Documentation Generation (`documentation-tool.ts`)

*   Analyzes code files using information from `analyzer/` and `crawler/`.
*   Constructs prompts using `prompt-config.ts` and `prompts/` modules.
*   Interacts with AI providers via `openrouter/client.ts` to generate Markdown documentation.
*   Supports recursive processing, updating existing files, and creating fallback files for large directories.

#### 4.2.2. Code Review (`review-tool.ts`)

*   Analyzes code using context-aware prompts for top-level and subdirectories.
*   Generates code review reports focusing on security, best practices, and potential bugs.
*   Leverages AI providers for review generation.

#### 4.2.3. Test Plan Generation (`testplan-tool.ts`)

*   Analyzes code to identify testing needs, edge cases, and dependencies.
*   Generates comprehensive test plans using AI.
*   Adapts prompts based on directory context.

#### 4.2.4. Diff Tool (`diff-tool.ts`)

*   Compares two versions of documentation (files or directories).
*   Reports differences, including added, removed, and modified content.
*   Supports various output formats (Markdown, JSON, console) via `diff-formatters.ts`.
*   Useful for tracking documentation drift in CI/CD pipelines.

#### 4.2.5. Inline Documentation (`inline-docs-tool.ts`)

*   Parses code (TypeScript, JavaScript, BSL) to identify symbols (functions, classes, etc.).
*   Generates inline documentation comments (JSDoc, TSDoc, BSL comments) using LLMs.
*   Can directly modify source files to insert comments.

### 4.3. Analysis

The `analyzer/` directory provides robust code parsing and analysis capabilities.

#### 4.3.1. TypeScript/JavaScript Analysis (`ts-compiler-analyzer.ts`)

*   Utilizes the TypeScript Compiler API for accurate parsing of `.ts` and `.js` files.
*   Extracts symbols, including functions, classes, interfaces, and their properties (parameters, JSDoc, export status).

#### 4.3.2. 1C:Enterprise (BSL) Analysis (`bsl-treesitter-analyzer.ts`, `bsl-integration.ts`)

*   Employs Tree-sitter for efficient and accurate parsing of BSL code.
*   Identifies procedures, functions, regions, export declarations, and comments.
*   Provides formatted Markdown output and LLM-friendly summaries of BSL code.

#### 4.3.3. 1C Structure Analysis (`structure-1c-analyzer.ts`)

*   Analyzes file paths to identify 1C:Enterprise metadata object types and module types based on naming conventions.
*   Provides context information for LLM prompts related to 1C structure.

#### 4.3.4. Metadata Analysis (`metadata-parser.ts`, `form-parser.ts`, etc.)

*   Parses 1C metadata XML files (`Form.xml`, general metadata files).
*   Extracts form structures, controls, attributes, events, and commands.
*   Validates form integrity by cross-referencing XML definitions with BSL code (`form-validator.ts`, `form-extended-validator.ts`).
*   Detects event handlers in form modules (`event-handler-detector.ts`).

### 4.4. Watch Mode (`watch/`)

*   **`file-watcher.ts`:** Monitors file system events (changes, additions, deletions) in specified directories.
*   **`WatchModeRunner`:** Manages the watcher, triggers documentation regeneration upon detected changes, and logs progress.
*   Supports configuration for include/exclude patterns, debouncing, and polling.

### 4.5. Benchmarking (`benchmark/`)

*   **`analysis-benchmark.ts`:** Benchmarks the performance of file analysis operations.
*   **`provider-benchmark.ts`:** Benchmarks the performance of different AI providers.
*   **`runner.ts`:** Core infrastructure for running benchmarks.
*   **`reporter.ts`:** Utilities for formatting and generating benchmark reports (Markdown, JSON).

### 4.6. Caching (`cache/`)

*   **`response-cache.ts`:** Implements a response cache for LLM API calls.
*   Stores responses based on content hash, provider, and model to reduce token usage and improve speed.
*   Manages cache size, expiration (TTL), and statistics.
*   Provides a `withCache` higher-order function to wrap AI calls.

### 4.7. CLI Interface (`cli/`)

*   **`index.ts`:** The main entry point for the command-line tool, using `commander`.
*   Defines commands for `generate`, `review`, `testplan`, `inline`, `diff`, `benchmark`, `browse`, and `info`.
*   Manages global options (provider, model, API key, etc.) via `utils/options.ts`.
*   Handles argument parsing and displays help information.

## 5. AI Provider Integration

The server supports multiple AI providers, with flexibility for configuration and rotation.

### 5.1. OpenRouter Client (`openrouter/client.ts`)

*   Provides a unified client interface using the OpenAI SDK, compatible with OpenRouter and other OpenAI-compatible APIs.
*   Handles API key management, model selection, and base URL configuration.
*   Includes logic for interacting with the `ProviderRotationManager` when rotation is enabled.
*   Manages request parameters like temperature and max tokens.
*   Implements methods for generating documentation with custom prompts and handling responses.

### 5.2. Provider Rotation (`providers/provider-rotation.ts`)

*   Manages a list of AI providers and automatically switches between them based on availability, error rates, and cost.
*   Tracks usage statistics (requests, tokens, errors) for each provider.
*   Allows configuration of primary and fallback providers.
*   Integrates with cost tracking (`cost/`) to monitor overall expenses.
*   Provides methods to create clients for the currently active provider.

### 5.3. Local LLM Configuration (`providers/local-llm-config.ts`)

*   Contains configurations and helper functions for using local LLMs, primarily Ollama.
*   Defines recommended models for different tasks and quality/speed trade-offs.
*   Provides utilities for checking Ollama server status, managing model downloads, and testing inference.

## 6. Error Handling (`errors/`)

*   Defines a hierarchy of custom error classes (`AutodocError`, `ConfigurationError`, `FileSystemError`, `ProviderError`, `ParserError`, `ValidationError`, `TimeoutError`) for structured error management.
*   Provides utility functions like `wrapError`, `isRetryableError`, and `getSuggestion` to standardize error handling and reporting.
*   Includes retry logic (`utils/retry.ts`) that integrates with these error types.

## 7. Utilities (`utils/`)

*   **`retry.ts`:** Implements robust retry logic with exponential backoff, jitter, and customizable retry conditions, essential for handling transient network or API errors.
*   **`version.ts`:** Provides application version and description information used by the CLI.
*   **`options.ts`:** Handles the parsing and validation of global CLI options.
*   **`output.ts`:** Provides utilities for formatted console output, including colors and progress bars.
*   **`fs.ts`:** General file system utility functions.