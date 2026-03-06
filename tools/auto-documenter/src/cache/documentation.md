# Autodoc Cache Module Documentation

This module provides functionality for caching responses from AI providers, significantly reducing token usage for repeated documentation tasks.

## `index.ts`

This file serves as the main entry point for the cache module. It exports the `ResponseCache` class and related functionalities defined in `response-cache.ts`.

## `response-cache.ts`

This file contains the core implementation of the response caching mechanism.

### Key Concepts

*   **Cache Configuration (`CacheConfig`)**: Defines settings for the cache, including the directory, time-to-live (TTL), maximum size, and whether caching is enabled.
*   **Default Configuration (`DEFAULT_CACHE_CONFIG`)**: Provides sensible default values for the cache configuration.
*   **Cache Entry Metadata (`CacheEntry`)**: Stores information about each cached item, such as its hash, provider, model, prompt type, timestamps, size, and hit count.
*   **Cache Statistics (`CacheStats`)**: Tracks performance metrics of the cache, including total entries, size, hits, misses, hit ratio, expired entries, and estimated tokens saved.
*   **Response Cache Class (`ResponseCache`)**: The main class responsible for managing the cache. It handles initialization, key generation, getting, setting, checking, deleting, clearing, and cleaning cache entries. It also manages cache statistics and enforces size limits.

### Core Functionality

*   **Initialization**: Sets up the cache directory and metadata directory, and loads existing statistics.
*   **Key Generation**: Creates a unique SHA256 hash for cache entries based on the content, provider, model, and prompt type. Content is normalized to ensure consistent hashing.
*   **Get Cache**: Retrieves a cached response using its key. It checks for existence, expiration, and updates hit statistics.
*   **Set Cache**: Stores a new response in the cache. It enforces the maximum cache size before writing the entry and its metadata.
*   **Has Cache**: Checks if a valid cache entry exists for a given key.
*   **Delete Cache**: Removes a specific cache entry and its associated metadata.
*   **Clear Cache**: Deletes all cache entries and resets statistics.
*   **Cleanup**: Removes expired cache entries.
*   **Statistics**: Provides access to current cache performance metrics.
*   **Entries**: Retrieves a list of all cached entries.
*   **Size Enforcement**: Automatically removes older cache entries when the cache size exceeds the configured limit.
*   **Stats Persistence**: Loads statistics on initialization and saves them to disk periodically or on shutdown (though explicit save function is provided).

### Helper Functions

*   **`createCache(config?: Partial<CacheConfig>)`**: A factory function to create and initialize a `ResponseCache` instance.
*   **`withCache<T>(cache: ResponseCache, fn: T, options: ...)`**: A higher-order function that wraps an asynchronous function (typically an AI provider call) with caching logic. It automatically handles generating cache keys, retrieving from cache, and storing results.

### File Relationships

*   `index.ts` exports all public members from `response-cache.ts`, making them accessible through the `cache` module.
*   `response-cache.ts` contains the entire implementation, utilizing Node.js built-in modules (`fs`, `path`, `crypto`) for file system operations and hashing.