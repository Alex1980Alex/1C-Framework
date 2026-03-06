/**
 * Retry utilities for robust error handling
 * @module utils/retry
 */

import { ProviderError, TimeoutError, isRetryableError } from '../errors/index.js';

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
export const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxRetries: 3,
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  backoffMultiplier: 2,
  shouldRetry: isRetryableError
};

/**
 * Calculate delay with exponential backoff and jitter
 */
export function calculateDelay(
  attempt: number,
  initialDelayMs: number,
  maxDelayMs: number,
  backoffMultiplier: number
): number {
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
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

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
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: Partial<RetryOptions> = {}
): Promise<T> {
  const config: RetryOptions = { ...DEFAULT_RETRY_OPTIONS, ...options };
  const errors: Error[] = [];

  for (let attempt = 1; attempt <= config.maxRetries + 1; attempt++) {
    try {
      return await fn();
    } catch (error) {
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
        (aggregateError as any).errors = errors;
        throw aggregateError;
      }

      // Calculate delay
      const delayMs = calculateDelay(
        attempt,
        config.initialDelayMs,
        config.maxDelayMs,
        config.backoffMultiplier
      );

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
export async function withRetryResult<T>(
  fn: () => Promise<T>,
  options: Partial<RetryOptions> = {}
): Promise<RetryResult<T>> {
  const config: RetryOptions = { ...DEFAULT_RETRY_OPTIONS, ...options };
  const errors: Error[] = [];

  for (let attempt = 1; attempt <= config.maxRetries + 1; attempt++) {
    try {
      const result = await fn();
      return {
        result,
        errors,
        attempts: attempt,
        success: true
      };
    } catch (error) {
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

      const delayMs = calculateDelay(
        attempt,
        config.initialDelayMs,
        config.maxDelayMs,
        config.backoffMultiplier
      );

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
export function createProviderRetry(
  providerName: string,
  options: Partial<RetryOptions> = {}
) {
  return async function <T>(fn: () => Promise<T>, operationName?: string): Promise<T> {
    const operationDesc = operationName ? ` (${operationName})` : '';

    return withRetry(fn, {
      ...options,
      onRetry: (error, attempt, delayMs) => {
        console.warn(
          `[${providerName}]${operationDesc} Attempt ${attempt} failed: ${error.message}. ` +
          `Retrying in ${Math.round(delayMs / 1000)}s...`
        );
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
        return (
          message.includes('econnreset') ||
          message.includes('etimedout') ||
          message.includes('socket hang up') ||
          message.includes('network') ||
          message.includes('fetch failed')
        );
      }
    });
  };
}

/**
 * Rate limiter for provider calls
 */
export class RateLimiter {
  private tokens: number;
  private lastRefill: number;
  private readonly maxTokens: number;
  private readonly refillRate: number; // tokens per second

  constructor(requestsPerMinute: number) {
    this.maxTokens = requestsPerMinute;
    this.tokens = requestsPerMinute;
    this.refillRate = requestsPerMinute / 60;
    this.lastRefill = Date.now();
  }

  /**
   * Acquire a token, waiting if necessary
   */
  async acquire(): Promise<void> {
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
  private refill(): void {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 1000;
    this.tokens = Math.min(this.maxTokens, this.tokens + elapsed * this.refillRate);
    this.lastRefill = now;
  }

  /**
   * Get current available tokens
   */
  getAvailableTokens(): number {
    this.refill();
    return Math.floor(this.tokens);
  }
}
