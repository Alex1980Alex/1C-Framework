/**
 * MCP Reasoner Error Classes
 * Comprehensive error handling for production environments
 */
export var ErrorCode;
(function (ErrorCode) {
    // Input validation errors
    ErrorCode["INVALID_INPUT"] = "INVALID_INPUT";
    ErrorCode["INVALID_THOUGHT"] = "INVALID_THOUGHT";
    ErrorCode["INVALID_STRATEGY"] = "INVALID_STRATEGY";
    ErrorCode["INVALID_PARAMETERS"] = "INVALID_PARAMETERS";
    // Resource errors
    ErrorCode["MEMORY_LIMIT_EXCEEDED"] = "MEMORY_LIMIT_EXCEEDED";
    ErrorCode["TIMEOUT_EXCEEDED"] = "TIMEOUT_EXCEEDED";
    ErrorCode["RATE_LIMIT_EXCEEDED"] = "RATE_LIMIT_EXCEEDED";
    ErrorCode["MAX_DEPTH_EXCEEDED"] = "MAX_DEPTH_EXCEEDED";
    // Internal errors
    ErrorCode["STATE_CORRUPTION"] = "STATE_CORRUPTION";
    ErrorCode["STRATEGY_FAILURE"] = "STRATEGY_FAILURE";
    ErrorCode["SERIALIZATION_ERROR"] = "SERIALIZATION_ERROR";
    // Network/MCP errors
    ErrorCode["MCP_PROTOCOL_ERROR"] = "MCP_PROTOCOL_ERROR";
    ErrorCode["CONNECTION_ERROR"] = "CONNECTION_ERROR";
    // Unknown errors
    ErrorCode["UNKNOWN_ERROR"] = "UNKNOWN_ERROR";
})(ErrorCode || (ErrorCode = {}));
export class ReasonerError extends Error {
    constructor(code, message, context, originalError, retryable = false) {
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
    constructor(message, context) {
        super(ErrorCode.INVALID_INPUT, message, context, undefined, false);
        this.name = 'ValidationError';
    }
}
export class ResourceError extends ReasonerError {
    constructor(code, message, context) {
        super(code, message, context, undefined, true);
        this.name = 'ResourceError';
    }
}
export class StrategyError extends ReasonerError {
    constructor(message, context, originalError) {
        super(ErrorCode.STRATEGY_FAILURE, message, context, originalError, true);
        this.name = 'StrategyError';
    }
}
/**
 * Error factory for creating specific error types
 */
export class ErrorFactory {
    static invalidInput(field, value, expected) {
        return new ValidationError(`Invalid ${field}: expected ${expected}, got ${typeof value}`, { field, value, expected });
    }
    static invalidThought(thought, reason) {
        return new ValidationError(`Invalid thought: ${reason}`, { thought: thought.substring(0, 100), reason });
    }
    static invalidStrategy(strategy, available) {
        return new ValidationError(`Invalid strategy: ${strategy}. Available: ${available.join(', ')}`, { strategy, available });
    }
    static memoryLimitExceeded(current, limit) {
        return new ResourceError(ErrorCode.MEMORY_LIMIT_EXCEEDED, `Memory limit exceeded: ${current}MB > ${limit}MB`, { current, limit });
    }
    static timeoutExceeded(duration, limit) {
        return new ResourceError(ErrorCode.TIMEOUT_EXCEEDED, `Operation timeout: ${duration}ms > ${limit}ms`, { duration, limit });
    }
    static rateLimitExceeded(requests, limit, window) {
        return new ResourceError(ErrorCode.RATE_LIMIT_EXCEEDED, `Rate limit exceeded: ${requests} requests in ${window}ms > ${limit}`, { requests, limit, window });
    }
    static maxDepthExceeded(depth, maxDepth) {
        return new ResourceError(ErrorCode.MAX_DEPTH_EXCEEDED, `Maximum depth exceeded: ${depth} > ${maxDepth}`, { depth, maxDepth });
    }
    static stateCorruption(details, context) {
        return new ReasonerError(ErrorCode.STATE_CORRUPTION, `State corruption detected: ${details}`, context, undefined, false);
    }
    static strategyFailure(strategy, error) {
        return new StrategyError(`Strategy ${strategy} failed: ${error.message}`, { strategy }, error);
    }
    static mcpProtocolError(operation, error) {
        return new ReasonerError(ErrorCode.MCP_PROTOCOL_ERROR, `MCP protocol error in ${operation}: ${error.message}`, { operation }, error, true);
    }
    static unknownError(error, context) {
        return new ReasonerError(ErrorCode.UNKNOWN_ERROR, `Unknown error: ${error.message}`, context, error, true);
    }
}
/**
 * Error handling utilities
 */
export class ErrorHandler {
    /**
     * Handle an error with proper logging and metrics
     */
    static handle(error, context) {
        let reasonerError;
        if (error instanceof ReasonerError) {
            reasonerError = error;
        }
        else {
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
    static trackError(code) {
        const count = this.errorCounts.get(code) || 0;
        this.errorCounts.set(code, count + 1);
        this.lastErrors.set(code, new Date());
    }
    /**
     * Get error statistics for monitoring
     */
    static getErrorStats() {
        const stats = {};
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
    static resetStats() {
        this.errorCounts.clear();
        this.lastErrors.clear();
    }
    /**
     * Check if an error is retryable
     */
    static isRetryable(error) {
        if (error instanceof ReasonerError) {
            return error.retryable;
        }
        return false;
    }
    /**
     * Create a sanitized error for client responses
     */
    static sanitizeForClient(error) {
        return {
            code: error.code,
            message: error.message,
            retryable: error.retryable,
            timestamp: error.timestamp.toISOString()
            // Exclude internal details like stack traces and context
        };
    }
}
ErrorHandler.errorCounts = new Map();
ErrorHandler.lastErrors = new Map();
