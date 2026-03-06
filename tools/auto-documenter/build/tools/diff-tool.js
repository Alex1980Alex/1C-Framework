/**
 * Documentation Diff Tool
 * Compares two versions of documentation and highlights changes
 * Useful for CI/CD pipelines to track documentation drift
 */
import * as fs from 'fs';
import * as path from 'path';
import { diffLines } from 'diff';
/**
 * Types of changes detected in documentation
 */
export var ChangeType;
(function (ChangeType) {
    ChangeType["ADDED"] = "added";
    ChangeType["REMOVED"] = "removed";
    ChangeType["MODIFIED"] = "modified";
    ChangeType["UNCHANGED"] = "unchanged";
})(ChangeType || (ChangeType = {}));
/**
 * Documentation Diff Tool
 * Compares documentation versions and produces structured diff reports
 */
export class DiffTool {
    constructor(options = {}) {
        this.options = {
            ignoreWhitespace: false,
            includeUnchanged: false,
            includePatterns: ['**/*.md', '**/*.txt'],
            excludePatterns: ['**/node_modules/**', '**/.git/**'],
            contextLines: 3,
            detectBreaking: true,
            ...options,
        };
    }
    /**
     * Compare two files and return changes
     */
    async compareFiles(basePath, targetPath) {
        const changes = [];
        const timestamp = new Date().toISOString();
        try {
            const baseContent = await this.readFileContent(basePath);
            const targetContent = await this.readFileContent(targetPath);
            if (baseContent === null && targetContent === null) {
                return {
                    summary: this.createEmptySummary(timestamp),
                    changes: [],
                    baseVersion: basePath,
                    targetVersion: targetPath,
                    success: false,
                    error: 'Both files do not exist',
                };
            }
            if (baseContent === null) {
                // New file added
                changes.push({
                    type: ChangeType.ADDED,
                    filePath: targetPath,
                    newContent: targetContent,
                    severity: 'info',
                });
            }
            else if (targetContent === null) {
                // File removed
                changes.push({
                    type: ChangeType.REMOVED,
                    filePath: basePath,
                    oldContent: baseContent,
                    severity: this.options.detectBreaking ? 'breaking' : 'warning',
                });
            }
            else {
                // Compare contents
                const fileChanges = this.diffContent(baseContent, targetContent, path.basename(basePath));
                changes.push(...fileChanges);
            }
            return {
                summary: this.calculateSummary(changes, timestamp),
                changes,
                baseVersion: basePath,
                targetVersion: targetPath,
                success: true,
            };
        }
        catch (error) {
            return {
                summary: this.createEmptySummary(timestamp),
                changes: [],
                baseVersion: basePath,
                targetVersion: targetPath,
                success: false,
                error: error instanceof Error ? error.message : String(error),
            };
        }
    }
    /**
     * Compare two directories and return changes
     */
    async compareDirectories(baseDir, targetDir) {
        const changes = [];
        const timestamp = new Date().toISOString();
        try {
            const baseFiles = await this.getDocumentationFiles(baseDir);
            const targetFiles = await this.getDocumentationFiles(targetDir);
            const allFiles = new Set([...baseFiles, ...targetFiles]);
            for (const relativePath of allFiles) {
                const basePath = path.join(baseDir, relativePath);
                const targetPath = path.join(targetDir, relativePath);
                const baseExists = baseFiles.includes(relativePath);
                const targetExists = targetFiles.includes(relativePath);
                if (!baseExists && targetExists) {
                    // New file
                    const content = await this.readFileContent(targetPath);
                    changes.push({
                        type: ChangeType.ADDED,
                        filePath: relativePath,
                        newContent: content || '',
                        severity: 'info',
                    });
                }
                else if (baseExists && !targetExists) {
                    // Removed file
                    const content = await this.readFileContent(basePath);
                    changes.push({
                        type: ChangeType.REMOVED,
                        filePath: relativePath,
                        oldContent: content || '',
                        severity: this.options.detectBreaking ? 'breaking' : 'warning',
                    });
                }
                else {
                    // Both exist - compare contents
                    const baseContent = await this.readFileContent(basePath);
                    const targetContent = await this.readFileContent(targetPath);
                    if (baseContent !== targetContent) {
                        const fileChanges = this.diffContent(baseContent || '', targetContent || '', relativePath);
                        changes.push(...fileChanges);
                    }
                    else if (this.options.includeUnchanged) {
                        changes.push({
                            type: ChangeType.UNCHANGED,
                            filePath: relativePath,
                            severity: 'info',
                        });
                    }
                }
            }
            return {
                summary: this.calculateSummary(changes, timestamp),
                changes,
                baseVersion: baseDir,
                targetVersion: targetDir,
                success: true,
            };
        }
        catch (error) {
            return {
                summary: this.createEmptySummary(timestamp),
                changes: [],
                baseVersion: baseDir,
                targetVersion: targetDir,
                success: false,
                error: error instanceof Error ? error.message : String(error),
            };
        }
    }
    /**
     * Compare content strings and return changes
     */
    diffContent(baseContent, targetContent, filePath) {
        const changes = [];
        // Normalize line endings
        const normalizedBase = this.normalizeContent(baseContent);
        const normalizedTarget = this.normalizeContent(targetContent);
        // Use diff library for line-by-line comparison
        const diff = diffLines(normalizedBase, normalizedTarget, {
            ignoreWhitespace: this.options.ignoreWhitespace,
        });
        let lineNumber = 1;
        let currentSection;
        for (const part of diff) {
            // Try to detect section from content
            const sectionMatch = part.value.match(/^#+\s+(.+)$/m);
            if (sectionMatch) {
                currentSection = sectionMatch[1];
            }
            if (part.added) {
                changes.push({
                    type: ChangeType.ADDED,
                    filePath,
                    lineStart: lineNumber,
                    lineEnd: lineNumber + this.countLines(part.value) - 1,
                    newContent: part.value,
                    section: currentSection,
                    severity: this.detectChangeSeverity(part.value, ChangeType.ADDED),
                });
            }
            else if (part.removed) {
                changes.push({
                    type: ChangeType.REMOVED,
                    filePath,
                    lineStart: lineNumber,
                    lineEnd: lineNumber + this.countLines(part.value) - 1,
                    oldContent: part.value,
                    section: currentSection,
                    severity: this.detectChangeSeverity(part.value, ChangeType.REMOVED),
                });
            }
            // Update line number for non-removed parts
            if (!part.removed) {
                lineNumber += this.countLines(part.value);
            }
        }
        return changes;
    }
    /**
     * Detect severity of a change
     */
    detectChangeSeverity(content, changeType) {
        if (!this.options.detectBreaking) {
            return 'info';
        }
        // Breaking change patterns
        const breakingPatterns = [
            /^##?\s*API/im, // API documentation
            /\bexport\b/i, // Export statements
            /\bpublic\b/i, // Public API
            /\bЭкспорт\b/i, // BSL Export
            /\bпубличн/i, // Public API (Russian)
            /\b(параметр|parameter)\b.*:/i, // Parameter documentation
            /\breturn(s|ed)?\b.*:/i, // Return documentation
            /\bВозвращаемое значение\b/i, // Return value (Russian)
        ];
        for (const pattern of breakingPatterns) {
            if (pattern.test(content)) {
                return changeType === ChangeType.REMOVED ? 'breaking' : 'warning';
            }
        }
        return 'info';
    }
    /**
     * Get all documentation files in a directory
     */
    async getDocumentationFiles(dir) {
        const files = [];
        const walk = async (currentDir, baseDir) => {
            try {
                const entries = await fs.promises.readdir(currentDir, {
                    withFileTypes: true,
                });
                for (const entry of entries) {
                    const fullPath = path.join(currentDir, entry.name);
                    const relativePath = path.relative(baseDir, fullPath);
                    // Check exclusion patterns
                    if (this.shouldExclude(relativePath)) {
                        continue;
                    }
                    if (entry.isDirectory()) {
                        await walk(fullPath, baseDir);
                    }
                    else if (this.isDocumentationFile(entry.name)) {
                        files.push(relativePath);
                    }
                }
            }
            catch {
                // Directory doesn't exist or can't be read
            }
        };
        await walk(dir, dir);
        return files.sort();
    }
    /**
     * Check if file should be excluded
     */
    shouldExclude(relativePath) {
        const excludePatterns = this.options.excludePatterns || [];
        const normalizedPath = relativePath.replace(/\\/g, '/');
        for (const pattern of excludePatterns) {
            // Handle directory patterns like **/node_modules/**
            const dirMatch = pattern.match(/\*\*\/([^*/]+)\/\*\*/);
            if (dirMatch) {
                const dirName = dirMatch[1];
                if (normalizedPath.includes(`/${dirName}/`) || normalizedPath.startsWith(`${dirName}/`)) {
                    return true;
                }
            }
            else if (this.matchGlob(normalizedPath, pattern)) {
                return true;
            }
        }
        return false;
    }
    /**
     * Check if file is a documentation file
     */
    isDocumentationFile(filename) {
        const includePatterns = this.options.includePatterns || ['**/*.md'];
        for (const pattern of includePatterns) {
            // Extract extension from pattern like "**/*.md" -> ".md"
            const extMatch = pattern.match(/\*\.(\w+)$/);
            if (extMatch) {
                const ext = '.' + extMatch[1];
                if (filename.toLowerCase().endsWith(ext.toLowerCase())) {
                    return true;
                }
            }
            else if (this.matchGlob(filename, pattern)) {
                return true;
            }
        }
        return false;
    }
    /**
     * Simple glob matching
     */
    matchGlob(filepath, pattern) {
        // Convert glob to regex
        const regexPattern = pattern
            .replace(/\*\*/g, '{{GLOBSTAR}}')
            .replace(/\*/g, '[^/]*')
            .replace(/{{GLOBSTAR}}/g, '.*')
            .replace(/\?/g, '.');
        const regex = new RegExp(`^${regexPattern}$`, 'i');
        return regex.test(filepath);
    }
    /**
     * Read file content safely
     */
    async readFileContent(filePath) {
        try {
            return await fs.promises.readFile(filePath, 'utf-8');
        }
        catch {
            return null;
        }
    }
    /**
     * Normalize content for comparison
     */
    normalizeContent(content) {
        // Normalize line endings
        let normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
        if (this.options.ignoreWhitespace) {
            // Trim trailing whitespace from each line
            normalized = normalized
                .split('\n')
                .map((line) => line.trimEnd())
                .join('\n');
        }
        return normalized;
    }
    /**
     * Count lines in content
     */
    countLines(content) {
        return (content.match(/\n/g) || []).length + 1;
    }
    /**
     * Calculate summary statistics
     */
    calculateSummary(changes, timestamp) {
        const filePaths = new Set();
        let linesAdded = 0;
        let linesRemoved = 0;
        let addedFiles = 0;
        let removedFiles = 0;
        let breakingChanges = 0;
        for (const change of changes) {
            filePaths.add(change.filePath);
            switch (change.type) {
                case ChangeType.ADDED:
                    if (change.newContent && !change.lineStart) {
                        // Whole file added
                        addedFiles++;
                    }
                    if (change.newContent) {
                        linesAdded += this.countLines(change.newContent);
                    }
                    break;
                case ChangeType.REMOVED:
                    if (change.oldContent && !change.lineStart) {
                        // Whole file removed
                        removedFiles++;
                    }
                    if (change.oldContent) {
                        linesRemoved += this.countLines(change.oldContent);
                    }
                    break;
            }
            if (change.severity === 'breaking') {
                breakingChanges++;
            }
        }
        const changedFiles = changes.filter((c) => c.type !== ChangeType.UNCHANGED).length;
        return {
            totalFiles: filePaths.size,
            changedFiles,
            addedFiles,
            removedFiles,
            linesAdded,
            linesRemoved,
            breakingChanges,
            timestamp,
        };
    }
    /**
     * Create empty summary
     */
    createEmptySummary(timestamp) {
        return {
            totalFiles: 0,
            changedFiles: 0,
            addedFiles: 0,
            removedFiles: 0,
            linesAdded: 0,
            linesRemoved: 0,
            breakingChanges: 0,
            timestamp,
        };
    }
}
// Export singleton instance
export const diffTool = new DiffTool();
//# sourceMappingURL=diff-tool.js.map