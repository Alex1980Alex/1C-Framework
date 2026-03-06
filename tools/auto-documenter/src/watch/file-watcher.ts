/**
 * File watcher module for watch mode
 * Watches directories for changes and triggers documentation regeneration
 * @module watch/file-watcher
 */

import * as fs from 'fs';
import * as path from 'path';
import { EventEmitter } from 'events';
import { minimatch } from 'minimatch';

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
export const DEFAULT_WATCH_OPTIONS: WatchOptions = {
  include: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.bsl'],
  exclude: ['**/node_modules/**', '**/dist/**', '**/.git/**', '**/*.d.ts'],
  debounceMs: 1000,
  recursive: true,
  pollIntervalMs: 500
};

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
export class FileWatcher extends EventEmitter {
  private readonly rootDir: string;
  private readonly options: WatchOptions;
  private watchers: fs.FSWatcher[] = [];
  private pendingChanges: FileChangeEvent[] = [];
  private debounceTimer: NodeJS.Timeout | null = null;
  private batchStartTime: Date | null = null;
  private isRunning = false;

  constructor(rootDir: string, options: Partial<WatchOptions> = {}) {
    super();
    this.rootDir = path.resolve(rootDir);
    this.options = { ...DEFAULT_WATCH_OPTIONS, ...options };
  }

  /**
   * Start watching for file changes
   */
  start(): void {
    if (this.isRunning) {
      return;
    }

    this.isRunning = true;

    try {
      this.watchDirectory(this.rootDir);
      this.emit('ready');
    } catch (error) {
      this.emit('error', error instanceof Error ? error : new Error(String(error)));
    }
  }

  /**
   * Stop watching for file changes
   */
  stop(): void {
    this.isRunning = false;

    // Clear debounce timer
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }

    // Close all watchers
    for (const watcher of this.watchers) {
      watcher.close();
    }
    this.watchers = [];

