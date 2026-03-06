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
export const DEFAULT_CONFIG = {
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
export function findConfigFile(startDir) {
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
export function parseConfigFile(filePath) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const ext = path.extname(filePath).toLowerCase();
    try {
        if (ext === '.yaml' || ext === '.yml') {
            return yaml.load(content);
        }
        else if (ext === '.json') {
            return JSON.parse(content);
        }
        else {
            // Try YAML first, then JSON
            try {
                return yaml.load(content);
            }
            catch {
                return JSON.parse(content);
            }
        }
    }
    catch (error) {
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
export function validateConfig(config) {
    const errors = [];
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
export function mergeConfigs(base, override) {
    const result = { ...base };
    if (override.version)
        result.version = override.version;
    if (override.extensions)
        result.extensions = override.extensions;
    if (override.ignore)
        result.ignore = override.ignore;
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
export function loadConfigWithInheritance(configPath) {
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
export function loadConfig(searchDir, cliOptions) {
    const startDir = searchDir || process.cwd();
    const configPath = findConfigFile(startDir);
    let config = { ...DEFAULT_CONFIG };
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
export function createSampleConfig(outputPath, format = 'yaml') {
    const sampleConfig = {
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
    let content;
    if (format === 'yaml') {
        content = `# Autodocument Configuration\n# See: https://github.com/your-repo/autodocument#configuration\n\n${yaml.dump(sampleConfig, { indent: 2 })}`;
    }
    else {
        content = JSON.stringify(sampleConfig, null, 2);
    }
    fs.writeFileSync(outputPath, content, 'utf-8');
}
//# sourceMappingURL=config-loader.js.map