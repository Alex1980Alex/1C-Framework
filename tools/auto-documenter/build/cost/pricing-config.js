/**
 * Pricing configuration for all AI providers
 * All prices are in USD per 1 million tokens
 */
/**
 * Complete pricing database for all providers
 */
export const PRICING_CONFIG = {
    /**
     * OpenRouter - Pay-as-you-go pricing
     * Prices vary by model, using Claude 3.7 Sonnet as reference
     */
    openrouter: {
        defaultModel: 'anthropic/claude-3.7-sonnet',
        isFree: false,
        models: {
            'anthropic/claude-3.7-sonnet': {
                inputPrice: 3.0,
                outputPrice: 15.0,
                isFree: false,
                description: 'Claude 3.7 Sonnet via OpenRouter',
            },
            'anthropic/claude-3.5-sonnet': {
                inputPrice: 3.0,
                outputPrice: 15.0,
                isFree: false,
                description: 'Claude 3.5 Sonnet via OpenRouter',
            },
            'openai/gpt-4': {
                inputPrice: 30.0,
                outputPrice: 60.0,
                isFree: false,
                description: 'GPT-4 via OpenRouter',
            },
            'openai/gpt-3.5-turbo': {
                inputPrice: 0.5,
                outputPrice: 1.5,
                isFree: false,
                description: 'GPT-3.5 Turbo via OpenRouter',
            },
            'google/gemini-pro': {
                inputPrice: 0.125,
                outputPrice: 0.375,
                isFree: false,
                description: 'Gemini Pro via OpenRouter',
            },
        },
    },
    /**
     * Google Gemini - Free tier available
     * Gemini 2.5 Flash-Lite is 5.3x faster than Flash
     */
    gemini: {
        defaultModel: 'gemini-2.5-flash-lite',
        isFree: true,
        models: {
            'gemini-2.5-flash-lite': {
                inputPrice: 0.0, // FREE
                outputPrice: 0.0, // FREE
                isFree: true,
                dailyLimit: {
                    requests: 1500, // 1,500 requests per day
                    // 60 RPM (requests per minute)
                },
                description: 'Gemini 2.5 Flash-Lite (5.3x faster, FREE)',
            },
            'gemini-2.5-flash': {
                inputPrice: 0.0, // FREE tier available
                outputPrice: 0.0,
                isFree: true,
                dailyLimit: {
                    requests: 1500,
                },
                description: 'Gemini 2.5 Flash (FREE tier)',
            },
            'gemini-1.5-pro': {
                inputPrice: 0.0, // FREE tier available
                outputPrice: 0.0,
                isFree: true,
                dailyLimit: {
                    requests: 1500,
                },
                description: 'Gemini 1.5 Pro (FREE tier)',
            },
        },
    },
    /**
     * Groq - Free tier with generous limits
     * Ultra-fast inference with Llama models
     */
    groq: {
        defaultModel: 'llama-3.3-70b-versatile',
        isFree: true,
        models: {
            'llama-3.3-70b-versatile': {
                inputPrice: 0.0, // FREE
                outputPrice: 0.0, // FREE
                isFree: true,
                dailyLimit: {
                    requests: 14400, // 14,400 requests/day
                    tokens: 500000, // 500,000 tokens/day
                },
                description: 'Llama 3.3 70B Versatile (FREE)',
            },
            'llama-3.1-70b-versatile': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                dailyLimit: {
                    requests: 14400,
                    tokens: 500000,
                },
                description: 'Llama 3.1 70B Versatile (FREE)',
            },
            'mixtral-8x7b-32768': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                dailyLimit: {
                    requests: 14400,
                    tokens: 500000,
                },
                description: 'Mixtral 8x7B (FREE)',
            },
        },
    },
    /**
     * xAI Grok - Pay-as-you-go
     * Pricing subject to change, check x.ai for current rates
     */
    grok: {
        defaultModel: 'grok-beta',
        isFree: false,
        models: {
            'grok-beta': {
                inputPrice: 5.0, // Estimated, check x.ai for actual pricing
                outputPrice: 15.0,
                isFree: false,
                description: 'Grok Beta (pay-as-you-go)',
            },
        },
    },
    /**
     * LLM Rotation Service - Unified gateway with automatic fallback
     * Costs depend on the provider selected by the rotation service
     * Generally uses free tiers first (Gemini, OpenRouter free models, Ollama)
     */
    rotation: {
        defaultModel: 'auto',
        isFree: true, // Primarily uses free providers
        models: {
            'auto': {
                inputPrice: 0.0, // Depends on actual provider used
                outputPrice: 0.0,
                isFree: true, // Defaults to free providers
                description: 'Auto-selected model via LLM Rotation Service',
            },
        },
    },
    /**
     * Ollama - Local models, completely free
     * All costs are $0 (local inference)
     */
    ollama: {
        defaultModel: 'qwen2.5-coder:14b',
        isFree: true,
        models: {
            // Fast models
            'qwen2.5-coder:7b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'Qwen2.5-Coder 7B (Local, FREE)',
            },
            'codellama:7b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'CodeLlama 7B (Local, FREE)',
            },
            'deepseek-coder:6.7b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'DeepSeek Coder 6.7B (Local, FREE)',
            },
            // Balanced models
            'qwen2.5-coder:14b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'Qwen2.5-Coder 14B (Local, FREE)',
            },
            'codellama:13b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'CodeLlama 13B (Local, FREE)',
            },
            'deepseek-coder-v2:16b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'DeepSeek Coder V2 16B (Local, FREE)',
            },
            // Quality models
            'qwen2.5-coder:32b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'Qwen2.5-Coder 32B (Local, FREE)',
            },
            'codellama:34b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'CodeLlama 34B (Local, FREE)',
            },
            'deepseek-coder:33b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'DeepSeek Coder 33B (Local, FREE)',
            },
            // General models
            'llama3.2:3b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'Llama 3.2 3B (Local, FREE)',
            },
            'mistral:7b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'Mistral 7B (Local, FREE)',
            },
            'phi3:3.8b': {
                inputPrice: 0.0,
                outputPrice: 0.0,
                isFree: true,
                description: 'Phi-3 3.8B (Local, FREE)',
            },
        },
    },
};
/**
 * Get pricing for a specific model
 * @param provider Provider name
 * @param model Model name (uses default if not specified)
 * @returns Model pricing or undefined if not found
 */
