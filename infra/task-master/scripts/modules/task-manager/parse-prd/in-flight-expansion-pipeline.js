/**
 * in-flight-expansion-pipeline.js
 * In-flight task expansion pipeline for immediate expansion after PRD parsing
 * Part of Task #99.3 - Implement In-Flight Task Expansion Pipeline
 */

import chalk from 'chalk';
import { expandTask, expandTaskWithPRDContext } from '../expand-task.js';
import { findTaskById } from '../../utils.js';

/**
 * In-flight expansion pipeline configuration
 */
export class ExpansionPipelineConfig {
	constructor(options = {}) {
		this.enabled = options.expandTasks || false;
		this.preserveDetail = options.preserveDetail || false;
		this.contextWindowSize = options.contextWindowSize || 1000;
		this.maxConcurrentExpansions = options.maxConcurrentExpansions || 3;
		this.expansionTimeout = options.expansionTimeout || 60000; // 60 seconds
		this.minComplexityThreshold = options.minComplexityThreshold || 2;
		this.maxSubtasksPerExpansion = options.maxSubtasksPerExpansion || 8;
		this.research = options.research || false;
		this.force = options.force || false;
	}

	/**
	 * Check if task should be expanded based on configuration
	 * @param {Object} task - Task to check
	 * @returns {boolean} True if task should be expanded
	 */
	shouldExpandTask(task) {
		if (!this.enabled) return false;

		// Check if task is marked as auto-expandable
		if (task.expansionMetadata?.autoExpandable) return true;

		// Check complexity threshold
		if (task.prdContext?.complexity >= this.minComplexityThreshold) return true;

		// Check if preserve detail mode is enabled (expand all tasks)
		if (this.preserveDetail) return true;

		return false;
	}
}

/**
 * Task expansion queue manager
 */
export class ExpansionQueue {
	constructor(config) {
		this.config = config;
		this.queue = [];
		this.inProgress = new Set();
		this.completed = new Map();
		this.failed = new Map();
		this.results = [];
	}

	/**
	 * Add task to expansion queue
	 * @param {Object} task - Task to expand
	 * @param {Object} prdContext - PRD context for expansion
	 */
	enqueue(task, prdContext) {
		this.queue.push({
			task,
			prdContext,
			priority: this.calculateExpansionPriority(task, prdContext),
			queuedAt: Date.now()
		});

		// Sort queue by priority (higher first)
		this.queue.sort((a, b) => b.priority - a.priority);
	}

	/**
	 * Calculate expansion priority for a task
	 * @param {Object} task - Task object
	 * @param {Object} prdContext - PRD context
	 * @returns {number} Priority score
	 */
	calculateExpansionPriority(task, prdContext) {
		let priority = 0;

		// Priority based on task priority
		const priorityScores = { 'critical': 4, 'high': 3, 'medium': 2, 'low': 1 };
		priority += priorityScores[task.priority] || 2;

		// Priority based on PRD context complexity
		if (prdContext?.complexity) {
			priority += prdContext.complexity;
		}

		// Priority based on PRD context type
		if (prdContext?.type === 'api' || prdContext?.type === 'feature') {
			priority += 2;
		}

		// Priority based on dependencies (tasks with no dependencies go first)
		if (!task.dependencies || task.dependencies.length === 0) {
			priority += 1;
		}

		return priority;
	}

	/**
	 * Get next task from queue for expansion
	 * @returns {Object|null} Next task to expand or null if queue is empty
	 */
	dequeue() {
		return this.queue.shift() || null;
	}

	/**
	 * Check if queue has remaining tasks
	 * @returns {boolean} True if queue has tasks
	 */
	hasNext() {
		return this.queue.length > 0;
	}

	/**
	 * Get current queue status
	 * @returns {Object} Queue status
	 */
	getStatus() {
		return {
			queued: this.queue.length,
			inProgress: this.inProgress.size,
			completed: this.completed.size,
			failed: this.failed.size,
			total: this.queue.length + this.inProgress.size + this.completed.size + this.failed.size
		};
	}
}

