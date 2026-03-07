/**
 * context-extractor.js
 * Basic context file extraction utility for AI operations
 * Supports reading context from files, cursor rules, and direct context input
 */

import fs from 'fs';
import path from 'path';
import { log } from '../utils.js';

/**
 * Maximum file size to read (in bytes) - 1MB default
 */
const MAX_FILE_SIZE = 1024 * 1024;

/**
 * Maximum total context length (in characters) - 50k default
 */
const MAX_CONTEXT_LENGTH = 50000;

/**
 * Context extraction result structure
 * @typedef {Object} ContextResult
 * @property {boolean} success - Whether extraction was successful
 * @property {string} content - Extracted context content
 * @property {string} source - Source description (file path, rule name, etc.)
 * @property {number} size - Size of extracted content in characters
 * @property {string} [error] - Error message if extraction failed
 */

/**
 * Extract context from a single file
 * @param {string} filePath - Path to the file to read
 * @param {Object} options - Extraction options
 * @param {number} [options.maxSize] - Maximum file size to read
 * @param {boolean} [options.validateUtf8] - Whether to validate UTF-8 encoding
 * @returns {Promise<ContextResult>} Extraction result
 */
export async function extractFromFile(filePath, options = {}) {
	const { maxSize = MAX_FILE_SIZE, validateUtf8 = true } = options;

	try {
		// Resolve absolute path
		const absolutePath = path.resolve(filePath);
		
		// Check if file exists
		if (!fs.existsSync(absolutePath)) {
			return {
				success: false,
				content: '',
				source: filePath,
				size: 0,
				error: `File not found: ${filePath}`
			};
		}

		// Check file stats
		const stats = fs.statSync(absolutePath);
		if (!stats.isFile()) {
			return {
				success: false,
				content: '',
				source: filePath,
				size: 0,
				error: `Path is not a file: ${filePath}`
			};
		}

		// Check file size
		if (stats.size > maxSize) {
			return {
				success: false,
				content: '',
				source: filePath,
				size: stats.size,
				error: `File too large: ${Math.round(stats.size / 1024)}KB > ${Math.round(maxSize / 1024)}KB`
			};
		}

		// Read file content
		const content = fs.readFileSync(absolutePath, 'utf8');

		// Basic UTF-8 validation if requested
		if (validateUtf8 && content.includes('\uFFFD')) {
			log('warn', `File ${filePath} may contain invalid UTF-8 characters`);
		}

		return {
			success: true,
			content: content,
			source: filePath,
			size: content.length
		};

	} catch (error) {
		return {
			success: false,
			content: '',
			source: filePath,
			size: 0,
			error: `Failed to read file: ${error.message}`
		};
	}
}

/**
 * Extract context from multiple files
 * @param {string[]} filePaths - Array of file paths to read
 * @param {Object} options - Extraction options
 * @param {number} [options.maxTotalSize] - Maximum total context size
 * @param {boolean} [options.continueOnError] - Continue processing if one file fails
 * @returns {Promise<ContextResult[]>} Array of extraction results
 */
export async function extractFromFiles(filePaths, options = {}) {
	const { maxTotalSize = MAX_CONTEXT_LENGTH, continueOnError = true } = options;
	const results = [];
	let totalSize = 0;

	for (const filePath of filePaths) {
		const result = await extractFromFile(filePath, options);
		
		if (result.success) {
			// Check if adding this file would exceed total size limit
			if (totalSize + result.size > maxTotalSize) {
				log('warn', `Skipping ${filePath}: would exceed total context size limit`);
				results.push({
					success: false,
					content: '',
					source: filePath,
					size: 0,
					error: 'Skipped: would exceed total context size limit'
				});
				continue;
			}
			totalSize += result.size;
		}

		results.push(result);

		// Stop processing if error occurred and continueOnError is false
		if (!result.success && !continueOnError) {
			break;
		}
	}

	return results;
}

/**
 * Extract context from cursor rules files
 * @param {string} rulesPattern - Pattern to match cursor rules (e.g., "*.md", "typescript.md")
 * @param {Object} options - Extraction options
 * @param {string} [options.rulesDir] - Directory containing cursor rules (default: .cursor/rules)
 * @param {string} [options.projectRoot] - Project root directory
 * @returns {Promise<ContextResult[]>} Array of extraction results
 */
export async function extractFromCursorRules(rulesPattern, options = {}) {
	const { 
		rulesDir = '.cursor/rules', 
		projectRoot = process.cwd() 
	} = options;

	try {
		const rulesPath = path.resolve(projectRoot, rulesDir);
		
		// Check if rules directory exists
		if (!fs.existsSync(rulesPath)) {
			return [{
				success: false,
				content: '',
				source: rulesPattern,
				size: 0,
				error: `Cursor rules directory not found: ${rulesPath}`
			}];
		}

		// Find matching rule files
		const allFiles = fs.readdirSync(rulesPath);
		const matchingFiles = [];

		if (rulesPattern === '*' || rulesPattern === '*.md') {
			// Match all .md files
			matchingFiles.push(...allFiles.filter(f => f.endsWith('.md')));
		} else if (rulesPattern.includes('*')) {
			// Handle glob patterns (basic implementation)
			const regex = new RegExp(
				rulesPattern.replace(/\*/g, '.*').replace(/\?/g, '.')
			);
			matchingFiles.push(...allFiles.filter(f => regex.test(f)));
		} else {
			// Exact filename match
			if (allFiles.includes(rulesPattern)) {
				matchingFiles.push(rulesPattern);
			}
		}

		if (matchingFiles.length === 0) {
			return [{
				success: false,
				content: '',
				source: rulesPattern,
				size: 0,
				error: `No cursor rules found matching pattern: ${rulesPattern}`
			}];
		}

		// Extract content from matching files
		const filePaths = matchingFiles.map(f => path.join(rulesPath, f));
		return await extractFromFiles(filePaths, options);

	} catch (error) {
		return [{
			success: false,
			content: '',
			source: rulesPattern,
			size: 0,
			error: `Failed to extract cursor rules: ${error.message}`
		}];
	}
}

