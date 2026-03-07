/**
 * ai-context-integration.js
 * Integration layer between context system and AI services
 */

import { ContextManager } from './context-manager.js';
import { parseContextOptions } from './context-options-helper.js';

/**
 * Enhance AI prompt with context from command options
 * @param {string} originalPrompt - The original AI prompt
 * @param {Object} options - Command options containing context settings
 * @param {Object} additionalContext - Additional context sources
 * @returns {Promise<string>} Enhanced prompt with context
 */
export async function enhancePromptWithContext(originalPrompt, options = {}, additionalContext = {}) {
	const contextOptions = parseContextOptions(options);

	// If no context options are specified, return original prompt
	if (!contextOptions.contextFiles.length &&
		!contextOptions.contextText &&
		!contextOptions.includeRules) {
		return originalPrompt;
	}

	const contextManager = new ContextManager();

	try {
		// Prepare context sources object
		const contextSources = {};

		// Add file contexts
		if (contextOptions.contextFiles.length > 0) {
			contextSources.files = contextOptions.contextFiles;
		}

		// Add cursor rules context
		if (contextOptions.includeRules) {
			contextSources.cursorRules = '.cursor/rules/*.md';
		}

		// Combine direct text contexts
		const directContexts = [];

		if (contextOptions.contextText) {
			directContexts.push(contextOptions.contextText);
		}

		if (additionalContext.taskContext) {
			directContexts.push(`### Task Context\n\n${additionalContext.taskContext}`);
		}

		if (additionalContext.projectContext) {
			directContexts.push(`### Project Context\n\n${additionalContext.projectContext}`);
		}

		if (directContexts.length > 0) {
			contextSources.direct = directContexts.join('\n\n');
		}

		// Combine all context sources
		const combinedContext = await contextManager.combineContextSources(contextSources, {
			maxTotalSize: 50000, // 50KB limit for context
			formatForPrompt: true
		});

		// Enhance the prompt with context
		if (combinedContext.success && combinedContext.content.trim().length > 0) {
			const enhancedPrompt = `${originalPrompt}

## Additional Context

${combinedContext.content}

---
Please consider the above context when responding to the main prompt.`;

			return enhancedPrompt;
		}

		return originalPrompt;

	} catch (error) {
		console.warn(`Warning: Failed to enhance prompt with context: ${error.message}`);
		return originalPrompt;
	}
}

/**
 * Create context summary for logging/debugging
 * @param {Object} options - Command options containing context settings
 * @returns {string} Context summary
 */
export function createContextSummary(options = {}) {
	const contextOptions = parseContextOptions(options);
	const parts = [];

	if (contextOptions.contextFiles.length > 0) {
		parts.push(`Files: ${contextOptions.contextFiles.join(', ')}`);
	}

	if (contextOptions.contextText) {
		const preview = contextOptions.contextText.length > 50
			? contextOptions.contextText.substring(0, 50) + '...'
			: contextOptions.contextText;
		parts.push(`Text: "${preview}"`);
	}

	if (contextOptions.includeRules) {
		parts.push('Cursor Rules: enabled');
	}

	return parts.length > 0 ? `Context: ${parts.join(', ')}` : 'No additional context';
}

/**
 * Validate context options before processing
 * @param {Object} options - Command options to validate
 * @returns {Object} Validation result with success flag and any errors
 */
export function validateContextOptions(options = {}) {
	const contextOptions = parseContextOptions(options);
	const errors = [];

	// Validate file paths exist (basic check)
	for (const filePath of contextOptions.contextFiles) {
		if (!filePath || typeof filePath !== 'string') {
			errors.push(`Invalid file path: ${filePath}`);
		}
	}

	// Validate context text length
	if (contextOptions.contextText && contextOptions.contextText.length > 10000) {
		errors.push('Context text is too long (max 10,000 characters)');
	}

	return {
		success: errors.length === 0,
		errors,
		contextOptions
	};
}