/**
 * File watcher module for watch mode
 * Watches directories for changes and triggers documentation regeneration
 * @module watch/file-watcher
 */
import { EventEmitter } from 'events';
/**
 * Watch mode configuration options
 */
export interface WatchOptions {
    /** Patterns to include (glob) */
    include: string[];
    /** Patterns to exclude (glob) */
    exclude: string[];
    /** Debounce delay in milliseconds */
    debounceMs: number;
    /** Watch subdirectories recursively */
    recursive: boolean;
    /** Polling interval for systems without native fs.watch support */
    pollIntervalMs?: number;
}
/**
 * Default watch options
 */
export declare const DEFAULT_WATCH_OPTIONS: WatchOptions;
/**
 * File change event
 */
export interface FileChangeEvent {
    /** Type of change */
    type: 'add' | 'change' | 'unlink';
    /** Path to the changed file */
    path: string;
    /** Timestamp of the change */
    timestamp: Date;
}
/**
 * Batch of file changes (after debouncing)
 */
export interface FileChangeBatch {
    /** All changes in the batch */
    changes: FileChangeEvent[];
    /** Unique files affected */
    files: string[];
    /** Start time of batch */
    startTime: Date;
    /** End time of batch */
    endTime: Date;
}
/**
 * File watcher events
 */
export interface FileWatcherEvents {
    'change': (event: FileChangeEvent) => void;
    'batch': (batch: FileChangeBatch) => void;
    'error': (error: Error) => void;
    'ready': () => void;
}
/**
 * File watcher class
 */
export declare class FileWatcher extends EventEmitter {
    private readonly rootDir;
    private readonly options;
    private watchers;
    private pendingChanges;
    private debounceTimer;
    private batchStartTime;
    private isRunning;
    constructor(rootDir: string, options?: Partial<WatchOptions>);
    /**
     * Start watching for file changes
     */
    start(): void;
    /**
     * Stop watching for file changes
     */
    stop(): void;
    /**
     * Check if a file path matches the include/exclude patterns
     */
    shouldWatch(filePath: string): boolean;
    /**
     * Watch a directory for changes
     */
    private watchDirectory;
    /**
     * Handle a file change event
     */
    private handleFileChange;
    /**
     * Flush pending changes as a batch
     */
    private flushChanges;
    /**
     * Get current watch status
     */
    getStatus(): {
        running: boolean;
        watchedDirs: number;
        pendingChanges: number;
    };
}
/**
 * Watch handler interface
 */
export interface WatchHandler {
    /** Handle a batch of file changes */
    onBatch(batch: FileChangeBatch): Promise<void>;
    /** Handle errors */
    onError?(error: Error): void;
    /** Handle ready event */
    onReady?(): void;
}
/**
 * Create and start a file watcher with handlers
 */
export declare function createWatcher(rootDir: string, options: Partial<WatchOptions>, handler: WatchHandler): FileWatcher;
/**
 * Watch mode runner
 */
export declare class WatchModeRunner {
    private watcher;
    private readonly rootDir;
    private readonly options;
    private regenerationCount;
    private lastRegenerationTime;
    constructor(rootDir: string, options?: Partial<WatchOptions>);
    /**
     * Start watch mode
     */
    start(regenerate: (files: string[]) => Promise<void>): Promise<void>;
    /**
     * Stop watch mode
     */
    stop(): void;
    /**
     * Get watch mode statistics
     */
    getStats(): {
        running: boolean;
        regenerationCount: number;
        lastRegenerationTime: Date | null;
    };
    /**
     * Format time for display
     */
    private formatTime;
}
