/**
 * enhanced-parse-prd.js
 * Enhanced PRD parsing with intelligent task expansion and context preservation
 * Part of Task #99.2 - Enhance Task Generation with PRD Context Preservation
 */

import chalk from 'chalk';
import {
	StreamingError,
	STREAMING_ERROR_CODES
} from '../../../../src/utils/stream-parser.js';
import { TimeoutManager } from '../../../../src/utils/timeout-manager.js';
import { getDebugFlag, getDefaultPriority } from '../../config-manager.js';

// Import configuration classes
import { PrdParseConfig, LoggingConfig } from './parse-prd-config.js';

// Import enhanced helper functions
import {
	readAndAnalyzePRDContent,
	processTasksWithContext,
	buildEnhancedPrompts,
	saveTasksWithPRDContext,
	validateEnhancedTasks
} from './enhanced-prd-helpers.js';

// Import original helpers for compatibility
import {
	loadExistingTasks,
	validateFileOperations,
	displayCliSummary,
	displayNonStreamingCliOutput
} from './parse-prd-helpers.js';

// Import handlers
import { handleStreamingService } from './parse-prd-streaming.js';
import { handleNonStreamingService } from './parse-prd-non-streaming.js';

// ============================================================================
// ENHANCED PARSING FUNCTIONS WITH PRD CONTEXT PRESERVATION
// ============================================================================

/**
 * Enhanced parsing logic with PRD analysis integration
 * @param {PrdParseConfig} config - Configuration object
 * @param {Function} serviceHandler - Handler function for AI service
 * @param {boolean} isStreaming - Whether this is streaming mode
 * @returns {Promise<Object>} Result object with success status and telemetry
 */