/**
 * Task expansion worker for processing individual expansions
 */
export class ExpansionWorker {
	constructor(config, projectRoot, tasksPath, targetTag, logger) {
		this.config = config;
		this.projectRoot = projectRoot;
		this.tasksPath = tasksPath;
		this.targetTag = targetTag;
		this.logger = logger;
	}

	/**
	 * Expand a single task with PRD context
	 * @param {Object} queueItem - Queue item containing task and context
	 * @returns {Promise<Object>} Expansion result
	 */
	async expandSingleTask(queueItem) {
		const { task, prdContext } = queueItem;
		const startTime = Date.now();

		try {
			this.logger.report(
				`Expanding task ${task.id}: ${task.title} (complexity: ${prdContext?.complexity || 'unknown'})`,
				'info'
			);

			// Prepare expansion options with PRD context
			const expansionOptions = {
				session: null, // Will be set by expand-task function
				mcpLog: this.logger,
				projectRoot: this.projectRoot,
				tag: this.targetTag,
				force: this.config.force,
				research: this.config.research,
				commandName: 'in-flight-expand',
				outputType: 'pipeline',
				// Enhanced options with PRD context
				prdContext: prdContext,
				contextWindow: prdContext?.contextWindow || '',
				maxSubtasks: this.config.maxSubtasksPerExpansion,
				preserveDetail: this.config.preserveDetail
			};

			// Create enhanced prompt for expansion
			const enhancedPrompt = this.buildEnhancedExpansionPrompt(task, prdContext);

			// Call PRD-enhanced expand-task function with enhanced context
			const result = await expandTaskWithPRDContext(
				task.id.toString(),
				this.tasksPath,
				enhancedPrompt,
				expansionOptions,
				'json'
			);

			const duration = Date.now() - startTime;

			if (result && result.success) {
				this.logger.report(
					`Successfully expanded task ${task.id} into ${result.subtasksAdded || 0} subtasks (${duration}ms)`,
					'info'
				);

				return {
					success: true,
					taskId: task.id,
					subtasksAdded: result.subtasksAdded || 0,
					duration,
					details: result.details || 'Expansion completed successfully'
				};
			} else {
				throw new Error(result?.message || 'Expansion failed without details');
			}

		} catch (error) {
			const duration = Date.now() - startTime;

			this.logger.report(
				`Failed to expand task ${task.id}: ${error.message} (${duration}ms)`,
				'error'
			);

			return {
				success: false,
				taskId: task.id,
				duration,
				error: error.message
			};
		}
	}

	/**
	 * Build enhanced expansion prompt with PRD context
	 * @param {Object} task - Task to expand
	 * @param {Object} prdContext - PRD context
	 * @returns {string} Enhanced expansion prompt
	 */
	buildEnhancedExpansionPrompt(task, prdContext) {
		if (!prdContext) {
			return `Break down this task into detailed subtasks: ${task.title}`;
		}

		const prompt = `## Task Expansion with PRD Context

**Task**: ${task.title}
**Description**: ${task.description}

### PRD Context Information
- **Source Section**: ${prdContext.sourceSection}
- **Section Type**: ${prdContext.type}
- **Complexity**: ${prdContext.complexity}/5
- **Keywords**: ${prdContext.keywords?.join(', ') || 'N/A'}

### Related PRD Content
${prdContext.contextWindow || prdContext.originalText}

### Expansion Guidelines
1. Create ${this.config.maxSubtasksPerExpansion || 6} or fewer meaningful subtasks
2. Each subtask should be specific to the PRD requirements
3. Maintain direct traceability to the original PRD specifications
4. Include implementation details from the PRD context
5. Consider dependencies and logical ordering

### Suggested Subtask Areas
${prdContext.suggestedSubtasks?.map(subtask => `- ${subtask}`).join('\n') || '- Analysis and planning\n- Implementation\n- Testing and validation'}

Please generate detailed subtasks that implement the specific requirements from the PRD context while maintaining the original intent and specifications.`;

		return prompt;
	}
}

