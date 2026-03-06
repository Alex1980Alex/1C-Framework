/**
 * Retry utilities for robust error handling
 * @module utils/retry
 */
import { ProviderError, TimeoutError, isRetryableError } from '../errors/index.js';
/**
 * Default retry options
 */
export const DEFAULT_RETRY_OPTIONS = {
    maxRetries: 3,
    initialDelayMs: 1000,
    maxDelayMs: 30000,
    backoffMultiplier: 2,
    shouldRetry: isRetryableError
};
/**
 * Calculate delay with exponential backoff and jitter
 */
export function calculateDelay(attempt, initialDelayMs, maxDelayMs, backoffMultiplier) {
    // Exponential backoff
    const exponentialDelay = initialDelayMs * Math.pow(backoffMultiplier, attempt - 1);
    // Cap at max delay
    const cappedDelay = Math.min(exponentialDelay, maxDelayMs);
    // Add jitter (0-25% of delay) to prevent thundering herd
    const jitter = Math.random() * 0.25 * cappedDelay;
    return Math.floor(cappedDelay + jitter);
}
/**
 * Sleep for specified milliseconds
 */
export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
/**
 * Execute a function with retry logic
 *
 * @param fn - Async function to execute
 * @param options - Retry options
 * @returns Result with either success value or collected errors
 */
export async function withRetry(fn, options = {}) {
    const config = { ...DEFAULT_RETRY_OPTIONS, ...options };
    const errors = [];
    for (let attempt = 1; attempt <= config.maxRetries + 1; attempt++) {
        try {
            return await fn();
        }
        catch (error) {
            const err = error instanceof Error ? error : new Error(String(error));
            errors.push(err);
            // Check if we should retry
            const shouldRetry = config.shouldRetry?.(error) ?? isRetryableError(error);
            const hasMoreRetries = attempt <= config.maxRetries;
            if (!shouldRetry || !hasMoreRetries) {
                // Throw the last error with all collected errors as context
                if (errors.length === 1) {
                    throw errors[0];
                }
                // Create aggregate error
                const aggregateMessage = `Operation failed after ${attempt} attempt(s). Last error: ${err.message}`;
                const aggregateError = new Error(aggregateMessage);
                aggregateError.errors = errors;
                throw aggregateError;
            }
            // Calculate delay
            const delayMs = calculateDelay(attempt, config.initialDelayMs, config.maxDelayMs, config.backoffMultiplier);
            // Notify about retry
            config.onRetry?.(err, attempt, delayMs);
            // Wait before retry
            await sleep(delayMs);
        }
    }
    // This should never be reached
    throw new Error('Unexpected retry loop exit');
}
/**
 * Execute a function with retry logic, returning detailed result
 *
 * @param fn - Async function to execute
 * @param options - Retry options
 * @returns Detailed retry result
 */
export async function withRetryResult(fn, options = {}) {
    const config = { ...DEFAULT_RETRY_OPTIONS, ...options };
    const errors = [];
    for (let attempt = 1; attempt <= config.maxRetries + 1; attempt++) {
        try {
            const result = await fn();
            return {
                result,
                errors,
                attempts: attempt,
                success: true
            };
        }
        catch (error) {
            const err = error instanceof Error ? error : new Error(String(error));
            errors.push(err);
            const shouldRetry = config.shouldRetry?.(error) ?? isRetryableError(error);
            const hasMoreRetries = attempt <= config.maxRetries;
            if (!shouldRetry || !hasMoreRetries) {
                return {
                    errors,
                    attempts: attempt,
                    success: false
                };
            }
            const delayMs = calculateDelay(attempt, config.initialDelayMs, config.maxDelayMs, config.backoffMultiplier);
            config.onRetry?.(err, attempt, delayMs);
            await sleep(delayMs);
        }
    }
    return {
        errors,
        attempts: config.maxRetries + 1,
        success: false
    };
}
/**
 * Create a retry wrapper for provider calls
 *
 * @param providerName - Name of the provider for error messages
 * @param options - Retry options
 * @returns A function that wraps async operations with retry logic
 */
export function createProviderRetry(providerName, options = {}) {
    return async function (fn, operationName) {
        const operationDesc = operationName ? ` (${operationName})` : '';
        return withRetry(fn, {
            ...options,
            onRetry: (error, attempt, delayMs) => {
                console.warn(`[${providerName}]${operationDesc} Attempt ${attempt} failed: ${error.message}. ` +
                    `Retrying in ${Math.round(delayMs / 1000)}s...`);
                options.onRetry?.(error, attempt, delayMs);
            },
            shouldRetry: (error) => {
                // Provider-specific retry logic
                if (error instanceof ProviderError) {
                    // Don't retry auth errors
                    if (error.isAuthError()) {
                        return false;
                    }
                    // Retry rate limits with longer delay
                    if (error.isRateLimited()) {
                        return true;
                    }
                    return error.retryable;
                }
                // Retry network timeouts
                if (error instanceof TimeoutError) {
                    return true;
                }
                // Retry common transient errors
                const message = error instanceof Error ? error.message.toLowerCase() : '';
                return (message.includes('econnreset') ||
                    message.includes('etimedout') ||
                    message.includes('socket hang up') ||
                    message.includes('network') ||
                    message.includes('fetch failed'));
            }
        });
    };
}
/**
 * Rate limiter for provider calls
 */
export class RateLimiter {
    constructor(requestsPerMinute) {
        this.maxTokens = requestsPerMinute;
        this.tokens = requestsPerMinute;
        this.refillRate = requestsPerMinute / 60;
        this.lastRefill = Date.now();
    }
    /**
     * Acquire a token, waiting if necessary
     */
    async acquire() {
        this.refill();
        if (this.tokens >= 1) {
            this.tokens -= 1;
            return;
        }
        // Calculate wait time
        const tokensNeeded = 1 - this.tokens;
        const waitTime = (tokensNeeded / this.refillRate) * 1000;
        await sleep(waitTime);
        this.refill();
        this.tokens -= 1;
    }
    /**
     * Refill tokens based on elapsed time
     */
    refill() {
        const now = Date.now();
        const elapsed = (now - this.lastRefill) / 1000;
        this.tokens = Math.min(this.maxTokens, this.tokens + elapsed * this.refillRate);
        this.lastRefill = now;
    }
    /**
     * Get current available tokens
     */
    getAvailableTokens() {
        this.refill();
        return Math.floor(this.tokens);
    }
}
//# sourceMappingURL=retry.js.map