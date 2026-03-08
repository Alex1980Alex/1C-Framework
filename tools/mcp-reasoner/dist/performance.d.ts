/**
 * Performance optimization utilities for MCP Reasoner
 * Includes caching, memory management, and performance monitoring
 */
import { ThoughtNode, ReasoningRequest, ReasoningResponse } from './types.js';
export interface CacheConfig {
    maxSize: number;
    ttlMs: number;
    compressionEnabled: boolean;
    persistToDisk: boolean;
}
export interface CacheEntry<T> {
    value: T;
    timestamp: number;
    accessCount: number;
    size: number;
}
export interface PerformanceMetrics {
    cacheHits: number;
    cacheMisses: number;
    averageProcessingTime: number;
    memoryUsage: NodeJS.MemoryUsage;
    requestCount: number;
    errorRate: number;
}
/**
 * High-performance cache with TTL and compression
 */
export declare class PerformanceCache<K, V> {
    private cache;
    private config;
    private metrics;
    constructor(config: CacheConfig);
    /**
     * Get value from cache
     */
    get(key: K): V | undefined;
    /**
     * Set value in cache
     */
    set(key: K, value: V): void;
    /**
     * Check if key exists in cache
     */
    has(key: K): boolean;
    /**
     * Clear cache
     */
    clear(): void;
    /**
     * Get cache metrics
     */
    getMetrics(): Record<string, any>;
    /**
     * Evict least recently used item
     */
    private evictLRU;
    /**
     * Clean up expired entries
     */
    private cleanup;
    /**
     * Estimate object size in bytes
     */
    private estimateSize;
}
/**
 * Response cache for reasoning requests
 */
export declare class ResponseCache {
    private cache;
    constructor(config?: Partial<CacheConfig>);
    /**
     * Generate cache key for request
     */
    private generateKey;
    /**
     * Get cached response
     */
    get(request: ReasoningRequest): ReasoningResponse | undefined;
    /**
     * Cache response
     */
    set(request: ReasoningRequest, response: ReasoningResponse): void;
    /**
     * Check if request is cached
     */
    has(request: ReasoningRequest): boolean;
    /**
     * Clear cache
     */
    clear(): void;
    /**
     * Get cache metrics
     */
    getMetrics(): Record<string, any>;
}
/**
 * Memory pool for object reuse
 */
export declare class ObjectPool<T> {
    private pool;
    private factory;
    private reset;
    private maxSize;
    constructor(factory: () => T, reset: (obj: T) => void, maxSize?: number);
    /**
     * Get object from pool or create new one
     */
    acquire(): T;
    /**
     * Return object to pool
     */
    release(obj: T): void;
    /**
     * Get pool statistics
     */
    getStats(): {
        available: number;
        maxSize: number;
        utilizationRate: number;
    };
}
/**
 * Performance monitor for tracking metrics
 */
export declare class PerformanceMonitor {
    private requestTimes;
    private errorCount;
    private requestCount;
    private startTime;
    /**
     * Record request processing time
     */
    recordRequest(processingTime: number, success: boolean): void;
    /**
     * Get performance metrics
     */
    getMetrics(): PerformanceMetrics;
    /**
     * Reset metrics
     */
    reset(): void;
}
/**
 * Memory manager for monitoring and optimization
 */
export declare class MemoryManager {
    private gcThreshold;
    private lastGC;
    private gcInterval;
    /**
     * Check if garbage collection should be triggered
     */
    shouldTriggerGC(): boolean;
    /**
     * Force garbage collection if available
     */
    forceGC(): void;
    /**
     * Get memory statistics
     */
    getMemoryStats(): Record<string, any>;
    /**
     * Set GC threshold
     */
    setGCThreshold(threshold: number): void;
}
/**
 * Performance optimizer with all components
 */
export declare class PerformanceOptimizer {
    responseCache: ResponseCache;
    monitor: PerformanceMonitor;
    memoryManager: MemoryManager;
    thoughtPool: ObjectPool<Partial<ThoughtNode>>;
    constructor(cacheConfig?: Partial<CacheConfig>);
    /**
     * Get comprehensive performance metrics
     */
    getMetrics(): Record<string, any>;
    /**
     * Perform maintenance operations
     */
    performMaintenance(): void;
}