/**
 * Main in-flight expansion pipeline
 */
export class InFlightExpansionPipeline {
	constructor(config, projectRoot, tasksPath, targetTag, logger) {
		this.config = new ExpansionPipelineConfig(config);
		this.projectRoot = projectRoot;
		this.tasksPath = tasksPath;
		this.targetTag = targetTag;
		this.logger = logger;
		this.queue = new ExpansionQueue(this.config);
		this.worker = new ExpansionWorker(
			this.config,
			projectRoot,
			tasksPath,
			targetTag,
			logger
		);
	}

	/**
	 * Process tasks and add eligible ones to expansion queue
	 * @param {Array} tasks - Tasks to process
	 * @param {Object} prdAnalysis - PRD analysis results
	 * @returns {Object} Processing summary
	 */
	processTasksForExpansion(tasks, prdAnalysis) {
		let eligibleCount = 0;
		let queuedCount = 0;

		tasks.forEach(task => {
			if (this.config.shouldExpandTask(task)) {
				eligibleCount++;

				// Get PRD context for expansion
				const prdContext = task.prdContext || this.findPRDContextForTask(task, prdAnalysis);

				if (prdContext) {
					this.queue.enqueue(task, prdContext);
					queuedCount++;
				} else {
					this.logger.report(
						`Task ${task.id} eligible for expansion but no PRD context found`,
						'warn'
					);
				}
			}
		});

		return {
			total: tasks.length,
			eligible: eligibleCount,
			queued: queuedCount,
			skipped: eligibleCount - queuedCount
		};
	}

	/**
	 * Find PRD context for a task
	 * @param {Object} task - Task object
	 * @param {Object} prdAnalysis - PRD analysis results
	 * @returns {Object|null} PRD context or null
	 */
	findPRDContextForTask(task, prdAnalysis) {
		if (task.prdContext) return task.prdContext;

		// Try to match task to PRD sections
		const taskTitle = task.title?.toLowerCase() || '';
		const taskDescription = task.description?.toLowerCase() || '';

		for (const [sectionTitle, section] of prdAnalysis.sectionMapping.sections) {
			const sectionTitleLower = sectionTitle.toLowerCase();

			if (sectionTitleLower.includes(taskTitle) ||
				taskTitle.includes(sectionTitleLower) ||
				section.content.toLowerCase().includes(taskDescription)) {

				return {
					sourceSection: `${sectionTitle} (Lines ${section.startLine}-${section.endLine})`,
					originalText: section.content,
					contextWindow: prdAnalysis.sectionMapping.createContextWindow(sectionTitle),
					complexity: section.complexity,
					type: section.type,
					keywords: prdAnalysis.sectionMapping.extractKeywords(section.content),
					suggestedSubtasks: this.getSuggestedSubtasksForType(section.type)
				};
			}
		}

		return null;
	}

	/**
	 * Get suggested subtasks for section type
	 * @param {string} type - Section type
	 * @returns {Array<string>} Suggested subtasks
	 */
	getSuggestedSubtasksForType(type) {
		const suggestions = {
			feature: ['Design specifications', 'Core implementation', 'Input validation', 'Unit tests', 'Integration testing'],
			api: ['Design endpoints', 'Request/response handling', 'Authentication', 'Documentation', 'Testing'],
			ui: ['UI mockups', 'Component implementation', 'Responsive design', 'User interactions', 'Accessibility'],
			technical: ['Research and planning', 'Architecture implementation', 'Performance optimization', 'Security', 'Documentation']
		};

		return suggestions[type] || ['Analysis', 'Implementation', 'Testing'];
	}

