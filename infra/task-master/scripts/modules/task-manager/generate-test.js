/**
 * generate-test.js
 * AI-powered test generation for Task Master tasks
 */

import fs from 'fs';
import path from 'path';
import chalk from 'chalk';
import { readJSON } from '../utils.js';
import { findTaskById } from '../utils.js';
import { getConfig } from '../config-manager.js';
import { generateTextService } from '../ai-services-unified.js';

/**
 * Generate Jest test file for a specific task using AI
 * @param {string} taskId - Task ID to generate tests for
 * @param {Object} options - Generation options
 * @returns {Promise<Object>} Generation result
 */
export async function generateTestForTask(taskId, options = {}) {
	const {
		tasksPath,
		outputDir = './tests',
		filePrefix = 'task_',
		research = false,
		overwrite = false,
		validate = true
	} = options;

	try {
		// Load tasks and find the target task
		const tasksData = readJSON(tasksPath);

		// Handle tagged data structure
		const tasks = Array.isArray(tasksData) ? tasksData : tasksData.tasks;
		const taskResult = findTaskById(tasks, taskId);
		const task = taskResult.task;

		if (!task) {
			throw new Error(`Task with ID ${taskId} not found`);
		}

		// Generate test content using AI
		const testContent = await generateTestContent(task, { research });

		// Determine output filename
		const filename = generateTestFilename(task, filePrefix);
		const outputPath = path.join(outputDir, filename);

		// Ensure output directory exists
		if (!fs.existsSync(outputDir)) {
			fs.mkdirSync(outputDir, { recursive: true });
		}

		// Check if file already exists
		if (fs.existsSync(outputPath) && !overwrite) {
			throw new Error(`Test file ${filename} already exists. Use --overwrite to replace it.`);
		}

		// Validate test content if requested
		if (validate) {
			validateTestContent(testContent, task);
		}

		// Write test file
		fs.writeFileSync(outputPath, testContent, 'utf8');

		return {
			success: true,
			filename,
			outputPath,
			task: {
				id: task.id,
				title: task.title
			},
			linesGenerated: testContent.split('\n').length
		};

	} catch (error) {
		return {
			success: false,
			error: error.message,
			taskId
		};
	}
}

/**
 * Generate test filename based on task structure
 * @param {Object} task - Task object
 * @param {string} prefix - File prefix
 * @returns {string} Generated filename
 */
function generateTestFilename(task, prefix = 'task_') {
	// Handle subtasks (e.g., task_024_001.test.js for subtask 24.1)
	if (task.isSubtask && task.parentTask) {
		const parentPadded = task.parentTask.id.toString().padStart(3, '0');
		const subtaskNumber = task.id.toString().padStart(3, '0');
		return `${prefix}${parentPadded}_${subtaskNumber}.test.js`;
	}

	// Handle parent tasks (e.g., task_024.test.js for task 24)
	const paddedId = task.id.toString().padStart(3, '0');
	return `${prefix}${paddedId}.test.js`;
}

/**
 * Generate test content using AI based on task details
 * @param {Object} task - Task object
 * @param {Object} options - Generation options
 * @returns {Promise<string>} Generated test content
 */
async function generateTestContent(task, options = {}) {
	const { research = false } = options;

	// Construct AI prompt for test generation
	const prompt = constructTestGenerationPrompt(task);

	// Get AI configuration
	const config = getConfig();
	const modelRole = research ? 'research' : 'main';

	// Call AI service to generate test content
	const response = await generateTextService({
		prompt,
		systemPrompt: 'You are a professional test engineer. Generate high-quality, comprehensive Jest test files.',
		role: modelRole,
		commandName: 'generate-test',
		outputType: 'cli'
	});

	// Extract and clean the test content
	return extractTestContent(response.mainResult);
}

/**
 * Construct comprehensive prompt for AI test generation
 * @param {Object} task - Task object
 * @returns {string} AI prompt
 */
function constructTestGenerationPrompt(task) {
	const isSubtask = !!task.parentId;
	const taskType = isSubtask ? 'subtask' : 'task';

	let prompt = `Generate a comprehensive Jest test file for the following ${taskType}:

**Task ID**: ${task.id}
**Title**: ${task.title}
**Status**: ${task.status}
**Description**: ${task.description || 'No description provided'}`;

	if (task.details) {
		prompt += `\n**Implementation Details**: ${task.details}`;
	}

	if (task.testStrategy) {
		prompt += `\n**Test Strategy**: ${task.testStrategy}`;
	}

	if (task.dependencies && task.dependencies.length > 0) {
		prompt += `\n**Dependencies**: ${task.dependencies.join(', ')}`;
	}

	if (task.subtasks && task.subtasks.length > 0) {
		prompt += `\n**Subtasks**:`;
		task.subtasks.forEach(subtask => {
			prompt += `\n- ${subtask.id}: ${subtask.title}`;
		});
	}

	prompt += `

**Requirements for the test file**:

1. **File Structure**: Create a proper TypeScript Jest test file with:
   - Appropriate imports for Jest and any required modules
   - Describe blocks for organizing test cases
   - Proper TypeScript types and interfaces

2. **Test Coverage**: Include tests for:
   - Main functionality described in the task
   - Edge cases and error conditions
   - Input validation
   - Expected outputs and side effects

3. **Mocking**: Create appropriate mocks for:
   - External dependencies mentioned in the task
   - File system operations (if applicable)
   - API calls (if applicable)
   - Database operations (if applicable)

4. **Test Organization**: Organize tests with:
   - Clear describe blocks for different aspects
   - Descriptive test names using "should" or "it" patterns
   - Setup and teardown as needed
   - Grouped related test cases

5. **Code Quality**: Ensure:
   - TypeScript compliance
   - Jest best practices
   - Clear and readable test code
   - Proper assertions using Jest matchers

6. **Comments**: Include:
   - Brief description of what the test file covers
   - Comments explaining complex test scenarios
   - Documentation for any custom test utilities

**Important**: Return ONLY the complete test file content, starting with imports and ending with the last test case. Do not include explanations or markdown formatting around the code.`;

	return prompt;
}

