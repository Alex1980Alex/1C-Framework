import { ProviderFactory } from './provider-factory.js';
import { CostTracker } from '../cost/cost-tracker.js';
/**
 * Provider rotation manager for automatic fallback between AI providers
 * Implements the "Free Tier Rotation" strategy
 */
export class ProviderRotationManager {
    constructor(config, budgetLimit) {
        this.usage = new Map();
        this.apiKeys = new Map();
        this.models = new Map();
        // Default configuration: Gemini -> OpenRouter -> Ollama
        this.config = {
            primaryProvider: config?.primaryProvider || 'gemini',
            fallbackProviders: config?.fallbackProviders || ['openrouter', 'ollama'],
            maxErrorsBeforeFallback: config?.maxErrorsBeforeFallback || 3,
            enableAutoRotation: config?.enableAutoRotation !== false,
        };
        this.currentProvider = this.config.primaryProvider;
        // Initialize cost tracking
        this.costTracker = new CostTracker(budgetLimit);
        // Initialize usage tracking
        this.initializeUsageTracking();
    }
    /**
     * Initialize usage tracking for all providers
     */
    initializeUsageTracking() {
        const allProviders = [this.config.primaryProvider, ...this.config.fallbackProviders];
        for (const provider of allProviders) {
            this.usage.set(provider, {
                requests: 0,
                tokens: 0,
                errors: 0,
                lastUsed: new Date(),
            });
        }
    }
    /**
     * Set API key for a provider
     * @param provider Provider name
     * @param apiKey API key
     */
    setApiKey(provider, apiKey) {
        this.apiKeys.set(provider, apiKey);
    }
    /**
     * Set model for a provider
     * @param provider Provider name
     * @param model Model name
     */
    setModel(provider, model) {
        this.models.set(provider, model);
    }
    /**
     * Get current active provider
     * @returns Current provider name
     */
    getCurrentProvider() {
        return this.currentProvider;
    }
    /**
     * Get current active model
     * @returns Current model name
     */
    getCurrentModel() {
        return this.models.get(this.currentProvider) ||
            ProviderFactory.getDefaultModel(this.currentProvider);
    }
    /**
     * Create a client for the current provider
     * @returns OpenAI client configured for current provider
     */
    createClient() {
        const apiKey = this.apiKeys.get(this.currentProvider);
        const model = this.getCurrentModel();
        try {
            const client = ProviderFactory.createClient(this.currentProvider, apiKey, model);
            console.error(`✅ Using provider: ${this.currentProvider.toUpperCase()} (model: ${model})`);
            return client;
        }
        catch (error) {
            console.error(`❌ Failed to create client for ${this.currentProvider}: ${error.message}`);
            // Try fallback if enabled
            if (this.config.enableAutoRotation) {
                return this.fallbackToNextProvider();
            }
            throw error;
        }
    }
    /**
     * Fallback to the next available provider
     * @returns OpenAI client for fallback provider
     */
    fallbackToNextProvider() {
        const currentIndex = this.config.fallbackProviders.indexOf(this.currentProvider);
        const nextIndex = currentIndex + 1;
        if (nextIndex < this.config.fallbackProviders.length) {
            this.currentProvider = this.config.fallbackProviders[nextIndex];
            console.error(`🔄 Falling back to: ${this.currentProvider.toUpperCase()}`);
            return this.createClient();
        }
        throw new Error('All providers failed. Please check your configuration and API keys.');
    }
    /**
     * Record successful request
     * @param inputTokens Number of input tokens used (optional)
     * @param outputTokens Number of output tokens used (optional)
     */
    recordSuccess(inputTokens, outputTokens) {
        const usage = this.usage.get(this.currentProvider);
        usage.requests++;
        const totalTokens = (inputTokens || 0) + (outputTokens || 0);
        usage.tokens += totalTokens;
        usage.lastUsed = new Date();
        // Record cost if token counts are available
        if (inputTokens !== undefined && outputTokens !== undefined) {
            const model = this.getCurrentModel();
            this.costTracker.recordRequest(this.currentProvider, model, inputTokens, outputTokens);
        }
    }
    /**
     * Record failed request
     * @param error Error message
     */
    recordError(error) {
        const usage = this.usage.get(this.currentProvider);
        usage.errors++;
        usage.lastError = error;
        // Check if we should fallback
        if (this.config.enableAutoRotation &&
            usage.errors >= this.config.maxErrorsBeforeFallback) {
            console.warn(`⚠️ Provider ${this.currentProvider} has ${usage.errors} errors. ` +
                `Switching to fallback...`);
            this.switchToFallback();
        }
    }
    /**
     * Force immediate switch to next provider (used for rate limit errors)
     * This bypasses the error count threshold and switches immediately
     */
    forceSwitch() {
        const usage = this.usage.get(this.currentProvider);
        usage.lastError = 'Rate limit - forced switch';
        console.warn(`🔄 Force switching from ${this.currentProvider.toUpperCase()} due to rate limit...`);
        this.switchToFallback();
    }
    /**
     * Switch to fallback provider
     */
    switchToFallback() {
        // Find next provider that isn't the current one
        const allProviders = [this.config.primaryProvider, ...this.config.fallbackProviders];
        const currentIndex = allProviders.indexOf(this.currentProvider);
        // Try next provider in the list
        for (let i = 1; i < allProviders.length; i++) {
            const nextIndex = (currentIndex + i) % allProviders.length;
            const nextProvider = allProviders[nextIndex];
            const usage = this.usage.get(nextProvider);
            // Skip if this provider has too many errors
            if (usage && usage.errors < this.config.maxErrorsBeforeFallback) {
                this.currentProvider = nextProvider;
                console.error(`🔄 Switched to provider: ${this.currentProvider.toUpperCase()}`);
                return;
            }
        }
        // All providers have errors - reset and start from primary
        console.warn('⚠️ All providers have errors. Resetting error counts...');
        for (const usage of this.usage.values()) {
            usage.errors = 0;
        }
        this.currentProvider = this.config.primaryProvider;
        console.error(`🔄 Reset to primary provider: ${this.currentProvider.toUpperCase()}`);
    }
    /**
     * Get usage statistics for all providers
     * @returns Map of provider usage statistics
     */
    getUsageStats() {
        return new Map(this.usage);
    }
    /**
     * Print usage statistics including cost information
     */
    printUsageStats() {
        console.error('\n📊 Provider Usage Statistics:\n');
        for (const [provider, usage] of this.usage.entries()) {
            const isCurrent = provider === this.currentProvider;
            console.error(`${isCurrent ? '👉 ' : '   '}${provider.toUpperCase()}:`);
            console.error(`   Requests: ${usage.requests}`);
            console.error(`   Tokens: ${usage.tokens.toLocaleString()}`);
            console.error(`   Errors: ${usage.errors}`);
            console.error(`   Last Used: ${usage.lastUsed.toLocaleString()}`);
            if (usage.lastError) {
                console.error(`   Last Error: ${usage.lastError}`);
            }
            console.error('');
        }
        // Print cost summary
        this.costTracker.printSummary();
    }
    /**
     * Reset all usage statistics
     */
    resetStats() {
        for (const usage of this.usage.values()) {
            usage.requests = 0;
            usage.tokens = 0;
            usage.errors = 0;
            usage.lastError = undefined;
        }
        this.costTracker.reset();
        console.error('✅ Usage statistics and cost tracking reset');
    }
    /**
     * Check if daily limits might be exceeded (basic estimation)
     * @returns Warning message if limits might be exceeded
     */
    checkLimits() {
        const usage = this.usage.get(this.currentProvider);
        // Simple heuristic checks
        if (this.currentProvider === 'gemini' && usage.requests > 1400) {
            return `⚠️ Approaching Gemini daily limit (${usage.requests}/1500 requests)`;
        }
        if (this.currentProvider === 'groq' && usage.tokens > 450000) {
            return `⚠️ Approaching Groq daily limit (${usage.tokens.toLocaleString()}/500,000 tokens)`;
        }
        // Check budget limits
        const budgetStatus = this.costTracker.checkBudget();
        if (budgetStatus.exceeded || budgetStatus.warningTriggered) {
            return budgetStatus.message || null;
        }
        return null;
    }
    /**
     * Get cost summary
     * @returns Cost summary
     */
    getCostSummary() {
        return this.costTracker.getSummary();
    }
    /**
     * Set budget limit
     * @param budgetLimit Budget limit configuration
     */
    setBudgetLimit(budgetLimit) {
        this.costTracker.setBudgetLimit(budgetLimit);
    }
    /**
     * Get current budget limit
     * @returns Current budget limit
     */
    getBudgetLimit() {
        return this.costTracker.getBudgetLimit();
    }
    /**
     * Export cost data to JSON
     * @returns JSON string with cost data
     */
    exportCostData() {
        return this.costTracker.exportToJSON();
    }
}
/**
 * Create default rotation manager with environment-based configuration
 */
