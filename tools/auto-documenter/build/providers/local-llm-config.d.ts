/**
 * Configuration for local LLM providers (Ollama, llama.cpp)
 * Provides optimized model selections for documentation generation tasks
 */
/**
 * Recommended Ollama models for documentation generation
 * Sorted by quality/speed trade-off
 */
export declare const OLLAMA_MODELS: {
    /**
     * Fast models - Good for large codebases, quick iterations
     * Speed: ★★★★★ | Quality: ★★★☆☆
     */
    fast: {
        'qwen2.5-coder:7b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
        'codellama:7b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
        'deepseek-coder:6.7b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
    };
    /**
     * Balanced models - Best overall choice for most use cases
     * Speed: ★★★★☆ | Quality: ★★★★☆
     */
    balanced: {
        'qwen2.5-coder:14b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
            isDefault: boolean;
        };
        'codellama:13b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
        'deepseek-coder-v2:16b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
    };
    /**
     * Quality models - Best documentation quality, slower inference
     * Speed: ★★★☆☆ | Quality: ★★★★★
     */
    quality: {
        'qwen2.5-coder:32b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
        'codellama:34b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
        'deepseek-coder:33b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
    };
    /**
     * General-purpose models - Not code-specific but can work
     * Speed: ★★★★☆ | Quality: ★★★☆☆
     */
    general: {
        'llama3.2:3b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
        'mistral:7b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
        'phi3:3.8b': {
            description: string;
            params: string;
            context: string;
            speed: string;
            recommendedFor: string[];
            estimatedTokensPerSec: number;
        };
    };
};
/**
 * Default model selection based on use case
 */
export declare const DEFAULT_MODELS: {
    readonly documentation: "qwen2.5-coder:14b";
    readonly codeReview: "qwen2.5-coder:14b";
    readonly testPlan: "qwen2.5-coder:14b";
    readonly quickAnalysis: "qwen2.5-coder:7b";
    readonly comprehensive: "qwen2.5-coder:32b";
};
/**
 * Ollama server configuration
 */
export interface OllamaConfig {
    baseURL: string;
    timeout: number;
    maxRetries: number;
    checkAvailability: boolean;
}
/**
 * Default Ollama configuration
 */
export declare const DEFAULT_OLLAMA_CONFIG: OllamaConfig;
/**
 * llama.cpp server configuration (for future implementation)
 */
export interface LlamaCppConfig {
    baseURL: string;
    timeout: number;
    maxRetries: number;
}
/**
 * Default llama.cpp configuration
 */
export declare const DEFAULT_LLAMA_CPP_CONFIG: LlamaCppConfig;
/**
 * Get all available Ollama model names
 */
export declare function getAvailableOllamaModels(): string[];
/**
 * Get recommended model for a specific task
 * @param task Task type
 * @param quality Quality preference ('fast' | 'balanced' | 'quality')
 * @returns Model name
 */
export declare function getRecommendedModel(task: keyof typeof DEFAULT_MODELS, quality?: 'fast' | 'balanced' | 'quality'): string;
/**
 * Get model information
 * @param modelName Model name
 * @returns Model information or undefined
 */
export declare function getModelInfo(modelName: string): any;
/**
 * Format model list for CLI display
 */
export declare function formatModelList(): string;
