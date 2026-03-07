/**
 * task-github-formatter.js
 * Advanced Task-to-GitHub content formatter with template support
 * Part of Task #101.2 - Create Task-to-GitHub Content Formatter
 */

/**
 * Advanced formatter for converting Task Master tasks to GitHub-compatible content
 * Provides customizable templates, advanced formatting options, and content optimization
 */
export class TaskGitHubFormatter {
	constructor(options = {}) {
		this.options = {
			defaultTemplate: 'standard',
			includeMetadata: true,
			markdownStyle: 'github',
			maxBodyLength: 65536, // GitHub issue body limit
			truncateStrategy: 'smart',
			enableTables: true,
			enableEmoji: false,
			...options
		};

		// Template configurations
		this.templates = {
			standard: this.getStandardTemplate(),
			detailed: this.getDetailedTemplate(),
			minimal: this.getMinimalTemplate(),
			bug: this.getBugTemplate(),
			feature: this.getFeatureTemplate(),
			epic: this.getEpicTemplate()
		};
	}

	/**
	 * Format a task as GitHub issue with advanced options
	 * @param {Object} task - Task Master task object
	 * @param {Object} options - Formatting options
	 * @returns {Object} Formatted issue data
	 */
	formatTask(task, options = {}) {
		const formatOptions = { ...this.options, ...options };
		const template = this.getTemplate(formatOptions.template || formatOptions.defaultTemplate);

		// Generate title
		const title = this.generateTitle(task, formatOptions);

		// Generate body using template
		const body = this.generateBody(task, template, formatOptions);

		// Apply length limits and optimization
		const optimizedBody = this.optimizeContent(body, formatOptions);

		// Generate labels
		const labels = this.generateLabels(task, formatOptions);

		return {
			title,
			body: optimizedBody,
			labels,
			assignees: formatOptions.assignees || [],
			milestone: formatOptions.milestone || null,
			metadata: {
				taskId: task.id,
				template: formatOptions.template || formatOptions.defaultTemplate,
				generatedAt: new Date().toISOString(),
				formatter: 'TaskGitHubFormatter',
				version: '1.0.0'
			}
		};
	}

	/**
	 * Generate issue title with customizable patterns
	 * @param {Object} task - Task object
	 * @param {Object} options - Formatting options
	 * @returns {string} Formatted title
	 */
	generateTitle(task, options) {
		if (options.title) {
			return options.title;
		}

		const patterns = {
			simple: task.title,
			prefixed: `[Task ${task.id}] ${task.title}`,
			typed: this.getTitleWithType(task),
			priority: this.getTitleWithPriority(task),
			status: `[${(task.status || 'pending').toUpperCase()}] ${task.title}`
		};

		const pattern = options.titlePattern || 'prefixed';
		return patterns[pattern] || patterns.prefixed;
	}

	/**
	 * Generate issue body using specified template
	 * @param {Object} task - Task object
	 * @param {Object} template - Template configuration
	 * @param {Object} options - Formatting options
	 * @returns {string} Formatted body
	 */
	generateBody(task, template, options) {
		const sections = [];

		// Process each template section
		for (const section of template.sections) {
			const content = this.generateSection(task, section, options);
			if (content) {
				sections.push(content);
			}
		}

		// Add footer
		sections.push(this.generateFooter(task, options));

		return sections.join('\n\n');
	}

	/**
	 * Generate individual section content
	 * @param {Object} task - Task object
	 * @param {Object} section - Section configuration
	 * @param {Object} options - Formatting options
	 * @returns {string|null} Section content
	 */
	generateSection(task, section, options) {
		switch (section.type) {
			case 'header':
				return this.generateHeader(task, section, options);
			case 'metadata':
				return this.generateMetadataSection(task, section, options);
			case 'description':
				return this.generateDescriptionSection(task, section, options);
			case 'details':
				return this.generateDetailsSection(task, section, options);
			case 'subtasks':
				return this.generateSubtasksSection(task, section, options);
			case 'dependencies':
				return this.generateDependenciesSection(task, section, options);
			case 'testing':
				return this.generateTestingSection(task, section, options);
			case 'acceptance':
				return this.generateAcceptanceSection(task, section, options);
			case 'custom':
				return this.generateCustomSection(task, section, options);
			default:
				return null;
		}
	}

