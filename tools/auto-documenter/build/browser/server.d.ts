/**
 * Documentation Server - HTTP server for browsing documentation
 * @module browser/server
 */
import { DocFile } from './scanner.js';
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
export declare class DocumentationServer {
    private config;
    private scanner;
    private renderer;
    private server;
    private files;
    private tree;
    constructor(config: ServerConfig);
    /**
     * Start the server
     */
    start(): Promise<string>;
    /**
     * Stop the server
     */
    stop(): Promise<void>;
    /**
     * Handle HTTP request
     */
    private handleRequest;
    /**
     * Send HTML response
     */
    private sendHtml;
    /**
     * Open browser
     */
    private openBrowser;
    /**
     * Get server URL
     */
    getUrl(): string;
    /**
     * Check if server is running
     */
    isRunning(): boolean;
    /**
     * Get scanned files
     */
    getFiles(): DocFile[];
    /**
     * Get statistics
     */
    getStats(): any;
}
