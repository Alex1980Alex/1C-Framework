/**
 * Documentation Server - HTTP server for browsing documentation
 * @module browser/server
 */

import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import * as url from 'url';
import { DocumentationScanner, DocFile, DirNode } from './scanner.js';
import { HtmlRenderer } from './renderer.js';

/**
 * Server configuration
 */
export interface ServerConfig {
  /** Root directory to serve */
  rootPath: string;
  /** Port number */
  port?: number;
  /** Host to bind to */
  host?: string;
  /** Browser title */
  title?: string;
  /** Auto-open browser */
  open?: boolean;
}

/**
 * Documentation Server class
 */
export class DocumentationServer {
  private config: Required<ServerConfig>;
  private scanner: DocumentationScanner;
  private renderer: HtmlRenderer;
  private server: http.Server | null = null;
  private files: DocFile[] = [];
  private tree: DirNode | null = null;

  constructor(config: ServerConfig) {
    this.config = {
      rootPath: path.resolve(config.rootPath),
      port: config.port || 3000,
      host: config.host || 'localhost',
      title: config.title || 'Documentation Browser',
      open: config.open ?? true
    };

    this.scanner = new DocumentationScanner(this.config.rootPath);
    this.renderer = new HtmlRenderer(this.config.title);
  }

  /**
   * Start the server
   */
  async start(): Promise<string> {
    // Scan for documentation files
    this.files = this.scanner.scan();
    this.tree = this.scanner.buildTree();

    // Create server
    this.server = http.createServer((req, res) => {
      this.handleRequest(req, res);
    });

    // Start listening
    return new Promise((resolve, reject) => {
      this.server!.listen(this.config.port, this.config.host, () => {
        const url = `http://${this.config.host}:${this.config.port}`;

        // Auto-open browser
        if (this.config.open) {
          this.openBrowser(url);
        }

        resolve(url);
      });

      this.server!.on('error', (err: any) => {
        if (err.code === 'EADDRINUSE') {
          reject(new Error(`Port ${this.config.port} is already in use`));
        } else {
          reject(err);
        }
      });
    });
  }

  /**
   * Stop the server
   */
  stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => {
          this.server = null;
          resolve();
        });
      } else {
        resolve();
      }
    });
  }

  /**
   * Handle HTTP request
   */
  private handleRequest(req: http.IncomingMessage, res: http.ServerResponse): void {
    const parsedUrl = url.parse(req.url || '/', true);
    const pathname = parsedUrl.pathname || '/';

    try {
      if (pathname === '/') {
        // Index page
        const stats = this.scanner.getStats();
        const html = this.renderer.renderIndex(this.files, this.tree!, stats);
        this.sendHtml(res, html);
      } else if (pathname === '/search') {
        // Search
        const query = (parsedUrl.query.q as string) || '';
        const results = this.scanner.search(query);
        const html = this.renderer.renderSearch(query, results, this.tree!);
        this.sendHtml(res, html);
      } else if (pathname.startsWith('/doc/')) {
        // Documentation page
        const docPath = decodeURIComponent(pathname.slice(5));
        const file = this.scanner.findByPath(docPath);

        if (file) {
          const content = fs.readFileSync(file.absolutePath, 'utf8');
          const html = this.renderer.renderDoc(file, content, this.tree!);
          this.sendHtml(res, html);
        } else {
          const html = this.renderer.render404(this.tree!);
          this.sendHtml(res, html, 404);
        }
      } else if (pathname === '/api/files') {
        // API: list files
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(this.files));
      } else if (pathname === '/api/stats') {
        // API: stats
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(this.scanner.getStats()));
      } else if (pathname === '/api/tree') {
        // API: directory tree
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(this.tree));
      } else if (pathname === '/refresh') {
        // Refresh documentation index
        this.files = this.scanner.scan();
        this.tree = this.scanner.buildTree();
        res.writeHead(302, { 'Location': '/' });
        res.end();
      } else {
        // 404
        const html = this.renderer.render404(this.tree!);
        this.sendHtml(res, html, 404);
      }
    } catch (error: any) {
      console.error('Server error:', error);
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end(`Internal Server Error: ${error.message}`);
    }
  }

  /**
   * Send HTML response
   */
  private sendHtml(res: http.ServerResponse, html: string, statusCode: number = 200): void {
    res.writeHead(statusCode, {
      'Content-Type': 'text/html; charset=utf-8',
      'Content-Length': Buffer.byteLength(html)
    });
    res.end(html);
  }

  /**
   * Open browser
   */
  private openBrowser(url: string): void {
    const { platform } = process;
    let command: string;

    switch (platform) {
      case 'darwin':
        command = `open "${url}"`;
        break;
      case 'win32':
        command = `start "" "${url}"`;
        break;
      default:
        command = `xdg-open "${url}"`;
    }

    const { exec } = require('child_process');
    exec(command, (err: any) => {
      if (err) {
        console.log(`Could not open browser automatically. Visit: ${url}`);
      }
    });
  }

  /**
   * Get server URL
   */
  getUrl(): string {
    return `http://${this.config.host}:${this.config.port}`;
  }

  /**
   * Check if server is running
   */
  isRunning(): boolean {
    return this.server !== null && this.server.listening;
  }

  /**
   * Get scanned files
   */
  getFiles(): DocFile[] {
    return [...this.files];
  }

  /**
   * Get statistics
   */
  getStats(): any {
    return this.scanner.getStats();
  }
}
