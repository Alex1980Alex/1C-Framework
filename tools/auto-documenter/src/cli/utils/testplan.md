# Test Plan: CLI Utilities

This document outlines the testing strategy for the CLI utility modules: `options.ts`, `output.ts`, and `version.ts`.

---

## 1. `options.ts`

This module handles CLI global options, provider configurations, and API key/model retrieval.

### 1.1. `setupGlobalOptions(program: Command)`

*   **Test Type:** Unit Tests
*   **Description:** Verifies that `commander` options are correctly added to the program instance. This involves checking option names, descriptions, defaults, and environment variable bindings.
*   **Edge Cases:**
    *   No options provided.
    *   Conflicting option definitions (if `commander` allowed it).
    *   Invalid `choices` for provider.
    *   Missing `default` values.
*   **Dependencies to Mock:**
    *   `commander.Command` and `commander.Option` classes to simulate program and option creation.

### 1.2. `getApiKey(provider: Provider, apiKey?: string)`

*   **Test Type:** Unit Tests
*   **Description:** Tests the logic for retrieving API keys from either the provided `apiKey` argument or environment variables.
*   **Edge Cases:**
    *   `apiKey` is provided.
    *   `apiKey` is not provided, but the corresponding environment variable is set.
    *   `apiKey` is not provided, and the environment variable is not set.
    *   `provider` is 'ollama' (which doesn't require an API key).
    *   Testing with all supported `Provider` types.
*   **Dependencies to Mock:**
    *   `process.env` to simulate environment variable values.

### 1.3. `getModel(provider: Provider, model?: string)`

*   **Test Type:** Unit Tests
*   **Description:** Verifies that the correct model name is returned, prioritizing the provided `model` argument over the default for the given `provider`.
*   **Edge Cases:**
    *   `model` argument is provided.
    *   `model` argument is not provided.
    *   Testing with all supported `Provider` types.
*   **Dependencies to Mock:** None.

### 1.4. `validateProviderConfig(provider: Provider, apiKey?: string)`

*   **Test Type:** Unit Tests
*   **Description:** Checks the validation logic for provider configurations, specifically ensuring API keys are present when required.
*   **Edge Cases:**
    *   `provider` is 'ollama' (should always be valid).
    *   `provider` requires an API key, and `apiKey` is provided.
    *   `provider` requires an API key, and `apiKey` is missing, but the environment variable is set.
    *   `provider` requires an API key, and `apiKey` is missing, and the environment variable is not set.
    *   Testing with all supported `Provider` types.
*   **Dependencies to Mock:**
    *   `process.env` to simulate environment variable values.

---

## 2. `output.ts`

This module provides utility functions for formatted terminal output, including colors and progress indicators.

### 2.1. `Output` Class

*   **Test Type:** Unit Tests
*   **Description:** Tests all public methods of the `Output` class (`success`, `error`, `warn`, `info`, `debug`, `progress`, `header`, `summary`, `log`, `newline`). This involves verifying the correct console methods are called (`log`, `error`, `warn`, `process.stdout.write`) with the expected formatted strings, including color codes and progress bar elements.
*   **Edge Cases:**
    *   `verbose` and `quiet` constructor arguments: Test combinations (e.g., `verbose=true, quiet=false`; `verbose=false, quiet=true`; `verbose=true, quiet=true`; `verbose=false, quiet=false`).
    *   `progress`: Test with `current` equal to `total`, `current` less than `total`, and `current` greater than `total` (though the latter might be an invalid state).
    *   `colorize`: Test with and without `supportsColor` being true.
    *   `summary`: Test with empty data object.
*   **Dependencies to Mock:**
    *   `console.log`, `console.error`, `console.warn` to capture output.
    *   `process.stdout.write` to capture progress bar output.
    *   `process.stdout.isTTY` and `process.env.NO_COLOR` to control color support.

### 2.2. `output` (default instance)

*   **Test Type:** Unit Tests
*   **Description:** Verifies that the default `output` instance is correctly created and behaves as expected. This is largely covered by testing the `Output` class methods, but ensures the default instance is functional.
*   **Edge Cases:** None specific to the default instance beyond those covered by the `Output` class.
*   **Dependencies to Mock:** Same as `Output` Class.

### 2.3. `createOutput(verbose: boolean, quiet: boolean)`

*   **Test Type:** Unit Tests
*   **Description:** Ensures that `createOutput` correctly instantiates and returns an `Output` object with the specified `verbose` and `quiet` settings.
*   **Edge Cases:** Same combinations of `verbose` and `quiet` as for the `Output` class constructor.
*   **Dependencies to Mock:** Same as `Output` Class.

---

## 3. `version.ts`

This module exports version information and a banner for the CLI.

### 3.1. Exports (`version`, `description`, `banner`)

*   **Test Type:** Unit Tests
*   **Description:** Verifies that the exported constants (`version`, `description`, `banner`) contain the expected values. The `banner` should be checked for correct formatting and inclusion of the `version`.
*   **Edge Cases:**
    *   Ensure `version` is a valid semantic version string.
    *   Ensure `banner` includes the correct version number and basic structure.
*   **Dependencies to Mock:** None.