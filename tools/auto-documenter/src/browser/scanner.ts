/**
 * Documentation Scanner - Find and index documentation files
 * @module browser/scanner
 */

import * as fs from 'fs';
import * as path from 'path';

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
export class DocumentationScanner {
  private rootPath: string;
  private docFiles: DocFile[] = [];
  private dirTree: DirNode | null = null;

  constructor(rootPath: string) {
    this.rootPath = path.resolve(rootPath);
  }

  /**
   * Scan directory for documentation files
   */
  scan(): DocFile[] {
    this.docFiles = [];
    this.scanDirectory(this.rootPath);
    return this.docFiles;
  }

  /**
   * Recursively scan directory
   */
  private scanDirectory(dirPath: string): void {
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
          } else if (this.isDocFile(entry)) {
            const docFile = this.createDocFile(fullPath, stat);
            this.docFiles.push(docFile);
          }
        } catch {
          // Skip inaccessible files
        }
      }
    } catch {
      // Skip inaccessible directories
    }
  }

  /**
   * Check if file is a documentation file
   */
  private isDocFile(filename: string): boolean {
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
  private createDocFile(absolutePath: string, stat: fs.Stats): DocFile {
    const relativePath = path.relative(this.rootPath, absolutePath);
    const name = path.basename(absolutePath);
    const directory = path.dirname(relativePath);

    // Determine type
    let type: DocFile['type'] = 'other';
    const lowerName = name.toLowerCase();
    if (lowerName === 'documentation.md') type = 'documentation';
    else if (lowerName === 'review.md') type = 'review';
    else if (lowerName === 'testplan.md') type = 'testplan';

    // Extract title from content
    let title: string | undefined;
    try {
      const content = fs.readFileSync(absolutePath, 'utf8');
      const titleMatch = content.match(/^#\s+(.+)$/m);
      if (titleMatch) {
        title = titleMatch[1];
      }
    } catch {
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
  buildTree(): DirNode {
    const root: DirNode = {
      name: path.basename(this.rootPath),
      path: '',
      type: 'directory',
      children: []
    };

    // Group files by directory
    const dirMap = new Map<string, DocFile[]>();

    for (const doc of this.docFiles) {
      const dir = doc.directory || '';
      if (!dirMap.has(dir)) {
        dirMap.set(dir, []);
      }
      dirMap.get(dir)!.push(doc);
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
  private sortTree(node: DirNode): void {
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
  getDocFiles(): DocFile[] {
    return [...this.docFiles];
  }

  /**
   * Get directory tree
   */
  getDirTree(): DirNode | null {
    return this.dirTree;
  }

  /**
   * Find file by relative path
   */
  findByPath(relativePath: string): DocFile | undefined {
    const normalizedPath = relativePath.replace(/\\/g, '/');
    return this.docFiles.find(f => f.relativePath === normalizedPath);
  }

  /**
   * Search files by query
   */
  search(query: string): DocFile[] {
    const lowerQuery = query.toLowerCase();
    return this.docFiles.filter(f =>
      f.name.toLowerCase().includes(lowerQuery) ||
      f.title?.toLowerCase().includes(lowerQuery) ||
      f.directory.toLowerCase().includes(lowerQuery)
    );
  }

  /**
   * Get statistics
   */
  getStats(): {
    totalFiles: number;
    byType: Record<string, number>;
    totalSize: number;
    directories: number;
  } {
    const byType: Record<string, number> = {};
    let totalSize = 0;
    const directories = new Set<string>();

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
