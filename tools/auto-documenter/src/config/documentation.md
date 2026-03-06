# Configuration Module Documentation

This module handles the loading, validation, and merging of application configuration. It supports loading from various file formats (YAML, JSON) and allows for configuration inheritance.

## `config-loader.ts`

This file contains the core logic for managing configuration.

### Key Interfaces

*   **`CliConfig`**: Defines options configurable via the command-line interface, such as default provider, model, output format, and verbosity settings.
*   **`DocsConfig`**: Specifies options related to documentation generation, including output filenames, and inclusion of private or internal members.
*   **`WatchConfig`**: Configures the watch mode, including paths to monitor, ignored patterns, debounce delays, and recursive watching.
*   **`CacheConfig`**: Manages cache settings, such as enabling/disabling the cache, specifying a directory, and setting time-to-live and maximum size.
*   **`AutodocConfig`**: Represents the complete configuration structure, encompassing CLI, documentation, watch, cache settings, file extensions, ignore patterns, and provider-specific configurations.

### Core Functions

*   **`findConfigFile(startDir: string)`**: Searches for a configuration file (e.g., `autodoc.config.yaml`, `.autodocrc.json`) starting from `startDir` and moving up through parent directories. Returns the path to the found config file or `null` if none is found.
*   **`parseConfigFile(filePath: string)`**: Reads and parses the content of a configuration file. It automatically detects and handles YAML and JSON formats. Throws a `ConfigurationError` if parsing fails.
*   **`validateConfig(config: AutodocConfig)`**: Validates the structure and values of a given `AutodocConfig` object against predefined rules. Returns an array of validation error messages.
*   **`mergeConfigs(base: AutodocConfig, override: AutodocConfig)`**: Performs a deep merge of two configuration objects. The `override` object's properties take precedence.
*   **`loadConfigWithInheritance(configPath: string)`**: Loads a configuration file and recursively loads any parent configurations specified via the `extends` property, merging them in the correct order.
*   **`loadConfig(searchDir?: string, cliOptions?: Partial<CliConfig>)`**: The main function for loading configuration. It first searches for a config file, then loads and merges it with default settings, and finally applies any provided `cliOptions` as overrides. It returns the final merged configuration and the path to the loaded config file.
*   **`createSampleConfig(outputPath: string, format: 'yaml' | 'json' = 'yaml')`**: Generates a sample configuration file in either YAML or JSON format at the specified `outputPath`.

### Constants

*   **`CONFIG_FILES`**: An array of common configuration file names that `findConfigFile` searches for, ordered by priority.
*   **`DEFAULT_CONFIG`**: An object containing the default configuration values used when no configuration file is found or for properties not specified in a config file.

## `index.ts`

This file serves as the main export point for the configuration module, re-exporting all public members from `config-loader.ts`.

### Exports

*   All exported members from `config-loader.ts` are made available under the `config` module.