async function enhancedParsePRDCore(config, serviceHandler, isStreaming) {
	const logger = new LoggingConfig(config.mcpLog, config.reportProgress);

	logger.report(
		`Enhanced PRD parsing: ${config.prdPath}, Mode: Context-Aware, Research: ${config.research}`,
		'info'
	);

	try {
		// Phase 1: Intelligent PRD Analysis
		logger.report('Phase 1: Analyzing PRD structure and complexity...', 'info');
		const prdData = readAndAnalyzePRDContent(config.prdPath, {
			minSectionWords: 30,
			maxSections: 25
		});

		logger.report(
			`PRD Analysis Complete - Complexity: ${prdData.analysis.complexityScore}/10, ` +
			`Sections: ${prdData.analysis.metrics.sectionCount}, ` +
			`Recommended Tasks: ${prdData.analysis.recommendedTaskCount}`,
			'info'
		);

		// Phase 2: Adaptive Task Count Determination
		let adaptiveNumTasks = config.numTasks;
		if (config.numTasks === 0 || config.adaptiveCount) {
			adaptiveNumTasks = prdData.analysis.recommendedTaskCount;
			logger.report(
				`Adaptive task count enabled: ${adaptiveNumTasks} tasks (was ${config.numTasks})`,
				'info'
			);
		}

		// Phase 3: Load existing tasks and validate operations
		const { existingTasks, nextId } = loadExistingTasks(
			config.tasksPath,
			config.targetTag
		);

		validateFileOperations({
			existingTasks,
			targetTag: config.targetTag,
			append: config.append,
			force: config.force,
			isMCP: config.isMCP,
			logger
		});

		// Phase 4: Build enhanced prompts with PRD context
		logger.report('Phase 2: Building context-aware prompts...', 'info');
		const prompts = await buildEnhancedPrompts(
			config,
			prdData.content,
			prdData.analysis,
			nextId
		);

		// Phase 5: Call AI service with enhanced prompts
		logger.report('Phase 3: Generating tasks with PRD context preservation...', 'info');
		const serviceResult = await serviceHandler(
			config,
			prompts,
			adaptiveNumTasks
		);

		// Phase 6: Process tasks with PRD context preservation
		logger.report('Phase 4: Processing tasks with context preservation...', 'info');
		const defaultPriority = getDefaultPriority(config.projectRoot) || 'medium';
		const processedNewTasks = processTasksWithContext(
			serviceResult.parsedTasks,
			nextId,
			existingTasks,
			defaultPriority,
			prdData.analysis
		);

		// Phase 7: Validate enhanced task structure
		const isValid = validateEnhancedTasks(processedNewTasks, logger);
		if (!isValid) {
			logger.report('Warning: Some tasks have structural issues', 'warn');
		}

		// Phase 8: Combine with existing tasks if appending
		const finalTasks = config.append
			? [...existingTasks, ...processedNewTasks]
			: processedNewTasks;

		// Phase 9: Save with PRD context metadata
		logger.report('Phase 5: Saving tasks with PRD analysis metadata...', 'info');
		saveTasksWithPRDContext(
			config.tasksPath,
			finalTasks,
			config.targetTag,
			logger,
			prdData.analysis
		);

		// Phase 10: Handle completion reporting with enhancement stats
		await handleEnhancedCompletionReporting(
			config,
			serviceResult,
			processedNewTasks,
			finalTasks,
			nextId,
			isStreaming,
			prdData.analysis
		);

		return {
			success: true,
			tasksPath: config.tasksPath,
			telemetryData: serviceResult.aiServiceResponse?.telemetryData,
			tagInfo: serviceResult.aiServiceResponse?.tagInfo,
			// Enhanced return data
			prdAnalysis: {
				complexityScore: prdData.analysis.complexityScore,
				recommendedTaskCount: prdData.analysis.recommendedTaskCount,
				sectionCount: prdData.analysis.metrics.sectionCount,
				shouldAutoExpand: prdData.shouldAutoExpand
			},
			enhancementStats: {
				tasksWithContext: processedNewTasks.filter(t => t.prdContext).length,
				autoExpandableTasks: processedNewTasks.filter(t => t.expansionMetadata?.autoExpandable).length,
				averageComplexity: processedNewTasks.reduce((sum, t) => sum + (t.prdContext?.complexity || 1), 0) / processedNewTasks.length
			}
		};
	} catch (error) {
		logger.report(`Error in enhanced PRD parsing: ${error.message}`, 'error');

		if (!config.isMCP) {
			console.error(chalk.red(`Enhanced Parse Error: ${error.message}`));
			if (getDebugFlag(config.projectRoot)) {
				console.error(error);
			}
		}
		throw error;
	}
}

/**
 * Enhanced completion reporting with PRD analysis insights
 * @param {PrdParseConfig} config - Configuration object
 * @param {Object} serviceResult - Result from service handler
 * @param {Array} processedNewTasks - New tasks that were processed
 * @param {Array} finalTasks - All tasks after processing
 * @param {number} nextId - Next available task ID
 * @param {boolean} isStreaming - Whether this was streaming mode
 * @param {Object} prdAnalysis - PRD analysis results
 */
