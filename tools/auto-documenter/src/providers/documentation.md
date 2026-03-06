# Codebase Documentation

This document provides an overview of the code files in this directory, explaining their functionality and relationships.

## `local-llm-config.ts`

This file contains configuration constants and helper functions for managing local Large Language Models (LLMs), specifically focusing on Ollama.

-   **`OLLAMA_MODELS`**: An object defining various Ollama models categorized by their performance characteristics (fast, balanced, quality, general). Each model entry includes details like description, parameter size, context window, estimated speed, and recommended use cases for documentation tasks.
-   **`DEFAULT_MODELS`**: A mapping of common documentation-related tasks to their recommended default Ollama model names.
-   **`OllamaConfig` / `DEFAULT_OLLAMA_CONFIG`**: Defines and provides default settings for connecting to an Ollama server, including base URL, timeout, and retry configurations.
-   **`LlamaCppConfig` / `DEFAULT_LLAMA_CPP_CONFIG`**: Defines and provides default settings for a potential future integration with `llama.cpp` servers.
-   **Helper Functions**:
    -   `getAvailableOllamaModels()`: Returns a list of all Ollama model names defined in `OLLAMA_MODELS`.
    -   `getRecommendedModel()`: Suggests an Ollama model based on a given task and desired quality/speed trade-off.
    -   `getModelInfo()`: Retrieves detailed information about a specific Ollama model.
    -   `formatModelList()`: Generates a formatted string listing recommended Ollama models for display.

## `ollama-utils.ts`

This file provides utility functions for interacting with the Ollama API, including checking server status, managing model downloads, and performing basic inference tests.

-   **`OllamaStatus` / `PullProgress`**: Interfaces defining the structure for Ollama server status and model pull progress information.
-   **Core Functions**:
    -   `checkOllamaAvailability()`: Pings the Ollama server to determine if it's running and returns its status, version, and a list of installed models.
    -   `isModelAvailable()`: Checks if a specified model is already installed on the local Ollama instance.
    -   `pullModel()`: Initiates the download of a model from the Ollama registry, with support for progress callbacks.
    -   `ensureModelAvailable()`: Orchestrates checking for a model's availability and automatically pulling it if it's missing and auto-pull is enabled.
    -   `getSetupInstructions()`: Provides a guide for setting up Ollama, including installation, server startup, model pulling, and configuration.
    -   `printDiagnostics()`: Outputs detailed information about the current Ollama setup, including server status, installed models, and recommendations for missing models.
    -   `testInference()`: Performs a simple text generation request to a specified Ollama model to verify basic functionality and measure response time.

## `provider-factory.ts`

This file acts as a factory for creating clients for various AI service providers, abstracting away the specifics of each API.

-   **`Provider`**: A type alias representing the supported AI providers (e.g., 'openrouter', 'gemini', 'groq', 'ollama', 'grok').
-   **`ProviderConfig`**: An interface defining the configuration structure for each supported provider, including its API base URL, default model, API key requirement, description, and potential daily limits.
-   **`PROVIDER_CONFIGS`**: A constant object holding the specific configurations for each `Provider`.
-   **`ProviderFactory` Class**:
    -   `createClient()`: The main method for instantiating an OpenAI-compatible client for a given provider, handling API key and base URL configurations.
    -   `getDefaultModel()`: Retrieves the default model name for a specified provider.
    -   `getProviderConfig()`: Returns the configuration details for a provider.
    -   `getAvailableProviders()`: Lists all supported provider names.
    -   `printProviderInfo()`: Displays information about all available providers to the console.
    -   `isValidProvider()`: Validates if a given string corresponds to a supported provider.
    -   `getApiKeyEnvVar()`: Returns the expected environment variable name for a provider's API key.

## `provider-rotation.ts`

This file manages the logic for automatically switching between different AI providers based on availability, error rates, and cost.

-   **`ProviderUsage`**: An interface to track statistics for each provider, including request counts, token usage, error counts, and last used timestamps.
-   **`RotationConfig`**: Defines the configuration for the rotation manager, specifying the primary provider, fallback providers, error thresholds for switching, and whether auto-rotation is enabled.
-   **`ProviderRotationManager` Class**:
    -   Manages the active provider and its configuration.
    -   Tracks usage statistics and costs for each provider.
    -   `setApiKey()` / `setModel()`: Methods to configure API keys and specific models for providers.
    -   `createClient()`: Creates an OpenAI client for the currently active provider, handling fallbacks if initialization fails.
    -   `recordSuccess()` / `recordError()`: Methods to log successful requests and errors, triggering provider fallbacks when error thresholds are met.
    -   `switchToFallback()`: Implements the logic to switch to the next available fallback provider.
    -   `getUsageStats()` / `printUsageStats()`: Provides access to and displays the collected usage statistics and cost information.
    -   `resetStats()`: Clears all usage and cost tracking data.
    -   `checkLimits()`: Performs basic checks against provider-specific limits and configured budget limits.
    -   `setBudgetLimit()` / `getBudgetLimit()`: Manages the overall budget for AI service usage.
    -   `exportCostData()`: Exports cost tracking data in JSON format.
-   **`createDefaultRotationManager()`**: A factory function that creates a `ProviderRotationManager` instance, configuring it based on environment variables for primary provider, API keys, and models.

## File Relationships

-   `local-llm-config.ts` provides model definitions and default configurations used by `ollama-utils.ts` and `provider-factory.ts`.
-   `ollama-utils.ts` offers specific tools for interacting with Ollama, which is one of the providers managed by `provider-factory.ts` and `provider-rotation.ts`.
-   `provider-factory.ts` serves as a central point for creating clients for various AI services, including Ollama and external APIs.
-   `provider-rotation.ts` utilizes `provider-factory.ts` to create clients and manages the switching logic between different providers based on their status and usage tracked internally. It also integrates with cost tracking mechanisms.