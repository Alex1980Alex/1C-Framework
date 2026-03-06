# Documentation Structure

This directory contains the core logic for analyzing code files, generating documentation, and aggregating these results across a project.

## File: `aggregator.ts`

This file defines the `DocumentationAggregator` class, which orchestrates the entire documentation generation process. It handles the traversal of directories, analysis of files, and the generation of documentation using other components.

### Key Functionality:

*   **Bottom-Up Processing:** The aggregator processes directories in a bottom-up fashion, ensuring that documentation for subdirectories is available when documenting parent directories.
*   **Directory Traversal:** It utilizes `DirectoryCrawler` to discover directories and files, respecting `.gitignore` rules.
*   **File Analysis:** It uses `FileAnalyzer` to determine if a directory's files are suitable for documentation based on size and count limits.
*   **Documentation Generation:** It delegates the actual documentation creation to `DocumentationGenerator`.
*   **Aggregation of Results:** It collects statistics on the overall documentation process, including the number of directories processed, successful generations, failures, and skipped files.
*   **Progress Reporting:** Supports an optional callback to provide real-time updates on the aggregation progress.

### Key Classes:

*   `DocumentationAggregator`: The main class responsible for managing the documentation workflow.

### Key Interfaces:

*   `AggregationResult`: Defines the structure of the results returned after the aggregation process.
*   `ProgressCallback`: Defines the signature for functions that can receive progress updates.

## File: `generator.ts`

This file defines the `DocumentationGenerator` class, responsible for creating documentation files. It interacts with an LLM (via `OpenRouterClient`) to generate content and manages the writing of these files to the filesystem.

### Key Functionality:

*   **LLM Interaction:** Uses `OpenRouterClient` to request documentation content based on analyzed code and existing documentation.
*   **File Handling:** Reads existing documentation files and writes newly generated ones.
*   **Update Logic:** Manages whether to update existing documentation files based on the `updateExisting` configuration.
*   **Skipping Logic:** Skips documentation generation for existing files if `updateExisting` is set to false.
*   **Handling Large Directories:** Creates a fallback `undocumented.md` file for directories that exceed analysis limits, providing reasons for the skip.

### Key Classes:

*   `DocumentationGenerator`: Handles the generation and writing of documentation files.

### Key Interfaces:

*   `DocumentationResult`: Defines the structure of the result for a single documentation generation operation.

## File Relationships:

*   `aggregator.ts` depends on `generator.ts` (and implicitly on `analyzer.ts` and `crawler.ts` through its constructor and internal calls).
*   `generator.ts` depends on `analyzer.ts` (for `AnalysisResult`) and `openrouter/client.ts` for LLM interaction.
*   The `DocumentationAggregator` class uses the `DocumentationGenerator` class to perform the actual documentation creation for each directory. The aggregator provides the context (directory path, analysis results, and subdirectory documentation) to the generator.