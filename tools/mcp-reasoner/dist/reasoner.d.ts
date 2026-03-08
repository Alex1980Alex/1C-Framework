import { ThoughtNode, ReasoningRequest, ReasoningResponse, ReasoningStats } from './types.js';
import { ReasoningStrategy } from './strategies/factory.js';
export declare class Reasoner {
    private stateManager;
    private currentStrategy;
    private strategies;
    private validator;
    private requestCounts;
    private requestTimes;
    private performanceOptimizer;
    constructor();
    processThought(request: ReasoningRequest): Promise<ReasoningResponse>;
    getStats(): Promise<ReasoningStats>;
    private getStrategyMetrics;
    getCurrentStrategyName(): ReasoningStrategy;
    getBestPath(): Promise<ThoughtNode[]>;
    clear(): Promise<void>;
    setStrategy(strategyType: ReasoningStrategy, beamWidth?: number, numSimulations?: number): void;
    getAvailableStrategies(): ReasoningStrategy[];
    /**
     * Check rate limits for requests
     */
    private checkRateLimit;
    /**
     * Check resource limits
     */
    private checkResourceLimits;
    /**
     * Switch strategy with error handling
     */
    private switchStrategy;
    /**
     * Process thought with timeout
     */
    private processWithTimeout;
    /**
     * Track request statistics
     */
    private trackRequest;
    /**
     * Sanitize request for logging (remove sensitive data)
     */
    private sanitizeRequestForLogging;
    /**
     * Get request statistics for monitoring
     */
    getRequestStats(): Record<string, any>;
    /**
     * Get health status
     */
    getHealthStatus(): Promise<Record<string, any>>;
}
