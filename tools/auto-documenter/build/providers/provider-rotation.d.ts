import { Provider } from './provider-factory.js';
import { OpenAI } from 'openai';
import { BudgetLimit } from '../cost/cost-tracker.js';
/**
 * Usage statistics for a provider
 */
interface ProviderUsage {
    requests: number;
    tokens: number;
    errors: number;
    lastUsed: Date;
    lastError?: string;
}
/**
 * Provider rotation strategy configuration
 */
interface RotationConfig {
    primaryProvider: Provider;
    fallbackProviders: Provider[];
    maxErrorsBeforeFallback: number;
    enableAutoRotation: boolean;
}
/**
 * Provider rotation manager for automatic fallback between AI providers
 * Implements the "Free Tier Rotation" strategy
 */
export declare class ProviderRotationManager {
    private config;
    private currentProvider;
    private usage;
    private apiKeys;
    private models;
    private costTracker;
    constructor(config?: Partial<RotationConfig>, budgetLimit?: BudgetLimit);
    /**
     * Initialize usage tracking for all providers
     */
    private initializeUsageTracking;
    /**
     * Set API key for a provider
     * @param provider Provider name
     * @param apiKey API key
     */
    setApiKey(provider: Provider, apiKey: string): void;
    /**
     * Set model for a provider
     * @param provider Provider name
     * @param model Model name
     */
    setModel(provider: Provider, model: string): void;
    /**
     * Get current active provider
     * @returns Current provider name
     */
    getCurrentProvider(): Provider;
    /**
     * Get current active model
     * @returns Current model name
     */
    getCurrentModel(): string;
    /**
     * Create a client for the current provider
     * @returns OpenAI client configured for current provider
     */
    createClient(): OpenAI;
    /**
     * Fallback to the next available provider
     * @returns OpenAI client for fallback provider
     */
    private fallbackToNextProvider;
    /**
     * Record successful request
     * @param inputTokens Number of input tokens used (optional)
     * @param outputTokens Number of output tokens used (optional)
     */
    recordSuccess(inputTokens?: number, outputTokens?: number): void;
    /**
     * Record failed request
     * @param error Error message
     */
    recordError(error: string): void;
    /**
     * Force immediate switch to next provider (used for rate limit errors)
     * This bypasses the error count threshold and switches immediately
     */
    forceSwitch(): void;
    /**
     * Switch to fallback provider
     */
    private switchToFallback;
    /**
     * Get usage statistics for all providers
     * @returns Map of provider usage statistics
     */
    getUsageStats(): Map<Provider, ProviderUsage>;
    /**
     * Print usage statistics including cost information
     */
    printUsageStats(): void;
    /**
     * Reset all usage statistics
     */
    resetStats(): void;
    /**
     * Check if daily limits might be exceeded (basic estimation)
     * @returns Warning message if limits might be exceeded
     */
    checkLimits(): string | null;
    /**
     * Get cost summary
     * @returns Cost summary
     */
    getCostSummary(): import("../cost/cost-tracker.js").CostSummary;
    /**
     * Set budget limit
     * @param budgetLimit Budget limit configuration
     */
    setBudgetLimit(budgetLimit: BudgetLimit): void;
    /**
     * Get current budget limit
     * @returns Current budget limit
     */
    getBudgetLimit(): BudgetLimit | undefined;
    /**
     * Export cost data to JSON
     * @returns JSON string with cost data
     */
    exportCostData(): string;
}
/**
 * Create default rotation manager with environment-based configuration
 */
export declare function createDefaultRotationManager(): ProviderRotationManager;
export {};