/**
 * Extract clean test content from AI response
 * @param {string} response - AI response
 * @returns {string} Clean test content
 */
function extractTestContent(response) {
	// Remove markdown code blocks if present
	let content = response.trim();

	// Remove leading/trailing markdown code blocks
	if (content.startsWith('```typescript') || content.startsWith('```ts')) {
		content = content.replace(/^```(?:typescript|ts)\n/, '');
	} else if (content.startsWith('```')) {
		content = content.replace(/^```\w*\n/, '');
	}

	if (content.endsWith('```')) {
		content = content.replace(/\n```$/, '');
	}

	// Ensure proper imports are present
	if (!content.includes('import') && !content.includes('require')) {
		content = `import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';\n\n${content}`;
	}

	return content.trim();
}

/**
 * Validate generated test content for basic quality checks
 * @param {string} content - Test content to validate
 * @param {Object} task - Original task object
 * @throws {Error} If validation fails
 */
function validateTestContent(content, task) {
	const validationErrors = [];

	// Check for basic Jest structure
	if (!content.includes('describe')) {
		validationErrors.push('Missing describe blocks');
	}

	if (!content.includes('it(') && !content.includes('test(')) {
		validationErrors.push('Missing test cases (it/test blocks)');
	}

	if (!content.includes('expect')) {
		validationErrors.push('Missing expect assertions');
	}

	// Check for imports
	if (!content.includes('import') && !content.includes('require')) {
		validationErrors.push('Missing import statements');
	}

	// Check minimum length (should be substantial)
	if (content.length < 500) {
		validationErrors.push('Test content seems too short (less than 500 characters)');
	}

	// Check for TypeScript syntax basics
	if (!content.includes(';') && !content.includes('{')) {
		validationErrors.push('Content does not appear to be valid TypeScript/JavaScript');
	}

	// Verify task reference in content
	const taskTitle = task.title.toLowerCase();
	const contentLower = content.toLowerCase();

	// Check if test content is related to the task
	const hasTaskReference = taskTitle.split(' ').some(word =>
		word.length > 3 && contentLower.includes(word.toLowerCase())
	);

	if (!hasTaskReference && !contentLower.includes('task') && !contentLower.includes(task.id.toString())) {
		validationErrors.push('Test content does not appear to reference the original task');
	}

	if (validationErrors.length > 0) {
		throw new Error(`Test validation failed:\n${validationErrors.map(err => `- ${err}`).join('\n')}`);
	}
}

/**
 * Get test generation statistics for a task
 * @param {Object} task - Task object
 * @returns {Object} Statistics about what tests should cover
 */
export function getTestGenerationStats(task) {
	const stats = {
		taskId: task.id,
		title: task.title,
		hasDescription: !!task.description,
		hasDetails: !!task.details,
		hasTestStrategy: !!task.testStrategy,
		dependencyCount: task.dependencies ? task.dependencies.length : 0,
		subtaskCount: task.subtasks ? task.subtasks.length : 0,
		estimatedTestCases: 0,
		complexity: 'low'
	};

	// Estimate number of test cases based on task characteristics
	let testCases = 2; // Base: happy path + error case

	if (stats.hasDescription) testCases += 1;
	if (stats.hasDetails) testCases += 2;
	if (stats.dependencyCount > 0) testCases += stats.dependencyCount;
	if (stats.subtaskCount > 0) testCases += Math.min(stats.subtaskCount, 5);

	stats.estimatedTestCases = testCases;

	// Determine complexity
	if (stats.subtaskCount > 5 || stats.dependencyCount > 3) {
		stats.complexity = 'high';
	} else if (stats.subtaskCount > 2 || stats.dependencyCount > 1 || stats.hasTestStrategy) {
		stats.complexity = 'medium';
	}

	return stats;
}

/**
 * Generate tests for multiple tasks
 * @param {Array<string>} taskIds - Array of task IDs
 * @param {Object} options - Generation options
 * @returns {Promise<Object>} Batch generation results
 */
export async function generateTestsForTasks(taskIds, options = {}) {
	const results = [];
	const { continueOnError = true } = options;

	for (const taskId of taskIds) {
		try {
			console.log(chalk.blue(`Generating tests for task ${taskId}...`));

			const result = await generateTestForTask(taskId, options);
			results.push(result);

			if (result.success) {
				console.log(chalk.green(`✓ Generated ${result.filename}`));
			} else {
				console.log(chalk.red(`✗ Failed to generate tests for task ${taskId}: ${result.error}`));
				if (!continueOnError) break;
			}

		} catch (error) {
			const failureResult = {
				success: false,
				error: error.message,
				taskId
			};
			results.push(failureResult);

			console.log(chalk.red(`✗ Error generating tests for task ${taskId}: ${error.message}`));
			if (!continueOnError) break;
		}
	}

	return {
		total: taskIds.length,
		successful: results.filter(r => r.success).length,
		failed: results.filter(r => !r.success).length,
		results
	};
}