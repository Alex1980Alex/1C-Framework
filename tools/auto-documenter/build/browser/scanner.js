/**
 * Documentation Scanner - Find and index documentation files
 * @module browser/scanner
 */
import * as fs from 'fs';
import * as path from 'path';
/**
 * Documentation Scanner class
 */
export class DocumentationScanner {
    constructor(rootPath) {
        this.docFiles = [];
        this.dirTree = null;
        this.rootPath = path.resolve(rootPath);
    }
    /**
     * Scan directory for documentation files
     */
    scan() {
        this.docFiles = [];
        this.scanDirectory(this.rootPath);
        return this.docFiles;
    }
    /**
     * Recursively scan directory
     */
    scanDirectory(dirPath) {
        try {
            const entries = fs.readdirSync(dirPath);
            for (const entry of entries) {
                const fullPath = path.join(dirPath, entry);
                try {
                    const stat = fs.statSync(fullPath);
                    if (stat.isDirectory()) {
                        // Skip hidden dirs and node_modules
                        if (!entry.startsWith('.') && entry !== 'node_modules' && entry !== 'build') {
                            this.scanDirectory(fullPath);
                        }
                    }
                    else if (this.isDocFile(entry)) {
                        const docFile = this.createDocFile(fullPath, stat);
                        this.docFiles.push(docFile);
                    }
                }
                catch {
                    // Skip inaccessible files
                }
            }
        }
        catch {
            // Skip inaccessible directories
        }
    }
    /**
     * Check if file is a documentation file
     */
    isDocFile(filename) {
        const docPatterns = [
            'documentation.md',
            'review.md',
            'testplan.md',
            'README.md',
            'CHANGELOG.md'
        ];
        const lowerName = filename.toLowerCase();
        return docPatterns.some(p => lowerName === p.toLowerCase()) ||
            (lowerName.endsWith('.md') && !lowerName.startsWith('_'));
    }
    /**
     * Create DocFile from path
     */
    createDocFile(absolutePath, stat) {
        const relativePath = path.relative(this.rootPath, absolutePath);
        const name = path.basename(absolutePath);
        const directory = path.dirname(relativePath);
        // Determine type
        let type = 'other';
        const lowerName = name.toLowerCase();
        if (lowerName === 'documentation.md')
            type = 'documentation';
        else if (lowerName === 'review.md')
            type = 'review';
        else if (lowerName === 'testplan.md')
            type = 'testplan';
        // Extract title from content
        let title;
        try {
            const content = fs.readFileSync(absolutePath, 'utf8');
            const titleMatch = content.match(/^#\s+(.+)$/m);
            if (titleMatch) {
                title = titleMatch[1];
            }
        }
        catch {
            // Ignore read errors
        }
        return {
            relativePath: relativePath.replace(/\\/g, '/'),
            absolutePath,
            name,
            type,
            directory: directory === '.' ? '' : directory.replace(/\\/g, '/'),
            size: stat.size,
            modified: stat.mtime,
            title
        };
    }
    /**
     * Build directory tree
     */
    buildTree() {
        const root = {
            name: path.basename(this.rootPath),
            path: '',
            type: 'directory',
            children: []
        };
        // Group files by directory
        const dirMap = new Map();
        for (const doc of this.docFiles) {
            const dir = doc.directory || '';
            if (!dirMap.has(dir)) {
                dirMap.set(dir, []);
            }
            dirMap.get(dir).push(doc);
        }
        // Build tree structure
        for (const [dirPath, files] of dirMap) {
            const parts = dirPath ? dirPath.split('/') : [];
            let current = root;
            // Create directory nodes
            for (let i = 0; i < parts.length; i++) {
                const part = parts[i];
                const currentPath = parts.slice(0, i + 1).join('/');
                let child = current.children?.find(c => c.name === part && c.type === 'directory');
                if (!child) {
                    child = {
                        name: part,
                        path: currentPath,
                        type: 'directory',
                        children: []
                    };
                    current.children = current.children || [];
                    current.children.push(child);
                }
                current = child;
            }
            // Add file nodes
            for (const file of files) {
                current.children = current.children || [];
                current.children.push({
                    name: file.name,
                    path: file.relativePath,
                    type: 'file',
                    docFile: file
                });
            }
        }
        // Sort children
        this.sortTree(root);
        this.dirTree = root;
        return root;
    }
    /**
     * Sort tree nodes (directories first, then alphabetically)
     */
    sortTree(node) {
        if (node.children) {
            node.children.sort((a, b) => {
                if (a.type !== b.type) {
                    return a.type === 'directory' ? -1 : 1;
                }
                return a.name.localeCompare(b.name);
            });
            for (const child of node.children) {
                this.sortTree(child);
            }
        }
    }
    /**
     * Get all documentation files
     */
    getDocFiles() {
        return [...this.docFiles];
    }
    /**
     * Get directory tree
     */
    getDirTree() {
        return this.dirTree;
    }
    /**
     * Find file by relative path
     */
    findByPath(relativePath) {
        const normalizedPath = relativePath.replace(/\\/g, '/');
        return this.docFiles.find(f => f.relativePath === normalizedPath);
    }
    /**
     * Search files by query
     */
    search(query) {
        const lowerQuery = query.toLowerCase();
        return this.docFiles.filter(f => f.name.toLowerCase().includes(lowerQuery) ||
            f.title?.toLowerCase().includes(lowerQuery) ||
            f.directory.toLowerCase().includes(lowerQuery));
    }
    /**
     * Get statistics
     */
    getStats() {
        const byType = {};
        let totalSize = 0;
        const directories = new Set();
        for (const file of this.docFiles) {
            byType[file.type] = (byType[file.type] || 0) + 1;
            totalSize += file.size;
            if (file.directory) {
                directories.add(file.directory);
            }
        }
        return {
            totalFiles: this.docFiles.length,
            byType,
            totalSize,
            directories: directories.size
        };
    }
}
//# sourceMappingURL=scanner.js.map