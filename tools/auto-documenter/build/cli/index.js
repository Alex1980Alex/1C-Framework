#!/usr/bin/env node
/**
 * Autodocument CLI
 *
 * Standalone command-line interface for automatic code documentation generation.
 * Supports multiple AI providers and various documentation tasks.
 *
 * Usage:
 *   autodoc generate <path> [options]       - Generate documentation
 *   autodoc review <path> [options]         - Generate code review
 *   autodoc testplan <path> [options]       - Generate test plan
 *   autodoc inline <path> [options]         - Generate inline docs
 *   autodoc diff <base> <target> [options]  - Compare documentation versions
 *
 * @module cli
 */
import { Command } from 'commander';
import { createGenerateCommand } from './commands/generate.js';
import { createReviewCommand } from './commands/review.js';
import { createTestplanCommand } from './commands/testplan.js';
import { createInlineCommand } from './commands/inline.js';
import { createInfoCommand } from './commands/info.js';
import { createBenchmarkCommand } from './commands/benchmark.js';
import { createBrowseCommand } from './commands/browse.js';
import { createDiffCommand } from './commands/diff.js';
import { version, description } from './utils/version.js';
import { setupGlobalOptions } from './utils/options.js';
/**
 * Main CLI entry point
 */
async function main() {
    const program = new Command();
    program
        .name('autodoc')
        .description(description)
        .version(version, '-v, --version', 'Display version number')
        .helpOption('-h, --help', 'Display help information');
    // Setup global options
    setupGlobalOptions(program);
    // Add commands
    program.addCommand(createGenerateCommand());
    program.addCommand(createReviewCommand());
    program.addCommand(createTestplanCommand());
    program.addCommand(createInlineCommand());
    program.addCommand(createInfoCommand());
    program.addCommand(createBenchmarkCommand());
    program.addCommand(createBrowseCommand());
    program.addCommand(createDiffCommand());
    // Parse arguments
    await program.parseAsync(process.argv);
    // If no command provided, show help
    if (process.argv.length <= 2) {
        program.help();
    }
}
// Run CLI
main().catch((error) => {
    console.error('Error:', error.message);
    process.exit(1);
});
export { main };
//# sourceMappingURL=index.js.map