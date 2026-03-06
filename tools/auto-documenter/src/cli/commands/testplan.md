# Test Plan for CLI Commands

This document outlines the testing strategy for the provided CLI command modules.

## General Testing Approach

The CLI commands are tested using a combination of:

*   **Unit Tests:** For individual functions and utility modules.
*   **Integration Tests:** To verify the interaction between different components of a command, including CLI argument parsing, core logic execution, and output formatting.
*   **End-to-End (E2E) Tests:** To simulate user interaction with the CLI, testing the complete command execution flow with various inputs and options.

## Mocking Strategy

Dependencies on external services (like AI providers) and file system operations will be mocked to ensure deterministic and fast tests. This includes mocking:

*   File system operations (`fs` module).
*   Network requests to AI APIs.
*   Third-party libraries that are not directly part of the CLI logic.
*   The `commander` library's argument parsing and action execution.

## Test Plan by File

---

### `benchmark.ts`

**Component:** `executeBenchmark` function and `createBenchmarkCommand`

**Testing Type:** Integration and E2E tests.

**Unit Tests:**
*   `executeBenchmark`: Test the logic for constructing `BenchmarkOptions` from raw inputs.
*   `createBenchmarkCommand`: Test the command definition, aliases, arguments, and options parsing.

**Integration Tests:**
*   Test `executeBenchmark` with various `BenchmarkOptions` to ensure correct benchmark suites are selected and executed.
*   Verify the output formatting logic for different `OutputFormat` options ('console', 'markdown', 'json').
*   Test the file saving functionality for the 'output' option.

**E2E Tests:**
*   Run the `benchmark` command with different types (`analysis`, `provider`, `scalability`, `all`) and formats, verifying the output and any generated files.
*   Test with invalid paths to ensure error handling.
*   Test with different iteration and maxFiles values.

**Edge Cases:**
*   `targetPath` does not exist (for analysis/scalability).
*   `iterations` or `maxFiles` are non-numeric or zero.
*   Invalid `type` or `format` options.
*   `output` path is invalid or not writable.
*   Benchmark execution fails internally (e.g., network errors, analysis errors).

**Dependencies to Mock:**
*   `fs.existsSync`, `fs.statSync`, `fs.writeFileSync`, `fs.promises.writeFile`
*   `path.resolve`
*   `AnalysisBenchmark` and `ProviderBenchmark` classes (mock their `runAnalysisBenchmark`, `runScalabilityBenchmark`, and `runComparisonBenchmark` methods).
*   `createOutput` utility.
*   `version` utility.
*   `generateBenchmarkReport`, `generateMarkdownReport`, `generateJsonReport` functions.

---

### `browse.ts`

**Component:** `executeBrowse` function and `createBrowseCommand`

**Testing Type:** Integration and E2E tests.

**Unit Tests:**
*   `executeBrowse`: Test the logic for constructing `BrowseOptions` from raw inputs.
*   `createBrowseCommand`: Test the command definition, aliases, arguments, and options parsing.

**Integration Tests:**
*   Test `executeBrowse` with various `BrowseOptions` to ensure the `DocumentationServer` is initialized correctly.
*   Verify error handling for invalid `targetPath`.
*   Test the handling of `SIGINT` and `SIGTERM` signals.

**E2E Tests:**
*   Run the `browse` command with different ports, hosts, and `noOpen` options.
*   Verify that the server starts successfully and output messages are displayed correctly.
*   Test the shutdown process using Ctrl+C.
*   Test with an invalid `targetPath`.

**Edge Cases:**
*   `targetPath` does not exist.
*   `port` is already in use.
*   `port` is an invalid number.
*   `host` is invalid.
*   `noOpen` option is not respected.

**Dependencies to Mock:**
*   `fs.existsSync`, `fs.statSync`
*   `path.resolve`, `path.basename`
*   `DocumentationServer` class (mock its `start`, `stop`, and `getStats` methods).
*   `createOutput` utility.
*   `process.on` for signal handling.

---

### `diff.ts`

**Component:** `executeDiff` function and `createDiffCommand`

**Testing Type:** Integration and E2E tests.

**Unit Tests:**
*   `executeDiff`: Test the logic for constructing `DiffCLIOptions` from raw inputs.
*   `createDiffCommand`: Test the command definition, aliases, arguments, and options parsing.

