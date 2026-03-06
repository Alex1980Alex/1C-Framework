/**
 * Error handling module for autodocument
 * @module errors
 */
/**
 * Base error class for autodocument
 */
export declare class AutodocError extends Error {
    readonly code: string;
    readonly suggestion?: string;
    readonly details?: Record<string, unknown>;
    readonly originalCause?: Error;
    constructor(message: string, code: string, options?: {
        suggestion?: string;
        details?: Record<string, unknown>;
        cause?: Error;
    });
    /**
     * Format error for CLI output
     */
    toUserMessage(): string;
}
/**
 * Configuration and validation errors
 */
export declare class ConfigurationError extends AutodocError {
    constructor(message: string, options?: {
        suggestion?: string;
        details?: Record<string, unknown>;
        cause?: Error;
    });
}
/**
 * File system errors (file not found, permission denied, etc.)
 */
export declare class FileSystemError extends AutodocError {
    readonly path: string;
    constructor(message: string, path: string, options?: {
        suggestion?: string;
        details?: Record<string, unknown>;
        cause?: Error;
    });
}
/**
 * AI Provider errors (API failures, rate limits, etc.)
 */
export declare class ProviderError extends AutodocError {
    readonly provider: string;
    readonly retryable: boolean;
    readonly statusCode?: number;
    constructor(message: string, provider: string, options?: {
        suggestion?: string;
        details?: Record<string, unknown>;
        cause?: Error;
        retryable?: boolean;
        statusCode?: number;
    });
    /**
     * Check if error is due to rate limiting
     */
    isRateLimited(): boolean;
    /**
     * Check if error is due to invalid API key
     */
    isAuthError(): boolean;
}
/**
 * Parser errors (invalid syntax, malformed files, etc.)
 */
export declare class ParserError extends AutodocError {
    readonly filePath?: string;
    readonly line?: number;
    readonly column?: number;
    constructor(message: string, options?: {
        suggestion?: string;
        details?: Record<string, unknown>;
        cause?: Error;
        filePath?: string;
        line?: number;
        column?: number;
    });
    toUserMessage(): string;
}
/**
 * Validation errors
 */
export declare class ValidationError extends AutodocError {
    readonly field?: string;
    constructor(message: string, options?: {
        suggestion?: string;
        details?: Record<string, unknown>;
        cause?: Error;
        field?: string;
    });
}
/**
 * Timeout errors
 */
export declare class TimeoutError extends AutodocError {
    readonly timeoutMs: number;
    readonly operation: string;
    constructor(operation: string, timeoutMs: number, options?: {
        suggestion?: string;
        details?: Record<string, unknown>;
        cause?: Error;
    });
}
/**
 * Error suggestions based on error type
 */
export declare const ERROR_SUGGESTIONS: Record<string, string>;
/**
 * Get suggestion for error message
 */
export declare function getSuggestion(errorType: string): string | undefined;
/**
 * Wrap any error into AutodocError
 */
export declare function wrapError(error: unknown, context?: string): AutodocError;
/**
 * Type guard for AutodocError
 */
export declare function isAutodocError(error: unknown): error is AutodocError;
/**
 * Type guard for retryable errors
 */
export declare function isRetryableError(error: unknown): boolean;
