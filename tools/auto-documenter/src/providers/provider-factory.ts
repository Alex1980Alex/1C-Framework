import { OpenAI } from 'openai';
import { ensureProviderAvailable, startOllama, checkOllamaAvailability, checkRotationAvailability } from './ollama-utils.js';

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
 * Provider configurations with endpoints and default models
 */
const PROVIDER_CONFIGS: Record<Provider, ProviderConfig> = {
  openrouter: {
    baseURL: 'https://openrouter.ai/api/v1',
    defaultModel: 'google/gemini-2.5-flash-lite',  // Cheap and fast Gemini model via OpenRouter
    requiresApiKey: true,
    description: 'OpenRouter API - Access to multiple models including Claude, GPT-4, Gemini',
    dailyLimit: 'Pay-as-you-go (Gemini Flash Lite: very cheap)',
  },
  gemini: {
    baseURL: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    defaultModel: 'gemini-2.0-flash',
    requiresApiKey: true,
    description: 'Google Gemini API - Free tier with generous limits (2.5 Flash-Lite: 5.3x faster)',
    dailyLimit: '1,500 requests/day, 60 RPM (FREE)',
  },
  groq: {
    baseURL: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.3-70b-versatile',
    requiresApiKey: true,
    description: 'Groq API - Ultra-fast inference with Llama models',
    dailyLimit: '500,000 tokens/day, 14,400 requests/day (FREE)',
  },
  grok: {
    baseURL: 'https://api.x.ai/v1',
    defaultModel: 'grok-beta',
    requiresApiKey: true,
    description: 'xAI Grok API - Advanced reasoning and real-time knowledge',
    dailyLimit: 'Pay-as-you-go (check x.ai for current pricing)',
  },
  ollama: {
    baseURL: 'http://localhost:11434/v1',
    defaultModel: 'gpt-oss:120b-cloud',  // Available model in local Ollama
    requiresApiKey: false,
    description: 'Ollama - Local models, unlimited usage, full privacy',
    dailyLimit: 'Unlimited (runs locally)',
  },
  rotation: {
    baseURL: 'http://localhost:8000/v1',
    defaultModel: 'auto',  // Automatically selects best provider
    requiresApiKey: false,
    description: 'LLM Rotation Service - Unified gateway with automatic fallback (Gemini → OpenRouter → Mistral → Ollama)',
    dailyLimit: 'Unlimited (uses multiple providers)',
  },
};

/**
 * Factory class for creating AI provider clients
 */
export class ProviderFactory {
  /**
   * Create an OpenAI-compatible client for the specified provider
   * @param provider The AI provider to use
   * @param apiKey API key for the provider (not needed for Ollama)
   * @param model Model to use (optional, uses default if not specified)
   * @returns Configured OpenAI client
   */
  static createClient(provider: Provider, apiKey?: string, model?: string): OpenAI {
    const config = PROVIDER_CONFIGS[provider];

    // Validate API key requirement
    if (config.requiresApiKey && !apiKey) {
      throw new Error(
        `API key is required for ${provider}. ` +
        `Set the appropriate environment variable or pass it to the constructor.`
      );
    }

    // Create OpenAI client with provider-specific configuration
    const client = new OpenAI({
      apiKey: apiKey || 'not-needed', // Ollama doesn't require API key
      baseURL: config.baseURL,
      defaultHeaders: provider === 'openrouter' ? {
        'HTTP-Referer': 'https://github.com/PARS-DOE/autodocument',
      } : {},
    });

    return client;
  }

  /**
   * Get the default model for a provider
   * @param provider The AI provider
   * @returns Default model name
   */
  static getDefaultModel(provider: Provider): string {
    return PROVIDER_CONFIGS[provider].defaultModel;
  }

  /**
   * Get configuration for a provider
   * @param provider The AI provider
   * @returns Provider configuration
   */
  static getProviderConfig(provider: Provider): ProviderConfig {
    return PROVIDER_CONFIGS[provider];
  }

