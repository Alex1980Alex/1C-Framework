/**
 * Change tracking module for incremental documentation
 * Only processes files that have changed since last run
 * @module incremental/change-tracker
 */
/**
 * File change status
 */
export type ChangeStatus = 'added' | 'modified' | 'deleted' | 'unchanged';
/**
 * File tracking info
 */
export interface TrackedFile {
    /** Relative path to file */
    path: string;
    /** Content hash */
    hash: string;
    /** Last modification timestamp */
    mtime: number;
    /** File size in bytes */
    size: number;
    /** Last processed timestamp */
    processedAt?: number;
}
/**
 * File change info
 */
export interface FileChange {
    /** Relative path */
    path: string;
    /** Change status */
    status: ChangeStatus;
    /** Previous hash (if modified) */
    previousHash?: string;
    /** Current hash */
    currentHash?: string;
}
/**
 * Tracking state file content
 */
export interface TrackingState {
    /** State version */
    version: string;
    /** Project root path */
    projectRoot: string;
    /** Last full run timestamp */
    lastFullRun?: number;
    /** Tracked files */
    files: Record<string, TrackedFile>;
    /** Git commit hash (if available) */
    gitCommit?: string;
}
/**
 * Change tracker configuration
 */
export interface ChangeTrackerConfig {
    /** State file name */
    stateFile: string;
    /** Use git for change detection */
    useGit: boolean;
    /** File extensions to track */
    extensions: string[];
    /** Patterns to ignore */
    ignore: string[];
}
/**
 * Default change tracker config
 */
export declare const DEFAULT_TRACKER_CONFIG: ChangeTrackerConfig;
/**
 * Change tracker class
 */
export declare class ChangeTracker {
    private readonly rootDir;
    private readonly config;
    private readonly statePath;
    private state;
    constructor(rootDir: string, config?: Partial<ChangeTrackerConfig>);
    /**
     * Load tracking state from file
     */
    loadState(): Promise<TrackingState>;
    /**
     * Save tracking state to file
     */
    saveState(): Promise<void>;
    /**
     * Get current git commit hash
     */
    private getGitCommit;
    /**
     * Get files changed according to git
     */
    private getGitChangedFiles;
    /**
     * Calculate file hash
     */
    private hashFile;
    /**
     * Check if file matches tracked extensions
     */
    private shouldTrack;
    /**
     * Get current file info
     */
    private getFileInfo;
    /**
     * Scan directory for files
     */
    private scanDirectory;
    /**
     * Detect changed files since last run
     */
    detectChanges(): Promise<FileChange[]>;
    /**
     * Mark files as processed
     */
    markProcessed(filePaths: string[]): Promise<void>;
    /**
     * Mark all current files as processed (full run)
     */
    markAllProcessed(): Promise<void>;
    /**
     * Reset tracking state
     */
    reset(): Promise<void>;
    /**
     * Get tracking statistics
     */
    getStats(): {
        totalFiles: number;
        lastFullRun: Date | null;
        gitCommit: string | null;
    };
}
/**
 * Incremental documentation generator options
 */
export interface IncrementalOptions {
    /** Force full regeneration */
    force?: boolean;
    /** Only check for changes, don't process */
    dryRun?: boolean;
    /** Verbose output */
    verbose?: boolean;
}
/**
 * Run incremental documentation with change tracking
 */
export declare function runIncremental(rootDir: string, processFiles: (files: string[]) => Promise<void>, options?: IncrementalOptions): Promise<{
    processed: number;
    skipped: number;
    changes: FileChange[];
}>;
