import { OpenAI } from 'openai';
import { getConfig } from '../config.js';
import { createDefaultRotationManager } from '../providers/provider-rotation.js';
/**
 * Helper function to create a delay
 */
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
/**
 * Check if LLM Rotation HTTP server is available
 */
async function checkRotationHttpAvailable(url) {
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 2000);
        const response = await fetch(`${url}/health`, { signal: controller.signal });
        clearTimeout(timeout);
        return response.ok;
    }
    catch {
        return false;
    }
}
/**
 * Client for communicating with AI providers using OpenAI SDK
 * Supports multiple providers: OpenRouter, Gemini, Groq, Ollama
 *
 * When useRotation=true, uses LLM Rotation HTTP (localhost:8000) as primary,
 * falling back to internal TypeScript rotation if HTTP server unavailable.
 */
export class OpenRouterClient {
    /**
     * Creates a new AI client with optional provider rotation
     * @param apiKey API key (overrides config and environment)
     * @param model LLM model to use (overrides config)
     * @param useRotation Enable provider rotation (default: true if ENABLE_ROTATION env is set)
     */
    constructor(apiKey, model, useRotation) {
        this.config = getConfig();
        this.useLlmRotationHttp = false;
        this.llmRotationHttpUrl = 'http://localhost:8000';
        this.maxRetries = 3;
        this.retryDelayMs = 2000;
        this.useRotation = useRotation ?? (process.env.ENABLE_ROTATION === 'true');
        this.llmRotationHttpUrl = process.env.LLM_ROTATION_URL || 'http://localhost:8000';
        // Placeholder - will be initialized in initializeClient()
        this.client = null;
    }
    /**
     * Initialize the client asynchronously (must be called after constructor)
     */
    async initializeClient(apiKey, model) {
        if (this.useRotation) {
            // Try LLM Rotation HTTP first
            const rotationAvailable = await checkRotationHttpAvailable(this.llmRotationHttpUrl);
            if (rotationAvailable) {
                // Use centralized LLM Rotation HTTP server
                this.useLlmRotationHttp = true;
                this.client = new OpenAI({
                    apiKey: 'not-needed',
                    baseURL: `${this.llmRotationHttpUrl}/v1`,
                });
                console.error(`✅ Using LLM Rotation HTTP (${this.llmRotationHttpUrl})`);
            }
            else {
                // Fallback to internal TypeScript rotation
                console.error(`⚠️ LLM Rotation HTTP not available, using internal rotation`);
                this.rotationManager = createDefaultRotationManager();
                // Override with provided keys if available
                if (apiKey) {
                    const provider = process.env.PRIMARY_PROVIDER || 'gemini';
                    this.rotationManager.setApiKey(provider, apiKey);
                }
                if (model) {
                    const provider = process.env.PRIMARY_PROVIDER || 'gemini';
                    this.rotationManager.setModel(provider, model);
                }
                this.client = this.rotationManager.createClient();
            }
        }
        else {
            // Legacy mode: use OpenRouter only
            if (apiKey) {
                this.config.openRouter.apiKey = apiKey;
            }
            if (model) {
                this.config.openRouter.model = model;
            }
            // Validate API key
            if (!this.config.openRouter.apiKey) {
                throw new Error('OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable or pass it to the constructor. ' +
                    'Or enable rotation mode with ENABLE_ROTATION=true to use free providers.');
            }
            // Initialize OpenAI client with OpenRouter base URL
            this.client = new OpenAI({
                apiKey: this.config.openRouter.apiKey,
                baseURL: this.config.openRouter.baseUrl,
                defaultHeaders: {
                    'HTTP-Referer': 'https://github.com/PARS-DOE/autodocument',
                },
            });
        }
    }
    /**
     * Ensure client is initialized (for backward compatibility)
     */
    async ensureInitialized() {
        if (!this.client) {
            await this.initializeClient();
        }
    }
    /**
     * Check if error is a rate limit error (429)
     */
    isRateLimitError(error) {
        return error?.status === 429 ||
            error?.code === 429 ||
            error?.message?.includes('429') ||
            error?.message?.toLowerCase().includes('rate limit') ||
            error?.message?.toLowerCase().includes('too many requests') ||
            error?.message?.toLowerCase().includes('quota exceeded');
    }
    /**
     * Check if error indicates provider/model is unavailable (should switch provider)
     * 404 = model not found, 401 = invalid API key, 403 = access denied
     */
    isProviderUnavailableError(error) {
        const status = error?.status || error?.code;
        return status === 404 || status === 401 || status === 403 ||
            error?.message?.toLowerCase().includes('model not found') ||
            error?.message?.toLowerCase().includes('not found') ||
            error?.message?.toLowerCase().includes('invalid api key') ||
            error?.message?.toLowerCase().includes('unauthorized') ||
            error?.message?.toLowerCase().includes('access denied');
    }
    /**
     * Check if error is a temporary error that can be retried
     */
    isRetryableError(error) {
        const status = error?.status || error?.code;
        // 429 = rate limit, 500/502/503/504 = server errors
        return status === 429 || status === 500 || status === 502 || status === 503 || status === 504;
    }
    /**
     * Make API request with retry logic and provider fallback
     */
    async makeRequestWithRetry(modelToUse, systemPrompt, userMessage, attempt = 1) {
        await this.ensureInitialized();
        try {
            const completion = await this.client.chat.completions.create({
                model: modelToUse,
                messages: [
                    { role: 'system', content: systemPrompt },
                    { role: 'user', content: userMessage }
                ],
                temperature: this.config.openRouter.temperature,
                max_tokens: this.config.openRouter.maxTokens,
            });
            return completion;
        }
        catch (error) {
            console.error(`API request failed (attempt ${attempt}/${this.maxRetries}): ${error.message}`);
            // Handle rate limit - switch provider immediately
            if (this.isRateLimitError(error) && this.rotationManager) {
                console.warn(`⚠️ Rate limit hit on ${this.rotationManager.getCurrentProvider()}. Switching provider...`);
                this.rotationManager.forceSwitch();
                this.client = this.rotationManager.createClient();
                const newModel = this.rotationManager.getCurrentModel();
                console.error(`🔄 Switched to ${this.rotationManager.getCurrentProvider()} (model: ${newModel})`);
                // Wait before retry with new provider
                await sleep(this.retryDelayMs);
                return this.makeRequestWithRetry(newModel, systemPrompt, userMessage, 1);
            }
            // Handle provider unavailable (404, 401, 403) - switch provider immediately
            if (this.isProviderUnavailableError(error) && this.rotationManager) {
                console.warn(`⚠️ Provider ${this.rotationManager.getCurrentProvider()} unavailable (${error?.status || error?.code}). Switching provider...`);
                this.rotationManager.forceSwitch();
                this.client = this.rotationManager.createClient();
                const newModel = this.rotationManager.getCurrentModel();
                console.error(`🔄 Switched to ${this.rotationManager.getCurrentProvider()} (model: ${newModel})`);
                // Wait before retry with new provider
                await sleep(this.retryDelayMs);
                return this.makeRequestWithRetry(newModel, systemPrompt, userMessage, 1);
            }
            // Retry for temporary errors
            if (this.isRetryableError(error) && attempt < this.maxRetries) {
                const delay = this.retryDelayMs * Math.pow(2, attempt - 1); // Exponential backoff
                console.error(`⏳ Retrying in ${delay}ms...`);
                await sleep(delay);
                return this.makeRequestWithRetry(modelToUse, systemPrompt, userMessage, attempt + 1);
            }
            // Non-retryable error or max retries reached
            throw error;
        }
    }
    /**
     * Generate content with a custom system prompt
     * @param files Array of file content objects with path and content
     * @param systemPrompt Custom system prompt to use
     * @param existingContent Optional existing content to update
     * @param isTopLevel Whether this is the top level of the directory structure
     * @param childrenContent Optional content from child directories
     */
    async generateWithCustomPrompt(files, systemPrompt, existingContent, isTopLevel = false, childrenContent) {
        try {
            // Prepare file contents for the prompt
            const fileContents = files.map(file => `File: ${file.path}\n\`\`\`\n${file.content}\n\`\`\``).join('\n\n');
            // Prepare children content if available
            const childrenDocsContent = childrenContent ?
                childrenContent.map(doc => `Sub-directory Content: ${doc.path}\n\`\`\`markdown\n${doc.content}\n\`\`\``).join('\n\n') : '';
            // Prepare user message based on the inputs
            // Prepare user message
            let userMessage;
            if (files.length === 0 && childrenContent && childrenContent.length > 0) {
                userMessage = "Generate content that synthesizes and summarizes information from the following subdirectory files. This directory contains no code files itself, but needs content that aggregates information from its subdirectories:";
            }
            else {
                userMessage = "Generate comprehensive but concise content for the following code files:";
                if (fileContents) {
                    userMessage += `\n\n${fileContents}`;
                }
            }
            if (childrenDocsContent) {
                userMessage += `\n\nAdditionally, incorporate information from these subdirectory files:\n\n${childrenDocsContent}`;
            }
            if (existingContent) {
                userMessage += `\n\nExisting content for reference:\n\`\`\`markdown\n${existingContent}\n\`\`\``;
            }
            userMessage += "\n\nThe output should be in Markdown format with appropriate headings and explanations. DO NOT INCLUDE CODE SAMPLES OR CODE BLOCKS.";
            // Ensure client is initialized
            await this.ensureInitialized();
            // Determine model to use
            // LLM Rotation HTTP uses 'auto' model (server selects best provider)
            const modelToUse = this.useLlmRotationHttp
                ? 'auto'
                : (this.rotationManager?.getCurrentModel() || this.config.openRouter.model);
            // Check limits before making request (only for internal rotation)
            if (this.rotationManager && !this.useLlmRotationHttp) {
                const warning = this.rotationManager.checkLimits();
                if (warning) {
                    console.warn(warning);
                }
            }
            // Make request to AI provider with retry logic
            const completion = await this.makeRequestWithRetry(modelToUse, systemPrompt, userMessage);
            // Extract generated documentation
            const choice = completion.choices?.[0];
            const generatedContent = choice?.message?.content || '';
            // Track usage if using internal rotation (LLM Rotation HTTP tracks its own stats)
            if (this.rotationManager && !this.useLlmRotationHttp) {
                const inputTokens = completion.usage?.prompt_tokens || 0;
                const outputTokens = completion.usage?.completion_tokens || 0;
                this.rotationManager.recordSuccess(inputTokens, outputTokens);
            }
            // Log provider info from LLM Rotation HTTP response
            if (this.useLlmRotationHttp && completion.x_rotation_info) {
                const info = completion.x_rotation_info;
                console.error(`📊 LLM Rotation: provider=${info.provider}, time=${info.response_time?.toFixed(2)}s`);
            }
            return {
                content: generatedContent,
                successful: true
            };
        }
        catch (error) {
            console.error('Error generating documentation:', error.message);
            // Track error if using internal rotation
            if (this.rotationManager && !this.useLlmRotationHttp) {
                this.rotationManager.recordError(error.message);
            }
            return {
                content: '',
                successful: false,
                error: error.message
            };
        }
    }
    /**
     * Generate documentation for a collection of files (for backward compatibility)
     * @param files Array of file content objects with path and content
     * @param existingDocumentation Optional existing documentation to update
     * @param isTopLevel Whether this is the top level of the directory structure
     * @param childrenDocs Optional documentation from child directories
     */
    async generateDocumentation(files, existingDocumentation, isTopLevel = false, childrenDocs) {
        // Determine prompt based on level
        let systemPrompt;
        if (isTopLevel) {
            systemPrompt = `You are a technical documentation expert. Create a high-level markdown documentation file that explains the functionality and architecture of a code project. This is the TOP-LEVEL directory, so provide a comprehensive overview of the entire project structure. DO NOT INCLUDE CODE SAMPLES. Keep your response concise and focused on explaining what each file does and how components relate.`;
        }
        else if (childrenDocs && childrenDocs.length > 0) {
            systemPrompt = `You are a technical documentation expert. Create a markdown documentation file that explains the functionality of the code files in this directory. Include a section that integrates information from subdirectory documentation to show how components relate. DO NOT INCLUDE CODE SAMPLES. Simply explain what each file in the directory does and recap key information from subdirectories.`;
        }
        else {
            systemPrompt = `You are a technical documentation expert. Create a concise markdown documentation file that explains the functionality of the code files in this directory. Focus on what the code does, key functions, and how the files are related. DO NOT INCLUDE CODE SAMPLES. Keep your response brief and clear.`;
        }
        // Add instruction about existing documentation
        if (existingDocumentation) {
            systemPrompt += ` There is existing documentation that may need updating. Review it and incorporate any still-relevant information, but update as needed to match the current code.`;
        }
        // Use the new method with the constructed prompt
        return this.generateWithCustomPrompt(files, systemPrompt, existingDocumentation, isTopLevel, childrenDocs);
    }
    /**
     * Print provider usage statistics (if rotation is enabled)
     */
    printUsageStats() {
        if (this.rotationManager) {
            this.rotationManager.printUsageStats();
        }
        else {
            console.error('Provider rotation is disabled. Enable with ENABLE_ROTATION=true');
        }
    }
    /**
     * Get current provider name (if rotation is enabled)
     */
    getCurrentProvider() {
        if (this.useLlmRotationHttp) {
            return 'llm-rotation-http';
        }
        return this.rotationManager?.getCurrentProvider();
    }
    /**
     * Get current model name
     */
    getCurrentModel() {
        if (this.useLlmRotationHttp) {
            return 'auto';
        }
        return this.rotationManager?.getCurrentModel() || this.config.openRouter.model;
    }
    /**
     * Check if using LLM Rotation HTTP
     */
    isUsingLlmRotationHttp() {
        return this.useLlmRotationHttp;
    }
}
//# sourceMappingURL=client.js.map