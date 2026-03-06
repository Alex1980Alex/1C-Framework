# Autodocument CLI Documentation

This document provides a comprehensive overview of the Autodocument Command Line Interface (CLI) tool. It details the functionality of the main entry point (`index.ts`) and integrates information from the `commands` and `utils` subdirectories to illustrate how different components work together.

## `index.ts` - Main CLI Entry Point

The `index.ts` file serves as the primary entry point for the Autodocument CLI. It is responsible for:

*   **Initializing the CLI Application**: It sets up the core structure of the command-line interface using the `commander` library.
*   **Defining Commands**: It registers various commands, each corresponding to a specific documentation-related task. These commands include:
    *   `generate`: For automatic code documentation generation.
    *   `review`: For generating code reviews.
    *   `testplan`: For creating test plans.
    *   `inline`: For generating inline code documentation.
    *   `info`: For displaying system and configuration information.
    *   `benchmark`: For running performance benchmarks.
    *   `browse`: For starting an interactive documentation browser.
    *   `diff`: For comparing documentation versions.
*   **Handling Global Options**: It integrates global options that can be applied across multiple commands, managed by the `setupGlobalOptions` utility.
*   **Parsing Arguments**: It parses the command-line arguments provided by the user.
*   **Displaying Help**: If no command is specified, it automatically displays the help information.
*   **Error Handling**: It includes a top-level error handler to catch and report any issues during execution.

The `index.ts` file orchestrates the user's interaction with the Autodocument tool, routing requests to the appropriate command handlers and ensuring a consistent user experience.

## Integrated Subdirectory Documentation

This section combines information from the `commands` and `utils` subdirectories to provide a holistic view of the CLI's capabilities and how its components interact.

### Command Functionality

The `commands` directory houses the logic for each individual CLI command. These commands leverage various utilities and external services to perform their tasks.

*   **`generate`**: This command is the core documentation generation feature. It takes a directory path as input and uses specified AI providers and models to create documentation. It supports recursive processing, updating existing files, and incremental generation.
*   **`review`**: This command analyzes code within a specified directory to generate a code review. It also utilizes AI providers and models for this task and can update existing review files.
*   **`testplan`**: Similar to `review`, this command focuses on generating a test plan for the code in a given directory, leveraging AI capabilities.
*   **`inline`**: This command is designed to add inline documentation comments (like JSDoc or TSDoc) directly into code files, again powered by AI.
*   **`diff`**: This command compares two versions of documentation (specified by base and target paths) and generates a report highlighting differences. It offers options to ignore whitespace, include unchanged files, and detect breaking changes.
*   **`benchmark`**: This command is used for performance testing. It can run benchmarks on analysis, AI provider performance, or scalability, with options for output format and iterations.
*   **`browse`**: This command starts a local web server to provide an interactive way to view generated documentation.
*   **`info`**: This command provides valuable system information, including details about supported AI providers, languages, available commands, global options, and usage examples.

### Utility Functions and Their Roles

The `utils` directory contains helper modules that support the core functionality of the CLI, particularly in `index.ts` and the command handlers.

*   **`options.ts`**: This module is crucial for managing how the CLI accepts and interprets user configurations. It defines the available AI providers and their default models, and the `setupGlobalOptions` function within it is called by `index.ts` to register these options with the command parser. It also handles API key retrieval and model selection, ensuring that commands have the necessary configuration to interact with AI services. The `validateProviderConfig` function ensures that essential keys are present before a command attempts to use a provider.
*   **`output.ts`**: This module is responsible for all user-facing output. It provides functions for displaying messages in various formats (success, error, info, debug), using colors for clarity, and showing progress bars for long operations. This utility is used extensively by all commands to provide feedback to the user.
*   **`version.ts`**: This module provides static metadata about the CLI application, such as its version number and a descriptive banner. This information is used by `index.ts` for displaying version details and potentially in the welcome banner.

### Integration Example: Generating Documentation

When you run the `autodoc generate <path>` command:

1.  `index.ts` receives the command and its arguments.
2.  It uses `commander` to parse the arguments, including any specific options for the `generate` command.
3.  The `setupGlobalOptions` function (from `utils/options.ts`) has already configured global options like AI provider and model selection.
4.  The `generate` command handler (defined in `commands/generate.ts`) is invoked.
5.  This handler uses utilities from `utils/options.ts` (like `getApiKey`, `getModel`, `validateProviderConfig`) to get the necessary AI configuration.
6.  It then interacts with the specified AI provider to generate documentation for the provided `<path>`.
7.  Throughout the process, the `output.ts` utility is used to display progress, success messages, or errors to the user.
8.  If the `--verbose` option is used, more detailed output from `utils/output.ts` is shown.

This demonstrates how `index.ts` acts as the orchestrator, `commands` provide specific task logic, and `utils` offer reusable functionalities for configuration, output, and metadata management.