**Integration Tests:**
*   Test `executeDiff` with different combinations of options (`ignoreWhitespace`, `includeUnchanged`, `detectBreaking`, `include`, `exclude`).
*   Verify correct behavior when comparing files vs. directories.
*   Test the output formatting for all supported `OutputFormat` options.
*   Test the file writing functionality for the `output` option.
*   Verify the exit code when `detectBreaking` is true and breaking changes are found.

**E2E Tests:**
*   Run the `diff` command comparing two directories with various options.
*   Run the `diff` command comparing two files with various options.
*   Test with include/exclude patterns.
*   Test saving the report to a file.
*   Test with paths that do not exist.
*   Test comparing a file with a directory.

**Edge Cases:**
*   `basePath` or `targetPath` do not exist.
*   `basePath` and `targetPath` are of different types (file vs. directory).
*   Empty directories or files.
*   Invalid include/exclude patterns.
*   `output` path is invalid or not writable.
*   `detectBreaking` enabled with no breaking changes.

**Dependencies to Mock:**
*   `fs.existsSync`, `fs.statSync`, `fs.promises.writeFile`
*   `path.resolve`
*   `DiffTool` class (mock its `compareFiles` and `compareDirectories` methods).
*   `getFormatter` function.
*   `createOutput` utility.
*   `process.exit` (to check exit codes).

---

### `generate.ts`

**Component:** `executeGenerate` function and `createGenerateCommand`

**Testing Type:** Integration and E2E tests.

**Unit Tests:**
*   `executeGenerate`: Test the logic for merging CLI options with configuration files.
*   `getAllFiles`: Test recursive file retrieval with various directory structures, including hidden directories and `node_modules`.
*   `createGenerateCommand`: Test command definition, aliases, arguments, and options parsing.

**Integration Tests:**
*   Test `executeGenerate` with different provider and model configurations.
*   Verify cache initialization and usage if enabled.
*   Test incremental and watch modes.
*   Verify environment variable setup for provider rotation.
*   Test error handling for invalid paths or provider configurations.

**E2E Tests:**
*   Run the `generate` command on a sample directory with different providers and models.
*   Test with cache enabled and disabled.
*   Test watch mode by modifying a file and observing documentation regeneration.
*   Test incremental mode with and without the `force` option.
*   Test with invalid API keys or missing configurations.

**Edge Cases:**
*   `targetPath` does not exist or is not a directory.
*   No code files found in the target directory.
*   Invalid provider or model specified.
*   API key is invalid or missing.
*   Cache directory is not writable.
*   Watch mode file change detection fails.
*   Incremental mode skips files incorrectly.

**Dependencies to Mock:**
*   `fs.existsSync`, `fs.statSync`, `fs.readdirSync`, `fs.promises.writeFile`
*   `path.resolve`, `path.join`
*   `FileAnalyzer` class (mock its `analyzeFiles` method).
*   `DocumentationTool` class (mock its `generate` method).
*   `createOutput` utility.
*   `getApiKey`, `getModel`, `validateProviderConfig`, `loadConfig` utilities.
*   `ResponseCache`, `createCache` functions.
*   `ChangeTracker`, `runIncremental` functions.
*   `WatchModeRunner` class (mock its `start` and `stop` methods).
*   `process.env` manipulation.

---

### `info.ts`

**Component:** `executeInfo` function and `createInfoCommand`

**Testing Type:** Unit and Integration tests.

**Unit Tests:**
*   `checkProviderStatus`: Test the logic for determining provider configuration status for all providers.
*   `executeInfo`: Test the formatting and content of the output for different provider statuses.
*   `createInfoCommand`: Test the command definition and action execution.

**Integration Tests:**
*   Run the `info` command and verify that all sections (Provider Status, Supported Languages, Available Commands, Global Options, Examples, Environment Variables) are displayed correctly.
*   Verify that the `checkProviderStatus` function correctly reflects the environment variables and API key configurations.

**Edge Cases:**
*   No environment variables set for API keys.
*   API keys are set but invalid (this would typically be caught by other commands, but `info` should reflect the *presence* of the key).
*   `verbose` and `quiet` options are handled correctly by `createOutput`.

**Dependencies to Mock:**
*   `version`, `banner` utilities.
*   `PROVIDERS`, `DEFAULT_MODELS` constants.
*   `getApiKey` utility.
*   `createOutput` utility.
*   `process.env` reading.

