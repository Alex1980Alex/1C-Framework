/**
 * MCP Reasoner Error Classes
 * Comprehensive error handling for production environments
 */

export enum ErrorCode {
  // Input validation errors
  INVALID_INPUT = 'INVALID_INPUT',
  INVALID_THOUGHT = 'INVALID_THOUGHT',
  INVALID_STRATEGY = 'INVALID_STRATEGY',
  INVALID_PARAMETERS = 'INVALID_PARAMETERS',

  // Resource errors
  MEMORY_LIMIT_EXCEEDED = 'MEMORY_LIMIT_EXCEEDED',
  TIMEOUT_EXCEEDED = 'TIMEOUT_EXCEEDED',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  MAX_DEPTH_EXCEEDED = 'MAX_DEPTH_EXCEEDED',

  // Internal errors
  STATE_CORRUPTION = 'STATE_CORRUPTION',
  STRATEGY_FAILURE = 'STRATEGY_FAILURE',
  SERIALIZATION_ERROR = 'SERIALIZATION_ERROR',

  // Network/MCP errors
  MCP_PROTOCOL_ERROR = 'MCP_PROTOCOL_ERROR',
  CONNECTION_ERROR = 'CONNECTION_ERROR',

  // Unknown errors
  UNKNOWN_ERROR = 'UNKNOWN_ERROR'
}

export class ReasonerError extends Error {
  public readonly code: ErrorCode;
  public readonly timestamp: Date;
  public readonly context?: Record<string, any>;
  public readonly originalError?: Error;
  public readonly retryable: boolean;

  constructor(
    code: ErrorCode,
    message: string,
    context?: Record<string, any>,
    originalError?: Error,
    retryable: boolean = false
  ) {
    super(message);
    this.name = 'ReasonerError';
    this.code = code;
    this.timestamp = new Date();
    this.context = context;
    this.originalError = originalError;
    this.retryable = retryable;

    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ReasonerError);
    }
  }

  toJSON() {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      timestamp: this.timestamp.toISOString(),
      context: this.context,
      retryable: this.retryable,
      stack: this.stack,
      originalError: this.originalError ? {
        name: this.originalError.name,
        message: this.originalError.message,
        stack: this.originalError.stack
      } : undefined
    };
  }
}

export class ValidationError extends ReasonerError {
  constructor(message: string, context?: Record<string, any>) {
    super(ErrorCode.INVALID_INPUT, message, context, undefined, false);
    this.name = 'ValidationError';
  }
}

export class ResourceError extends ReasonerError {
  constructor(code: ErrorCode, message: string, context?: Record<string, any>) {
    super(code, message, context, undefined, true);
    this.name = 'ResourceError';
  }
}

export class StrategyError extends ReasonerError {
  constructor(message: string, context?: Record<string, any>, originalError?: Error) {
    super(ErrorCode.STRATEGY_FAILURE, message, context, originalError, true);
    this.name = 'StrategyError';
  }
}

/**
 * Error factory for creating specific error types
 */
export class ErrorFactory {
  static invalidInput(field: string, value: any, expected: string): ValidationError {
    return new ValidationError(
      `Invalid ${field}: expected ${expected}, got ${typeof value}`,
      { field, value, expected }
    );
  }

  static invalidThought(thought: string, reason: string): ValidationError {
    return new ValidationError(
      `Invalid thought: ${reason}`,
      { thought: thought.substring(0, 100), reason }
    );
  }

  static invalidStrategy(strategy: string, available: string[]): ValidationError {
    return new ValidationError(
      `Invalid strategy: ${strategy}. Available: ${available.join(', ')}`,
      { strategy, available }
    );
  }

  static memoryLimitExceeded(current: number, limit: number): ResourceError {
    return new ResourceError(
      ErrorCode.MEMORY_LIMIT_EXCEEDED,
      `Memory limit exceeded: ${current}MB > ${limit}MB`,
      { current, limit }
    );
  }

  static timeoutExceeded(duration: number, limit: number): ResourceError {
    return new ResourceError(
      ErrorCode.TIMEOUT_EXCEEDED,
      `Operation timeout: ${duration}ms > ${limit}ms`,
      { duration, limit }
    );
  }

  static rateLimitExceeded(requests: number, limit: number, window: number): ResourceError {
    return new ResourceError(
      ErrorCode.RATE_LIMIT_EXCEEDED,
      `Rate limit exceeded: ${requests} requests in ${window}ms > ${limit}`,
      { requests, limit, window }
    );
  }

  static maxDepthExceeded(depth: number, maxDepth: number): ResourceError {
    return new ResourceError(
      ErrorCode.MAX_DEPTH_EXCEEDED,
      `Maximum depth exceeded: ${depth} > ${maxDepth}`,
      { depth, maxDepth }
    );
  }

  static stateCorruption(details: string, context?: Record<string, any>): ReasonerError {
    return new ReasonerError(
      ErrorCode.STATE_CORRUPTION,
      `State corruption detected: ${details}`,
      context,
      undefined,
      false
    );
  }

  static strategyFailure(strategy: string, error: Error): StrategyError {
    return new StrategyError(
      `Strategy ${strategy} failed: ${error.message}`,
      { strategy },
      error
    );
  }

  static mcpProtocolError(operation: string, error: Error): ReasonerError {
    return new ReasonerError(
      ErrorCode.MCP_PROTOCOL_ERROR,
      `MCP protocol error in ${operation}: ${error.message}`,
      { operation },
      error,
      true
    );
  }

  static unknownError(error: Error, context?: Record<string, any>): ReasonerError {
    return new ReasonerError(
      ErrorCode.UNKNOWN_ERROR,
      `Unknown error: ${error.message}`,
      context,
      error,
      true
    );
  }
}

/**
 * Error handling utilities
 */
export class ErrorHandler {
  private static errorCounts = new Map<ErrorCode, number>();
  private static lastErrors = new Map<ErrorCode, Date>();

  /**
   * Handle an error with proper logging and metrics
   */
  static handle(error: Error, context?: Record<string, any>): ReasonerError {
    let reasonerError: ReasonerError;

    if (error instanceof ReasonerError) {
      reasonerError = error;
    } else {
      reasonerError = ErrorFactory.unknownError(error, context);
    }

    // Track error statistics
    this.trackError(reasonerError.code);

    // Log error (in production, this would go to a proper logger)
    console.error('ReasonerError:', reasonerError.toJSON());

    return reasonerError;
  }

  /**
   * Track error occurrences for monitoring
   */
  private static trackError(code: ErrorCode): void {
    const count = this.errorCounts.get(code) || 0;
    this.errorCounts.set(code, count + 1);
    this.lastErrors.set(code, new Date());
  }

  /**
   * Get error statistics for monitoring
   */
  static getErrorStats(): Record<string, any> {
    const stats: Record<string, any> = {};

    for (const [code, count] of this.errorCounts.entries()) {
      stats[code] = {
        count,
        lastOccurrence: this.lastErrors.get(code)?.toISOString()
      };
    }

    return stats;
  }

  /**
   * Reset error statistics
   */
  static resetStats(): void {
    this.errorCounts.clear();
    this.lastErrors.clear();
  }

  /**
   * Check if an error is retryable
   */
  static isRetryable(error: Error): boolean {
    if (error instanceof ReasonerError) {
      return error.retryable;
    }
    return false;
  }

  /**
   * Create a sanitized error for client responses
   */
  static sanitizeForClient(error: ReasonerError): Record<string, any> {
    return {
      code: error.code,
      message: error.message,
      retryable: error.retryable,
      timestamp: error.timestamp.toISOString()
      // Exclude internal details like stack traces and context
    };
  }
}