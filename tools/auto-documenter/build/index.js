#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ErrorCode, ListToolsRequestSchema, McpError, } from '@modelcontextprotocol/sdk/types.js';
import { getConfig } from './config.js';
import { ToolRegistry } from './tools/registry.js';
import { ToolAggregator } from './tools/aggregator.js';
import * as fs from 'fs';
import * as nodePath from 'path';
/**
 * Checks if the given path is a 1C:Enterprise configuration
 * Detects by presence of typical 1C metadata folders or .bsl files
 */
function is1CConfiguration(dirPath) {
    try {
        // Normalize path for cross-platform compatibility
        const normalizedPath = dirPath.replace(/\\/g, '/');
        // Check if path contains typical 1C configuration patterns
        const patterns1C = [
            '/configuration/',
            '/CommonModules/',
            '/Catalogs/',
            '/Documents/',
            '/InformationRegisters/',
            '/AccumulationRegisters/',
            '/DataProcessors/',
            '/Reports/',
            '/Subsystems/'
        ];
        if (patterns1C.some(pattern => normalizedPath.includes(pattern))) {
            return true;
        }
        // Check if directory contains .bsl files or 1C metadata folders
        if (fs.existsSync(dirPath)) {
            const entries = fs.readdirSync(dirPath, { withFileTypes: true });
            // Check for typical 1C metadata folder names
            const metadataFolders = ['CommonModules', 'Catalogs', 'Documents', 'InformationRegisters',
                'AccumulationRegisters', 'DataProcessors', 'Reports', 'Subsystems',
                'Ext', 'Forms', 'Commands', 'Templates'];
            for (const entry of entries) {
                if (entry.isDirectory() && metadataFolders.includes(entry.name)) {
                    return true;
                }
                // Check for .bsl files
                if (entry.isFile() && entry.name.toLowerCase().endsWith('.bsl')) {
                    return true;
                }
            }
            // Check subdirectories for .bsl files (one level deep)
            for (const entry of entries) {
                if (entry.isDirectory()) {
                    const subPath = nodePath.join(dirPath, entry.name);
                    try {
                        const subEntries = fs.readdirSync(subPath);
                        if (subEntries.some(f => f.toLowerCase().endsWith('.bsl'))) {
                            return true;
                        }
                    }
                    catch {
                        // Ignore permission errors
                    }
                }
            }
        }
        return false;
    }
    catch {
        return false;
    }
}
/**
 * Calculates the output directory for 1C configurations
 * If path ends with /src, creates docs/ at the same level
 * Otherwise creates docs/ inside the path
 */
function calculate1COutputDir(inputPath) {
    const normalizedPath = inputPath.replace(/\\/g, '/');
    // If path ends with /src, put docs at the same level
    if (normalizedPath.endsWith('/src') || normalizedPath.endsWith('/src/')) {
        const parentDir = nodePath.dirname(inputPath);
        return nodePath.join(parentDir, 'docs');
    }
    // Check if 'src' is in the path - go to parent of src
    const srcIndex = normalizedPath.lastIndexOf('/src/');
    if (srcIndex !== -1) {
        const configRoot = inputPath.substring(0, srcIndex);
        return nodePath.join(configRoot, 'docs');
    }
    // Default: create docs/ inside the input path
    return nodePath.join(inputPath, 'docs');
}
/**
 * Validates the arguments for auto-* tools
 */
function isValidAutoToolArgs(args) {
    return (typeof args === 'object' &&
        args !== null &&
        typeof args.path === 'string' &&
        (args.outputDir === undefined || typeof args.outputDir === 'string') &&
        (args.openRouterApiKey === undefined || typeof args.openRouterApiKey === 'string') &&
        (args.model === undefined || typeof args.model === 'string') &&
        (args.updateExisting === undefined || typeof args.updateExisting === 'boolean'));
}
/**
 * Main MCP server class for the autodocument tools
 */
