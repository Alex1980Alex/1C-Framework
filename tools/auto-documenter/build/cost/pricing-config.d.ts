/**
 * Pricing configuration for all AI providers
 * All prices are in USD per 1 million tokens
 */
export type Provider = 'openrouter' | 'gemini' | 'groq' | 'ollama' | 'grok' | 'rotation';
/**
 * Model pricing information
 */
export interface ModelPricing {
    inputPrice: number;
    outputPrice: number;
    isFree: boolean;
    dailyLimit?: {
        requests?: number;
        tokens?: number;
    };
    description?: string;
}
/**
 * Provider pricing configuration
 */
export interface ProviderPricing {
    defaultModel: string;
    models: Record<string, ModelPricing>;
    isFree: boolean;
}
/**
 * Complete pricing database for all providers
 */
export declare const PRICING_CONFIG: Record<Provider, ProviderPricing>;
/**
 * Get pricing for a specific model
 * @param provider Provider name
 * @param model Model name (uses default if not specified)
 * @returns Model pricing or undefined if not found
 */
export declare function getModelPricing(provider: Provider, model?: string): ModelPricing | undefined;
/**
 * Calculate cost for a given token usage
 * @param provider Provider name
 * @param model Model name
 * @param inputTokens Number of input tokens
 * @param outputTokens Number of output tokens
 * @returns Cost in USD, or 0 if model pricing not found or is free
 */
export declare function calculateCost(provider: Provider, model: string, inputTokens: number, outputTokens: number): number;
/**
 * Check if a provider/model is free
 * @param provider Provider name
 * @param model Model name (optional)
 * @returns True if free, false if paid
 */
export declare function isFreeModel(provider: Provider, model?: string): boolean;
/**
 * Get daily limits for a model
 * @param provider Provider name
 * @param model Model name (optional)
 * @returns Daily limits or undefined
 */
export declare function getDailyLimits(provider: Provider, model?: string): ModelPricing['dailyLimit'];
/**
 * Format cost for display
 * @param cost Cost in USD
 * @returns Formatted string
 */
export declare function formatCost(cost: number): string;
/**
 * Print pricing information for all providers
 */
export declare function printPricingInfo(): void;