  /**
   * Get all available providers
   * @returns Array of provider names
   */
  static getAvailableProviders(): Provider[] {
    return Object.keys(PROVIDER_CONFIGS) as Provider[];
  }

  /**
   * Print information about all available providers
   */
  static printProviderInfo(): void {
    console.error('\n📊 Available AI Providers:\n');

    for (const [name, config] of Object.entries(PROVIDER_CONFIGS)) {
      console.error(`${name.toUpperCase()}:`);
      console.error(`  Description: ${config.description}`);
      console.error(`  Default Model: ${config.defaultModel}`);
      console.error(`  Daily Limit: ${config.dailyLimit}`);
      console.error(`  Requires API Key: ${config.requiresApiKey ? 'Yes' : 'No'}`);
      console.error('');
    }
  }

  /**
   * Validate provider name
   * @param provider Provider name to validate
   * @returns True if valid, false otherwise
   */
  static isValidProvider(provider: string): provider is Provider {
    return provider in PROVIDER_CONFIGS;
  }

  /**
   * Get environment variable name for provider API key
   * @param provider The AI provider
   * @returns Environment variable name
   */
  static getApiKeyEnvVar(provider: Provider): string {
    const envVars: Record<Provider, string> = {
      openrouter: 'OPENROUTER_API_KEY',
      gemini: 'GEMINI_API_KEY',
      groq: 'GROQ_API_KEY',
      grok: 'GROK_API_KEY',
      ollama: '', // Not needed
      rotation: '', // Not needed - uses internal rotation
    };
    return envVars[provider];
  }

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
  static async createSmartClient(
    rotationURL: string = 'http://localhost:8000',
    ollamaURL: string = 'http://localhost:11434'
  ): Promise<SmartProviderResult> {
    console.error('🔍 Smart Provider Selection: checking available providers...');

    // Use ensureProviderAvailable to get the best available provider
    const result = await ensureProviderAvailable(rotationURL, ollamaURL);

    if (result.provider === null || result.url === null) {
      throw new Error(
        `No LLM provider available!\n` +
        `  • LLM Rotation HTTP (${rotationURL}) - not available\n` +
        `  • Ollama (${ollamaURL}) - not available and could not be started\n\n` +
        `Please start one of the providers:\n` +
        `  1. LLM Rotation: python shared/llm_rotation_http.py --port 8000\n` +
        `  2. Ollama: ollama serve`
      );
    }

    // Create client based on selected provider
    if (result.provider === 'rotation') {
      const client = new OpenAI({
        apiKey: 'not-needed',
        baseURL: `${result.url}/v1`,
      });

      console.error(`✅ Using LLM Rotation HTTP (${result.url})`);

      return {
        client,
        provider: 'rotation',
        model: 'auto', // Rotation service auto-selects model
        url: result.url,
      };
    } else {
      // Ollama fallback
      const client = new OpenAI({
        apiKey: 'not-needed',
        baseURL: `${result.url}/v1`,
      });

      const defaultModel = PROVIDER_CONFIGS.ollama.defaultModel;
      console.error(`✅ Using Ollama (${result.url}) with model: ${defaultModel}`);

      return {
        client,
        provider: 'ollama',
        model: defaultModel,
        url: result.url,
      };
    }
  }

  /**
   * Check if LLM Rotation HTTP is available
   * @param url LLM Rotation server URL
   * @returns True if available
   */
  static async isRotationAvailable(url: string = 'http://localhost:8000'): Promise<boolean> {
    const status = await checkRotationAvailability(url);
    return status.available;
  }

  /**
   * Check if Ollama is available
   * @param url Ollama server URL
   * @returns True if available
   */
  static async isOllamaAvailable(url: string = 'http://localhost:11434'): Promise<boolean> {
    const status = await checkOllamaAvailability(url);
    return status.available;
  }

  /**
   * Ensure Ollama is running, start if needed
   * @param url Ollama server URL
   * @returns True if Ollama is running (started or already was running)
   */
  static async ensureOllamaRunning(url: string = 'http://localhost:11434'): Promise<boolean> {
    return await startOllama(url);
  }
}
