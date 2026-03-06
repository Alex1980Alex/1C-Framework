# Tool Documentation

This directory contains modules for automating various development tasks using Large Language Models (LLMs).

## `aggregator.ts`

This module orchestrates the execution of different "auto-tools" (like documentation generation, code review, etc.) across a project's directory structure. It processes directories in a bottom-up fashion, ensuring that child directory content is available when processing parent directories.

**Key Functionality:**

*   **Directory Traversal:** Uses `DirectoryCrawler` to discover and order directories for processing.
*   **File Analysis:** Leverages `FileAnalyzer` to determine if a directory's content is suitable for processing.
*   **Tool Execution:** Integrates with `BaseTool` implementations to generate content for each directory.
*   **Progress Reporting:** Supports a callback mechanism to report progress during the aggregation process.
*   **Result Aggregation:** Collects statistics on successful generations, failures, updates, skips, and fallback file creations.

**Core Components:**

*   `ToolAggregator`: The main class responsible for the aggregation logic.
*   `AggregationResult`: An interface defining the structure of the aggregated results.
*   `ProgressCallback`: A type for the function used to report progress.

## `base-tool.ts`

This file defines the abstract base class and interfaces for all "auto-tools". It establishes a common structure for configuration, execution, and results.

**Key Functionality:**

*   **Abstract Tool Definition:** Provides an abstract `BaseTool` class that concrete tools must extend.
*   **Configuration Management:** Defines `BaseToolConfig` and handles tool-specific configurations.
*   **Result Structure:** Defines `AutoToolResult` for consistent return values from tool operations.
*   **Core Methods:** Declares abstract methods like `generate` and `createFallbackContent` that must be implemented by subclasses.
*   **Helper Methods:** Includes utility methods for retrieving output filenames, fallback filenames, and formatting results.

**Core Components:**

*   `BaseToolConfig`: Interface for tool configuration.
*   `AutoToolResult`: Interface for the result of a tool's operation.
*   `BaseTool`: Abstract class for all auto-tools.

## `diff-formatters.ts`

This module provides various formatters for displaying the results of the `DiffTool`. It supports outputting differences in Markdown, JSON, console-friendly (with colors), and GitHub Actions summary formats.

**Key Functionality:**

*   **Output Formatting:** Implements different strategies for presenting diff results.
*   **Markdown Formatting:** Generates a human-readable Markdown report.
*   **JSON Formatting:** Outputs results in a machine-readable JSON format, suitable for CI/CD pipelines.
*   **Console Formatting:** Provides colored output for terminals.
*   **GitHub Formatting:** Creates output compatible with GitHub Actions job summaries and annotations.
*   **Formatter Factory:** Includes a factory function (`getFormatter`) to easily select the desired formatter.

**Core Components:**

*   `OutputFormat`: Type defining the available output formats.
*   `DiffFormatter`: Interface for all formatter classes.
*   `MarkdownFormatter`, `JsonFormatter`, `ConsoleFormatter`, `GitHubFormatter`: Concrete formatter implementations.
*   `getFormatter`: Factory function.

## `diff-tool.ts`

This module implements a tool for comparing two versions of documentation (files or directories) and reporting the differences. It's designed to be used in CI/CD pipelines to track documentation drift.

**Key Functionality:**

*   **File and Directory Comparison:** Can compare individual files or recursively compare entire directories.
*   **Change Detection:** Identifies added, removed, and modified lines or files.
*   **Breaking Change Detection:** Optionally detects breaking changes in documentation.
*   **Pattern Filtering:** Supports include and exclude patterns for files.
*   **Summary Statistics:** Calculates metrics like total files, changed files, lines added/removed, and breaking changes.
*   **Structured Output:** Returns a detailed `DiffResult` object containing summary and detailed changes.

**Core Components:**

*   `ChangeType`: Enum for different types of changes.
*   `DocumentationChange`: Interface representing a single detected change.
*   `DiffSummary`: Interface for summary statistics.
*   `DiffResult`: Interface for the complete diff output.
*   `DiffOptions`: Interface for configuring the diff operation.
*   `DiffTool`: The main class for performing comparisons.

