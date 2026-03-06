/**
 * Output formatters for Documentation Diff Tool
 * Supports Markdown, JSON, and Console output formats
 */
import { ChangeType } from './diff-tool.js';
/**
 * Markdown formatter for documentation and GitHub PRs
 */
export class MarkdownFormatter {
    format(result) {
        const lines = [];
        // Header
        lines.push('# Documentation Diff Report');
        lines.push('');
        lines.push(`**Generated:** ${result.summary.timestamp}`);
        lines.push(`**Base:** \`${result.baseVersion}\``);
        lines.push(`**Target:** \`${result.targetVersion}\``);
        lines.push('');
        // Status badge
        if (!result.success) {
            lines.push(`> ❌ **Error:** ${result.error}`);
            lines.push('');
            return lines.join('\n');
        }
        // Summary
        lines.push('## Summary');
        lines.push('');
        lines.push(this.formatSummaryTable(result.summary));
        lines.push('');
        // Breaking changes warning
        if (result.summary.breakingChanges > 0) {
            lines.push('> ⚠️ **Warning:** This diff contains breaking changes!');
            lines.push('');
        }
        // Changes by file
        if (result.changes.length > 0) {
            lines.push('## Changes');
            lines.push('');
            const changesByFile = this.groupByFile(result.changes);
            for (const [filePath, changes] of Object.entries(changesByFile)) {
                lines.push(`### 📄 ${filePath}`);
                lines.push('');
                for (const change of changes) {
                    lines.push(this.formatChange(change));
                    lines.push('');
                }
            }
        }
        else {
            lines.push('## Changes');
            lines.push('');
            lines.push('✅ No changes detected.');
            lines.push('');
        }
        return lines.join('\n');
    }
    formatSummaryTable(summary) {
        const lines = [];
        lines.push('| Metric | Value |');
        lines.push('|--------|-------|');
        lines.push(`| Total Files | ${summary.totalFiles} |`);
        lines.push(`| Changed Files | ${summary.changedFiles} |`);
        lines.push(`| Added Files | ${summary.addedFiles} |`);
        lines.push(`| Removed Files | ${summary.removedFiles} |`);
        lines.push(`| Lines Added | +${summary.linesAdded} |`);
        lines.push(`| Lines Removed | -${summary.linesRemoved} |`);
        lines.push(`| Breaking Changes | ${summary.breakingChanges} |`);
        return lines.join('\n');
    }
    formatChange(change) {
        const icon = this.getChangeIcon(change.type);
        const severity = this.getSeverityBadge(change.severity);
        let result = `${icon} **${change.type.toUpperCase()}**`;
        if (change.section) {
            result += ` in section "${change.section}"`;
        }
        if (change.lineStart) {
            result += ` (lines ${change.lineStart}-${change.lineEnd || change.lineStart})`;
        }
        result += ` ${severity}`;
        result += '\n';
        // Add code blocks for content
        if (change.oldContent && change.type === ChangeType.REMOVED) {
            result += '\n```diff\n';
            result += change.oldContent
                .split('\n')
                .map((line) => `- ${line}`)
                .join('\n');
            result += '\n```\n';
        }
        if (change.newContent && change.type === ChangeType.ADDED) {
            result += '\n```diff\n';
            result += change.newContent
                .split('\n')
                .map((line) => `+ ${line}`)
                .join('\n');
            result += '\n```\n';
        }
        return result;
    }
    getChangeIcon(type) {
        switch (type) {
            case ChangeType.ADDED:
                return '🟢';
            case ChangeType.REMOVED:
                return '🔴';
            case ChangeType.MODIFIED:
                return '🟡';
            case ChangeType.UNCHANGED:
                return '⚪';
        }
    }
    getSeverityBadge(severity) {
        switch (severity) {
            case 'breaking':
                return '`BREAKING`';
            case 'warning':
                return '`⚠️`';
            default:
                return '';
        }
    }
    groupByFile(changes) {
        const grouped = {};
        for (const change of changes) {
            if (!grouped[change.filePath]) {
                grouped[change.filePath] = [];
            }
            grouped[change.filePath].push(change);
        }
        return grouped;
    }
}
/**
 * JSON formatter for CI/CD integration
 */
export class JsonFormatter {
    format(result) {
        return JSON.stringify(result, null, 2);
    }
}
/**
 * Console formatter with colors for terminal output
 */
