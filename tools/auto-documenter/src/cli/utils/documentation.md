# CLI Utilities Documentation

This document describes the utility modules for the Command Line Interface (CLI).

## `options.ts`

This module handles the configuration of global command-line options for the CLI application. It defines available AI providers, their default models, and an interface for CLI options.

### Key Features:

*   **Provider Definitions**: Defines a list of supported AI providers (`PROVIDERS`) and maps them to their default models (`DEFAULT_MODELS`).
*   **CLI Options Interface**: Defines the `CLIOptions` interface, outlining all configurable parameters for the CLI.
*   **Global Option Setup**: The `setupGlobalOptions` function integrates these options into a Commander.js program instance, defining flags, defaults, and environment variable fallbacks.
*   **API Key Management**: The `getApiKey` function retrieves API keys from command-line options or environment variables, supporting various providers.
*   **Model Selection**: The `getModel` function determines the AI model to use, prioritizing user-provided models over provider defaults.
*   **Configuration Validation**: The `validateProviderConfig` function checks if necessary API keys are provided for specific AI providers.

### File Relationships:

*   This file is responsible for defining and managing the core configuration options that will be used by the CLI's main command processing logic.

## `output.ts`

This module provides utilities for formatted terminal output, including colored text, progress bars, and structured messages.

### Key Features:

*   **Color Support**: Detects terminal capabilities and applies ANSI color codes for enhanced readability.
*   **Output Formatting**: Offers methods for printing success, error, warning, info, debug, and progress messages.
*   **Progress Bar**: Implements a visual progress bar for long-running operations.
*   **Structured Output**: Provides functions for printing section headers and summary tables.
*   **Output Control**: Allows suppression of non-essential output via `quiet` mode and enables verbose logging.
*   **`Output` Class**: Encapsulates output formatting logic, allowing for customizable instances.
*   **Default Instance**: Exports a default `output` instance for immediate use and a `createOutput` function for custom configurations.

### File Relationships:

*   This module is used throughout the CLI application to provide user feedback and status updates.

## `version.ts`

This module contains static information about the CLI application, including its version, description, and a formatted banner.

### Key Features:

*   **Version Information**: Exports the current `version` string.
*   **Application Description**: Exports a brief `description` of the CLI's purpose.
*   **Welcome Banner**: Exports a multi-line `banner` string for display on startup, including version and key features.

### File Relationships:

*   This module provides essential metadata that can be displayed to the user, often used in conjunction with the output utilities.