/**
 * Response from the LLM after generating documentation
 */
export interface DocumentationResponse {
    content: string;
    successful: boolean;
    error?: string;
}
/**
 * Client for communicating with AI providers using OpenAI SDK
 * Supports multiple providers: OpenRouter, Gemini, Groq, Ollama
 *
 * When useRotation=true, uses LLM Rotation HTTP (localhost:8000) as primary,
 * falling back to internal TypeScript rotation if HTTP server unavailable.
 */
export declare class OpenRouterClient {
    private client;
    private config;
    private rotationManager?;
    private useRotation;
    private useLlmRotationHttp;
    private llmRotationHttpUrl;
    private maxRetries;
    private retryDelayMs;
    /**
     * Creates a new AI client with optional provider rotation
     * @param apiKey API key (overrides config and environment)
     * @param model LLM model to use (overrides config)
     * @param useRotation Enable provider rotation (default: true if ENABLE_ROTATION env is set)
     */
    constructor(apiKey?: string, model?: string, useRotation?: boolean);
    /**
     * Initialize the client asynchronously (must be called after constructor)
     */
    initializeClient(apiKey?: string, model?: string): Promise<void>;
    /**
     * Ensure client is initialized (for backward compatibility)
     */
    private ensureInitialized;
    /**
     * Check if error is a rate limit error (429)
     */
    private isRateLimitError;
    /**
     * Check if error indicates provider/model is unavailable (should switch provider)
     * 404 = model not found, 401 = invalid API key, 403 = access denied
     */
    private isProviderUnavailableError;
    /**
     * Check if error is a temporary error that can be retried
     */
    private isRetryableError;
    /**
     * Make API request with retry logic and provider fallback
     */
    private makeRequestWithRetry;
    /**
     * Generate content with a custom system prompt
     * @param files Array of file content objects with path and content
     * @param systemPrompt Custom system prompt to use
     * @param existingContent Optional existing content to update
     * @param isTopLevel Whether this is the top level of the directory structure
     * @param childrenContent Optional content from child directories
     */
    generateWithCustomPrompt(files: Array<{
        path: string;
        content: string;
    }>, systemPrompt: string, existingContent?: string, isTopLevel?: boolean, childrenContent?: Array<{
        path: string;
        content: string;
    }>): Promise<DocumentationResponse>;
    /**
     * Generate documentation for a collection of files (for backward compatibility)
     * @param files Array of file content objects with path and content
     * @param existingDocumentation Optional existing documentation to update
     * @param isTopLevel Whether this is the top level of the directory structure
     * @param childrenDocs Optional documentation from child directories
     */
    generateDocumentation(files: Array<{
        path: string;
        content: string;
    }>, existingDocumentation?: string, isTopLevel?: boolean, childrenDocs?: Array<{
        path: string;
        content: string;
    }>): Promise<DocumentationResponse>;
    /**
     * Print provider usage statistics (if rotation is enabled)
     */
    printUsageStats(): void;
    /**
     * Get current provider name (if rotation is enabled)
     */
    getCurrentProvider(): string | undefined;
    /**
     * Get current model name
     */
    getCurrentModel(): string;
    /**
     * Check if using LLM Rotation HTTP
     */
    isUsingLlmRotationHttp(): boolean;
}
