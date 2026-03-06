/**
 * Change tracking module for incremental documentation
 * Only processes files that have changed since last run
 * @module incremental/change-tracker
 */
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { execSync } from 'child_process';
/**
 * Default change tracker config
 */
export const DEFAULT_TRACKER_CONFIG = {
    stateFile: '.autodoc-state.json',
    useGit: true,
    extensions: ['.ts', '.tsx', '.js', '.jsx', '.bsl', '.py'],
    ignore: ['**/node_modules/**', '**/dist/**', '**/.git/**']
};
/**
 * Change tracker class
 */
export class ChangeTracker {
    constructor(rootDir, config = {}) {
        this.state = null;
        this.rootDir = path.resolve(rootDir);
        this.config = { ...DEFAULT_TRACKER_CONFIG, ...config };
        this.statePath = path.join(this.rootDir, this.config.stateFile);
    }
    /**
     * Load tracking state from file
     */
    async loadState() {
        if (fs.existsSync(this.statePath)) {
            try {
                const content = fs.readFileSync(this.statePath, 'utf-8');
                this.state = JSON.parse(content);
                return this.state;
            }
            catch {
                // Corrupted state, start fresh
            }
        }
        // Initialize new state
        this.state = {
            version: '1.0',
            projectRoot: this.rootDir,
            files: {}
        };
        return this.state;
    }
    /**
     * Save tracking state to file
     */
    async saveState() {
        if (!this.state) {
            return;
        }
        const content = JSON.stringify(this.state, null, 2);
        fs.writeFileSync(this.statePath, content, 'utf-8');
    }
    /**
     * Get current git commit hash
     */
    getGitCommit() {
        if (!this.config.useGit) {
            return null;
        }
        try {
            const result = execSync('git rev-parse HEAD', {
                cwd: this.rootDir,
                encoding: 'utf-8',
                stdio: ['pipe', 'pipe', 'pipe']
            });
            return result.trim();
        }
        catch {
            return null;
        }
    }
    /**
     * Get files changed according to git
     */
    getGitChangedFiles(sinceCommit) {
        if (!this.config.useGit) {
            return [];
        }
        try {
            const baseRef = sinceCommit || 'HEAD~1';
            const result = execSync(`git diff --name-only ${baseRef} HEAD 2>/dev/null || git ls-files`, {
                cwd: this.rootDir,
                encoding: 'utf-8',
                stdio: ['pipe', 'pipe', 'pipe']
            });
            return result.trim().split('\n').filter(Boolean);
        }
        catch {
            return [];
        }
    }
    /**
     * Calculate file hash
     */
    hashFile(filePath) {
        const content = fs.readFileSync(filePath);
        return crypto.createHash('md5').update(content).digest('hex');
    }
    /**
     * Check if file matches tracked extensions
     */
    shouldTrack(filePath) {
        const ext = path.extname(filePath).toLowerCase();
        return this.config.extensions.includes(ext);
    }
    /**
     * Get current file info
     */
    getFileInfo(relativePath) {
        const fullPath = path.join(this.rootDir, relativePath);
        if (!fs.existsSync(fullPath)) {
            return null;
        }
        const stat = fs.statSync(fullPath);
        if (!stat.isFile()) {
            return null;
        }
        return {
            path: relativePath,
            hash: this.hashFile(fullPath),
            mtime: stat.mtimeMs,
            size: stat.size
        };
    }
    /**
     * Scan directory for files
     */
    scanDirectory(dirPath, relativeTo = '') {
        const files = [];
        if (!fs.existsSync(dirPath)) {
            return files;
        }
        const entries = fs.readdirSync(dirPath, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(dirPath, entry.name);
            const relativePath = path.join(relativeTo, entry.name);
            // Check ignore patterns
            const shouldIgnore = this.config.ignore.some(pattern => {
                const normalizedPath = relativePath.replace(/\\/g, '/');
                if (pattern.includes('*')) {
                    // Simple glob matching
                    const regex = new RegExp('^' + pattern.replace(/\*\*/g, '.*').replace(/\*/g, '[^/]*') + '$');
                    return regex.test(normalizedPath);
                }
                return normalizedPath.includes(pattern.replace(/\*/g, ''));
            });
            if (shouldIgnore) {
                continue;
            }
            if (entry.isDirectory()) {
                files.push(...this.scanDirectory(fullPath, relativePath));
            }
            else if (entry.isFile() && this.shouldTrack(entry.name)) {
                files.push(relativePath);
            }
        }
        return files;
    }
    /**
     * Detect changed files since last run
     */
    async detectChanges() {
        await this.loadState();
        const changes = [];
        // Get current files
        const currentFiles = this.scanDirectory(this.rootDir);
        const currentFilesSet = new Set(currentFiles);
        const previousFiles = new Set(Object.keys(this.state.files));
        // Try git-based detection first
        const gitCommit = this.getGitCommit();
        const gitChangedFiles = gitCommit && this.state.gitCommit
            ? new Set(this.getGitChangedFiles(this.state.gitCommit))
            : null;
        // Check each current file
        for (const filePath of currentFiles) {
            const currentInfo = this.getFileInfo(filePath);
            if (!currentInfo)
                continue;
            const previousInfo = this.state.files[filePath];
            if (!previousInfo) {
                // New file
                changes.push({
                    path: filePath,
                    status: 'added',
                    currentHash: currentInfo.hash
                });
            }
            else if (currentInfo.hash !== previousInfo.hash) {
                // Modified file
                changes.push({
                    path: filePath,
                    status: 'modified',
                    previousHash: previousInfo.hash,
                    currentHash: currentInfo.hash
                });
            }
            else if (gitChangedFiles?.has(filePath)) {
                // Git says it changed, even if hash is same
                changes.push({
                    path: filePath,
                    status: 'modified',
                    previousHash: previousInfo.hash,
                    currentHash: currentInfo.hash
                });
            }
            // else: unchanged
        }
        // Check for deleted files
        for (const filePath of previousFiles) {
            if (!currentFilesSet.has(filePath)) {
                changes.push({
                    path: filePath,
                    status: 'deleted',
                    previousHash: this.state.files[filePath].hash
                });
            }
        }
        return changes;
    }
    /**
     * Mark files as processed
     */
    async markProcessed(filePaths) {
        if (!this.state) {
            await this.loadState();
        }
        const now = Date.now();
        for (const filePath of filePaths) {
            const info = this.getFileInfo(filePath);
            if (info) {
                this.state.files[filePath] = {
                    ...info,
                    processedAt: now
                };
            }
            else {
                // File was deleted
                delete this.state.files[filePath];
            }
        }
        // Update git commit
        const gitCommit = this.getGitCommit();
        if (gitCommit) {
            this.state.gitCommit = gitCommit;
        }
        await this.saveState();
    }
    /**
     * Mark all current files as processed (full run)
     */
    async markAllProcessed() {
        if (!this.state) {
            await this.loadState();
        }
        const now = Date.now();
        const currentFiles = this.scanDirectory(this.rootDir);
        // Clear old state
        this.state.files = {};
        for (const filePath of currentFiles) {
            const info = this.getFileInfo(filePath);
            if (info) {
                this.state.files[filePath] = {
                    ...info,
                    processedAt: now
                };
            }
        }
        // Update metadata
        this.state.lastFullRun = now;
        const gitCommit = this.getGitCommit();
        if (gitCommit) {
            this.state.gitCommit = gitCommit;
        }
        await this.saveState();
    }
    /**
     * Reset tracking state
     */
    async reset() {
        if (fs.existsSync(this.statePath)) {
            fs.unlinkSync(this.statePath);
        }
        this.state = null;
    }
    /**
     * Get tracking statistics
     */
    getStats() {
        if (!this.state) {
            return {
                totalFiles: 0,
                lastFullRun: null,
                gitCommit: null
            };
        }
        return {
            totalFiles: Object.keys(this.state.files).length,
            lastFullRun: this.state.lastFullRun
                ? new Date(this.state.lastFullRun)
                : null,
            gitCommit: this.state.gitCommit || null
        };
    }
}
/**
 * Run incremental documentation with change tracking
 */