async function handleEnhancedCompletionReporting(
	config,
	serviceResult,
	processedNewTasks,
	finalTasks,
	nextId,
	isStreaming,
	prdAnalysis
) {
	const { aiServiceResponse, estimatedInputTokens, estimatedOutputTokens } =
		serviceResult;

	// Calculate enhancement statistics
	const tasksWithContext = processedNewTasks.filter(task => task.prdContext);
	const autoExpandableTasks = processedNewTasks.filter(task => task.expansionMetadata?.autoExpandable);
	const averageComplexity = processedNewTasks.length > 0
		? processedNewTasks.reduce((sum, task) => sum + (task.prdContext?.complexity || 1), 0) / processedNewTasks.length
		: 0;

	// MCP progress reporting with enhancement data
	if (config.reportProgress) {
		const hasValidTelemetry =
			aiServiceResponse?.telemetryData &&
			(aiServiceResponse.telemetryData.inputTokens > 0 ||
				aiServiceResponse.telemetryData.outputTokens > 0);

		let completionMessage;
		if (hasValidTelemetry) {
			const cost = aiServiceResponse.telemetryData.totalCost || 0;
			completionMessage = `Enhanced parsing complete! Generated ${processedNewTasks.length} tasks with context preservation. ` +
				`PRD Analysis: ${prdAnalysis.complexityScore}/10 complexity, ${tasksWithContext.length} tasks with PRD context, ` +
				`${autoExpandableTasks.length} auto-expandable. Cost: $${cost.toFixed(4)}`;
		} else {
			completionMessage = `Enhanced parsing complete! Generated ${processedNewTasks.length} context-aware tasks. ` +
				`PRD Analysis: ${prdAnalysis.complexityScore}/10 complexity, ${prdAnalysis.metrics.sectionCount} sections analyzed.`;
		}

		config.reportProgress({
			progress: 100,
			message: completionMessage
		});
	}

	// CLI output for non-MCP mode
	if (!config.isMCP) {
		if (isStreaming) {
			displayEnhancedCliSummary(
				processedNewTasks,
				finalTasks,
				nextId,
				config.tasksPath,
				config.targetTag,
				prdAnalysis,
				{
					tasksWithContext: tasksWithContext.length,
					autoExpandableTasks: autoExpandableTasks.length,
					averageComplexity
				}
			);
		} else {
			displayEnhancedNonStreamingCliOutput(
				processedNewTasks,
				config.tasksPath,
				config.targetTag,
				prdAnalysis
			);
		}
	}
}

/**
 * Display enhanced CLI summary with PRD analysis insights
 * @param {Array} processedNewTasks - Processed new tasks
 * @param {Array} finalTasks - All final tasks
 * @param {number} nextId - Next task ID
 * @param {string} tasksPath - Tasks file path
 * @param {string} targetTag - Target tag
 * @param {Object} prdAnalysis - PRD analysis results
 * @param {Object} enhancementStats - Enhancement statistics
 */
function displayEnhancedCliSummary(
	processedNewTasks,
	finalTasks,
	nextId,
	tasksPath,
	targetTag,
	prdAnalysis,
	enhancementStats
) {
	console.log('\n' + chalk.green('✓ Enhanced PRD parsing completed successfully!'));

	console.log('\n' + chalk.bold('📊 PRD Analysis Summary:'));
	console.log(`   Complexity Score: ${chalk.cyan(prdAnalysis.complexityScore + '/10')}`);
	console.log(`   Sections Analyzed: ${chalk.cyan(prdAnalysis.metrics.sectionCount)}`);
	console.log(`   Features Identified: ${chalk.cyan(prdAnalysis.metrics.featureCount)}`);
	console.log(`   Technical Depth: ${chalk.cyan(prdAnalysis.metrics.technicalDepth.toFixed(1) + '/2.0')}`);

	console.log('\n' + chalk.bold('🎯 Task Generation Results:'));
	console.log(`   Tasks Generated: ${chalk.green(processedNewTasks.length)}`);
	console.log(`   With PRD Context: ${chalk.cyan(enhancementStats.tasksWithContext + '/' + processedNewTasks.length)}`);
	console.log(`   Auto-Expandable: ${chalk.yellow(enhancementStats.autoExpandableTasks)}`);
	console.log(`   Average Complexity: ${chalk.cyan(enhancementStats.averageComplexity.toFixed(1) + '/5.0')}`);

	console.log('\n' + chalk.bold('💾 Output:'));
	console.log(`   File: ${chalk.blue(tasksPath)}`);
	console.log(`   Tag: ${chalk.blue(targetTag)}`);
	console.log(`   Total Tasks: ${chalk.green(finalTasks.length)}`);

	if (enhancementStats.autoExpandableTasks > 0) {
		console.log('\n' + chalk.yellow('💡 Tip: ') +
			`${enhancementStats.autoExpandableTasks} tasks are marked for auto-expansion. ` +
			`Use ${chalk.cyan('--expand-tasks')} flag for immediate expansion.`);
	}

	console.log('\n' + chalk.gray('Run ') + chalk.cyan('task-master list') + chalk.gray(' to view your tasks.'));
}

