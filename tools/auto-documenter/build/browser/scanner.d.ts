/**
 * Documentation Scanner - Find and index documentation files
 * @module browser/scanner
 */
/**
 * Documentation file info
 */
export interface DocFile {
    /** File path relative to root */
    relativePath: string;
    /** Absolute file path */
    absolutePath: string;
    /** File name */
    name: string;
    /** File type (documentation, review, testplan) */
    type: 'documentation' | 'review' | 'testplan' | 'other';
    /** Parent directory */
    directory: string;
    /** File size in bytes */
    size: number;
    /** Last modified date */
    modified: Date;
    /** Title extracted from content */
    title?: string;
}
/**
 * Directory tree node
 */
export interface DirNode {
    name: string;
    path: string;
    type: 'directory' | 'file';
    children?: DirNode[];
    docFile?: DocFile;
}
/**
 * Documentation Scanner class
 */
export declare class DocumentationScanner {
    private rootPath;
    private docFiles;
    private dirTree;
    constructor(rootPath: string);
    /**
     * Scan directory for documentation files
     */
    scan(): DocFile[];
    /**
     * Recursively scan directory
     */
    private scanDirectory;
    /**
     * Check if file is a documentation file
     */
    private isDocFile;
    /**
     * Create DocFile from path
     */
    private createDocFile;
    /**
     * Build directory tree
     */
    buildTree(): DirNode;
    /**
     * Sort tree nodes (directories first, then alphabetically)
     */
    private sortTree;
    /**
     * Get all documentation files
     */
    getDocFiles(): DocFile[];
    /**
     * Get directory tree
     */
    getDirTree(): DirNode | null;
    /**
     * Find file by relative path
     */
    findByPath(relativePath: string): DocFile | undefined;
    /**
     * Search files by query
     */
    search(query: string): DocFile[];
    /**
     * Get statistics
     */
    getStats(): {
        totalFiles: number;
        byType: Record<string, number>;
        totalSize: number;
        directories: number;
    };
}
