/**
 * context-manager.js
 * Main context management module for AI operations
 * Handles all context extraction and formatting for AI prompts
 */

import path from 'path';
import { log } from '../utils.js';
import {
	extractFromFile,
	extractFromFiles,
	extractFromCursorRules,
	formatContextForPrompt,
	getContextStats,
	validateContext,
	truncateContext
} from './context-extractor.js';

/**
 * Context manager for handling all context operations
 */
export class ContextManager {
	constructor(options = {}) {
		this.projectRoot = options.projectRoot || process.cwd();
		this.maxContextLength = options.maxContextLength || 50000;
		this.includeStats = options.includeStats || false;
		this.verbose = options.verbose || false;
	}

	/**
	 * Extract context from files specified by --context-file option
	 * @param {string|string[]} filePaths - File path(s) to extract context from
	 * @param {Object} options - Extraction options
	 * @returns {Promise<Object>} Context extraction result
	 */
	async extractFileContext(filePaths, options = {}) {
		const files = Array.isArray(filePaths) ? filePaths : [filePaths];
		
		if (this.verbose) {
			log('info', `Extracting context from ${files.length} file(s)`);
		}

		const results = await extractFromFiles(files, {
			maxTotalSize: this.maxContextLength,
			...options
		});

		const successfulResults = results.filter(r => r.success);
		const failedResults = results.filter(r => !r.success);

		if (failedResults.length > 0 && this.verbose) {
			failedResults.forEach(result => {
				log('warn', `Failed to read ${result.source}: ${result.error}`);
			});
		}

		return {
			success: successfulResults.length > 0,
			content: formatContextForPrompt(successfulResults, {
				includeSource: true,
				includeErrors: false
			}),
			stats: getContextStats(results),
			results: results
		};
	}

	/**
	 * Extract context from cursor rules specified by --context-rules option
	 * @param {string} rulesPattern - Pattern to match cursor rules
	 * @param {Object} options - Extraction options
	 * @returns {Promise<Object>} Context extraction result
	 */
	async extractCursorRulesContext(rulesPattern, options = {}) {
		if (this.verbose) {
			log('info', `Extracting cursor rules context: ${rulesPattern}`);
		}

		const results = await extractFromCursorRules(rulesPattern, {
			projectRoot: this.projectRoot,
			...options
		});

		const successfulResults = results.filter(r => r.success);
		const failedResults = results.filter(r => !r.success);

		if (failedResults.length > 0 && this.verbose) {
			failedResults.forEach(result => {
				log('warn', `Failed to read cursor rules ${result.source}: ${result.error}`);
			});
		}

		return {
			success: successfulResults.length > 0,
			content: formatContextForPrompt(successfulResults, {
				includeSource: true,
				includeErrors: false
			}),
			stats: getContextStats(results),
			results: results
		};
	}

	/**
	 * Process direct context input from --context option
	 * @param {string} contextText - Direct context text
	 * @param {Object} options - Processing options
	 * @returns {Object} Context processing result
	 */
	processDirectContext(contextText, options = {}) {
		if (this.verbose) {
			log('info', `Processing direct context input (${contextText.length} characters)`);
		}

		// Validate context
		const validation = validateContext(contextText, {
			maxLength: this.maxContextLength
		});

		let processedContent = contextText;

		// Truncate if necessary
		if (!validation.valid && validation.issues.some(issue => issue.includes('too long'))) {
			processedContent = truncateContext(contextText, this.maxContextLength, {
				strategy: 'end'
			});
			
			if (this.verbose) {
				log('warn', `Context truncated from ${contextText.length} to ${processedContent.length} characters`);
			}
		}

		return {
			success: true,
			content: `### Direct Context\n\n${processedContent}`,
			stats: {
				totalFiles: 1,
				successfulFiles: 1,
				failedFiles: 0,
				totalCharacters: processedContent.length
			},
			validation: validation
		};
	}