export function createDefaultRotationManager() {
    const manager = new ProviderRotationManager({
        primaryProvider: process.env.PRIMARY_PROVIDER || 'gemini',
        fallbackProviders: ['openrouter', 'ollama'],
        enableAutoRotation: process.env.ENABLE_AUTO_ROTATION !== 'false',
    });
    // Set API keys from environment
    const geminiKey = process.env.GEMINI_API_KEY;
    const groqKey = process.env.GROQ_API_KEY;
    const openrouterKey = process.env.OPENROUTER_API_KEY;
    if (geminiKey)
        manager.setApiKey('gemini', geminiKey);
    if (groqKey)
        manager.setApiKey('groq', groqKey);
    if (openrouterKey)
        manager.setApiKey('openrouter', openrouterKey);
    // Set models from environment
    const geminiModel = process.env.GEMINI_MODEL;
    const groqModel = process.env.GROQ_MODEL;
    const ollamaModel = process.env.OLLAMA_MODEL;
    const openrouterModel = process.env.OPENROUTER_MODEL;
    if (geminiModel)
        manager.setModel('gemini', geminiModel);
    if (groqModel)
        manager.setModel('groq', groqModel);
    if (ollamaModel)
        manager.setModel('ollama', ollamaModel);
    if (openrouterModel)
        manager.setModel('openrouter', openrouterModel);
    return manager;
}
//# sourceMappingURL=provider-rotation.js.map