export class ConsoleFormatter {
    constructor() {
        this.colors = {
            reset: '\x1b[0m',
            bright: '\x1b[1m',
            dim: '\x1b[2m',
            red: '\x1b[31m',
            green: '\x1b[32m',
            yellow: '\x1b[33m',
            blue: '\x1b[34m',
            cyan: '\x1b[36m',
        };
    }
    format(result) {
        const lines = [];
        // Header
        lines.push('');
        lines.push(`${this.colors.bright}${this.colors.cyan}📊 Documentation Diff Report${this.colors.reset}`);
        lines.push(`${this.colors.dim}${'─'.repeat(50)}${this.colors.reset}`);
        lines.push('');
        if (!result.success) {
            lines.push(`${this.colors.red}❌ Error: ${result.error}${this.colors.reset}`);
            return lines.join('\n');
        }
        // Summary
        lines.push(`${this.colors.bright}Summary:${this.colors.reset}`);
        lines.push(`  Base:    ${result.baseVersion}`);
        lines.push(`  Target:  ${result.targetVersion}`);
        lines.push('');
        lines.push(`  ${this.colors.green}+${result.summary.linesAdded} lines${this.colors.reset}  ` +
            `${this.colors.red}-${result.summary.linesRemoved} lines${this.colors.reset}`);
        lines.push(`  ${result.summary.changedFiles} files changed`);
        if (result.summary.breakingChanges > 0) {
            lines.push('');
            lines.push(`${this.colors.yellow}⚠️  ${result.summary.breakingChanges} breaking change(s) detected!${this.colors.reset}`);
        }
        // Changes
        if (result.changes.length > 0) {
            lines.push('');
            lines.push(`${this.colors.bright}Changes:${this.colors.reset}`);
            const changesByFile = this.groupByFile(result.changes);
            for (const [filePath, changes] of Object.entries(changesByFile)) {
                lines.push('');
                lines.push(`${this.colors.blue}  ${filePath}${this.colors.reset}`);
                for (const change of changes) {
                    lines.push(this.formatChange(change));
                }
            }
        }
        else {
            lines.push('');
            lines.push(`${this.colors.green}✅ No changes detected.${this.colors.reset}`);
        }
        lines.push('');
        return lines.join('\n');
    }
    formatChange(change) {
        const icon = this.getChangeIcon(change.type);
        const color = this.getChangeColor(change.type);
        const severityMarker = change.severity === 'breaking'
            ? ` ${this.colors.yellow}[BREAKING]${this.colors.reset}`
            : '';
        let line = `    ${icon} ${color}${change.type}${this.colors.reset}`;
        if (change.lineStart) {
            line += ` at line ${change.lineStart}`;
        }
        if (change.section) {
            line += ` in "${change.section}"`;
        }
        line += severityMarker;
        return line;
    }
    getChangeIcon(type) {
        switch (type) {
            case ChangeType.ADDED:
                return `${this.colors.green}+${this.colors.reset}`;
            case ChangeType.REMOVED:
                return `${this.colors.red}-${this.colors.reset}`;
            case ChangeType.MODIFIED:
                return `${this.colors.yellow}~${this.colors.reset}`;
            case ChangeType.UNCHANGED:
                return ' ';
        }
    }
    getChangeColor(type) {
        switch (type) {
            case ChangeType.ADDED:
                return this.colors.green;
            case ChangeType.REMOVED:
                return this.colors.red;
            case ChangeType.MODIFIED:
                return this.colors.yellow;
            default:
                return '';
        }
    }
    groupByFile(changes) {
        const grouped = {};
        for (const change of changes) {
            if (!grouped[change.filePath]) {
                grouped[change.filePath] = [];
            }
            grouped[change.filePath].push(change);
        }
        return grouped;
    }
}
/**
 * GitHub Actions formatter (creates job summary output)
 */
export class GitHubFormatter {
    format(result) {
        const lines = [];
        // GitHub Actions summary format
        lines.push('## 📊 Documentation Diff Report');
        lines.push('');
        if (!result.success) {
            lines.push(`::error::Documentation diff failed: ${result.error}`);
            return lines.join('\n');
        }
        // Summary section
        lines.push('<details>');
        lines.push('<summary>Summary</summary>');
        lines.push('');
        lines.push('| Metric | Value |');
        lines.push('|--------|-------|');
        lines.push(`| Changed Files | ${result.summary.changedFiles} |`);
        lines.push(`| Lines Added | +${result.summary.linesAdded} |`);
        lines.push(`| Lines Removed | -${result.summary.linesRemoved} |`);
        lines.push(`| Breaking Changes | ${result.summary.breakingChanges} |`);
        lines.push('');
        lines.push('</details>');
        lines.push('');
        // Breaking changes annotation
        if (result.summary.breakingChanges > 0) {
            lines.push(`::warning::Documentation contains ${result.summary.breakingChanges} breaking change(s)`);
            lines.push('');
        }
        // File annotations for GitHub
        for (const change of result.changes) {
            if (change.severity === 'breaking') {
                const file = change.filePath;
                const line = change.lineStart || 1;
                lines.push(`::warning file=${file},line=${line}::Breaking change detected in documentation`);
            }
        }
        return lines.join('\n');
    }
}
/**
 * Factory function to get formatter by type
 */
export function getFormatter(format) {
    switch (format) {
        case 'markdown':
            return new MarkdownFormatter();
        case 'json':
            return new JsonFormatter();
        case 'console':
            return new ConsoleFormatter();
        case 'github':
            return new GitHubFormatter();
        default:
            return new ConsoleFormatter();
    }
}
//# sourceMappingURL=diff-formatters.js.map