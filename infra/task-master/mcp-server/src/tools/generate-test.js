/**
 * tools/generate-test.js
 * Tool to generate AI-powered Jest test files for tasks
 */

import { z } from 'zod';
import {
	handleApiResult,
	createErrorResponse,
	withNormalizedProjectRoot
} from './utils.js';
import {
	generateTestForTask,
	generateTestsForTasks,
	getTestGenerationStats
} from '../../../scripts/modules/task-manager/generate-test.js';
import { findTasksPath } from '../core/utils/path-utils.js';
import path from 'path';

/**
 * Register the generate-test tool with the MCP server
 * @param {Object} server - FastMCP server instance
 */
export function registerGenerateTestTool(server) {
	server.addTool({
		name: 'generate_test',
		description: 'Generate AI-powered Jest test files for one or more tasks',
		parameters: z.object({
			id: z
				.string()
				.optional()
				.describe('Single task ID to generate test for'),
			ids: z
				.string()
				.optional()
				.describe('Comma-separated list of task IDs to generate tests for'),
			outputDir: z
				.string()
				.optional()
				.default('./tests')
				.describe('Output directory for test files (default: ./tests)'),
			filePrefix: z
				.string()
				.optional()
				.default('task_')
				.describe('Prefix for generated test files (default: task_)'),
			research: z
				.boolean()
				.optional()
				.default(false)
				.describe('Use research capabilities for enhanced test generation'),
			overwrite: z
				.boolean()
				.optional()
				.default(false)
				.describe('Overwrite existing test files'),
			validate: z
				.boolean()
				.optional()
				.default(true)
				.describe('Validate generated test content'),
			continueOnError: z
				.boolean()
				.optional()
				.default(true)
				.describe('Continue generating tests even if one fails (for batch mode)'),
			projectRoot: z
				.string()
				.describe('Absolute path to the project root directory'),
			tag: z
				.string()
				.optional()
				.describe('Tag context to operate on')
		}),
		execute: withNormalizedProjectRoot(async (args, { log, session }) => {
			const {
				id,
				ids,
				outputDir,
				filePrefix,
				research,
				overwrite,
				validate,
				continueOnError,
				projectRoot,
				tag
			} = args;

			try {
				// Validate required parameters
				if (!id && !ids) {
					return createErrorResponse('Either id or ids parameter must be provided');
				}

				if (id && ids) {
					return createErrorResponse('Cannot specify both id and ids parameters');
				}

				// Find tasks file path
				const tasksPath = findTasksPath(projectRoot, tag);

				log.info(`Generating tests with options:`, {
					tasksPath,
					outputDir: path.resolve(projectRoot, outputDir),
					filePrefix,
					research,
					overwrite,
					validate
				});

				// Prepare options for generation
				const options = {
					tasksPath,
					outputDir: path.resolve(projectRoot, outputDir),
					filePrefix,
					research,
					overwrite,
					validate,
					continueOnError
				};

				let result;

				if (id) {
					// Single task generation
					log.info(`Generating test for task ID: ${id}`);
					result = await generateTestForTask(id, options);

					if (result.success) {
						return {
							success: true,
							message: `Test generation completed successfully`,
							filename: result.filename,
							location: result.location,
							lines: result.lines
						};
					} else {
						return createErrorResponse(`Test generation failed: ${result.error}`);
					}
				} else {
					// Batch generation
					const taskIds = ids.split(',').map(taskId => taskId.trim());
					log.info(`Generating tests for task IDs: ${taskIds.join(', ')}`);

					result = await generateTestsForTasks(taskIds, options);

					return {
						success: true,
						message: `Batch test generation completed`,
						total: result.total,
						successful: result.successful,
						failed: result.failed,
						results: result.results
					};
				}

			} catch (error) {
				log.error(`Error in generate-test tool: ${error.message}`);
				return createErrorResponse(`Generate test failed: ${error.message}`);
			}
		})
	});
}

/**
 * Register the get-test-stats tool with the MCP server
 * @param {Object} server - FastMCP server instance
 */
export function registerGetTestStatsTool(server) {
	server.addTool({
		name: 'get_test_stats',
		description: 'Get test generation statistics and preview for a task',
		parameters: z.object({
			id: z
				.string()
				.describe('Task ID to get test generation statistics for'),
			projectRoot: z
				.string()
				.describe('Absolute path to the project root directory'),
			tag: z
				.string()
				.optional()
				.describe('Tag context to operate on')
		}),
		execute: withNormalizedProjectRoot(async (args, { log, session }) => {
			const { id, projectRoot, tag } = args;

			try {
				// Find tasks file path
				const tasksPath = findTasksPath(projectRoot, tag);

				// Load tasks and find the target task
				const { readJSON, findTaskById } = await import('../../../scripts/modules/utils.js');
				const tasksData = readJSON(tasksPath);
				const tasks = Array.isArray(tasksData) ? tasksData : tasksData.tasks;
				const taskResult = findTaskById(tasks, id);
				const task = taskResult.task;

				if (!task) {
					return createErrorResponse(`Task with ID ${id} not found`);
				}

				// Get test generation statistics
				const stats = getTestGenerationStats(task);

				log.info(`Generated test statistics for task ${id}`);

				return {
					success: true,
					taskId: stats.taskId,
					title: stats.title,
					complexity: stats.complexity,
					estimatedTestCases: stats.estimatedTestCases,
					hasDescription: stats.hasDescription,
					hasDetails: stats.hasDetails,
					hasTestStrategy: stats.hasTestStrategy,
					dependencyCount: stats.dependencyCount,
					subtaskCount: stats.subtaskCount
				};

			} catch (error) {
				log.error(`Error in get-test-stats tool: ${error.message}`);
				return createErrorResponse(`Get test stats failed: ${error.message}`);
			}
		})
	});
}