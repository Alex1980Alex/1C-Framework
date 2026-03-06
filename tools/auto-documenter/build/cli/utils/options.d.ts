/**
 * CLI Global Options Configuration
 * @module cli/utils/options
 */
import { Command } from 'commander';
/**
 * Available AI providers
 */
export declare const PROVIDERS: readonly ["gemini", "groq", "ollama", "grok", "openrouter"];
export type Provider = typeof PROVIDERS[number];
/**
 * Default models per provider
 */
export declare const DEFAULT_MODELS: Record<Provider, string>;
/**
 * CLI Options interface
 */
export interface CLIOptions {
    provider: Provider;
    model?: string;
    apiKey?: string;
    output?: string;
    update: boolean;
    verbose: boolean;
    quiet: boolean;
    recursive: boolean;
    watch: boolean;
    cache: boolean;
    cacheDir?: string;
    incremental: boolean;
    force: boolean;
    config?: string;
}
/**
 * Setup global options for the CLI program
 * @param program Commander program instance
 */
export declare function setupGlobalOptions(program: Command): void;
/**
 * Get API key for provider from options or environment
 * @param provider Provider name
 * @param apiKey API key from options
 * @returns API key or undefined
 */
export declare function getApiKey(provider: Provider, apiKey?: string): string | undefined;
/**
 * Get model for provider from options or default
 * @param provider Provider name
 * @param model Model from options
 * @returns Model name
 */
export declare function getModel(provider: Provider, model?: string): string;
/**
 * Validate provider configuration
 * @param provider Provider name
 * @param apiKey API key
 * @returns Error message or null if valid
 */
export declare function validateProviderConfig(provider: Provider, apiKey?: string): string | null;