---

### `inline.ts`

**Component:** `executeInline` function and `createInlineCommand`

**Testing Type:** Integration and E2E tests.

**Unit Tests:**
*   `executeInline`: Test the logic for setting up environment variables and merging options.
*   `getAllFiles`: Test recursive file retrieval (same as in `generate.ts`).
*   `createInlineCommand`: Test command definition, aliases, arguments, and options parsing.

**Integration Tests:**
*   Test `executeInline` with different provider and model configurations.
*   Verify error handling for invalid paths or provider configurations.
*   Test the `update` option.

**E2E Tests:**
*   Run the `inline` command on a sample directory with different providers and models.
*   Test with invalid API keys or missing configurations.
*   Verify that inline documentation is generated and applied to files.

**Edge Cases:**
*   `targetPath` does not exist or is not a directory.
*   No code files found in the target directory.
*   Invalid provider or model specified.
*   API key is invalid or missing.
*   The `InlineDocsTool` fails to generate documentation.

**Dependencies to Mock:**
*   `fs.existsSync`, `fs.statSync`, `fs.readdirSync`
*   `path.resolve`, `path.join`
*   `FileAnalyzer` class (mock its `analyzeFiles` method).
*   `InlineDocsTool` class (mock its `generate` method).
*   `createOutput` utility.
*   `getApiKey`, `getModel`, `validateProviderConfig` utilities.
*   `process.env` manipulation.

---

### `review.ts`

**Component:** `executeReview` function and `createReviewCommand`

**Testing Type:** Integration and E2E tests.

**Unit Tests:**
*   `executeReview`: Test the logic for setting up environment variables and merging options.
*   `getAllFiles`: Test recursive file retrieval (same as in `generate.ts`).
*   `createReviewCommand`: Test command definition, aliases, arguments, and options parsing.

**Integration Tests:**
*   Test `executeReview` with different provider and model configurations.
*   Verify error handling for invalid paths or provider configurations.
*   Test the `update` option.

**E2E Tests:**
*   Run the `review` command on a sample directory with different providers and models.
*   Test with invalid API keys or missing configurations.
*   Verify that code review comments are generated and applied to files.

**Edge Cases:**
*   `targetPath` does not exist or is not a directory.
*   No code files found in the target directory.
*   Invalid provider or model specified.
*   API key is invalid or missing.
*   The `ReviewTool` fails to generate a review.

**Dependencies to Mock:**
*   `fs.existsSync`, `fs.statSync`, `fs.readdirSync`
*   `path.resolve`, `path.join`
*   `FileAnalyzer` class (mock its `analyzeFiles` method).
*   `ReviewTool` class (mock its `generate` method).
*   `createOutput` utility.
*   `getApiKey`, `getModel`, `validateProviderConfig` utilities.
*   `process.env` manipulation.

---

### `testplan.ts`

**Component:** `executeTestplan` function and `createTestplanCommand`

**Testing Type:** Integration and E2E tests.

**Unit Tests:**
*   `executeTestplan`: Test the logic for setting up environment variables and merging options.
*   `getAllFiles`: Test recursive file retrieval (same as in `generate.ts`).
*   `createTestplanCommand`: Test command definition, aliases, arguments, and options parsing.

**Integration Tests:**
*   Test `executeTestplan` with different provider and model configurations.
*   Verify error handling for invalid paths or provider configurations.
*   Test the `update` option.

**E2E Tests:**
*   Run the `testplan` command on a sample directory with different providers and models.
*   Test with invalid API keys or missing configurations.
*   Verify that a test plan is generated and applied to files.

**Edge Cases:**
*   `targetPath` does not exist or is not a directory.
*   No code files found in the target directory.
*   Invalid provider or model specified.
*   API key is invalid or missing.
*   The `TestPlanTool` fails to generate a test plan.

**Dependencies to Mock:**
*   `fs.existsSync`, `fs.statSync`, `fs.readdirSync`
*   `path.resolve`, `path.join`
*   `FileAnalyzer` class (mock its `analyzeFiles` method).
*   `TestPlanTool` class (mock its `generate` method).
*   `createOutput` utility.
*   `getApiKey`, `getModel`, `validateProviderConfig` utilities.
*   `process.env` manipulation.