	/**
	 * Generate header section
	 */
	generateHeader(task, section, options) {
		if (!section.enabled) return null;

		const emoji = options.enableEmoji ? this.getTaskEmoji(task) : '';
		const headerText = section.showTitle !== false ? task.title : section.text || 'Task Details';

		return `# ${emoji}${headerText}`;
	}

	/**
	 * Generate metadata section
	 */
	generateMetadataSection(task, section, options) {
		if (!section.enabled || !options.includeMetadata) return null;

		const metadata = [];

		if (section.fields.includes('id')) {
			metadata.push(`**Task Master ID**: ${task.id}`);
		}

		if (section.fields.includes('priority') && task.priority) {
			metadata.push(`**Priority**: ${task.priority}`);
		}

		if (section.fields.includes('status') && task.status) {
			metadata.push(`**Status**: ${task.status}`);
		}

		if (section.fields.includes('complexity') && task.complexity) {
			metadata.push(`**Complexity**: ${task.complexity}`);
		}

		if (section.fields.includes('estimatedHours') && task.estimatedHours) {
			metadata.push(`**Estimated Hours**: ${task.estimatedHours}`);
		}

		return metadata.length > 0 ? metadata.join('\n') : null;
	}

	/**
	 * Generate description section
	 */
	generateDescriptionSection(task, section, options) {
		if (!section.enabled || !task.description) return null;

		const title = section.title || 'Description';
		const content = this.formatText(task.description, options);

		return `## ${title}\n${content}`;
	}

	/**
	 * Generate implementation details section
	 */
	generateDetailsSection(task, section, options) {
		if (!section.enabled || !task.details) return null;

		const title = section.title || 'Implementation Details';
		const content = this.formatText(task.details, options);

		return `## ${title}\n${content}`;
	}

	/**
	 * Generate subtasks section with checkbox list
	 */
	generateSubtasksSection(task, section, options) {
		if (!section.enabled || !task.subtasks || task.subtasks.length === 0) return null;

		const title = section.title || 'Subtasks';
		const items = task.subtasks.map(subtask => {
			const checked = subtask.status === 'done' ? 'x' : ' ';
			const priorityIndicator = options.showSubtaskPriority && subtask.priority
				? ` [${subtask.priority}]`
				: '';
			return `- [${checked}] ${subtask.title}${priorityIndicator}`;
		});

		return `## ${title}\n${items.join('\n')}`;
	}

	/**
	 * Generate dependencies section
	 */
	generateDependenciesSection(task, section, options) {
		if (!section.enabled || !task.dependencies || task.dependencies.length === 0) return null;

		const title = section.title || 'Dependencies';
		const items = task.dependencies.map(depId => `- Task #${depId}`);

		return `## ${title}\n${items.join('\n')}`;
	}

	/**
	 * Generate testing strategy section
	 */
	generateTestingSection(task, section, options) {
		if (!section.enabled || !task.testStrategy) return null;

		const title = section.title || 'Testing Strategy';
		const content = this.formatText(task.testStrategy, options);

		return `## ${title}\n${content}`;
	}

	/**
	 * Generate acceptance criteria section
	 */
	generateAcceptanceSection(task, section, options) {
		if (!section.enabled || !task.acceptanceCriteria) return null;

		const title = section.title || 'Acceptance Criteria';

		if (Array.isArray(task.acceptanceCriteria)) {
			const items = task.acceptanceCriteria.map(criteria => `- [ ] ${criteria}`);
			return `## ${title}\n${items.join('\n')}`;
		} else {
			const content = this.formatText(task.acceptanceCriteria, options);
			return `## ${title}\n${content}`;
		}
	}

	/**
	 * Generate custom section based on configuration
	 */
	generateCustomSection(task, section, options) {
		if (!section.enabled || !section.content) return null;

		// Template variable replacement
		let content = section.content;
		content = content.replace(/\{\{task\.(\w+)\}\}/g, (match, field) => {
			return task[field] || '';
		});
		content = content.replace(/\{\{options\.(\w+)\}\}/g, (match, field) => {
			return options[field] || '';
		});

		return content;
	}

