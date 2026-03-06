/**
 * CLI Global Options Configuration
 * @module cli/utils/options
 */
import { Option } from 'commander';
/**
 * Available AI providers
 */
export const PROVIDERS = ['gemini', 'groq', 'ollama', 'grok', 'openrouter'];
/**
 * Default models per provider
 */
export const DEFAULT_MODELS = {
    gemini: 'gemini-2.5-flash-lite', // Fast and free
    groq: 'llama-3.3-70b-versatile',
    ollama: 'gpt-oss:120b-cloud', // Available locally
    grok: 'grok-2-1212',
    openrouter: 'google/gemini-2.5-flash-lite' // Cheap via OpenRouter
};
/**
 * Setup global options for the CLI program
 * @param program Commander program instance
 */
export function setupGlobalOptions(program) {
    program
        .addOption(new Option('-p, --provider <provider>', 'AI provider to use')
        .choices(PROVIDERS)
        .default('gemini')
        .env('PRIMARY_PROVIDER'))
        .option('-m, --model <model>', 'Model to use (defaults to provider\'s default model)')
        .option('-k, --api-key <key>', 'API key for the provider (can also use env vars)')
        .option('-o, --output <path>', 'Output directory (defaults to input directory)')
        .option('-u, --update', 'Update existing documentation files', false)
        .option('--verbose', 'Enable verbose output', false)
        .option('-q, --quiet', 'Suppress non-essential output', false)
        .option('-r, --recursive', 'Process directories recursively', true)
        // Phase 2: New productivity options
        .option('-w, --watch', 'Watch mode: regenerate on file changes', false)
        .option('--cache', 'Enable AI response caching', false)
        .option('--cache-dir <path>', 'Cache directory path')
        .option('-i, --incremental', 'Incremental mode: only process changed files', false)
        .option('-f, --force', 'Force full regeneration (ignore incremental state)', false)
        .option('-c, --config <path>', 'Path to configuration file (autodoc.config.yaml)');
}
/**
 * Get API key for provider from options or environment
 * @param provider Provider name
 * @param apiKey API key from options
 * @returns API key or undefined
 */
export function getApiKey(provider, apiKey) {
    if (apiKey)
        return apiKey;
    const envVars = {
        gemini: 'GEMINI_API_KEY',
        groq: 'GROQ_API_KEY',
        ollama: '', // No API key needed
        grok: 'XAI_API_KEY',
        openrouter: 'OPENROUTER_API_KEY'
    };
    const envVar = envVars[provider];
    return envVar ? process.env[envVar] : undefined;
}
/**
 * Get model for provider from options or default
 * @param provider Provider name
 * @param model Model from options
 * @returns Model name
 */
export function getModel(provider, model) {
    return model || DEFAULT_MODELS[provider];
}
/**
 * Validate provider configuration
 * @param provider Provider name
 * @param apiKey API key
 * @returns Error message or null if valid
 */
export function validateProviderConfig(provider, apiKey) {
    // Ollama doesn't need API key
    if (provider === 'ollama') {
        return null;
    }
    if (!apiKey) {
        const envVars = {
            gemini: 'GEMINI_API_KEY',
            groq: 'GROQ_API_KEY',
            ollama: '',
            grok: 'XAI_API_KEY',
            openrouter: 'OPENROUTER_API_KEY'
        };
        return `Missing API key for ${provider}. Set ${envVars[provider]} environment variable or use --api-key option.`;
    }
    return null;
}
//# sourceMappingURL=options.js.map