	/**
	 * Execute the expansion pipeline
	 * @returns {Promise<Object>} Pipeline execution results
	 */
	async execute() {
		if (!this.config.enabled) {
			return {
				success: true,
				skipped: true,
				message: 'In-flight expansion disabled'
			};
		}

		const startTime = Date.now();
		const results = [];

		this.logger.report(
			`Starting in-flight expansion pipeline: ${this.queue.getStatus().queued} tasks queued`,
			'info'
		);

		// Process queue with controlled concurrency
		const activePromises = new Set();

		while (this.queue.hasNext() || activePromises.size > 0) {
			// Start new expansions up to concurrency limit
			while (this.queue.hasNext() && activePromises.size < this.config.maxConcurrentExpansions) {
				const queueItem = this.queue.dequeue();
				if (queueItem) {
					const promise = this.worker.expandSingleTask(queueItem)
						.then(result => {
							results.push(result);
							activePromises.delete(promise);
							return result;
						})
						.catch(error => {
							const errorResult = {
								success: false,
								taskId: queueItem.task.id,
								error: error.message
							};
							results.push(errorResult);
							activePromises.delete(promise);
							return errorResult;
						});

					activePromises.add(promise);
				}
			}

			// Wait for at least one promise to complete if queue is empty
			if (activePromises.size > 0) {
				await Promise.race(activePromises);
			}
		}

		const duration = Date.now() - startTime;
		const successCount = results.filter(r => r.success).length;
		const failureCount = results.filter(r => !r.success).length;
		const totalSubtasks = results.reduce((sum, r) => sum + (r.subtasksAdded || 0), 0);

		this.logger.report(
			`In-flight expansion pipeline completed: ${successCount} successful, ${failureCount} failed, ` +
			`${totalSubtasks} subtasks created (${duration}ms)`,
			'info'
		);

		return {
			success: true,
			duration,
			processed: results.length,
			successful: successCount,
			failed: failureCount,
			totalSubtasksCreated: totalSubtasks,
			results
		};
	}

	/**
	 * Get pipeline statistics
	 * @returns {Object} Pipeline statistics
	 */
	getStatistics() {
		return {
			config: {
				enabled: this.config.enabled,
				preserveDetail: this.config.preserveDetail,
				maxConcurrent: this.config.maxConcurrentExpansions,
				minComplexity: this.config.minComplexityThreshold
			},
			queue: this.queue.getStatus()
		};
	}
}

/**
 * Factory function to create and execute in-flight expansion
 * @param {Array} tasks - Tasks to process for expansion
 * @param {Object} prdAnalysis - PRD analysis results
 * @param {Object} config - Expansion configuration
 * @param {string} projectRoot - Project root path
 * @param {string} tasksPath - Tasks file path
 * @param {string} targetTag - Target tag
 * @param {Object} logger - Logger instance
 * @returns {Promise<Object>} Expansion results
 */
export async function executeInFlightExpansion(
	tasks,
	prdAnalysis,
	config,
	projectRoot,
	tasksPath,
	targetTag,
	logger
) {
	const pipeline = new InFlightExpansionPipeline(
		config,
		projectRoot,
		tasksPath,
		targetTag,
		logger
	);

	// Process tasks to identify expansion candidates
	const processingResult = pipeline.processTasksForExpansion(tasks, prdAnalysis);

	logger.report(
		`Expansion processing: ${processingResult.eligible}/${processingResult.total} eligible, ` +
		`${processingResult.queued} queued`,
		'info'
	);

	// Execute expansion pipeline
	const executionResult = await pipeline.execute();

	return {
		...executionResult,
		processing: processingResult,
		statistics: pipeline.getStatistics()
	};
}

/**
 * Helper function to check if expansion should be enabled
 * @param {Object} options - Parse options
 * @param {Object} prdAnalysis - PRD analysis results
 * @returns {boolean} True if expansion should be enabled
 */
export function shouldEnableInFlightExpansion(options, prdAnalysis) {
	// Explicit flag
	if (options.expandTasks) return true;

	// Auto-enable for complex PRDs in preserve detail mode
	if (options.preserveDetail && prdAnalysis.complexityScore >= 6) return true;

	// Auto-enable if many auto-expandable tasks detected
	const autoExpandableCount = Array.from(prdAnalysis.sectionMapping.sections.values())
		.filter(section => section.complexity >= 3).length;

	if (autoExpandableCount >= 5) return true;

	return false;
}