	/**
	 * Generate footer with Task Master reference
	 */
	generateFooter(task, options) {
		const projectName = options.projectName ? ` in project "${options.projectName}"` : '';
		const timestamp = new Date().toLocaleDateString();

		return `---\n*Exported from Task Master on ${timestamp}*\n**Task Master Reference**: Task #${task.id}${projectName}`;
	}

	/**
	 * Generate smart labels based on task properties
	 */
	generateLabels(task, options) {
		const labels = new Set(options.labels || []);

		// Auto-generate labels based on task properties
		if (options.autoLabels !== false) {
			// Priority labels
			if (task.priority) {
				labels.add(`priority:${task.priority}`);
			}

			// Status labels
			if (task.status && task.status !== 'pending') {
				labels.add(`status:${task.status}`);
			}

			// Complexity labels
			if (task.complexity) {
				labels.add(`complexity:${task.complexity}`);
			}

			// Type detection
			const taskType = this.detectTaskType(task);
			if (taskType) {
				labels.add(taskType);
			}

			// Size labels
			const sizeLabel = this.detectTaskSize(task);
			if (sizeLabel) {
				labels.add(sizeLabel);
			}
		}

		return Array.from(labels);
	}

	/**
	 * Detect task type based on content analysis
	 */
	detectTaskType(task) {
		const text = `${task.title} ${task.description || ''}`.toLowerCase();

		if (text.includes('bug') || text.includes('fix') || text.includes('error')) {
			return 'bug';
		}
		if (text.includes('feature') || text.includes('implement') || text.includes('add')) {
			return 'enhancement';
		}
		if (text.includes('document') || text.includes('readme') || text.includes('guide')) {
			return 'documentation';
		}
		if (text.includes('test') || text.includes('spec') || text.includes('coverage')) {
			return 'testing';
		}
		if (text.includes('refactor') || text.includes('cleanup') || text.includes('optimize')) {
			return 'refactoring';
		}

		return null;
	}

	/**
	 * Detect task size based on complexity and subtask count
	 */
	detectTaskSize(task) {
		const subtaskCount = task.subtasks ? task.subtasks.length : 0;
		const hasDetails = !!(task.details && task.details.length > 100);
		const estimatedHours = task.estimatedHours || 0;

		if (estimatedHours > 40 || subtaskCount > 10 || (subtaskCount > 5 && hasDetails)) {
			return 'size:large';
		}
		if (estimatedHours > 8 || subtaskCount > 3 || hasDetails) {
			return 'size:medium';
		}
		if (estimatedHours <= 2 || subtaskCount === 0) {
			return 'size:small';
		}

		return null;
	}

	/**
	 * Get emoji for task based on type and priority
	 */
	getTaskEmoji(task) {
		const type = this.detectTaskType(task);
		const emojis = {
			bug: '🐛 ',
			enhancement: '✨ ',
			documentation: '📚 ',
			testing: '🧪 ',
			refactoring: '♻️ '
		};

		if (task.priority === 'critical') {
			return '🚨 ';
		}
		if (task.priority === 'high') {
			return '⚡ ';
		}

		return emojis[type] || '📋 ';
	}

	/**
	 * Generate title with type indicator
	 */
	getTitleWithType(task) {
		const type = this.detectTaskType(task);
		if (type) {
			return `[${type.toUpperCase()}] ${task.title}`;
		}
		return `[Task ${task.id}] ${task.title}`;
	}

	/**
	 * Generate title with priority indicator
	 */
	getTitleWithPriority(task) {
		if (task.priority) {
			return `[${task.priority.toUpperCase()}] ${task.title}`;
		}
		return task.title;
	}

