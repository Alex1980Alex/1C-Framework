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
 * Default watch options
 */
export const DEFAULT_WATCH_OPTIONS = {
    include: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.bsl'],
    exclude: ['**/node_modules/**', '**/dist/**', '**/.git/**', '**/*.d.ts'],
    debounceMs: 1000,
    recursive: true,
    pollIntervalMs: 500
};
/**
 * File watcher class
 */
export class FileWatcher extends EventEmitter {
    constructor(rootDir, options = {}) {
        super();
        this.watchers = [];
        this.pendingChanges = [];
        this.debounceTimer = null;
        this.batchStartTime = null;
        this.isRunning = false;
        this.rootDir = path.resolve(rootDir);
        this.options = { ...DEFAULT_WATCH_OPTIONS, ...options };
    }
    /**
     * Start watching for file changes
     */
    start() {
        if (this.isRunning) {
            return;
        }
        this.isRunning = true;
        try {
            this.watchDirectory(this.rootDir);
            this.emit('ready');
        }
        catch (error) {
            this.emit('error', error instanceof Error ? error : new Error(String(error)));
        }
    }
    /**
     * Stop watching for file changes
     */
    stop() {
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
    shouldWatch(filePath) {
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
    watchDirectory(dirPath) {
        if (!fs.existsSync(dirPath)) {
            return;
        }
        const stat = fs.statSync(dirPath);
        if (!stat.isDirectory()) {
            return;
        }
        try {
            const watcher = fs.watch(dirPath, { recursive: this.options.recursive }, (eventType, filename) => {
                if (!filename || !this.isRunning) {
                    return;
                }
                const fullPath = path.join(dirPath, filename);
                // Check if file matches patterns
                if (!this.shouldWatch(fullPath)) {
                    return;
                }
                // Determine event type
                let changeType = 'change';
                if (!fs.existsSync(fullPath)) {
                    changeType = 'unlink';
                }
                else if (eventType === 'rename') {
                    // Could be add or rename
                    changeType = 'add';
                }
                this.handleFileChange({
                    type: changeType,
                    path: fullPath,
                    timestamp: new Date()
                });
            });
            watcher.on('error', (error) => {
                this.emit('error', error);
            });
            this.watchers.push(watcher);
        }
        catch (error) {
            this.emit('error', error instanceof Error ? error : new Error(String(error)));
        }
    }
    /**
     * Handle a file change event
     */
    handleFileChange(event) {
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
    flushChanges() {
        if (this.pendingChanges.length === 0) {
            return;
        }
        // Deduplicate files
        const uniqueFiles = [...new Set(this.pendingChanges.map(c => c.path))];
        const batch = {
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
    getStatus() {
        return {
            running: this.isRunning,
            watchedDirs: this.watchers.length,
            pendingChanges: this.pendingChanges.length
        };
    }
}
/**
 * Create and start a file watcher with handlers
 */
export function createWatcher(rootDir, options, handler) {
    const watcher = new FileWatcher(rootDir, options);
    watcher.on('batch', async (batch) => {
        try {
            await handler.onBatch(batch);
        }
        catch (error) {
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
    constructor(rootDir, options = {}) {
        this.watcher = null;
        this.regenerationCount = 0;
        this.lastRegenerationTime = null;
        this.rootDir = rootDir;
        this.options = { ...DEFAULT_WATCH_OPTIONS, ...options };
    }
    /**
     * Start watch mode
     */
    async start(regenerate) {
        console.log(`\n🔍 Starting watch mode in: ${this.rootDir}`);
        console.log(`   Include: ${this.options.include.join(', ')}`);
        console.log(`   Exclude: ${this.options.exclude.join(', ')}`);
        console.log(`   Debounce: ${this.options.debounceMs}ms`);
        console.log(`\n   Press Ctrl+C to stop.\n`);
        this.watcher = createWatcher(this.rootDir, this.options, {
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
                }
                catch (error) {
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
        });
    }
    /**
     * Stop watch mode
     */
    stop() {
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
    getStats() {
        return {
            running: this.watcher !== null,
            regenerationCount: this.regenerationCount,
            lastRegenerationTime: this.lastRegenerationTime
        };
    }
    /**
     * Format time for display
     */
    formatTime(date) {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
}
//# sourceMappingURL=file-watcher.js.map