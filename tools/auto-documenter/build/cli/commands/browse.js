/**
 * Browse Command - Start interactive documentation browser
 * @module cli/commands/browse
 */
import { Command } from 'commander';
import * as path from 'path';
import * as fs from 'fs';
import { createOutput } from '../utils/output.js';
import { DocumentationServer } from '../../browser/index.js';
/**
 * Execute browse command
 */
async function executeBrowse(targetPath, options, output) {
    const absolutePath = path.resolve(targetPath);
    // Validate path exists
    if (!fs.existsSync(absolutePath)) {
        throw new Error(`Path does not exist: ${absolutePath}`);
    }
    output.header('Documentation Browser');
    output.info(`Directory: ${absolutePath}`);
    output.info(`Port: ${options.port}`);
    output.newline();
    // Create and start server
    const server = new DocumentationServer({
        rootPath: absolutePath,
        port: options.port,
        host: options.host,
        title: `Documentation: ${path.basename(absolutePath)}`,
        open: !options.noOpen
    });
    try {
        output.info('Starting server...');
        const url = await server.start();
        const stats = server.getStats();
        output.success(`Server running at: ${url}`);
        output.newline();
        output.summary({
            'Documentation files': stats.totalFiles,
            'Directories': stats.directories,
            'Documentation': stats.byType.documentation || 0,
            'Reviews': stats.byType.review || 0,
            'Test Plans': stats.byType.testplan || 0
        });
        output.newline();
        output.info('Press Ctrl+C to stop the server');
        // Handle shutdown
        process.on('SIGINT', async () => {
            output.newline();
            output.info('Shutting down server...');
            await server.stop();
            output.success('Server stopped');
            process.exit(0);
        });
        process.on('SIGTERM', async () => {
            await server.stop();
            process.exit(0);
        });
        // Keep process alive
        await new Promise(() => { });
    }
    catch (error) {
        throw new Error(`Failed to start server: ${error.message}`);
    }
}
/**
 * Create browse command
 */
export function createBrowseCommand() {
    const command = new Command('browse')
        .alias('serve')
        .alias('view')
        .description('Start interactive documentation browser')
        .argument('[path]', 'Directory containing documentation', '.')
        .option('-p, --port <number>', 'Port number', '3000')
        .option('-H, --host <host>', 'Host to bind to', 'localhost')
        .option('--no-open', 'Do not auto-open browser')
        .action(async (targetPath, options, cmd) => {
        const globalOpts = cmd.optsWithGlobals();
        const output = createOutput(globalOpts.verbose, globalOpts.quiet);
        const browseOptions = {
            port: parseInt(options.port, 10),
            host: options.host,
            noOpen: options.open === false,
            verbose: globalOpts.verbose,
            quiet: globalOpts.quiet
        };
        try {
            await executeBrowse(targetPath, browseOptions, output);
        }
        catch (error) {
            output.error(error.message);
            process.exit(1);
        }
    });
    return command;
}
//# sourceMappingURL=browse.js.map