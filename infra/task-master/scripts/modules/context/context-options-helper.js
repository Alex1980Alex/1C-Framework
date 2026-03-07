/**
 * context-options-helper.js
 * Helper functions for adding context options to commander.js commands
 */

/**
 * Add standard context options to a command
 * @param {Command} command - Commander.js command to add options to
 * @returns {Command} The command with context options added
 */
export function addContextOptions(command) {
	return command
		.option(
			'--context-file <files>',
			'Comma-separated file paths to include as context for AI operations'
		)
		.option(
			'--context <text>',
			'Additional custom context text to include in AI prompts'
		)
		.option(
			'--context-rules',
			'Include .cursor/rules/*.md files as context for AI operations'
		);
}

/**
 * Parse context options from command line arguments
 * @param {Object} options - Command options object
 * @returns {Object} Parsed context options
 */
export function parseContextOptions(options) {
	const contextOptions = {
		contextFiles: [],
		contextText: null,
		includeRules: false
	};

	// Parse context files
	if (options.contextFile) {
		contextOptions.contextFiles = options.contextFile
			.split(',')
			.map(file => file.trim())
			.filter(file => file.length > 0);
	}

	// Parse custom context text
	if (options.context) {
		contextOptions.contextText = options.context.trim();
	}

	// Parse context rules flag
	if (options.contextRules) {
		contextOptions.includeRules = true;
	}

	return contextOptions;
}

/**
 * Generate help text for context options
 * @returns {string} Help text
 */
export function getContextOptionsHelp() {
	return `
Context Options:
  --context-file <files>   Include file contents as context (comma-separated)
  --context <text>         Include custom text as context
  --context-rules          Include .cursor/rules/*.md files as context

Examples:
  --context-file "README.md,docs/api.md"
  --context "This is a web application project"
  --context-rules
  --context-file "src/main.js" --context "Focus on error handling" --context-rules`;
}