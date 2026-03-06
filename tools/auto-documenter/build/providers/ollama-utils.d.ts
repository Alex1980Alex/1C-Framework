/**
 * Ollama server status
 */
export interface OllamaStatus {
    available: boolean;
    version?: string;
    models: string[];
    error?: string;
}
/**
 * Model pull progress
 */
export interface PullProgress {
    status: string;
    digest?: string;
    total?: number;
    completed?: number;
}
/**
 * Check if Ollama server is running
 * @param baseURL Ollama server URL (default: http://localhost:11434)
 * @returns Ollama status
 */
export declare function checkOllamaAvailability(baseURL?: string): Promise<OllamaStatus>;
/**
 * Check if a specific model is available locally
 * @param modelName Model name to check
 * @param baseURL Ollama server URL
 * @returns True if model is available
 */
export declare function isModelAvailable(modelName: string, baseURL?: string): Promise<boolean>;
/**
 * Pull a model from Ollama registry
 * @param modelName Model name to pull
 * @param baseURL Ollama server URL
 * @param onProgress Progress callback
 */
export declare function pullModel(modelName: string, baseURL?: string, onProgress?: (progress: PullProgress) => void): Promise<void>;
/**
 * Ensure a model is available, pull if needed
 * @param modelName Model name
 * @param baseURL Ollama server URL
 * @param autoPull Automatically pull if not available (default: true)
 * @returns True if model is ready
 */
export declare function ensureModelAvailable(modelName: string, baseURL?: string, autoPull?: boolean): Promise<boolean>;
/**
 * Get recommended setup instructions
 * @param includeInstall Include Ollama installation instructions
 */
export declare function getSetupInstructions(includeInstall?: boolean): string;
/**
 * Print diagnostic information about Ollama setup
 */
export declare function printDiagnostics(baseURL?: string): Promise<void>;
/**
 * Test Ollama inference with a simple prompt
 * @param modelName Model to test
 * @param baseURL Ollama server URL
 */
export declare function testInference(modelName: string, baseURL?: string): Promise<{
    success: boolean;
    response?: string;
    error?: string;
    timeMs?: number;
}>;
/**
 * Start Ollama server if not running
 * @param baseURL Ollama server URL
 * @returns True if server started or already running
 */
export declare function startOllama(baseURL?: string): Promise<boolean>;
/**
 * Check LLM Rotation HTTP server availability
 * @param rotationURL LLM Rotation server URL (default: http://localhost:8000)
 * @returns Status object
 */
export declare function checkRotationAvailability(rotationURL?: string): Promise<{
    available: boolean;
    providers?: number;
    error?: string;
}>;
/**
 * Ensure either LLM Rotation or Ollama is available
 * @param rotationURL LLM Rotation server URL
 * @param ollamaURL Ollama server URL
 * @returns Object with available provider info
 */
export declare function ensureProviderAvailable(rotationURL?: string, ollamaURL?: string): Promise<{
    provider: 'rotation' | 'ollama' | null;
    url: string | null;
    error?: string;
}>;
