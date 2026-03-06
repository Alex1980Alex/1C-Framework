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
/**
 * Main CLI entry point
 */
declare function main(): Promise<void>;
export { main };