	/**
	 * Combine multiple context sources into a single formatted context
	 * @param {Object} contextSources - Object containing different context types
	 * @param {string[]} [contextSources.files] - File paths for context
	 * @param {string} [contextSources.cursorRules] - Cursor rules pattern
	 * @param {string} [contextSources.direct] - Direct context text
	 * @param {Object} options - Combination options
	 * @returns {Promise<Object>} Combined context result
	 */
	async combineContextSources(contextSources, options = {}) {
		const contextSections = [];
		const allStats = [];
		const allResults = [];

		// Process file context
		if (contextSources.files && contextSources.files.length > 0) {
			const fileContext = await this.extractFileContext(contextSources.files, options);
			if (fileContext.success) {
				contextSections.push(fileContext.content);
				allStats.push(fileContext.stats);
				allResults.push(...fileContext.results);
			}
		}

		// Process cursor rules context
		if (contextSources.cursorRules) {
			const rulesContext = await this.extractCursorRulesContext(contextSources.cursorRules, options);
			if (rulesContext.success) {
				contextSections.push(rulesContext.content);
				allStats.push(rulesContext.stats);
				allResults.push(...rulesContext.results);
			}
		}

		// Process direct context
		if (contextSources.direct) {
			const directContext = this.processDirectContext(contextSources.direct, options);
			if (directContext.success) {
				contextSections.push(directContext.content);
				allStats.push(directContext.stats);
			}
		}

		// Combine all context sections
		const combinedContent = contextSections.join('\n\n---\n\n');

		// Calculate combined stats
		const combinedStats = this.combineStats(allStats);

		// Validate and potentially truncate combined content
		const validation = validateContext(combinedContent, {
			maxLength: this.maxContextLength
		});

		let finalContent = combinedContent;
		if (!validation.valid && validation.issues.some(issue => issue.includes('too long'))) {
			finalContent = truncateContext(combinedContent, this.maxContextLength, {
				strategy: 'end',
				marker: '\n\n[... context truncated due to length limits ...]\n\n'
			});
			
			if (this.verbose) {
				log('warn', `Combined context truncated from ${combinedContent.length} to ${finalContent.length} characters`);
			}
		}

		return {
			success: contextSections.length > 0,
			content: finalContent,
			stats: combinedStats,
			validation: validation,
			results: allResults
		};
	}

	/**
	 * Combine statistics from multiple context extractions
	 * @param {Object[]} statsArray - Array of stats objects
	 * @returns {Object} Combined statistics
	 */
	combineStats(statsArray) {
		if (statsArray.length === 0) {
			return {
				totalFiles: 0,
				successfulFiles: 0,
				failedFiles: 0,
				totalCharacters: 0
			};
		}

		return {
			totalFiles: statsArray.reduce((sum, stats) => sum + stats.totalFiles, 0),
			successfulFiles: statsArray.reduce((sum, stats) => sum + stats.successfulFiles, 0),
			failedFiles: statsArray.reduce((sum, stats) => sum + stats.failedFiles, 0),
			totalCharacters: statsArray.reduce((sum, stats) => sum + stats.totalCharacters, 0)
		};
	}

	/**
	 * Format context for inclusion in AI prompts with proper sectioning
	 * @param {string} contextContent - Context content to format
	 * @param {Object} options - Formatting options
	 * @returns {string} Formatted context for AI prompts
	 */
	formatForAIPrompt(contextContent, options = {}) {
		const { includeHeader = true, sectionTitle = 'Additional Context' } = options;

		if (!contextContent || contextContent.trim().length === 0) {
			return '';
		}

		let formatted = '';
		
		if (includeHeader) {
			formatted += `\n\n## ${sectionTitle}\n\n`;
		}
		
		formatted += contextContent.trim();
		
		return formatted;
	}

	/**
	 * Get context summary for logging/debugging
	 * @param {Object} contextResult - Context extraction result
	 * @returns {string} Human-readable context summary
	 */
	getContextSummary(contextResult) {
		if (!contextResult.success) {
			return 'No context extracted';
		}

		const stats = contextResult.stats;
		const summary = [];

		if (stats.successfulFiles > 0) {
			summary.push(`${stats.successfulFiles} file(s)`);
		}

		if (stats.totalCharacters > 0) {
			const size = stats.totalCharacters > 1000 
				? `${Math.round(stats.totalCharacters / 1000)}k chars`
				: `${stats.totalCharacters} chars`;
			summary.push(size);
		}

		if (stats.failedFiles > 0) {
			summary.push(`${stats.failedFiles} failed`);
		}

		return summary.length > 0 ? summary.join(', ') : 'Empty context';
	}
}

/**
 * Parse context-related command line options
 * @param {Object} options - Command line options object
 * @returns {Object} Parsed context sources
 */
export function parseContextOptions(options) {
	const contextSources = {};

	// Parse --context-file option
	if (options.contextFile) {
		contextSources.files = Array.isArray(options.contextFile) 
			? options.contextFile 
			: [options.contextFile];
	}

	// Parse --context-rules option
	if (options.contextRules) {
		contextSources.cursorRules = options.contextRules;
	}

	// Parse --context option
	if (options.context) {
		contextSources.direct = options.context;
	}

	return contextSources;
}

/**
 * Add context options to a Commander.js command
 * @param {Command} command - Commander.js command instance
 * @returns {Command} Command with context options added
 */
export function addContextOptions(command) {
	return command
		.option('--context-file <file>', 'Include context from specified file(s)', (value, previous) => {
			return previous ? [...previous, value] : [value];
		})
		.option('--context-rules <pattern>', 'Include context from cursor rules matching pattern')
		.option('--context <text>', 'Include direct context text');
}

export default ContextManager;