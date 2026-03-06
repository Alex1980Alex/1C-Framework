/**
 * Configuration for the autodocument MCP server.
 *
 * Note: Prompt configurations are stored in src/prompt-config.ts.
 * For customizing the prompts used by the auto-* tools, modify that file.
 */
export interface AutodocumentConfig {
  // OpenRouter settings
  openRouter: {
    apiKey: string;
    model: string;
    baseUrl: string;
    temperature: number;
    maxTokens: number;
  };

  // File processing settings
  fileProcessing: {
    codeExtensions: string[];
    maxFileSizeKb: number;
    maxFilesPerDirectory: number;
  };
  // Documentation settings
  documentation: {
    outputFilename: string;
    fallbackFilename: string;
    updateExisting: boolean;
  };

  // Parallel processing settings
  parallelProcessing: {
    enabled: boolean;
    maxConcurrency: number;  // Max directories to process simultaneously within a level
    requestDelayMs: number;  // Delay between requests to avoid rate limiting
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
export const defaultConfig: AutodocumentConfig = {
  openRouter: {
    apiKey: process.env.OPENROUTER_API_KEY || '',
    model: 'anthropic/claude-3-7-sonnet',
    baseUrl: 'https://openrouter.ai/api/v1',
    temperature: 0.5, // Lower temperature for more focused, deterministic responses
    maxTokens: 4000, // Reduced max tokens to limit response size
  },
  
  fileProcessing: {
    codeExtensions: ['.ts', '.js', '.tsx', '.jsx', '.py', '.java', '.c', '.cpp', '.cs', '.php', '.rb', '.go', '.rs', '.bsl'],
    maxFileSizeKb: 100,
    maxFilesPerDirectory: 10,
  },
  
  documentation: {
    outputFilename: 'documentation.md',
    fallbackFilename: 'undocumented.md',
    updateExisting: true,
  },

  parallelProcessing: {
    enabled: true,  // Enable parallel processing by default
    maxConcurrency: 5,  // Process up to 5 directories at the same time
    requestDelayMs: 2000,  // 2 second delay between batches to avoid rate limiting
  },
};

/**
 * Gets the current configuration by merging defaults with environment variables.
 */
export function getConfig(overrides?: Partial<AutodocumentConfig>): AutodocumentConfig {
  const config = { ...defaultConfig };
  
  // Override with environment variables if present
  if (process.env.OPENROUTER_API_KEY) {
    config.openRouter.apiKey = process.env.OPENROUTER_API_KEY;
  }
  
  if (process.env.OPENROUTER_MODEL) {
    config.openRouter.model = process.env.OPENROUTER_MODEL;
  }
  
  if (process.env.MAX_FILE_SIZE_KB) {
    config.fileProcessing.maxFileSizeKb = parseInt(process.env.MAX_FILE_SIZE_KB, 10);
  }
  
  if (process.env.MAX_FILES_PER_DIR) {
    config.fileProcessing.maxFilesPerDirectory = parseInt(process.env.MAX_FILES_PER_DIR, 10);
  }

  // Parallel processing environment variables
  if (process.env.PARALLEL_ENABLED) {
    config.parallelProcessing.enabled = process.env.PARALLEL_ENABLED === 'true';
  }

  if (process.env.PARALLEL_MAX_CONCURRENCY) {
    config.parallelProcessing.maxConcurrency = parseInt(process.env.PARALLEL_MAX_CONCURRENCY, 10);
  }

  if (process.env.REQUEST_DELAY_MS) {
    config.parallelProcessing.requestDelayMs = parseInt(process.env.REQUEST_DELAY_MS, 10);
  }

  // Apply manual overrides if provided
  if (overrides) {
    return {
      ...config,
      ...overrides,
      openRouter: {
        ...config.openRouter,
        ...(overrides.openRouter || {}),
      },
      fileProcessing: {
        ...config.fileProcessing,
        ...(overrides.fileProcessing || {}),
      },
      documentation: {
        ...config.documentation,
        ...(overrides.documentation || {}),
      },
      parallelProcessing: {
        ...config.parallelProcessing,
        ...(overrides.parallelProcessing || {}),
      },
    };
  }

  return config;
}