class AutodocumentServer {
    constructor() {
        this.config = getConfig();
        // Initialize tool registry
        // Always use rotation mode - tools explicitly set useRotation=true
        // API keys and models will be read from environment variables in provider-rotation
        this.toolRegistry = new ToolRegistry(undefined, undefined);
        this.server = new Server({
            name: 'autodocument-server',
            version: '0.1.0',
        }, {
            capabilities: {
                tools: {},
            },
        });
        this.setupToolHandlers();
        // Error handling
        this.server.onerror = (error) => console.error('[MCP Error]', error);
        process.on('SIGINT', async () => {
            await this.server.close();
            process.exit(0);
        });
    }
    /**
     * Sets up the tool handlers for the MCP server
     */
    setupToolHandlers() {
        // List available tools
        this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
            tools: this.toolRegistry.getToolSchemas(),
        }));
        // Handle tool calls
        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            // Check if the tool exists
            if (!this.toolRegistry.hasTool(request.params.name)) {
                throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${request.params.name}`);
            }
            // Validate arguments
            if (!isValidAutoToolArgs(request.params.arguments)) {
                throw new McpError(ErrorCode.InvalidParams, `Invalid arguments for ${request.params.name} tool. Expected: path (string), outputDir? (string), openRouterApiKey? (string), model? (string), updateExisting? (boolean)`);
            }
            const { path, outputDir, openRouterApiKey, model, updateExisting } = request.params.arguments;
            const toolName = request.params.name;
            try {
                // Determine effective output directory
                // For 1C configurations: auto-calculate docs/ path if outputDir not specified
                let effectiveOutputDir = outputDir;
                if (!effectiveOutputDir && is1CConfiguration(path)) {
                    effectiveOutputDir = calculate1COutputDir(path);
                    console.error(`[1C Auto] Detected 1C configuration, outputDir set to: ${effectiveOutputDir}`);
                }
                console.error(`Starting ${toolName} for directory: ${path}${effectiveOutputDir ? ` -> ${effectiveOutputDir}` : ''} (updateExisting: ${updateExisting ?? 'default'})`);
                // Get the tool from the registry
                const tool = this.toolRegistry.getTool(toolName);
                // Create an aggregator with the provided arguments
                const aggregator = new ToolAggregator(path, tool, updateExisting, effectiveOutputDir);
                // Get progress token from the request metadata if available
                const progressToken = request.params._meta?.progressToken || `autodoc-${Date.now()}`;
                // Create a progress callback for logging progress and preventing timeouts
                const progressCallback = (directory, fileCount, currentDir, totalDirs) => {
                    // Calculate progress percentage
                    const percent = Math.round((currentDir / totalDirs) * 100);
                    // Log detailed progress to console - this will be seen in the logs
                    console.error(`[${percent}%] Processing directory: ${directory} (${fileCount} files, ${currentDir}/${totalDirs})`);
                    // Add heartbeat logging to prevent timeouts
                    if (currentDir % 3 === 0 || percent % 10 === 0) {
                        console.error(`Heartbeat at ${new Date().toISOString()}: ${percent}% complete`);
                    }
                };
                // Run the tool process with progress updates
                const result = await aggregator.run(progressCallback);
                // Format the result for display
                const resultSummary = tool.formatResultSummary(result);
                return {
                    content: [
                        {
                            type: 'text',
                            text: resultSummary,
                        },
                    ],
                };
            }
            catch (error) {
                console.error('Error generating documentation:', error);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Error generating documentation: ${error.message}`,
                        },
                    ],
                    isError: true,
                };
            }
        });
    }
    // No more need for formatResultSummary here - it's now handled by each tool
    /**
     * Starts the MCP server
     */
    async run() {
        const transport = new StdioServerTransport();
        await this.server.connect(transport);
        console.error('Autodocument MCP server running on stdio');
    }
}
// Run the server
const server = new AutodocumentServer();
server.run().catch(console.error);
//# sourceMappingURL=index.js.map