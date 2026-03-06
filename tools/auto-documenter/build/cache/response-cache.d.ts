/**
 * Response caching module for AI provider responses
 * Saves ~90% of tokens on repeated documentation runs
 * @module cache/response-cache
 */
/**
 * Cache configuration
 */
export interface CacheConfig {
    /** Cache directory path */
    directory: string;
    /** Time-to-live in seconds */
    ttlSeconds: number;
    /** Maximum cache size in MB */
    maxSizeMb: number;
    /** Enable caching */
    enabled: boolean;
}
/**
 * Default cache configuration
 */
export declare const DEFAULT_CACHE_CONFIG: CacheConfig;
/**
 * Cache entry metadata
 */
export interface CacheEntry {
    /** Content hash */
    hash: string;
    /** Provider used */
    provider: string;
    /** Model used */
    model: string;
    /** Prompt type (documentation, review, etc.) */
    promptType: string;
    /** Creation timestamp */
    createdAt: number;
    /** Expiration timestamp */
    expiresAt: number;
    /** Size in bytes */
    sizeBytes: number;
    /** Number of cache hits */
    hits: number;
}
/**
 * Cache statistics
 */
export interface CacheStats {
    /** Total entries */
    totalEntries: number;
    /** Total size in bytes */
    totalSizeBytes: number;
    /** Cache hits */
    hits: number;
    /** Cache misses */
    misses: number;
    /** Hit ratio (0-1) */
    hitRatio: number;
    /** Expired entries */
    expiredEntries: number;
    /** Tokens saved (estimated) */
    tokensSaved: number;
}
/**
 * Response cache class
 */
export declare class ResponseCache {
    private readonly config;
    private readonly cacheDir;
    private readonly metaDir;
    private stats;
    constructor(config?: Partial<CacheConfig>);
    /**
     * Initialize the cache directory
     */
    initialize(): Promise<void>;
    /**
     * Generate cache key from content and options
     */
    generateKey(content: string, provider: string, model: string, promptType: string): string;
    /**
     * Normalize content for consistent hashing
     */
    private normalizeContent;
    /**
     * Get cached response
     */
    get(key: string): Promise<string | null>;
    /**
     * Store response in cache
     */
    set(key: string, response: string, provider: string, model: string, promptType: string): Promise<void>;
    /**
     * Check if entry exists and is valid
     */
    has(key: string): Promise<boolean>;
    /**
     * Delete cache entry
     */
    delete(key: string): Promise<void>;
    /**
     * Clear all cache entries
     */
    clear(): Promise<void>;
    /**
     * Clean expired entries
     */
    cleanup(): Promise<number>;
    /**
     * Get cache statistics
     */
    getStats(): CacheStats;
    /**
     * Get list of all cache entries
     */
    getEntries(): Promise<CacheEntry[]>;
    /**
     * Get cache path for key
     */
    private getCachePath;
    /**
     * Get meta path for key
     */
    private getMetaPath;
    /**
     * Update hit ratio
     */
    private updateHitRatio;
    /**
     * Enforce maximum cache size
     */
    private enforceMaxSize;
    /**
     * Load stats from disk
     */
    private loadStats;
    /**
     * Save stats to disk
     */
    saveStats(): Promise<void>;
}
/**
 * Create and initialize a response cache
 */
export declare function createCache(config?: Partial<CacheConfig>): Promise<ResponseCache>;
/**
 * Cache wrapper for async functions
 * Automatically caches the result of AI provider calls
 */
export declare function withCache<T extends (...args: any[]) => Promise<string>>(cache: ResponseCache, fn: T, options: {
    provider: string;
    model: string;
    promptType: string;
    getContentKey: (...args: Parameters<T>) => string;
}): T;
