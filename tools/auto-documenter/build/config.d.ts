/**
 * Configuration for the autodocument MCP server.
 *
 * Note: Prompt configurations are stored in src/prompt-config.ts.
 * For customizing the prompts used by the auto-* tools, modify that file.
 */
export interface AutodocumentConfig {
    openRouter: {
        apiKey: string;
        model: string;
        baseUrl: string;
        temperature: number;
        maxTokens: number;
    };
    fileProcessing: {
        codeExtensions: string[];
        maxFileSizeKb: number;
        maxFilesPerDirectory: number;
    };
    documentation: {
        outputFilename: string;
        fallbackFilename: string;
        updateExisting: boolean;
    };
    parallelProcessing: {
        enabled: boolean;
        maxConcurrency: number;
        requestDelayMs: number;
    };
}
/**
* Note: Tool-specific prompts are defined in src/prompt-config.ts
* This includes prompts for:
* - Documentation generation
* - Test plan generation
* - And future auto-* tools
*/
/**
 * Default configuration values for the autodocument MCP server.
 */
export declare const defaultConfig: AutodocumentConfig;
/**
 * Gets the current configuration by merging defaults with environment variables.
 */
export declare function getConfig(overrides?: Partial<AutodocumentConfig>): AutodocumentConfig;
