/**
 * Documentation Diff Tool
 * Compares two versions of documentation and highlights changes
 * Useful for CI/CD pipelines to track documentation drift
 */
/**
 * Types of changes detected in documentation
 */
export declare enum ChangeType {
    ADDED = "added",
    REMOVED = "removed",
    MODIFIED = "modified",
    UNCHANGED = "unchanged"
}
/**
 * Represents a single change in documentation
 */
export interface DocumentationChange {
    /** Type of change */
    type: ChangeType;
    /** File path relative to base directory */
    filePath: string;
    /** Line number where change starts (1-based) */
    lineStart?: number;
    /** Line number where change ends (1-based) */
    lineEnd?: number;
    /** Original content (for modified/removed) */
    oldContent?: string;
    /** New content (for modified/added) */
    newContent?: string;
    /** Section header if identifiable */
    section?: string;
    /** Severity of change: info, warning, breaking */
    severity: 'info' | 'warning' | 'breaking';
}
/**
 * Summary statistics for diff results
 */
export interface DiffSummary {
    /** Total files compared */
    totalFiles: number;
    /** Files with changes */
    changedFiles: number;
    /** New files added */
    addedFiles: number;
    /** Files removed */
    removedFiles: number;
    /** Total lines added */
    linesAdded: number;
    /** Total lines removed */
    linesRemoved: number;
    /** Breaking changes count */
    breakingChanges: number;
    /** Timestamp of comparison */
    timestamp: string;
}
/**
 * Complete diff result
 */
export interface DiffResult {
    /** Summary statistics */
    summary: DiffSummary;
    /** Detailed changes */
    changes: DocumentationChange[];
    /** Base version identifier */
    baseVersion: string;
    /** Target version identifier */
    targetVersion: string;
    /** Whether comparison was successful */
    success: boolean;
    /** Error message if any */
    error?: string;
}
/**
 * Options for diff operation
 */
export interface DiffOptions {
    /** Ignore whitespace changes */
    ignoreWhitespace?: boolean;
    /** Include unchanged files in result */
    includeUnchanged?: boolean;
    /** File patterns to include (glob) */
    includePatterns?: string[];
    /** File patterns to exclude (glob) */
    excludePatterns?: string[];
    /** Context lines around changes */
    contextLines?: number;
    /** Detect breaking changes (removed exports, etc.) */
    detectBreaking?: boolean;
}
/**
 * Documentation Diff Tool
 * Compares documentation versions and produces structured diff reports
 */
export declare class DiffTool {
    private options;
    constructor(options?: DiffOptions);
    /**
     * Compare two files and return changes
     */
    compareFiles(basePath: string, targetPath: string): Promise<DiffResult>;
    /**
     * Compare two directories and return changes
     */
    compareDirectories(baseDir: string, targetDir: string): Promise<DiffResult>;
    /**
     * Compare content strings and return changes
     */
    private diffContent;
    /**
     * Detect severity of a change
     */
    private detectChangeSeverity;
    /**
     * Get all documentation files in a directory
     */
    private getDocumentationFiles;
    /**
     * Check if file should be excluded
     */
    private shouldExclude;
    /**
     * Check if file is a documentation file
     */
    private isDocumentationFile;
    /**
     * Simple glob matching
     */
    private matchGlob;
    /**
     * Read file content safely
     */
    private readFileContent;
    /**
     * Normalize content for comparison
     */
    private normalizeContent;
    /**
     * Count lines in content
     */
    private countLines;
    /**
     * Calculate summary statistics
     */
    private calculateSummary;
    /**
     * Create empty summary
     */
    private createEmptySummary;
}
export declare const diffTool: DiffTool;
