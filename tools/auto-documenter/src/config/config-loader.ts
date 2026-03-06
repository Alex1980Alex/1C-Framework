/**
 * Configuration file loader
 * Searches for and loads configuration from various file formats
 * @module config/config-loader
 */

import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { ConfigurationError } from '../errors/index.js';

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
    gemini?: { model?: string; temperature?: number };
    groq?: { model?: string; temperature?: number };
    ollama?: { model?: string; baseUrl?: string };
    grok?: { model?: string; temperature?: number };
    openrouter?: { model?: string; temperature?: number };
  };
}

/**
 * Config file names to search for (in order of priority)
 */
export const CONFIG_FILES = [
  'autodoc.config.yaml',
  'autodoc.config.yml',
  'autodoc.config.json',
  '.autodocrc.yaml',
  '.autodocrc.yml',
  '.autodocrc.json',
  '.autodocrc'
];

/**
 * Default configuration values
 */
export const DEFAULT_CONFIG: AutodocConfig = {
  version: '1.0',
  cli: {
    provider: 'gemini',
    format: 'markdown',
    verbose: false,
    quiet: false,
    updateExisting: true
  },
  docs: {
    outputFilename: 'documentation.md',
    includePrivate: false,
    includeInternal: false,
    language: 'ru'
  },
  watch: {
    include: ['**/*.ts', '**/*.bsl'],
    exclude: ['**/node_modules/**', '**/dist/**', '**/.git/**'],
    debounceMs: 1000,
    recursive: true
  },
  cache: {
    enabled: true,
    directory: '.autodoc-cache',
    ttlSeconds: 86400, // 24 hours
    maxSizeMb: 100
  },
  extensions: [
    '.ts', '.tsx', '.js', '.jsx',
    '.py', '.java', '.cs', '.go', '.rs',
    '.bsl', '.os'
  ],
  ignore: [
    '**/node_modules/**',
    '**/dist/**',
    '**/build/**',
    '**/.git/**',
    '**/*.min.js',
    '**/*.d.ts'
  ]
};

/**
 * Find config file in directory and parent directories
 */
export function findConfigFile(startDir: string): string | null {
  let currentDir = path.resolve(startDir);
  const root = path.parse(currentDir).root;

  while (currentDir !== root) {
    for (const configFile of CONFIG_FILES) {
      const configPath = path.join(currentDir, configFile);
      if (fs.existsSync(configPath)) {
        return configPath;
      }
    }
    currentDir = path.dirname(currentDir);
  }

  return null;
}

/**
 * Parse config file content
 */
