/**
 * Output formatters for Documentation Diff Tool
 * Supports Markdown, JSON, and Console output formats
 */
import { DiffResult } from './diff-tool.js';
/**
 * Output format type
 */
export type OutputFormat = 'markdown' | 'json' | 'console' | 'github';
/**
 * Base formatter interface
 */
export interface DiffFormatter {
    format(result: DiffResult): string;
}
/**
 * Markdown formatter for documentation and GitHub PRs
 */
export declare class MarkdownFormatter implements DiffFormatter {
    format(result: DiffResult): string;
    private formatSummaryTable;
    private formatChange;
    private getChangeIcon;
    private getSeverityBadge;
    private groupByFile;
}
/**
 * JSON formatter for CI/CD integration
 */
export declare class JsonFormatter implements DiffFormatter {
    format(result: DiffResult): string;
}
/**
 * Console formatter with colors for terminal output
 */
export declare class ConsoleFormatter implements DiffFormatter {
    private colors;
    format(result: DiffResult): string;
    private formatChange;
    private getChangeIcon;
    private getChangeColor;
    private groupByFile;
}
/**
 * GitHub Actions formatter (creates job summary output)
 */
export declare class GitHubFormatter implements DiffFormatter {
    format(result: DiffResult): string;
}
/**
 * Factory function to get formatter by type
 */
export declare function getFormatter(format: OutputFormat): DiffFormatter;