/**
 * Format context content for inclusion in AI prompts
 * @param {ContextResult[]} contextResults - Array of context extraction results
 * @param {Object} options - Formatting options
 * @param {boolean} [options.includeSource] - Include source information in output
 * @param {boolean} [options.includeErrors] - Include error information in output
 * @param {string} [options.separator] - Separator between context sections
 * @returns {string} Formatted context content
 */
export function formatContextForPrompt(contextResults, options = {}) {
	const { 
		includeSource = true, 
		includeErrors = false, 
		separator = '\n\n---\n\n' 
	} = options;

	const sections = [];

	for (const result of contextResults) {
		if (result.success && result.content.trim()) {
			let section = '';
			
			if (includeSource) {
				section += `### Context from: ${result.source}\n\n`;
			}
			
			section += result.content.trim();
			sections.push(section);
		} else if (includeErrors && !result.success) {
			sections.push(`### Error reading ${result.source}: ${result.error}`);
		}
	}

	return sections.join(separator);
}

/**
 * Get context statistics for multiple extraction results
 * @param {ContextResult[]} contextResults - Array of context extraction results
 * @returns {Object} Context statistics
 */
export function getContextStats(contextResults) {
	const stats = {
		totalFiles: contextResults.length,
		successfulFiles: 0,
		failedFiles: 0,
		totalCharacters: 0,
		averageFileSize: 0,
		largestFile: null,
		smallestFile: null
	};

	const successfulResults = contextResults.filter(r => r.success);
	stats.successfulFiles = successfulResults.length;
	stats.failedFiles = stats.totalFiles - stats.successfulFiles;

	if (successfulResults.length > 0) {
		stats.totalCharacters = successfulResults.reduce((sum, r) => sum + r.size, 0);
		stats.averageFileSize = Math.round(stats.totalCharacters / successfulResults.length);
		
		const sizes = successfulResults.map(r => ({ source: r.source, size: r.size }));
		sizes.sort((a, b) => b.size - a.size);
		
		stats.largestFile = sizes[0];
		stats.smallestFile = sizes[sizes.length - 1];
	}

	return stats;
}

/**
 * Validate context content for common issues
 * @param {string} content - Context content to validate
 * @param {Object} options - Validation options
 * @param {number} [options.maxLength] - Maximum allowed length
 * @param {boolean} [options.checkEncoding] - Check for encoding issues
 * @returns {Object} Validation result
 */
export function validateContext(content, options = {}) {
	const { maxLength = MAX_CONTEXT_LENGTH, checkEncoding = true } = options;
	const issues = [];

	// Check length
	if (content.length > maxLength) {
		issues.push(`Content too long: ${content.length} > ${maxLength} characters`);
	}

	// Check encoding
	if (checkEncoding) {
		if (content.includes('\uFFFD')) {
			issues.push('Content contains invalid UTF-8 characters');
		}
		
		// Check for unusual control characters
		const controlChars = content.match(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g);
		if (controlChars) {
			issues.push(`Content contains ${controlChars.length} control characters`);
		}
	}

	// Check for very long lines (might indicate binary content)
	const lines = content.split('\n');
	const longLines = lines.filter(line => line.length > 1000);
	if (longLines.length > 0) {
		issues.push(`Content has ${longLines.length} very long lines (>1000 chars each)`);
	}

	return {
		valid: issues.length === 0,
		issues: issues,
		length: content.length,
		lineCount: lines.length
	};
}

/**
 * Truncate context content to fit within size limits
 * @param {string} content - Content to truncate
 * @param {number} maxLength - Maximum allowed length
 * @param {Object} options - Truncation options
 * @param {string} [options.strategy] - Truncation strategy ('end', 'middle', 'start')
 * @param {string} [options.marker] - Marker to indicate truncation
 * @returns {string} Truncated content
 */
export function truncateContext(content, maxLength, options = {}) {
	const { strategy = 'end', marker = '\n\n[... content truncated ...]\n\n' } = options;

	if (content.length <= maxLength) {
		return content;
	}

	const markerLength = marker.length;
	const availableLength = maxLength - markerLength;

	switch (strategy) {
		case 'start':
			return marker + content.slice(content.length - availableLength);
		
		case 'middle':
			const halfLength = Math.floor(availableLength / 2);
			return content.slice(0, halfLength) + marker + content.slice(content.length - halfLength);
		
		case 'end':
		default:
			return content.slice(0, availableLength) + marker;
	}
}

export default {
	extractFromFile,
	extractFromFiles,
	extractFromCursorRules,
	formatContextForPrompt,
	getContextStats,
	validateContext,
	truncateContext,
	MAX_FILE_SIZE,
	MAX_CONTEXT_LENGTH
};