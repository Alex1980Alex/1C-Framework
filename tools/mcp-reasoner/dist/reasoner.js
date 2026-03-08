import { CONFIG } from './types.js';
import { StateManager } from './state.js';
import { StrategyFactory, ReasoningStrategy } from './strategies/factory.js';
import { ErrorHandler, ErrorFactory } from './errors.js';
import { InputValidator } from './validation.js';
import { PerformanceOptimizer } from './performance.js';
export class Reasoner {
    constructor() {
        this.requestCounts = new Map();
        this.requestTimes = new Map();
        this.validator = new InputValidator();
        this.performanceOptimizer = new PerformanceOptimizer();
        this.stateManager = new StateManager(CONFIG.cacheSize);
        // Initialize available strategies
        this.strategies = new Map();
        // Initialize base strategies
        this.strategies.set(ReasoningStrategy.BEAM_SEARCH, StrategyFactory.createStrategy(ReasoningStrategy.BEAM_SEARCH, this.stateManager, CONFIG.beamWidth));
        this.strategies.set(ReasoningStrategy.MCTS, StrategyFactory.createStrategy(ReasoningStrategy.MCTS, this.stateManager, undefined, CONFIG.numSimulations));
        // Initialize experimental MCTS strategies
        this.strategies.set(ReasoningStrategy.MCTS_002_ALPHA, StrategyFactory.createStrategy(ReasoningStrategy.MCTS_002_ALPHA, this.stateManager, undefined, CONFIG.numSimulations));
        this.strategies.set(ReasoningStrategy.MCTS_002_ALT_ALPHA, StrategyFactory.createStrategy(ReasoningStrategy.MCTS_002_ALT_ALPHA, this.stateManager, undefined, CONFIG.numSimulations));
        // Initialize BSL-specific strategies (1C architecture analysis)
        this.strategies.set(ReasoningStrategy.BSL_ARCHITECTURE, StrategyFactory.createStrategy(ReasoningStrategy.BSL_ARCHITECTURE, this.stateManager));
        this.strategies.set(ReasoningStrategy.BSL_DOCUMENT_PATTERNS, StrategyFactory.createStrategy(ReasoningStrategy.BSL_DOCUMENT_PATTERNS, this.stateManager));
        this.strategies.set(ReasoningStrategy.BSL_SUBSYSTEM_ANALYSIS, StrategyFactory.createStrategy(ReasoningStrategy.BSL_SUBSYSTEM_ANALYSIS, this.stateManager));
        // Set default strategy
        const defaultStrategy = CONFIG.defaultStrategy;
        this.currentStrategy = this.strategies.get(defaultStrategy) ||
            this.strategies.get(ReasoningStrategy.BEAM_SEARCH);
    }
    async processThought(request) {
        const startTime = Date.now();
        try {
            // 1. Validate and sanitize input
            const sanitizedRequest = this.validator.validateRequest(request);
            // 2. Check cache first
            const cachedResponse = this.performanceOptimizer.responseCache.get(sanitizedRequest);
            if (cachedResponse) {
                this.trackRequest(true);
                this.performanceOptimizer.monitor.recordRequest(Date.now() - startTime, true);
                return {
                    ...cachedResponse,
                    strategyUsed: this.getCurrentStrategyName()
                };
            }
            // 3. Check rate limits
            this.checkRateLimit();
            // 4. Check resource limits
            await this.checkResourceLimits(sanitizedRequest);
            // 5. Perform maintenance if needed
            this.performanceOptimizer.performMaintenance();
            // 6. Switch strategy if requested
            if (sanitizedRequest.strategyType && this.strategies.has(sanitizedRequest.strategyType)) {
                await this.switchStrategy(sanitizedRequest);
            }
            // 7. Process thought using current strategy with timeout
            const response = await this.processWithTimeout(sanitizedRequest);
            // 8. Cache the response
            this.performanceOptimizer.responseCache.set(sanitizedRequest, response);
            // 9. Track successful request
            this.trackRequest(true);
            this.performanceOptimizer.monitor.recordRequest(Date.now() - startTime, true);
            // 10. Add strategy information to response
            return {
                ...response,
                strategyUsed: this.getCurrentStrategyName()
            };
        }
        catch (error) {
            // Track failed request
            this.trackRequest(false);
            this.performanceOptimizer.monitor.recordRequest(Date.now() - startTime, false);
            // Handle and rethrow as ReasonerError
            throw ErrorHandler.handle(error, {
                request: this.sanitizeRequestForLogging(request),
                processingTime: Date.now() - startTime
            });
        }
    }
    async getStats() {
        const nodes = await this.stateManager.getAllNodes();
        if (nodes.length === 0) {
            return {
                totalNodes: 0,
                averageScore: 0,
                maxDepth: 0,
                branchingFactor: 0,
                strategyMetrics: {}
            };
        }
        const scores = nodes.map(n => n.score);
        const depths = nodes.map(n => n.depth);
        const branchingFactors = nodes.map(n => n.children.length);
        const metrics = await this.getStrategyMetrics();
        return {
            totalNodes: nodes.length,
            averageScore: scores.reduce((a, b) => a + b, 0) / scores.length,
            maxDepth: Math.max(...depths),
            branchingFactor: branchingFactors.reduce((a, b) => a + b, 0) / nodes.length,
            strategyMetrics: metrics
        };
    }
    async getStrategyMetrics() {
        const metrics = {};
        for (const [name, strategy] of this.strategies.entries()) {
            metrics[name] = await strategy.getMetrics();
            if (strategy === this.currentStrategy) {
                metrics[name] = {
                    ...metrics[name],
                    active: true
                };
            }
        }
        return metrics;
    }
    getCurrentStrategyName() {
        for (const [name, strategy] of this.strategies.entries()) {
            if (strategy === this.currentStrategy) {
                return name;
            }
        }
        return ReasoningStrategy.BEAM_SEARCH;
    }
    async getBestPath() {
        return this.currentStrategy.getBestPath();
    }
    async clear() {
        await this.stateManager.clear();
        // Clear all strategies
        for (const strategy of this.strategies.values()) {
            await strategy.clear();
        }
    }
    setStrategy(strategyType, beamWidth, numSimulations) {
        if (!this.strategies.has(strategyType)) {
            throw new Error(`Unknown strategy type: ${strategyType}`);
        }
        // Create new strategy instance with appropriate parameters
        if (strategyType === ReasoningStrategy.BEAM_SEARCH) {
            this.currentStrategy = StrategyFactory.createStrategy(strategyType, this.stateManager, beamWidth);
        }
        else {
            // All MCTS variants (base and experimental) use numSimulations
            this.currentStrategy = StrategyFactory.createStrategy(strategyType, this.stateManager, undefined, numSimulations);
        }
        // Update strategy in map
        this.strategies.set(strategyType, this.currentStrategy);
    }
    getAvailableStrategies() {
        return Array.from(this.strategies.keys());
    }
    /**
     * Check rate limits for requests
     */
    checkRateLimit() {
        const now = Date.now();
        const window = 60000; // 1 minute window
        const maxRequests = 100; // Max 100 requests per minute
        // Clean old entries
        const cutoff = now - window;
        for (const [key, times] of this.requestTimes.entries()) {
            const validTimes = times.filter(time => time > cutoff);
            if (validTimes.length === 0) {
                this.requestTimes.delete(key);
            }
            else {
                this.requestTimes.set(key, validTimes);
            }
        }
        // Check current rate
        const clientId = 'global'; // In production, use actual client identification
        const times = this.requestTimes.get(clientId) || [];
        if (times.length >= maxRequests) {
            throw ErrorFactory.rateLimitExceeded(times.length, maxRequests, window);
        }
    }
    /**
     * Check resource limits
     */
    async checkResourceLimits(request) {
        // Check memory usage
        const memoryUsage = process.memoryUsage();
        const maxMemoryMB = 500; // 500MB limit
        const currentMemoryMB = memoryUsage.heapUsed / 1024 / 1024;
        if (currentMemoryMB > maxMemoryMB) {
            throw ErrorFactory.memoryLimitExceeded(currentMemoryMB, maxMemoryMB);
        }
        // Check state size
        const nodeCount = await this.stateManager.getNodeCount();
        const maxNodes = 10000;
        if (nodeCount > maxNodes) {
            throw ErrorFactory.stateCorruption(`Too many nodes in state: ${nodeCount} > ${maxNodes}`, { nodeCount, maxNodes });
        }
        // Check thought depth
        if (request.thoughtNumber > CONFIG.maxDepth * 10) {
            throw ErrorFactory.maxDepthExceeded(request.thoughtNumber, CONFIG.maxDepth * 10);
        }
    }
    /**
     * Switch strategy with error handling
     */
    async switchStrategy(request) {
        try {
            const strategyType = request.strategyType;
            // Create new strategy instance with appropriate parameters
            if (strategyType === ReasoningStrategy.BEAM_SEARCH) {
                this.currentStrategy = StrategyFactory.createStrategy(strategyType, this.stateManager, request.beamWidth);
            }
            else {
                // All MCTS variants (base and experimental) use numSimulations
                this.currentStrategy = StrategyFactory.createStrategy(strategyType, this.stateManager, undefined, request.numSimulations);
            }
            // Update strategy in map
            this.strategies.set(strategyType, this.currentStrategy);
        }
        catch (error) {
            throw ErrorFactory.strategyFailure(request.strategyType, error);
        }
    }
    /**
     * Process thought with timeout
     */
    async processWithTimeout(request) {
        const timeout = 30000; // 30 second timeout
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                reject(ErrorFactory.timeoutExceeded(timeout, timeout));
            }, timeout);
            this.currentStrategy.processThought(request)
                .then(response => {
                clearTimeout(timer);
                resolve(response);
            })
                .catch(error => {
                clearTimeout(timer);
                reject(error);
            });
        });
    }
    /**
     * Track request statistics
     */
    trackRequest(success) {
        const now = Date.now();
        const clientId = 'global'; // In production, use actual client identification
        // Track request times for rate limiting
        const times = this.requestTimes.get(clientId) || [];
        times.push(now);
        this.requestTimes.set(clientId, times);
        // Track request counts
        const key = success ? 'success' : 'failure';
        const count = this.requestCounts.get(key) || 0;
        this.requestCounts.set(key, count + 1);
    }
    /**
     * Sanitize request for logging (remove sensitive data)
     */
    sanitizeRequestForLogging(request) {
        return {
            thoughtNumber: request.thoughtNumber,
            totalThoughts: request.totalThoughts,
            nextThoughtNeeded: request.nextThoughtNeeded,
            strategyType: request.strategyType,
            beamWidth: request.beamWidth,
            numSimulations: request.numSimulations,
            // Truncate thought for logging
            thought: request.thought.substring(0, 100) + (request.thought.length > 100 ? '...' : '')
        };
    }
    /**
     * Get request statistics for monitoring
     */
    getRequestStats() {
        return {
            requests: Object.fromEntries(this.requestCounts),
            errors: ErrorHandler.getErrorStats(),
            memory: process.memoryUsage(),
            uptime: process.uptime(),
            performance: this.performanceOptimizer.getMetrics()
        };
    }
    /**
     * Get health status
     */
    async getHealthStatus() {
        try {
            const memoryUsage = process.memoryUsage();
            const nodeCount = await this.stateManager.getNodeCount();
            return {
                status: 'healthy',
                timestamp: new Date().toISOString(),
                memory: {
                    heapUsed: memoryUsage.heapUsed,
                    heapTotal: memoryUsage.heapTotal,
                    external: memoryUsage.external,
                    arrayBuffers: memoryUsage.arrayBuffers
                },
                state: {
                    nodeCount,
                    currentStrategy: this.getCurrentStrategyName(),
                    availableStrategies: this.getAvailableStrategies()
                },
                requests: this.getRequestStats()
            };
        }
        catch (error) {
            return {
                status: 'unhealthy',
                timestamp: new Date().toISOString(),
                error: error instanceof Error ? error.message : 'Unknown error'
            };
        }
    }
}