/**
 * Display enhanced non-streaming CLI output
 * @param {Array} processedNewTasks - Processed new tasks
 * @param {string} tasksPath - Tasks file path
 * @param {string} targetTag - Target tag
 * @param {Object} prdAnalysis - PRD analysis results
 */
function displayEnhancedNonStreamingCliOutput(
	processedNewTasks,
	tasksPath,
	targetTag,
	prdAnalysis
) {
	console.log('\n' + chalk.green('✓ Enhanced task generation completed!'));

	const tasksWithContext = processedNewTasks.filter(task => task.prdContext);
	const autoExpandable = processedNewTasks.filter(task => task.expansionMetadata?.autoExpandable);

	console.log(`\n${chalk.bold('Enhanced Generation Stats:')}`);
	console.log(`• PRD Complexity: ${chalk.cyan(prdAnalysis.complexityScore + '/10')}`);
	console.log(`• Tasks with Context: ${chalk.cyan(tasksWithContext.length + '/' + processedNewTasks.length)}`);
	console.log(`• Auto-Expandable: ${chalk.yellow(autoExpandable.length)}`);

	if (autoExpandable.length > 0) {
		console.log(`\n${chalk.yellow('💡 Auto-Expansion Available:')}`);
		autoExpandable.slice(0, 3).forEach(task => {
			console.log(`   • ${task.title} (${task.prdContext?.type || 'general'})`);
		});
		if (autoExpandable.length > 3) {
			console.log(`   ... and ${autoExpandable.length - 3} more`);
		}
	}
}

/**
 * Main enhanced parsing function for streaming mode
 * @param {string} prdPath - Path to PRD file
 * @param {string} tasksPath - Path to tasks file
 * @param {number} numTasks - Number of tasks to generate
 * @param {Object} options - Enhanced parsing options
 * @param {string} outputType - Output type
 * @returns {Promise<Object>} Parse result
 */
export async function enhancedParsePRDStreaming(
	prdPath,
	tasksPath,
	numTasks,
	options = {},
	outputType = 'cli'
) {
	const config = new PrdParseConfig({
		prdPath,
		tasksPath,
		numTasks,
		...options,
		outputType
	});

	return await enhancedParsePRDCore(config, handleStreamingService, true);
}

/**
 * Main enhanced parsing function for non-streaming mode
 * @param {string} prdPath - Path to PRD file
 * @param {string} tasksPath - Path to tasks file
 * @param {number} numTasks - Number of tasks to generate
 * @param {Object} options - Enhanced parsing options
 * @param {string} outputType - Output type
 * @returns {Promise<Object>} Parse result
 */
export async function enhancedParsePRDNonStreaming(
	prdPath,
	tasksPath,
	numTasks,
	options = {},
	outputType = 'cli'
) {
	const config = new PrdParseConfig({
		prdPath,
		tasksPath,
		numTasks,
		...options,
		outputType
	});

	return await enhancedParsePRDCore(config, handleNonStreamingService, false);
}

/**
 * Enhanced PRD parsing with automatic mode selection
 * @param {string} prdPath - Path to PRD file
 * @param {string} tasksPath - Path to tasks file
 * @param {number} numTasks - Number of tasks to generate
 * @param {Object} options - Enhanced parsing options
 * @param {string} outputType - Output type
 * @returns {Promise<Object>} Parse result
 */
export default async function enhancedParsePRD(
	prdPath,
	tasksPath,
	numTasks,
	options = {},
	outputType = 'cli'
) {
	// Determine if we should use streaming based on options or complexity
	const useStreaming = options.streaming !== false;

	if (useStreaming) {
		return await enhancedParsePRDStreaming(
			prdPath,
			tasksPath,
			numTasks,
			options,
			outputType
		);
	} else {
		return await enhancedParsePRDNonStreaming(
			prdPath,
			tasksPath,
			numTasks,
			options,
			outputType
		);
	}
}

// Functions are already exported individually above