    // Flush pending changes
    if (this.pendingChanges.length > 0) {
      this.flushChanges();
    }
  }

  /**
   * Check if a file path matches the include/exclude patterns
   */
  shouldWatch(filePath: string): boolean {
    const relativePath = path.relative(this.rootDir, filePath);

    // Check exclude patterns first
    for (const pattern of this.options.exclude) {
      if (minimatch(relativePath, pattern, { dot: true })) {
        return false;
      }
    }

    // Check include patterns
    for (const pattern of this.options.include) {
      if (minimatch(relativePath, pattern, { dot: true })) {
        return true;
      }
    }

    return false;
  }

  /**
   * Watch a directory for changes
   */
  private watchDirectory(dirPath: string): void {
    if (!fs.existsSync(dirPath)) {
      return;
    }

    const stat = fs.statSync(dirPath);
    if (!stat.isDirectory()) {
      return;
    }

    try {
      const watcher = fs.watch(
        dirPath,
        { recursive: this.options.recursive },
        (eventType, filename) => {
          if (!filename || !this.isRunning) {
            return;
          }

          const fullPath = path.join(dirPath, filename);

          // Check if file matches patterns
          if (!this.shouldWatch(fullPath)) {
            return;
          }

          // Determine event type
          let changeType: FileChangeEvent['type'] = 'change';
          if (!fs.existsSync(fullPath)) {
            changeType = 'unlink';
          } else if (eventType === 'rename') {
            // Could be add or rename
            changeType = 'add';
          }

          this.handleFileChange({
            type: changeType,
            path: fullPath,
            timestamp: new Date()
          });
        }
      );

      watcher.on('error', (error) => {
        this.emit('error', error);
      });

      this.watchers.push(watcher);
    } catch (error) {
      this.emit('error', error instanceof Error ? error : new Error(String(error)));
    }
  }

  /**
   * Handle a file change event
   */
  private handleFileChange(event: FileChangeEvent): void {
    // Emit individual change event
    this.emit('change', event);

    // Add to pending changes
    this.pendingChanges.push(event);

    // Track batch start time
    if (!this.batchStartTime) {
      this.batchStartTime = new Date();
    }

    // Reset debounce timer
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      this.flushChanges();
    }, this.options.debounceMs);
  }

  /**
   * Flush pending changes as a batch
   */
  private flushChanges(): void {
    if (this.pendingChanges.length === 0) {
      return;
    }

    // Deduplicate files
    const uniqueFiles = [...new Set(this.pendingChanges.map(c => c.path))];

    const batch: FileChangeBatch = {
      changes: [...this.pendingChanges],
      files: uniqueFiles,
      startTime: this.batchStartTime || new Date(),
      endTime: new Date()
    };

    // Clear pending changes
    this.pendingChanges = [];
    this.batchStartTime = null;
    this.debounceTimer = null;

    // Emit batch event
    this.emit('batch', batch);
  }

  /**
   * Get current watch status
   */
  getStatus(): {
    running: boolean;
    watchedDirs: number;
    pendingChanges: number;
  } {
    return {
      running: this.isRunning,
      watchedDirs: this.watchers.length,
      pendingChanges: this.pendingChanges.length
    };
  }
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
export function createWatcher(
  rootDir: string,
  options: Partial<WatchOptions>,
  handler: WatchHandler
): FileWatcher {
  const watcher = new FileWatcher(rootDir, options);

  watcher.on('batch', async (batch) => {
    try {
      await handler.onBatch(batch);
    } catch (error) {
      handler.onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  });

  watcher.on('error', (error) => {
    handler.onError?.(error);
  });

  watcher.on('ready', () => {
    handler.onReady?.();
  });

  watcher.start();
  return watcher;
}

/**
 * Watch mode runner
 */
export class WatchModeRunner {
  private watcher: FileWatcher | null = null;
  private readonly rootDir: string;
  private readonly options: WatchOptions;
  private regenerationCount = 0;
  private lastRegenerationTime: Date | null = null;

  constructor(rootDir: string, options: Partial<WatchOptions> = {}) {
    this.rootDir = rootDir;
    this.options = { ...DEFAULT_WATCH_OPTIONS, ...options };
  }

  /**
   * Start watch mode
   */
  async start(regenerate: (files: string[]) => Promise<void>): Promise<void> {
    console.log(`\n🔍 Starting watch mode in: ${this.rootDir}`);
    console.log(`   Include: ${this.options.include.join(', ')}`);
    console.log(`   Exclude: ${this.options.exclude.join(', ')}`);
    console.log(`   Debounce: ${this.options.debounceMs}ms`);
    console.log(`\n   Press Ctrl+C to stop.\n`);

    this.watcher = createWatcher(
      this.rootDir,
      this.options,
      {
        onBatch: async (batch) => {
          this.regenerationCount++;
          this.lastRegenerationTime = new Date();

          console.log(`\n📝 [${this.formatTime(new Date())}] Detected ${batch.files.length} changed file(s):`);
          for (const file of batch.files.slice(0, 5)) {
            console.log(`   - ${path.relative(this.rootDir, file)}`);
          }
          if (batch.files.length > 5) {
            console.log(`   ... and ${batch.files.length - 5} more`);
          }

          console.log(`\n⚙️  Regenerating documentation...`);

          try {
            await regenerate(batch.files);
            console.log(`✅ Documentation updated successfully.`);
          } catch (error) {
            console.error(`❌ Regeneration failed: ${error instanceof Error ? error.message : String(error)}`);
          }

          console.log(`\n   Watching for changes...`);
        },
        onError: (error) => {
          console.error(`❌ Watch error: ${error.message}`);
        },
        onReady: () => {
          console.log(`✅ Watcher ready. Watching for changes...`);
        }
      }
    );
  }

  /**
   * Stop watch mode
   */
  stop(): void {
    if (this.watcher) {
      this.watcher.stop();
      this.watcher = null;

      console.log(`\n🛑 Watch mode stopped.`);
      console.log(`   Total regenerations: ${this.regenerationCount}`);
      if (this.lastRegenerationTime) {
        console.log(`   Last regeneration: ${this.formatTime(this.lastRegenerationTime)}`);
      }
    }
  }

  /**
   * Get watch mode statistics
   */
  getStats(): {
    running: boolean;
    regenerationCount: number;
    lastRegenerationTime: Date | null;
  } {
    return {
      running: this.watcher !== null,
      regenerationCount: this.regenerationCount,
      lastRegenerationTime: this.lastRegenerationTime
    };
  }

  /**
   * Format time for display
   */
  private formatTime(date: Date): string {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }
}
