/**
 * Configuration for local LLM providers (Ollama, llama.cpp)
 * Provides optimized model selections for documentation generation tasks
 */
/**
 * Recommended Ollama models for documentation generation
 * Sorted by quality/speed trade-off
 */
export const OLLAMA_MODELS = {
    /**
     * Fast models - Good for large codebases, quick iterations
     * Speed: ★★★★★ | Quality: ★★★☆☆
     */
    fast: {
        'qwen2.5-coder:7b': {
            description: 'Alibaba Qwen2.5-Coder 7B - Excellent code understanding, very fast',
            params: '7B',
            context: '32K tokens',
            speed: 'very-fast',
            recommendedFor: ['documentation', 'code-review', 'quick-analysis'],
            estimatedTokensPerSec: 50,
        },
        'codellama:7b': {
            description: 'Meta CodeLlama 7B - Good code generation, fast inference',
            params: '7B',
            context: '16K tokens',
            speed: 'fast',
            recommendedFor: ['documentation', 'simple-tasks'],
            estimatedTokensPerSec: 45,
        },
        'deepseek-coder:6.7b': {
            description: 'DeepSeek Coder 6.7B - Balanced speed/quality for coding tasks',
            params: '6.7B',
            context: '16K tokens',
            speed: 'fast',
            recommendedFor: ['documentation', 'code-explanation'],
            estimatedTokensPerSec: 48,
        },
    },
    /**
     * Balanced models - Best overall choice for most use cases
     * Speed: ★★★★☆ | Quality: ★★★★☆
     */
    balanced: {
        'qwen2.5-coder:14b': {
            description: 'Alibaba Qwen2.5-Coder 14B - Excellent quality, reasonable speed',
            params: '14B',
            context: '32K tokens',
            speed: 'medium',
            recommendedFor: ['documentation', 'code-review', 'test-generation'],
            estimatedTokensPerSec: 30,
            isDefault: true, // Default model for balanced mode
        },
        'codellama:13b': {
            description: 'Meta CodeLlama 13B - Good balance for code tasks',
            params: '13B',
            context: '16K tokens',
            speed: 'medium',
            recommendedFor: ['documentation', 'code-generation'],
            estimatedTokensPerSec: 28,
        },
        'deepseek-coder-v2:16b': {
            description: 'DeepSeek Coder V2 16B - Latest version with improved coding',
            params: '16B',
            context: '32K tokens',
            speed: 'medium',
            recommendedFor: ['documentation', 'complex-code-analysis'],
            estimatedTokensPerSec: 25,
        },
    },
    /**
     * Quality models - Best documentation quality, slower inference
     * Speed: ★★★☆☆ | Quality: ★★★★★
     */
    quality: {
        'qwen2.5-coder:32b': {
            description: 'Alibaba Qwen2.5-Coder 32B - Highest quality code documentation',
            params: '32B',
            context: '32K tokens',
            speed: 'slow',
            recommendedFor: ['critical-documentation', 'architectural-docs'],
            estimatedTokensPerSec: 15,
        },
        'codellama:34b': {
            description: 'Meta CodeLlama 34B - Very high quality code understanding',
            params: '34B',
            context: '16K tokens',
            speed: 'slow',
            recommendedFor: ['comprehensive-documentation'],
            estimatedTokensPerSec: 12,
        },
        'deepseek-coder:33b': {
            description: 'DeepSeek Coder 33B - Top-tier code analysis and docs',
            params: '33B',
            context: '16K tokens',
            speed: 'slow',
            recommendedFor: ['critical-documentation', 'detailed-analysis'],
            estimatedTokensPerSec: 14,
        },
    },
    /**
     * General-purpose models - Not code-specific but can work
     * Speed: ★★★★☆ | Quality: ★★★☆☆
     */
    general: {
        'llama3.2:3b': {
            description: 'Meta Llama 3.2 3B - Ultra-fast general model',
            params: '3B',
            context: '128K tokens',
            speed: 'very-fast',
            recommendedFor: ['simple-docs', 'summaries'],
            estimatedTokensPerSec: 80,
        },
        'mistral:7b': {
            description: 'Mistral 7B - Good general-purpose model',
            params: '7B',
            context: '32K tokens',
            speed: 'fast',
            recommendedFor: ['general-documentation'],
            estimatedTokensPerSec: 45,
        },
        'phi3:3.8b': {
            description: 'Microsoft Phi-3 3.8B - Compact but capable',
            params: '3.8B',
            context: '128K tokens',
            speed: 'very-fast',
            recommendedFor: ['quick-docs', 'summaries'],
            estimatedTokensPerSec: 70,
        },
    },
};
/**
 * Default model selection based on use case
 */