## `documentation-tool.ts`

This tool is responsible for generating documentation for code files using an LLM. It analyzes code, constructs prompts with relevant context (including BSL and 1C metadata), and generates documentation files.

**Key Functionality:**

*   **Documentation Generation:** Uses `OpenRouterClient` to generate documentation based on code content and context.
*   **Context Enrichment:** Integrates with BSL-specific prompts and 1C metadata analysis to provide richer context to the LLM.
*   **File Analysis Integration:** Works with `AnalysisResult` to process code files.
*   **Update Existing Files:** Supports updating existing documentation files if configured.
*   **Fallback Content:** Generates placeholder content for directories that exceed processing limits.

**Core Components:**

*   `DocumentationToolConfig`: Configuration specific to the documentation tool.
*   `DocumentationTool`: The main class for generating documentation.

## `inline-docs-tool.ts`

This tool focuses on generating inline documentation comments (like JSDoc or BSL comments) directly within code files. It parses code to identify functions, classes, and interfaces, and then uses an LLM to generate documentation for them.

**Key Functionality:**

*   **Symbol Extraction:** Parses TypeScript/JavaScript and BSL code to find exportable symbols (functions, classes, interfaces).
*   **LLM-Powered Documentation:** Uses `OpenRouterClient` to generate documentation comments for extracted symbols.
*   **Contextual Prompts:** Employs specific prompts for BSL code, considering module types and 1C structure.
*   **File Modification:** Directly modifies source files to insert generated documentation comments (can be run in dry-run mode).
*   **Result Reporting:** Outputs a summary and detailed results of the inline documentation process.

**Core Components:**

*   `InlineDocsToolConfig`: Configuration for the inline documentation tool.
*   `InlineDocsFileResult`: Structure for documenting the results for a single file.
*   `ExtendedBSLSymbol`: Enhanced structure for BSL symbols.
*   `InlineDocsTool`: The main class for generating inline documentation.

## `registry.ts`

This module manages a collection of all available "auto-tools". It provides functionality to register new tools, retrieve tools by name, and get metadata about all registered tools.

**Key Functionality:**

*   **Tool Registration:** Allows adding new `BaseTool` implementations to the registry.
*   **Tool Retrieval:** Provides a way to get a specific tool instance by its name.
*   **Tool Metadata:** Exposes methods to get all registered tools or their input schemas.
*   **Centralized Management:** Acts as a central point for discovering and accessing different development automation tools.

**Core Components:**

*   `ToolRegistry`: The main class for managing the tool registry.

## `review-tool.ts`

This tool is designed to perform automated code reviews. It analyzes code files within a directory structure and generates a review report, focusing on aspects like security, best practices, and potential improvements.

**Key Functionality:**

*   **Code Analysis:** Processes code files using `AnalysisResult`.
*   **LLM-Powered Review:** Utilizes `OpenRouterClient` to generate review comments and suggestions.
*   **Contextual Prompts:** Employs different prompts based on whether it's processing the top-level directory or subdirectories.
*   **Update Existing Files:** Supports updating previously generated review files.
*   **Fallback Content:** Generates a placeholder file if a directory exceeds processing limits.

**Core Components:**

*   `ReviewToolConfig`: Configuration for the code review tool.
*   `ReviewTool`: The main class for generating code reviews.

## `testplan-tool.ts`

This tool automates the generation of test plans for code repositories. It analyzes code files and directories to create a structured test plan document.

**Key Functionality:**

*   **Code Analysis:** Processes code files using `AnalysisResult`.
*   **LLM-Powered Test Plan Generation:** Uses `OpenRouterClient` to generate test plan content.
*   **Contextual Prompts:** Adapts prompts based on the processing context (top-level vs. subdirectory).
*   **Update Existing Files:** Allows updating existing test plan files.
*   **Fallback Content:** Creates a fallback file for directories that are too large or complex to process.

**Core Components:**

*   `TestPlanToolConfig`: Configuration for the test plan tool.
*   `TestPlanTool`: The main class for generating test plans.