export async function runIncremental(rootDir, processFiles, options = {}) {
    const tracker = new ChangeTracker(rootDir);
    if (options.force) {
        // Full run
        await tracker.reset();
        const files = await tracker.detectChanges();
        const allFiles = files.map(f => f.path);
        if (!options.dryRun) {
            await processFiles(allFiles);
            await tracker.markAllProcessed();
        }
        return {
            processed: allFiles.length,
            skipped: 0,
            changes: files
        };
    }
    // Incremental run
    const changes = await tracker.detectChanges();
    const filesToProcess = changes
        .filter(c => c.status === 'added' || c.status === 'modified')
        .map(c => c.path);
    if (!options.dryRun && filesToProcess.length > 0) {
        await processFiles(filesToProcess);
        await tracker.markProcessed(filesToProcess);
    }
    // Also mark deleted files
    const deletedFiles = changes
        .filter(c => c.status === 'deleted')
        .map(c => c.path);
    if (!options.dryRun && deletedFiles.length > 0) {
        await tracker.markProcessed(deletedFiles);
    }
    const totalFiles = (await tracker.loadState()).files;
    const skipped = Object.keys(totalFiles).length - filesToProcess.length;
    return {
        processed: filesToProcess.length,
        skipped: Math.max(0, skipped),
        changes
    };
}
//# sourceMappingURL=change-tracker.js.map