export function parseConfigFile(filePath: string): AutodocConfig {
  const content = fs.readFileSync(filePath, 'utf-8');
  const ext = path.extname(filePath).toLowerCase();

  try {
    if (ext === '.yaml' || ext === '.yml') {
      return yaml.load(content) as AutodocConfig;
    } else if (ext === '.json') {
      return JSON.parse(content);
    } else {
      // Try YAML first, then JSON
      try {
        return yaml.load(content) as AutodocConfig;
      } catch {
        return JSON.parse(content);
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new ConfigurationError(`Failed to parse config file: ${filePath}`, {
      suggestion: `Check that the file is valid ${ext === '.json' ? 'JSON' : 'YAML'}`,
      cause: error instanceof Error ? error : undefined
    });
  }
}

/**
 * Validate configuration
 */
export function validateConfig(config: AutodocConfig): string[] {
  const errors: string[] = [];

  // Validate provider
  if (config.cli?.provider) {
    const validProviders = ['gemini', 'groq', 'ollama', 'grok', 'openrouter'];
    if (!validProviders.includes(config.cli.provider)) {
      errors.push(`Invalid provider: ${config.cli.provider}. Valid: ${validProviders.join(', ')}`);
    }
  }

  // Validate format
  if (config.cli?.format) {
    const validFormats = ['console', 'markdown', 'json'];
    if (!validFormats.includes(config.cli.format)) {
      errors.push(`Invalid format: ${config.cli.format}. Valid: ${validFormats.join(', ')}`);
    }
  }

  // Validate cache settings
  if (config.cache?.ttlSeconds !== undefined && config.cache.ttlSeconds < 0) {
    errors.push('cache.ttlSeconds must be non-negative');
  }

  if (config.cache?.maxSizeMb !== undefined && config.cache.maxSizeMb <= 0) {
    errors.push('cache.maxSizeMb must be positive');
  }

  // Validate watch settings
  if (config.watch?.debounceMs !== undefined && config.watch.debounceMs < 0) {
    errors.push('watch.debounceMs must be non-negative');
  }

  return errors;
}

/**
 * Deep merge two config objects
 */
export function mergeConfigs(base: AutodocConfig, override: AutodocConfig): AutodocConfig {
  const result: AutodocConfig = { ...base };

  if (override.version) result.version = override.version;
  if (override.extensions) result.extensions = override.extensions;
  if (override.ignore) result.ignore = override.ignore;

  // Merge cli
  if (override.cli) {
    result.cli = { ...result.cli, ...override.cli };
  }

  // Merge docs
  if (override.docs) {
    result.docs = { ...result.docs, ...override.docs };
  }

  // Merge watch
  if (override.watch) {
    result.watch = { ...result.watch, ...override.watch };
  }

  // Merge cache
  if (override.cache) {
    result.cache = { ...result.cache, ...override.cache };
  }

  // Merge providers
  if (override.providers) {
    result.providers = {
      ...result.providers,
      gemini: { ...result.providers?.gemini, ...override.providers?.gemini },
      groq: { ...result.providers?.groq, ...override.providers?.groq },
      ollama: { ...result.providers?.ollama, ...override.providers?.ollama },
      grok: { ...result.providers?.grok, ...override.providers?.grok },
      openrouter: { ...result.providers?.openrouter, ...override.providers?.openrouter }
    };
  }

  return result;
}

/**
 * Load configuration with inheritance support
 */
export function loadConfigWithInheritance(configPath: string): AutodocConfig {
  const config = parseConfigFile(configPath);
  const configDir = path.dirname(configPath);

  if (config.extends) {
    const parentPath = path.resolve(configDir, config.extends);
    if (!fs.existsSync(parentPath)) {
      throw new ConfigurationError(`Extended config not found: ${config.extends}`, {
        suggestion: `Check that the file exists at ${parentPath}`
      });
    }
    const parentConfig = loadConfigWithInheritance(parentPath);
    return mergeConfigs(parentConfig, config);
  }

  return config;
}

/**
 * Load configuration from file or defaults
 *
 * @param searchDir - Directory to start searching for config
 * @param cliOptions - CLI options that override config file
 * @returns Merged configuration
 */
export function loadConfig(
  searchDir?: string,
  cliOptions?: Partial<CliConfig>
): { config: AutodocConfig; configPath: string | null } {
  const startDir = searchDir || process.cwd();
  const configPath = findConfigFile(startDir);

  let config: AutodocConfig = { ...DEFAULT_CONFIG };

  if (configPath) {
    const fileConfig = loadConfigWithInheritance(configPath);

    // Validate
    const errors = validateConfig(fileConfig);
    if (errors.length > 0) {
      throw new ConfigurationError(`Invalid configuration in ${configPath}:\n${errors.join('\n')}`, {
        suggestion: 'Fix the configuration errors and try again'
      });
    }

    config = mergeConfigs(config, fileConfig);
  }

  // Apply CLI overrides
  if (cliOptions) {
    config.cli = { ...config.cli, ...cliOptions };
  }

  return { config, configPath };
}

/**
 * Create a sample config file
 */
export function createSampleConfig(outputPath: string, format: 'yaml' | 'json' = 'yaml'): void {
  const sampleConfig: AutodocConfig = {
    version: '1.0',
    cli: {
      provider: 'gemini',
      format: 'markdown',
      verbose: false,
      updateExisting: true
    },
    docs: {
      outputFilename: 'documentation.md',
      includePrivate: false,
      language: 'ru'
    },
    watch: {
      include: ['src/**/*.ts', 'src/**/*.bsl'],
      exclude: ['**/node_modules/**', '**/dist/**'],
      debounceMs: 1000
    },
    cache: {
      enabled: true,
      ttlSeconds: 86400
    },
    extensions: ['.ts', '.js', '.bsl'],
    ignore: ['**/node_modules/**', '**/dist/**']
  };

  let content: string;
  if (format === 'yaml') {
    content = `# Autodocument Configuration\n# See: https://github.com/your-repo/autodocument#configuration\n\n${yaml.dump(sampleConfig, { indent: 2 })}`;
  } else {
    content = JSON.stringify(sampleConfig, null, 2);
  }

  fs.writeFileSync(outputPath, content, 'utf-8');
}
