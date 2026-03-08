/**
 * Performance optimization utilities for MCP Reasoner
 * Includes caching, memory management, and performance monitoring
 */
/**
 * High-performance cache with TTL and compression
 */
export class PerformanceCache {
    constructor(config) {
        this.cache = new Map();
        this.metrics = {
            hits: 0,
            misses: 0,
            evictions: 0,
            totalSize: 0
        };
        this.config = config;
        // Set up periodic cleanup
        setInterval(() => this.cleanup(), Math.min(this.config.ttlMs / 4, 60000));
    }
    /**
     * Get value from cache
     */
    get(key) {
        const entry = this.cache.get(key);
        if (!entry) {
            this.metrics.misses++;
            return undefined;
        }
        // Check TTL
        if (Date.now() - entry.timestamp > this.config.ttlMs) {
            this.cache.delete(key);
            this.metrics.misses++;
            this.metrics.totalSize -= entry.size;
            return undefined;
        }
        // Update access metrics
        entry.accessCount++;
        this.metrics.hits++;
        // Move to end (LRU)
        this.cache.delete(key);
        this.cache.set(key, entry);
        return entry.value;
    }
    /**
     * Set value in cache
     */
    set(key, value) {
        const size = this.estimateSize(value);
        // Check if we need to evict
        while (this.cache.size >= this.config.maxSize) {
            this.evictLRU();
        }
        const entry = {
            value,
            timestamp: Date.now(),
            accessCount: 1,
            size
        };
        this.cache.set(key, entry);
        this.metrics.totalSize += size;
    }
    /**
     * Check if key exists in cache
     */
    has(key) {
        const entry = this.cache.get(key);
        if (!entry)
            return false;
        // Check TTL
        if (Date.now() - entry.timestamp > this.config.ttlMs) {
            this.cache.delete(key);
            this.metrics.totalSize -= entry.size;
            return false;
        }
        return true;
    }
    /**
     * Clear cache
     */
    clear() {
        this.cache.clear();
        this.metrics.totalSize = 0;
    }
    /**
     * Get cache metrics
     */
    getMetrics() {
        return {
            ...this.metrics,
            hitRate: this.metrics.hits / (this.metrics.hits + this.metrics.misses) || 0,
            size: this.cache.size,
            averageSize: this.metrics.totalSize / this.cache.size || 0
        };
    }
    /**
     * Evict least recently used item
     */
    evictLRU() {
        const firstKey = this.cache.keys().next().value;
        if (firstKey !== undefined) {
            const entry = this.cache.get(firstKey);
            if (entry) {
                this.metrics.totalSize -= entry.size;
                this.metrics.evictions++;
            }
            this.cache.delete(firstKey);
        }
    }
    /**
     * Clean up expired entries
     */
    cleanup() {
        const now = Date.now();
        const toDelete = [];
        for (const [key, entry] of this.cache.entries()) {
            if (now - entry.timestamp > this.config.ttlMs) {
                toDelete.push(key);
                this.metrics.totalSize -= entry.size;
            }
        }
        toDelete.forEach(key => this.cache.delete(key));
    }
    /**
     * Estimate object size in bytes
     */
    estimateSize(value) {
        try {
            return JSON.stringify(value).length * 2; // Rough estimate (UTF-16)
        }
        catch {
            return 1000; // Default size for non-serializable objects
        }
    }
}
/**
 * Response cache for reasoning requests
 */
export class ResponseCache {
    constructor(config = {}) {
        const defaultConfig = {
            maxSize: 1000,
            ttlMs: 300000, // 5 minutes
            compressionEnabled: true,
            persistToDisk: false
        };
        this.cache = new PerformanceCache({ ...defaultConfig, ...config });
    }
    /**
     * Generate cache key for request
     */
    generateKey(request) {
        // Create deterministic key based on request parameters
        const keyData = {
            thought: request.thought,
            thoughtNumber: request.thoughtNumber,
            totalThoughts: request.totalThoughts,
            strategyType: request.strategyType,
            beamWidth: request.beamWidth,
            numSimulations: request.numSimulations
        };
        return Buffer.from(JSON.stringify(keyData)).toString('base64');
    }
    /**
     * Get cached response
     */
    get(request) {
        const key = this.generateKey(request);
        return this.cache.get(key);
    }
    /**
     * Cache response
     */
    set(request, response) {
        const key = this.generateKey(request);
        this.cache.set(key, response);
    }
    /**
     * Check if request is cached
     */
    has(request) {
        const key = this.generateKey(request);
        return this.cache.has(key);
    }
    /**
     * Clear cache
     */
    clear() {
        this.cache.clear();
    }
    /**
     * Get cache metrics
     */
    getMetrics() {
        return this.cache.getMetrics();
    }
}
/**
 * Memory pool for object reuse
 */
