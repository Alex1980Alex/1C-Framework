/**
 * Retry utilities for robust error handling
 * @module utils/retry
 */
/**
 * Retry configuration options
 */
export interface RetryOptions {
    /** Maximum number of retry attempts */
    maxRetries: number;
    /** Initial delay in milliseconds */
    initialDelayMs: number;
    /** Maximum delay in milliseconds */
    maxDelayMs: number;
    /** Multiplier for exponential backoff */
    backoffMultiplier: number;
    /** Optional callback for retry events */
    onRetry?: (error: Error, attempt: number, delayMs: number) => void;
    /** Function to determine if error is retryable */
    shouldRetry?: (error: unknown) => boolean;
}
/**
 * Default retry options
 */
export declare const DEFAULT_RETRY_OPTIONS: RetryOptions;
/**
 * Calculate delay with exponential backoff and jitter
 */
export declare function calculateDelay(attempt: number, initialDelayMs: number, maxDelayMs: number, backoffMultiplier: number): number;
/**
 * Sleep for specified milliseconds
 */
export declare function sleep(ms: number): Promise<void>;
/**
 * Result of a retry operation
 */
export interface RetryResult<T> {
    /** The successful result (if any) */
    result?: T;
    /** Array of errors from failed attempts */
    errors: Error[];
    /** Total number of attempts made */
    attempts: number;
    /** Whether the operation succeeded */
    success: boolean;
}
/**
 * Execute a function with retry logic
 *
 * @param fn - Async function to execute
 * @param options - Retry options
 * @returns Result with either success value or collected errors
 */
export declare function withRetry<T>(fn: () => Promise<T>, options?: Partial<RetryOptions>): Promise<T>;
/**
 * Execute a function with retry logic, returning detailed result
 *
 * @param fn - Async function to execute
 * @param options - Retry options
 * @returns Detailed retry result
 */
export declare function withRetryResult<T>(fn: () => Promise<T>, options?: Partial<RetryOptions>): Promise<RetryResult<T>>;
/**
 * Create a retry wrapper for provider calls
 *
 * @param providerName - Name of the provider for error messages
 * @param options - Retry options
 * @returns A function that wraps async operations with retry logic
 */
export declare function createProviderRetry(providerName: string, options?: Partial<RetryOptions>): <T>(fn: () => Promise<T>, operationName?: string) => Promise<T>;
/**
 * Rate limiter for provider calls
 */
export declare class RateLimiter {
    private tokens;
    private lastRefill;
    private readonly maxTokens;
    private readonly refillRate;
    constructor(requestsPerMinute: number);
    /**
     * Acquire a token, waiting if necessary
     */
    acquire(): Promise<void>;
    /**
     * Refill tokens based on elapsed time
     */
    private refill;
    /**
     * Get current available tokens
     */
    getAvailableTokens(): number;
}
