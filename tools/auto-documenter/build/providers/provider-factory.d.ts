import { OpenAI } from 'openai';
/**
 * Supported AI providers for documentation generation
 */
export type Provider = 'openrouter' | 'gemini' | 'groq' | 'ollama' | 'grok' | 'rotation';
/**
 * Result of smart provider selection
 */
export interface SmartProviderResult {
    client: OpenAI;
    provider: 'rotation' | 'ollama';
    model: string;
    url: string;
}
/**
 * Configuration for each provider
 */
interface ProviderConfig {
    baseURL: string;
    defaultModel: string;
    requiresApiKey: boolean;
    description: string;
    dailyLimit?: string;
}
/**
 * Factory class for creating AI provider clients
 */
export declare class ProviderFactory {
    /**
     * Create an OpenAI-compatible client for the specified provider
     * @param provider The AI provider to use
     * @param apiKey API key for the provider (not needed for Ollama)
     * @param model Model to use (optional, uses default if not specified)
     * @returns Configured OpenAI client
     */
    static createClient(provider: Provider, apiKey?: string, model?: string): OpenAI;
    /**
     * Get the default model for a provider
     * @param provider The AI provider
     * @returns Default model name
     */
    static getDefaultModel(provider: Provider): string;
    /**
     * Get configuration for a provider
     * @param provider The AI provider
     * @returns Provider configuration
     */
    static getProviderConfig(provider: Provider): ProviderConfig;
    /**
     * Get all available providers
     * @returns Array of provider names
     */
    static getAvailableProviders(): Provider[];
    /**
     * Print information about all available providers
     */
    static printProviderInfo(): void;
    /**
     * Validate provider name
     * @param provider Provider name to validate
     * @returns True if valid, false otherwise
     */
    static isValidProvider(provider: string): provider is Provider;
    /**
     * Get environment variable name for provider API key
     * @param provider The AI provider
     * @returns Environment variable name
     */
    static getApiKeyEnvVar(provider: Provider): string;
    /**
     * Create a smart client with automatic fallback
     *
     * Priority:
     * 1. LLM Rotation HTTP Server (localhost:8000) - if available
     * 2. Ollama (localhost:11434) - fallback, with auto-start if not running
     *
     * @param rotationURL LLM Rotation server URL (default: http://localhost:8000)
     * @param ollamaURL Ollama server URL (default: http://localhost:11434)
     * @returns SmartProviderResult with client, provider type, model and URL
     */
    static createSmartClient(rotationURL?: string, ollamaURL?: string): Promise<SmartProviderResult>;
    /**
     * Check if LLM Rotation HTTP is available
     * @param url LLM Rotation server URL
     * @returns True if available
     */
    static isRotationAvailable(url?: string): Promise<boolean>;
    /**
     * Check if Ollama is available
     * @param url Ollama server URL
     * @returns True if available
     */
    static isOllamaAvailable(url?: string): Promise<boolean>;
    /**
     * Ensure Ollama is running, start if needed
     * @param url Ollama server URL
     * @returns True if Ollama is running (started or already was running)
     */
    static ensureOllamaRunning(url?: string): Promise<boolean>;
}
export {};