export class ObjectPool {
    constructor(factory, reset, maxSize = 100) {
        this.pool = [];
        this.factory = factory;
        this.reset = reset;
        this.maxSize = maxSize;
    }
    /**
     * Get object from pool or create new one
     */
    acquire() {
        if (this.pool.length > 0) {
            return this.pool.pop();
        }
        return this.factory();
    }
    /**
     * Return object to pool
     */
    release(obj) {
        if (this.pool.length < this.maxSize) {
            this.reset(obj);
            this.pool.push(obj);
        }
    }
    /**
     * Get pool statistics
     */
    getStats() {
        return {
            available: this.pool.length,
            maxSize: this.maxSize,
            utilizationRate: (this.maxSize - this.pool.length) / this.maxSize
        };
    }
}
/**
 * Performance monitor for tracking metrics
 */
export class PerformanceMonitor {
    constructor() {
        this.requestTimes = [];
        this.errorCount = 0;
        this.requestCount = 0;
        this.startTime = Date.now();
    }
    /**
     * Record request processing time
     */
    recordRequest(processingTime, success) {
        this.requestTimes.push(processingTime);
        this.requestCount++;
        if (!success) {
            this.errorCount++;
        }
        // Keep only recent times (last 1000 requests)
        if (this.requestTimes.length > 1000) {
            this.requestTimes = this.requestTimes.slice(-1000);
        }
    }
    /**
     * Get performance metrics
     */
    getMetrics() {
        const avgTime = this.requestTimes.length > 0
            ? this.requestTimes.reduce((a, b) => a + b, 0) / this.requestTimes.length
            : 0;
        return {
            cacheHits: 0, // Will be set by caller
            cacheMisses: 0, // Will be set by caller
            averageProcessingTime: avgTime,
            memoryUsage: process.memoryUsage(),
            requestCount: this.requestCount,
            errorRate: this.requestCount > 0 ? this.errorCount / this.requestCount : 0
        };
    }
    /**
     * Reset metrics
     */
    reset() {
        this.requestTimes = [];
        this.errorCount = 0;
        this.requestCount = 0;
        this.startTime = Date.now();
    }
}
/**
 * Memory manager for monitoring and optimization
 */
export class MemoryManager {
    constructor() {
        this.gcThreshold = 100 * 1024 * 1024; // 100MB
        this.lastGC = Date.now();
        this.gcInterval = 60000; // 1 minute
    }
    /**
     * Check if garbage collection should be triggered
     */
    shouldTriggerGC() {
        const now = Date.now();
        const memUsage = process.memoryUsage();
        // Trigger GC if memory usage is high or enough time has passed
        return (memUsage.heapUsed > this.gcThreshold ||
            (now - this.lastGC > this.gcInterval));
    }
    /**
     * Force garbage collection if available
     */
    forceGC() {
        if (global.gc) {
            global.gc();
            this.lastGC = Date.now();
        }
    }
    /**
     * Get memory statistics
     */
    getMemoryStats() {
        const usage = process.memoryUsage();
        return {
            heapUsed: usage.heapUsed,
            heapTotal: usage.heapTotal,
            heapUtilization: usage.heapUsed / usage.heapTotal,
            external: usage.external,
            arrayBuffers: usage.arrayBuffers,
            gcRecommended: this.shouldTriggerGC(),
            lastGC: this.lastGC
        };
    }
    /**
     * Set GC threshold
     */
    setGCThreshold(threshold) {
        this.gcThreshold = threshold;
    }
}
/**
 * Performance optimizer with all components
 */
export class PerformanceOptimizer {
    constructor(cacheConfig) {
        this.responseCache = new ResponseCache(cacheConfig);
        this.monitor = new PerformanceMonitor();
        this.memoryManager = new MemoryManager();
        // Create object pool for ThoughtNode objects
        this.thoughtPool = new ObjectPool(() => ({}), (obj) => {
            // Reset object properties
            Object.keys(obj).forEach(key => delete obj[key]);
        }, 50);
    }
    /**
     * Get comprehensive performance metrics
     */
    getMetrics() {
        const cacheMetrics = this.responseCache.getMetrics();
        const performanceMetrics = this.monitor.getMetrics();
        const memoryStats = this.memoryManager.getMemoryStats();
        const poolStats = this.thoughtPool.getStats();
        return {
            cache: cacheMetrics,
            performance: {
                ...performanceMetrics,
                cacheHits: cacheMetrics.hits,
                cacheMisses: cacheMetrics.misses
            },
            memory: memoryStats,
            pool: poolStats,
            timestamp: new Date().toISOString()
        };
    }
    /**
     * Perform maintenance operations
     */
    performMaintenance() {
        // Force GC if needed
        if (this.memoryManager.shouldTriggerGC()) {
            this.memoryManager.forceGC();
        }
    }
}