	/**
	 * Format text content with markdown optimization
	 */
	formatText(text, options) {
		if (!text) return '';

		let formatted = text;

		// Normalize line endings
		formatted = formatted.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

		// Improve code block formatting
		formatted = formatted.replace(/```(\w*)\n([\s\S]*?)\n```/g, (match, lang, code) => {
			return `\`\`\`${lang}\n${code.trim()}\n\`\`\``;
		});

		// Fix inline code formatting
		formatted = formatted.replace(/`([^`]+)`/g, '`$1`');

		// Ensure proper list formatting
		formatted = formatted.replace(/^(\s*)[-*+] /gm, '$1- ');

		// Fix table formatting if enabled
		if (options.enableTables) {
			formatted = this.optimizeTableFormatting(formatted);
		}

		return formatted;
	}

	/**
	 * Optimize table formatting for GitHub
	 */
	optimizeTableFormatting(text) {
		// Basic table formatting fixes
		return text.replace(/\|(\s*[^|\n]+\s*)\|/g, (match, content) => {
			return `| ${content.trim()} |`;
		});
	}

	/**
	 * Optimize content length and apply truncation strategies
	 */
	optimizeContent(content, options) {
		if (content.length <= options.maxBodyLength) {
			return content;
		}

		switch (options.truncateStrategy) {
			case 'smart':
				return this.smartTruncate(content, options.maxBodyLength);
			case 'simple':
				return content.substring(0, options.maxBodyLength - 100) + '\n\n*[Content truncated due to length limits]*';
			case 'summary':
				return this.generateSummary(content, options.maxBodyLength);
			default:
				return content;
		}
	}

	/**
	 * Smart truncation that preserves structure
	 */
	smartTruncate(content, maxLength) {
		const lines = content.split('\n');
		const truncatedLines = [];
		let currentLength = 0;
		const footerText = '\n\n*[Content truncated - see full details in Task Master]*';
		const targetLength = maxLength - footerText.length;

		for (const line of lines) {
			if (currentLength + line.length + 1 > targetLength) {
				break;
			}
			truncatedLines.push(line);
			currentLength += line.length + 1;
		}

		return truncatedLines.join('\n') + footerText;
	}

	/**
	 * Generate content summary for very long content
	 */
	generateSummary(content, maxLength) {
		// Extract key sections
		const sections = content.split(/^##\s+/m);
		const summary = ['# Summary'];

		for (const section of sections.slice(1)) {
			const [title, ...contentLines] = section.split('\n');
			const sectionContent = contentLines.join('\n').trim();

			if (sectionContent) {
				const preview = sectionContent.length > 200
					? sectionContent.substring(0, 200) + '...'
					: sectionContent;
				summary.push(`## ${title}\n${preview}\n`);
			}
		}

		summary.push('*[Full details available in Task Master]*');
		return summary.join('\n\n');
	}

	/**
	 * Get template configuration by name
	 */
	getTemplate(name) {
		return this.templates[name] || this.templates.standard;
	}

	/**
	 * Standard template configuration
	 */
	getStandardTemplate() {
		return {
			name: 'standard',
			description: 'Standard task format with all sections',
			sections: [
				{
					type: 'header',
					enabled: true,
					showTitle: true
				},
				{
					type: 'metadata',
					enabled: true,
					fields: ['id', 'priority', 'status']
				},
				{
					type: 'description',
					enabled: true,
					title: 'Description'
				},
				{
					type: 'details',
					enabled: true,
					title: 'Implementation Details'
				},
				{
					type: 'subtasks',
					enabled: true,
					title: 'Subtasks'
				},
				{
					type: 'dependencies',
					enabled: true,
					title: 'Dependencies'
				},
				{
					type: 'testing',
					enabled: true,
					title: 'Testing Strategy'
				}
			]
		};
	}

	/**
	 * Detailed template with comprehensive information
	 */
	getDetailedTemplate() {
		return {
			name: 'detailed',
			description: 'Comprehensive format with all available fields',
			sections: [
				{
					type: 'header',
					enabled: true,
					showTitle: true
				},
				{
					type: 'metadata',
					enabled: true,
					fields: ['id', 'priority', 'status', 'complexity', 'estimatedHours']
				},
				{
					type: 'description',
					enabled: true,
					title: 'Description'
				},
				{
					type: 'details',
					enabled: true,
					title: 'Implementation Details'
				},
				{
					type: 'acceptance',
					enabled: true,
					title: 'Acceptance Criteria'
				},
				{
					type: 'subtasks',
					enabled: true,
					title: 'Subtasks'
				},
				{
					type: 'dependencies',
					enabled: true,
					title: 'Dependencies'
				},
				{
					type: 'testing',
					enabled: true,
					title: 'Testing Strategy'
				}
			]
		};
	}

	/**
	 * Minimal template for simple tasks
	 */
	getMinimalTemplate() {
		return {
			name: 'minimal',
			description: 'Compact format with essential information only',
			sections: [
				{
					type: 'header',
					enabled: true,
					showTitle: true
				},
				{
					type: 'metadata',
					enabled: true,
					fields: ['id', 'priority']
				},
				{
					type: 'description',
					enabled: true,
					title: 'Description'
				},
				{
					type: 'subtasks',
					enabled: true,
					title: 'Tasks'
				}
			]
		};
	}

	/**
	 * Bug report template
	 */
	getBugTemplate() {
		return {
			name: 'bug',
			description: 'Bug report format with reproduction steps',
			sections: [
				{
					type: 'header',
					enabled: true,
					showTitle: true
				},
				{
					type: 'metadata',
					enabled: true,
					fields: ['id', 'priority', 'status']
				},
				{
					type: 'description',
					enabled: true,
					title: 'Bug Description'
				},
				{
					type: 'custom',
					enabled: true,
					content: '## Reproduction Steps\n{{task.reproductionSteps}}'
				},
				{
					type: 'custom',
					enabled: true,
					content: '## Expected Behavior\n{{task.expectedBehavior}}'
				},
				{
					type: 'custom',
					enabled: true,
					content: '## Actual Behavior\n{{task.actualBehavior}}'
				},
				{
					type: 'details',
					enabled: true,
					title: 'Technical Details'
				},
				{
					type: 'testing',
					enabled: true,
					title: 'Verification Steps'
				}
			]
		};
	}

	/**
	 * Feature request template
	 */
	getFeatureTemplate() {
		return {
			name: 'feature',
			description: 'Feature request format with user stories',
			sections: [
				{
					type: 'header',
					enabled: true,
					showTitle: true
				},
				{
					type: 'metadata',
					enabled: true,
					fields: ['id', 'priority', 'status', 'estimatedHours']
				},
				{
					type: 'custom',
					enabled: true,
					content: '## User Story\n{{task.userStory}}'
				},
				{
					type: 'description',
					enabled: true,
					title: 'Feature Description'
				},
				{
					type: 'acceptance',
					enabled: true,
					title: 'Acceptance Criteria'
				},
				{
					type: 'details',
					enabled: true,
					title: 'Implementation Plan'
				},
				{
					type: 'subtasks',
					enabled: true,
					title: 'Development Tasks'
				},
				{
					type: 'testing',
					enabled: true,
					title: 'Testing Plan'
				}
			]
		};
	}

	/**
	 * Epic template for large initiatives
	 */
	getEpicTemplate() {
		return {
			name: 'epic',
			description: 'Epic format for large initiatives with multiple components',
			sections: [
				{
					type: 'header',
					enabled: true,
					showTitle: true
				},
				{
					type: 'metadata',
					enabled: true,
					fields: ['id', 'priority', 'status', 'complexity', 'estimatedHours']
				},
				{
					type: 'custom',
					enabled: true,
					content: '## Epic Overview\n{{task.epicOverview}}'
				},
				{
					type: 'custom',
					enabled: true,
					content: '## Business Value\n{{task.businessValue}}'
				},
				{
					type: 'description',
					enabled: true,
					title: 'Detailed Description'
				},
				{
					type: 'custom',
					enabled: true,
					content: '## Success Metrics\n{{task.successMetrics}}'
				},
				{
					type: 'subtasks',
					enabled: true,
					title: 'Epic Components'
				},
				{
					type: 'dependencies',
					enabled: true,
					title: 'Dependencies'
				},
				{
					type: 'custom',
					enabled: true,
					content: '## Rollout Plan\n{{task.rolloutPlan}}'
				}
			]
		};
	}

	/**
	 * Create custom template
	 * @param {string} name - Template name
	 * @param {Object} config - Template configuration
	 */
	addCustomTemplate(name, config) {
		this.templates[name] = {
			name,
			description: config.description || 'Custom template',
			sections: config.sections || []
		};
	}

	/**
	 * Preview formatting without creating issue
	 * @param {Object} task - Task object
	 * @param {Object} options - Formatting options
	 * @returns {Object} Preview data
	 */
	preview(task, options = {}) {
		const formatted = this.formatTask(task, options);

		return {
			...formatted,
			stats: {
				titleLength: formatted.title.length,
				bodyLength: formatted.body.length,
				labelCount: formatted.labels.length,
				isWithinLimits: formatted.body.length <= this.options.maxBodyLength,
				template: formatted.metadata.template
			}
		};
	}
}

export default TaskGitHubFormatter;