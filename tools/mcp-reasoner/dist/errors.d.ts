/**
 * MCP Reasoner Error Classes
 * Comprehensive error handling for production environments
 */
export declare enum ErrorCode {
    INVALID_INPUT = "INVALID_INPUT",
    INVALID_THOUGHT = "INVALID_THOUGHT",
    INVALID_STRATEGY = "INVALID_STRATEGY",
    INVALID_PARAMETERS = "INVALID_PARAMETERS",
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED",
    TIMEOUT_EXCEEDED = "TIMEOUT_EXCEEDED",
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED",
    MAX_DEPTH_EXCEEDED = "MAX_DEPTH_EXCEEDED",
    STATE_CORRUPTION = "STATE_CORRUPTION",
    STRATEGY_FAILURE = "STRATEGY_FAILURE",
    SERIALIZATION_ERROR = "SERIALIZATION_ERROR",
    MCP_PROTOCOL_ERROR = "MCP_PROTOCOL_ERROR",
    CONNECTION_ERROR = "CONNECTION_ERROR",
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
}
export declare class ReasonerError extends Error {
    readonly code: ErrorCode;
    readonly timestamp: Date;
    readonly context?: Record<string, any>;
    readonly originalError?: Error;
    readonly retryable: boolean;
    constructor(code: ErrorCode, message: string, context?: Record<string, any>, originalError?: Error, retryable?: boolean);
    toJSON(): {
        name: string;
        code: ErrorCode;
        message: string;
        timestamp: string;
        context: Record<string, any> | undefined;
        retryable: boolean;
        stack: string | undefined;
        originalError: {
            name: string;
            message: string;
            stack: string | undefined;
        } | undefined;
    };
}
export declare class ValidationError extends ReasonerError {
    constructor(message: string, context?: Record<string, any>);
}
export declare class ResourceError extends ReasonerError {
    constructor(code: ErrorCode, message: string, context?: Record<string, any>);
}
export declare class StrategyError extends ReasonerError {
    constructor(message: string, context?: Record<string, any>, originalError?: Error);
}
/**
 * Error factory for creating specific error types
 */
export declare class ErrorFactory {
    static invalidInput(field: string, value: any, expected: string): ValidationError;
    static invalidThought(thought: string, reason: string): ValidationError;
    static invalidStrategy(strategy: string, available: string[]): ValidationError;
    static memoryLimitExceeded(current: number, limit: number): ResourceError;
    static timeoutExceeded(duration: number, limit: number): ResourceError;
    static rateLimitExceeded(requests: number, limit: number, window: number): ResourceError;
    static maxDepthExceeded(depth: number, maxDepth: number): ResourceError;
    static stateCorruption(details: string, context?: Record<string, any>): ReasonerError;
    static strategyFailure(strategy: string, error: Error): StrategyError;
    static mcpProtocolError(operation: string, error: Error): ReasonerError;
    static unknownError(error: Error, context?: Record<string, any>): ReasonerError;
}
/**
 * Error handling utilities
 */
export declare class ErrorHandler {
    private static errorCounts;
    private static lastErrors;
    /**
     * Handle an error with proper logging and metrics
     */
    static handle(error: Error, context?: Record<string, any>): ReasonerError;
    /**
     * Track error occurrences for monitoring
     */
    private static trackError;
    /**
     * Get error statistics for monitoring
     */
    static getErrorStats(): Record<string, any>;
    /**
     * Reset error statistics
     */
    static resetStats(): void;
    /**
     * Check if an error is retryable
     */
    static isRetryable(error: Error): boolean;
    /**
     * Create a sanitized error for client responses
     */
    static sanitizeForClient(error: ReasonerError): Record<string, any>;
}
