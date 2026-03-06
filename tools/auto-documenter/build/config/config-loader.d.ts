/**
 * Configuration file loader
 * Searches for and loads configuration from various file formats
 * @module config/config-loader
 */
/**
 * CLI-specific configuration options
 */
export interface CliConfig {
    /** Default provider */
    provider?: 'gemini' | 'groq' | 'ollama' | 'grok' | 'openrouter';
    /** Default model */
    model?: string;
    /** API key (not recommended in config file) */
    apiKey?: string;
    /** Output format */
    format?: 'console' | 'markdown' | 'json';
    /** Verbose output */
    verbose?: boolean;
    /** Quiet mode */
    quiet?: boolean;
    /** Update existing docs */
    updateExisting?: boolean;
}
/**
 * Documentation generation options
 */
export interface DocsConfig {
    /** Output filename */
    outputFilename?: string;
    /** Include private members */
    includePrivate?: boolean;
    /** Include internal functions */
    includeInternal?: boolean;
    /** Language for BSL docs */
    language?: 'ru' | 'en';
}
/**
 * Watch mode configuration
 */
export interface WatchConfig {
    /** Enable watch mode */
    enabled?: boolean;
    /** Paths to watch */
    include?: string[];
    /** Patterns to ignore */
    exclude?: string[];
    /** Debounce delay in ms */
    debounceMs?: number;
    /** Watch subdirectories */
    recursive?: boolean;
}
/**
 * Cache configuration
 */
export interface CacheConfig {
    /** Enable caching */
    enabled?: boolean;
    /** Cache directory */
    directory?: string;
    /** Time-to-live in seconds */
    ttlSeconds?: number;
    /** Maximum cache size in MB */
    maxSizeMb?: number;
}
/**
 * Full configuration schema
 */
export interface AutodocConfig {
    /** Configuration file version */
    version?: string;
    /** Extends another config file */
    extends?: string;
    /** CLI defaults */
    cli?: CliConfig;
    /** Documentation options */
    docs?: DocsConfig;
    /** Watch mode options */
    watch?: WatchConfig;
    /** Cache options */
    cache?: CacheConfig;
    /** File extensions to process */
    extensions?: string[];
    /** Patterns to ignore */
    ignore?: string[];
    /** Provider-specific settings */
    providers?: {
        gemini?: {
            model?: string;
            temperature?: number;
        };
        groq?: {
            model?: string;
            temperature?: number;
        };
        ollama?: {
            model?: string;
            baseUrl?: string;
        };
        grok?: {
            model?: string;
            temperature?: number;
        };
        openrouter?: {
            model?: string;
            temperature?: number;
        };
    };
}
/**
 * Config file names to search for (in order of priority)
 */
export declare const CONFIG_FILES: string[];
/**
 * Default configuration values
 */
export declare const DEFAULT_CONFIG: AutodocConfig;
/**
 * Find config file in directory and parent directories
 */
export declare function findConfigFile(startDir: string): string | null;
/**
 * Parse config file content
 */
export declare function parseConfigFile(filePath: string): AutodocConfig;
/**
 * Validate configuration
 */
export declare function validateConfig(config: AutodocConfig): string[];
/**
 * Deep merge two config objects
 */
export declare function mergeConfigs(base: AutodocConfig, override: AutodocConfig): AutodocConfig;
/**
 * Load configuration with inheritance support
 */
export declare function loadConfigWithInheritance(configPath: string): AutodocConfig;
/**
 * Load configuration from file or defaults
 *
 * @param searchDir - Directory to start searching for config
 * @param cliOptions - CLI options that override config file
 * @returns Merged configuration
 */
export declare function loadConfig(searchDir?: string, cliOptions?: Partial<CliConfig>): {
    config: AutodocConfig;
    configPath: string | null;
};
/**
 * Create a sample config file
 */
export declare function createSampleConfig(outputPath: string, format?: 'yaml' | 'json'): void;
