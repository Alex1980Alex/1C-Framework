/**
 * Error handling module for autodocument
 * @module errors
 */

/**
 * Base error class for autodocument
 */
export class AutodocError extends Error {
  public readonly code: string;
  public readonly suggestion?: string;
  public readonly details?: Record<string, unknown>;
  public readonly originalCause?: Error;

  constructor(
    message: string,
    code: string,
    options?: {
      suggestion?: string;
      details?: Record<string, unknown>;
      cause?: Error;
    }
  ) {
    super(message);
    this.name = 'AutodocError';
    this.code = code;
    this.suggestion = options?.suggestion;
    this.details = options?.details;
    this.originalCause = options?.cause;

    // Maintains proper stack trace for V8
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  /**
   * Format error for CLI output
   */
  toUserMessage(): string {
    let msg = `[${this.code}] ${this.message}`;
    if (this.suggestion) {
      msg += `\n\nSuggestion: ${this.suggestion}`;
    }
    return msg;
  }
}

/**
 * Configuration and validation errors
 */
export class ConfigurationError extends AutodocError {
  constructor(
    message: string,
    options?: {
      suggestion?: string;
      details?: Record<string, unknown>;
      cause?: Error;
    }
  ) {
    super(message, 'CONFIG_ERROR', options);
    this.name = 'ConfigurationError';
  }
}

/**
 * File system errors (file not found, permission denied, etc.)
 */
export class FileSystemError extends AutodocError {
  public readonly path: string;

  constructor(
    message: string,
    path: string,
    options?: {
      suggestion?: string;
      details?: Record<string, unknown>;
      cause?: Error;
    }
  ) {
    super(message, 'FS_ERROR', { ...options, details: { ...options?.details, path } });
    this.name = 'FileSystemError';
    this.path = path;
  }
}

/**
 * AI Provider errors (API failures, rate limits, etc.)
 */
export class ProviderError extends AutodocError {
  public readonly provider: string;
  public readonly retryable: boolean;
  public readonly statusCode?: number;

  constructor(
    message: string,
    provider: string,
    options?: {
      suggestion?: string;
      details?: Record<string, unknown>;
      cause?: Error;
      retryable?: boolean;
      statusCode?: number;
    }
  ) {
    super(message, 'PROVIDER_ERROR', options);
    this.name = 'ProviderError';
    this.provider = provider;
    this.retryable = options?.retryable ?? false;
    this.statusCode = options?.statusCode;
  }

  /**
   * Check if error is due to rate limiting
   */
  isRateLimited(): boolean {
    return this.statusCode === 429 || this.message.toLowerCase().includes('rate limit');
  }

  /**
   * Check if error is due to invalid API key
   */
  isAuthError(): boolean {
    return this.statusCode === 401 || this.statusCode === 403;
  }
}

/**
 * Parser errors (invalid syntax, malformed files, etc.)
 */
export class ParserError extends AutodocError {
  public readonly filePath?: string;
  public readonly line?: number;
  public readonly column?: number;

  constructor(
    message: string,
    options?: {
      suggestion?: string;
      details?: Record<string, unknown>;
      cause?: Error;
      filePath?: string;
      line?: number;
      column?: number;
    }
  ) {
    super(message, 'PARSER_ERROR', options);
    this.name = 'ParserError';
    this.filePath = options?.filePath;
    this.line = options?.line;
    this.column = options?.column;
  }

  toUserMessage(): string {
    let location = '';
    if (this.filePath) {
      location = this.filePath;
      if (this.line !== undefined) {
        location += `:${this.line}`;
        if (this.column !== undefined) {
          location += `:${this.column}`;
        }
      }
      location = ` at ${location}`;
    }
    return `[${this.code}] ${this.message}${location}${this.suggestion ? `\n\nSuggestion: ${this.suggestion}` : ''}`;
  }
}

/**
 * Validation errors
 */
export class ValidationError extends AutodocError {
  public readonly field?: string;

  constructor(
    message: string,
    options?: {
      suggestion?: string;
      details?: Record<string, unknown>;
      cause?: Error;
      field?: string;
    }
  ) {
    super(message, 'VALIDATION_ERROR', options);
    this.name = 'ValidationError';
    this.field = options?.field;
  }
}

/**
 * Timeout errors
 */
export class TimeoutError extends AutodocError {
  public readonly timeoutMs: number;
  public readonly operation: string;

  constructor(
    operation: string,
    timeoutMs: number,
    options?: {
      suggestion?: string;
      details?: Record<string, unknown>;
      cause?: Error;
    }
  ) {
    super(`Operation '${operation}' timed out after ${timeoutMs}ms`, 'TIMEOUT_ERROR', {
      ...options,
      suggestion: options?.suggestion ?? 'Try increasing the timeout or check network connectivity'
    });
    this.name = 'TimeoutError';
    this.timeoutMs = timeoutMs;
    this.operation = operation;
  }
}

/**
 * Error suggestions based on error type
 */
export const ERROR_SUGGESTIONS: Record<string, string> = {
  // Provider errors
  GEMINI_API_KEY: 'Set GEMINI_API_KEY environment variable or use --api-key option',
  GROQ_API_KEY: 'Set GROQ_API_KEY environment variable or use --api-key option',
  GROK_API_KEY: 'Set GROK_API_KEY environment variable or use --api-key option',
  OPENROUTER_API_KEY: 'Set OPENROUTER_API_KEY environment variable or use --api-key option',
  OLLAMA_NOT_RUNNING: 'Start Ollama server with: ollama serve',
  RATE_LIMITED: 'Wait a few minutes or switch to a different provider with --provider option',
  ALL_PROVIDERS_FAILED: 'Check your API keys and network connectivity. Try with --verbose for details.',

  // File errors
  PATH_NOT_EXISTS: 'Check that the path exists and is spelled correctly',
  PATH_NOT_DIRECTORY: 'Provide a directory path, not a file path',
  PERMISSION_DENIED: 'Check file permissions or run with appropriate privileges',

  // Config errors
  INVALID_PROVIDER: 'Valid providers: gemini, groq, ollama, grok, openrouter',
  INVALID_FORMAT: 'Valid output formats: console, markdown, json',

  // Parser errors
  INVALID_BSL: 'Check BSL syntax. The file may have encoding issues.',
  INVALID_XML: 'Check XML syntax. The file may be corrupted.',
  FORM_VALIDATION_FAILED: 'Form.xml and Module.bsl may be out of sync. Regenerate the form.'
};

/**
 * Get suggestion for error message
 */
export function getSuggestion(errorType: string): string | undefined {
  return ERROR_SUGGESTIONS[errorType];
}

/**
 * Wrap any error into AutodocError
 */
export function wrapError(error: unknown, context?: string): AutodocError {
  if (error instanceof AutodocError) {
    return error;
  }

  const message = error instanceof Error ? error.message : String(error);
  const fullMessage = context ? `${context}: ${message}` : message;

  return new AutodocError(fullMessage, 'UNKNOWN_ERROR', {
    cause: error instanceof Error ? error : undefined
  });
}

/**
 * Type guard for AutodocError
 */
export function isAutodocError(error: unknown): error is AutodocError {
  return error instanceof AutodocError;
}

/**
 * Type guard for retryable errors
 */
export function isRetryableError(error: unknown): boolean {
  if (error instanceof ProviderError) {
    return error.retryable && !error.isAuthError();
  }
  if (error instanceof TimeoutError) {
    return true;
  }
  return false;
}
