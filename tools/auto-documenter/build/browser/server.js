/**
 * Documentation Server - HTTP server for browsing documentation
 * @module browser/server
 */
import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import * as url from 'url';
import { DocumentationScanner } from './scanner.js';
import { HtmlRenderer } from './renderer.js';
/**
 * Documentation Server class
 */
export class DocumentationServer {
    constructor(config) {
        this.server = null;
        this.files = [];
        this.tree = null;
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
    async start() {
        // Scan for documentation files
        this.files = this.scanner.scan();
        this.tree = this.scanner.buildTree();
        // Create server
        this.server = http.createServer((req, res) => {
            this.handleRequest(req, res);
        });
        // Start listening
        return new Promise((resolve, reject) => {
            this.server.listen(this.config.port, this.config.host, () => {
                const url = `http://${this.config.host}:${this.config.port}`;
                // Auto-open browser
                if (this.config.open) {
                    this.openBrowser(url);
                }
                resolve(url);
            });
            this.server.on('error', (err) => {
                if (err.code === 'EADDRINUSE') {
                    reject(new Error(`Port ${this.config.port} is already in use`));
                }
                else {
                    reject(err);
                }
            });
        });
    }
    /**
     * Stop the server
     */
    stop() {
        return new Promise((resolve) => {
            if (this.server) {
                this.server.close(() => {
                    this.server = null;
                    resolve();
                });
            }
            else {
                resolve();
            }
        });
    }
    /**
     * Handle HTTP request
     */
    handleRequest(req, res) {
        const parsedUrl = url.parse(req.url || '/', true);
        const pathname = parsedUrl.pathname || '/';
        try {
            if (pathname === '/') {
                // Index page
                const stats = this.scanner.getStats();
                const html = this.renderer.renderIndex(this.files, this.tree, stats);
                this.sendHtml(res, html);
            }
            else if (pathname === '/search') {
                // Search
                const query = parsedUrl.query.q || '';
                const results = this.scanner.search(query);
                const html = this.renderer.renderSearch(query, results, this.tree);
                this.sendHtml(res, html);
            }
            else if (pathname.startsWith('/doc/')) {
                // Documentation page
                const docPath = decodeURIComponent(pathname.slice(5));
                const file = this.scanner.findByPath(docPath);
                if (file) {
                    const content = fs.readFileSync(file.absolutePath, 'utf8');
                    const html = this.renderer.renderDoc(file, content, this.tree);
                    this.sendHtml(res, html);
                }
                else {
                    const html = this.renderer.render404(this.tree);
                    this.sendHtml(res, html, 404);
                }
            }
            else if (pathname === '/api/files') {
                // API: list files
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(this.files));
            }
            else if (pathname === '/api/stats') {
                // API: stats
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(this.scanner.getStats()));
            }
            else if (pathname === '/api/tree') {
                // API: directory tree
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(this.tree));
            }
            else if (pathname === '/refresh') {
                // Refresh documentation index
                this.files = this.scanner.scan();
                this.tree = this.scanner.buildTree();
                res.writeHead(302, { 'Location': '/' });
                res.end();
            }
            else {
                // 404
                const html = this.renderer.render404(this.tree);
                this.sendHtml(res, html, 404);
            }
        }
        catch (error) {
            console.error('Server error:', error);
            res.writeHead(500, { 'Content-Type': 'text/plain' });
            res.end(`Internal Server Error: ${error.message}`);
        }
    }
    /**
     * Send HTML response
     */
    sendHtml(res, html, statusCode = 200) {
        res.writeHead(statusCode, {
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Length': Buffer.byteLength(html)
        });
        res.end(html);
    }
    /**
     * Open browser
     */
    openBrowser(url) {
        const { platform } = process;
        let command;
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
        exec(command, (err) => {
            if (err) {
                console.log(`Could not open browser automatically. Visit: ${url}`);
            }
        });
    }
    /**
     * Get server URL
     */
    getUrl() {
        return `http://${this.config.host}:${this.config.port}`;
    }
    /**
     * Check if server is running
     */
    isRunning() {
        return this.server !== null && this.server.listening;
    }
    /**
     * Get scanned files
     */
    getFiles() {
        return [...this.files];
    }
    /**
     * Get statistics
     */
    getStats() {
        return this.scanner.getStats();
    }
}
//# sourceMappingURL=server.js.map