export function getModelPricing(provider, model) {
    const providerPricing = PRICING_CONFIG[provider];
    if (!providerPricing) {
        return undefined;
    }
    const modelName = model || providerPricing.defaultModel;
    return providerPricing.models[modelName];
}
/**
 * Calculate cost for a given token usage
 * @param provider Provider name
 * @param model Model name
 * @param inputTokens Number of input tokens
 * @param outputTokens Number of output tokens
 * @returns Cost in USD, or 0 if model pricing not found or is free
 */
export function calculateCost(provider, model, inputTokens, outputTokens) {
    const pricing = getModelPricing(provider, model);
    if (!pricing || pricing.isFree) {
        return 0.0;
    }
    const inputCost = (inputTokens / 1000000) * pricing.inputPrice;
    const outputCost = (outputTokens / 1000000) * pricing.outputPrice;
    return inputCost + outputCost;
}
/**
 * Check if a provider/model is free
 * @param provider Provider name
 * @param model Model name (optional)
 * @returns True if free, false if paid
 */
export function isFreeModel(provider, model) {
    const pricing = getModelPricing(provider, model);
    return pricing?.isFree ?? false;
}
/**
 * Get daily limits for a model
 * @param provider Provider name
 * @param model Model name (optional)
 * @returns Daily limits or undefined
 */
export function getDailyLimits(provider, model) {
    const pricing = getModelPricing(provider, model);
    return pricing?.dailyLimit;
}
/**
 * Format cost for display
 * @param cost Cost in USD
 * @returns Formatted string
 */
export function formatCost(cost) {
    if (cost === 0) {
        return 'FREE';
    }
    if (cost < 0.001) {
        return `$${(cost * 1000).toFixed(4)} (per 1K requests)`;
    }
    if (cost < 0.01) {
        return `$${cost.toFixed(4)}`;
    }
    if (cost < 1) {
        return `$${cost.toFixed(3)}`;
    }
    return `$${cost.toFixed(2)}`;
}
/**
 * Print pricing information for all providers
 */
export function printPricingInfo() {
    console.error('\n💰 AI Provider Pricing:\n');
    for (const [providerName, config] of Object.entries(PRICING_CONFIG)) {
        const provider = providerName;
        console.error(`${providerName.toUpperCase()}: ${config.isFree ? '✅ FREE TIER AVAILABLE' : '💳 PAID'}`);
        console.error(`  Default Model: ${config.defaultModel}`);
        const defaultPricing = config.models[config.defaultModel];
        if (defaultPricing) {
            if (defaultPricing.isFree) {
                console.error(`  Price: FREE`);
                if (defaultPricing.dailyLimit) {
                    if (defaultPricing.dailyLimit.requests) {
                        console.error(`  Daily Limit: ${defaultPricing.dailyLimit.requests.toLocaleString()} requests/day`);
                    }
                    if (defaultPricing.dailyLimit.tokens) {
                        console.error(`  Token Limit: ${defaultPricing.dailyLimit.tokens.toLocaleString()} tokens/day`);
                    }
                }
            }
            else {
                console.error(`  Input: $${defaultPricing.inputPrice}/1M tokens`);
                console.error(`  Output: $${defaultPricing.outputPrice}/1M tokens`);
            }
        }
        console.error('');
    }
}
//# sourceMappingURL=pricing-config.js.map