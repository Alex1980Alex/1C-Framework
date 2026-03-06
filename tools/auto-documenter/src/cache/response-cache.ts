/**
 * Response caching module for AI provider responses
 * Saves ~90% of tokens on repeated documentation runs
 * @module cache/response-cache
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

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
export const DEFAULT_CACHE_CONFIG: CacheConfig = {
  directory: '.autodoc-cache',
  ttlSeconds: 86400, // 24 hours
  maxSizeMb: 100,
  enabled: true
};

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
export class ResponseCache {
  private readonly config: CacheConfig;
  private readonly cacheDir: string;
  private readonly metaDir: string;
  private stats: CacheStats = {
    totalEntries: 0,
    totalSizeBytes: 0,
    hits: 0,
    misses: 0,
    hitRatio: 0,
    expiredEntries: 0,
    tokensSaved: 0
  };

  constructor(config: Partial<CacheConfig> = {}) {
    this.config = { ...DEFAULT_CACHE_CONFIG, ...config };
    this.cacheDir = path.resolve(this.config.directory);
    this.metaDir = path.join(this.cacheDir, '.meta');
  }

  /**
   * Initialize the cache directory
   */
  async initialize(): Promise<void> {
    if (!this.config.enabled) {
      return;
    }

    if (!fs.existsSync(this.cacheDir)) {
      fs.mkdirSync(this.cacheDir, { recursive: true });
    }

    if (!fs.existsSync(this.metaDir)) {
      fs.mkdirSync(this.metaDir, { recursive: true });
    }

    // Load stats
    await this.loadStats();
  }

  /**
   * Generate cache key from content and options
   */
  generateKey(
    content: string,
    provider: string,
    model: string,
    promptType: string
  ): string {
    const data = JSON.stringify({
      content: this.normalizeContent(content),
      provider,
      model,
      promptType
    });
    return crypto.createHash('sha256').update(data).digest('hex');
  }

  /**
   * Normalize content for consistent hashing
   */
  private normalizeContent(content: string): string {
    return content
      .replace(/\r\n/g, '\n')
      .replace(/\s+$/gm, '')
      .trim();
  }

  /**
   * Get cached response
   */
  async get(key: string): Promise<string | null> {
    if (!this.config.enabled) {
      return null;
    }

    const cachePath = this.getCachePath(key);
    const metaPath = this.getMetaPath(key);

    if (!fs.existsSync(cachePath) || !fs.existsSync(metaPath)) {
      this.stats.misses++;
      return null;
    }

    try {
      const meta: CacheEntry = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));

      // Check expiration
      if (Date.now() > meta.expiresAt) {
        this.stats.expiredEntries++;
        this.stats.misses++;
        await this.delete(key);
        return null;
      }

      // Update hit count
      meta.hits++;
      fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2));

      const response = fs.readFileSync(cachePath, 'utf-8');
      this.stats.hits++;
      // Estimate tokens saved (roughly 4 chars per token)
      this.stats.tokensSaved += Math.ceil(response.length / 4);
      this.updateHitRatio();

      return response;
    } catch {
      this.stats.misses++;
      return null;
    }
  }

  /**
   * Store response in cache
   */
  async set(
    key: string,
    response: string,
    provider: string,
    model: string,
    promptType: string
  ): Promise<void> {
    if (!this.config.enabled) {
      return;
    }

    // Check cache size limit
    await this.enforceMaxSize(response.length);

    const cachePath = this.getCachePath(key);
    const metaPath = this.getMetaPath(key);

    const meta: CacheEntry = {
      hash: key,
      provider,
      model,
      promptType,
      createdAt: Date.now(),
      expiresAt: Date.now() + this.config.ttlSeconds * 1000,
      sizeBytes: Buffer.byteLength(response, 'utf-8'),
      hits: 0
    };

    try {
      fs.writeFileSync(cachePath, response, 'utf-8');
      fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2), 'utf-8');
      this.stats.totalEntries++;
      this.stats.totalSizeBytes += meta.sizeBytes;
    } catch (error) {
      console.error('Failed to write cache entry:', error);
    }
  }

  /**
   * Check if entry exists and is valid
   */
  async has(key: string): Promise<boolean> {
    if (!this.config.enabled) {
      return false;
    }

    const cachePath = this.getCachePath(key);
    const metaPath = this.getMetaPath(key);

    if (!fs.existsSync(cachePath) || !fs.existsSync(metaPath)) {
      return false;
    }

    try {
      const meta: CacheEntry = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
      return Date.now() <= meta.expiresAt;
    } catch {
      return false;
    }
  }

  /**
   * Delete cache entry
   */
  async delete(key: string): Promise<void> {
    const cachePath = this.getCachePath(key);
    const metaPath = this.getMetaPath(key);

    if (fs.existsSync(metaPath)) {
      try {
        const meta: CacheEntry = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
        this.stats.totalSizeBytes -= meta.sizeBytes;
        this.stats.totalEntries--;
      } catch {
        // Ignore
      }
    }

    if (fs.existsSync(cachePath)) {
      fs.unlinkSync(cachePath);
    }

    if (fs.existsSync(metaPath)) {
      fs.unlinkSync(metaPath);
    }
  }

  /**
   * Clear all cache entries
   */
  async clear(): Promise<void> {
    if (fs.existsSync(this.cacheDir)) {
      fs.rmSync(this.cacheDir, { recursive: true });
      fs.mkdirSync(this.cacheDir, { recursive: true });
      fs.mkdirSync(this.metaDir, { recursive: true });
    }

    this.stats = {
      totalEntries: 0,
      totalSizeBytes: 0,
      hits: this.stats.hits,
      misses: this.stats.misses,
      hitRatio: this.stats.hitRatio,
      expiredEntries: 0,
      tokensSaved: this.stats.tokensSaved
    };
  }

  /**
   * Clean expired entries
   */
  async cleanup(): Promise<number> {
    if (!fs.existsSync(this.metaDir)) {
      return 0;
    }

    const files = fs.readdirSync(this.metaDir);
    let cleaned = 0;

    for (const file of files) {
      if (!file.endsWith('.json')) continue;

      const metaPath = path.join(this.metaDir, file);
      try {
        const meta: CacheEntry = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
        if (Date.now() > meta.expiresAt) {
          await this.delete(meta.hash);
          cleaned++;
        }
      } catch {
        // Remove corrupted meta file
        fs.unlinkSync(metaPath);
        cleaned++;
      }
    }

    return cleaned;
  }

  /**
   * Get cache statistics
   */
  getStats(): CacheStats {
    return { ...this.stats };
  }

  /**
   * Get list of all cache entries
   */
  async getEntries(): Promise<CacheEntry[]> {
    if (!fs.existsSync(this.metaDir)) {
      return [];
    }

    const files = fs.readdirSync(this.metaDir);
    const entries: CacheEntry[] = [];

    for (const file of files) {
      if (!file.endsWith('.json')) continue;

      const metaPath = path.join(this.metaDir, file);
      try {
        const meta: CacheEntry = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
        entries.push(meta);
      } catch {
        // Skip corrupted entries
      }
    }

    return entries;
  }

  /**
   * Get cache path for key
   */
  private getCachePath(key: string): string {
    return path.join(this.cacheDir, `${key}.cache`);
  }

  /**
   * Get meta path for key
   */
  private getMetaPath(key: string): string {
    return path.join(this.metaDir, `${key}.json`);
  }

  /**
   * Update hit ratio
   */
  private updateHitRatio(): void {
    const total = this.stats.hits + this.stats.misses;
    this.stats.hitRatio = total > 0 ? this.stats.hits / total : 0;
  }

  /**
   * Enforce maximum cache size
   */
  private async enforceMaxSize(newEntrySize: number): Promise<void> {
    const maxBytes = this.config.maxSizeMb * 1024 * 1024;

    if (this.stats.totalSizeBytes + newEntrySize <= maxBytes) {
      return;
    }

    // Get entries sorted by last access (oldest first)
    const entries = await this.getEntries();
    entries.sort((a, b) => a.createdAt - b.createdAt);

    // Remove oldest entries until we have space
    for (const entry of entries) {
      if (this.stats.totalSizeBytes + newEntrySize <= maxBytes * 0.8) {
        break;
      }
      await this.delete(entry.hash);
    }
  }

  /**
   * Load stats from disk
   */
  private async loadStats(): Promise<void> {
    const statsPath = path.join(this.cacheDir, 'stats.json');

    if (fs.existsSync(statsPath)) {
      try {
        const saved = JSON.parse(fs.readFileSync(statsPath, 'utf-8'));
        this.stats.hits = saved.hits || 0;
        this.stats.misses = saved.misses || 0;
        this.stats.tokensSaved = saved.tokensSaved || 0;
        this.updateHitRatio();
      } catch {
        // Ignore
      }
    }

    // Recalculate size and entries
    const entries = await this.getEntries();
    this.stats.totalEntries = entries.length;
    this.stats.totalSizeBytes = entries.reduce((sum, e) => sum + e.sizeBytes, 0);
  }

  /**
   * Save stats to disk
   */
  async saveStats(): Promise<void> {
    const statsPath = path.join(this.cacheDir, 'stats.json');
    const toSave = {
      hits: this.stats.hits,
      misses: this.stats.misses,
      tokensSaved: this.stats.tokensSaved
    };
    fs.writeFileSync(statsPath, JSON.stringify(toSave, null, 2));
  }
}

/**
 * Create and initialize a response cache
 */
export async function createCache(config?: Partial<CacheConfig>): Promise<ResponseCache> {
  const cache = new ResponseCache(config);
  await cache.initialize();
  return cache;
}

/**
 * Cache wrapper for async functions
 * Automatically caches the result of AI provider calls
 */
export function withCache<T extends (...args: any[]) => Promise<string>>(
  cache: ResponseCache,
  fn: T,
  options: {
    provider: string;
    model: string;
    promptType: string;
    getContentKey: (...args: Parameters<T>) => string;
  }
): T {
  return (async (...args: Parameters<T>): Promise<string> => {
    const contentKey = options.getContentKey(...args);
    const cacheKey = cache.generateKey(
      contentKey,
      options.provider,
      options.model,
      options.promptType
    );

    // Try to get from cache
    const cached = await cache.get(cacheKey);
    if (cached !== null) {
      return cached;
    }

    // Call original function
    const result = await fn(...args);

    // Store in cache
    await cache.set(
      cacheKey,
      result,
      options.provider,
      options.model,
      options.promptType
    );

    return result;
  }) as T;
}