export const DEFAULT_MODELS = {
    documentation: 'qwen2.5-coder:14b',
    codeReview: 'qwen2.5-coder:14b',
    testPlan: 'qwen2.5-coder:14b',
    quickAnalysis: 'qwen2.5-coder:7b',
    comprehensive: 'qwen2.5-coder:32b',
};
/**
 * Default Ollama configuration
 */
export const DEFAULT_OLLAMA_CONFIG = {
    baseURL: 'http://localhost:11434',
    timeout: 120000, // 2 minutes for local inference
    maxRetries: 3,
    checkAvailability: true,
};
/**
 * Default llama.cpp configuration
 */
export const DEFAULT_LLAMA_CPP_CONFIG = {
    baseURL: 'http://localhost:8080',
    timeout: 120000,
    maxRetries: 3,
};
/**
 * Get all available Ollama model names
 */
export function getAvailableOllamaModels() {
    const allModels = [];
    for (const category of Object.values(OLLAMA_MODELS)) {
        allModels.push(...Object.keys(category));
    }
    return allModels;
}
/**
 * Get recommended model for a specific task
 * @param task Task type
 * @param quality Quality preference ('fast' | 'balanced' | 'quality')
 * @returns Model name
 */
export function getRecommendedModel(task, quality = 'balanced') {
    // For quick analysis, always use fast models
    if (task === 'quickAnalysis') {
        return 'qwen2.5-coder:7b';
    }
    // For comprehensive tasks, prefer quality
    if (task === 'comprehensive') {
        return quality === 'fast' ? 'qwen2.5-coder:14b' : 'qwen2.5-coder:32b';
    }
    // For other tasks, respect quality preference
    const modelsByQuality = {
        fast: 'qwen2.5-coder:7b',
        balanced: 'qwen2.5-coder:14b',
        quality: 'qwen2.5-coder:32b',
    };
    return modelsByQuality[quality];
}
/**
 * Get model information
 * @param modelName Model name
 * @returns Model information or undefined
 */
export function getModelInfo(modelName) {
    for (const category of Object.values(OLLAMA_MODELS)) {
        if (modelName in category) {
            return category[modelName];
        }
    }
    return undefined;
}
/**
 * Format model list for CLI display
 */
export function formatModelList() {
    let output = '\n📊 Recommended Ollama Models for Documentation:\n\n';
    for (const [category, models] of Object.entries(OLLAMA_MODELS)) {
        output += `${category.toUpperCase()} MODELS:\n`;
        for (const [modelName, info] of Object.entries(models)) {
            const isDefault = info.isDefault ? ' (DEFAULT)' : '';
            output += `  • ${modelName}${isDefault}\n`;
            output += `    ${info.description}\n`;
            output += `    Parameters: ${info.params} | Context: ${info.context}\n`;
            output += `    Speed: ~${info.estimatedTokensPerSec} tokens/sec\n`;
            output += `    Best for: ${info.recommendedFor.join(', ')}\n\n`;
        }
    }
    output += '💡 Quick Install:\n';
    output += '   ollama pull qwen2.5-coder:14b  # Recommended default\n';
    output += '   ollama pull qwen2.5-coder:7b   # Fast alternative\n\n';
    return output;
}
//# sourceMappingURL=local-llm-config.js.map