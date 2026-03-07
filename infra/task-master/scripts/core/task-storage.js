/**
 * task-storage.js
 * Task storage utilities for CLI interface
 * Part of Task #101.4 - Create Comprehensive CLI Interface
 */

import fs from 'fs/promises';
import path from 'path';

/**
 * Default task storage path
 */
const DEFAULT_TASKS_PATH = '.taskmaster/tasks/tasks.json';

/**
 * Load tasks from storage
 * @param {string} tasksPath - Path to tasks file
 * @returns {Promise<Array>} Array of tasks
 */
export async function loadTasks(tasksPath = DEFAULT_TASKS_PATH) {
	try {
		const fullPath = path.resolve(tasksPath);
		const data = await fs.readFile(fullPath, 'utf8');
		const parsed = JSON.parse(data);

		// Handle different task file formats
		if (Array.isArray(parsed)) {
			return parsed;
		}

		if (parsed.tasks && Array.isArray(parsed.tasks)) {
			return parsed.tasks;
		}

		if (parsed.data && Array.isArray(parsed.data)) {
			return parsed.data;
		}

		throw new Error('Invalid task file format');

	} catch (error) {
		if (error.code === 'ENOENT') {
			throw new Error(`Tasks file not found: ${tasksPath}. Make sure Task Master is initialized.`);
		}
		throw error;
	}
}

/**
 * Save tasks to storage
 * @param {Array} tasks - Array of tasks to save
 * @param {string} tasksPath - Path to tasks file
 * @returns {Promise<void>}
 */
export async function saveTasks(tasks, tasksPath = DEFAULT_TASKS_PATH) {
	try {
		const fullPath = path.resolve(tasksPath);

		// Ensure directory exists
		await fs.mkdir(path.dirname(fullPath), { recursive: true });

		// Read existing file to preserve format
		let existingData = {};
		try {
			const existing = await fs.readFile(fullPath, 'utf8');
			existingData = JSON.parse(existing);
		} catch (error) {
			// File doesn't exist, create new format
		}

		// Preserve existing format structure
		let dataToSave;
		if (Array.isArray(existingData)) {
			dataToSave = tasks;
		} else if (existingData.tasks) {
			dataToSave = {
				...existingData,
				tasks,
				lastUpdated: new Date().toISOString()
			};
		} else {
			dataToSave = {
				tasks,
				metadata: {
					version: '1.0.0',
					lastUpdated: new Date().toISOString(),
					totalTasks: tasks.length
				}
			};
		}

		await fs.writeFile(fullPath, JSON.stringify(dataToSave, null, 2), 'utf8');

	} catch (error) {
		throw new Error(`Failed to save tasks: ${error.message}`);
	}
}

/**
 * Find task by ID
 * @param {string} taskId - Task ID to find
 * @param {string} tasksPath - Path to tasks file
 * @returns {Promise<Object|null>} Found task or null
 */
export async function findTask(taskId, tasksPath = DEFAULT_TASKS_PATH) {
	const tasks = await loadTasks(tasksPath);
	return tasks.find(task => task.id === taskId) || null;
}

/**
 * Update task in storage
 * @param {string} taskId - Task ID to update
 * @param {Object} updates - Updates to apply
 * @param {string} tasksPath - Path to tasks file
 * @returns {Promise<Object>} Updated task
 */
export async function updateTask(taskId, updates, tasksPath = DEFAULT_TASKS_PATH) {
	const tasks = await loadTasks(tasksPath);
	const taskIndex = tasks.findIndex(task => task.id === taskId);

	if (taskIndex === -1) {
		throw new Error(`Task ${taskId} not found`);
	}

	// Apply updates
	tasks[taskIndex] = {
		...tasks[taskIndex],
		...updates,
		lastUpdated: new Date().toISOString()
	};

	await saveTasks(tasks, tasksPath);
	return tasks[taskIndex];
}

/**
 * Filter tasks by criteria
 * @param {Object} criteria - Filter criteria
 * @param {string} tasksPath - Path to tasks file
 * @returns {Promise<Array>} Filtered tasks
 */
export async function filterTasks(criteria, tasksPath = DEFAULT_TASKS_PATH) {
	const tasks = await loadTasks(tasksPath);

	return tasks.filter(task => {
		// Filter by status
		if (criteria.status && task.status !== criteria.status) {
			return false;
		}

		// Filter by priority
		if (criteria.priority && task.priority !== criteria.priority) {
			return false;
		}

		// Filter by ID prefix
		if (criteria.prefix && !task.id.startsWith(criteria.prefix)) {
			return false;
		}

		// Filter by search term
		if (criteria.search) {
			const searchTerm = criteria.search.toLowerCase();
			const title = (task.title || '').toLowerCase();
			const description = (task.description || '').toLowerCase();

			if (!title.includes(searchTerm) && !description.includes(searchTerm)) {
				return false;
			}
		}

		// Filter by tags
		if (criteria.tags && Array.isArray(criteria.tags)) {
			const taskTags = task.tags || [];
			if (!criteria.tags.some(tag => taskTags.includes(tag))) {
				return false;
			}
		}

		return true;
	});
}

/**
 * Get task statistics
 * @param {string} tasksPath - Path to tasks file
 * @returns {Promise<Object>} Task statistics
 */
export async function getTaskStatistics(tasksPath = DEFAULT_TASKS_PATH) {
	const tasks = await loadTasks(tasksPath);

	const stats = {
		total: tasks.length,
		byStatus: {},
		byPriority: {},
		withSubtasks: 0,
		withDependencies: 0,
		completionRate: 0
	};

	// Calculate statistics
	tasks.forEach(task => {
		// By status
		const status = task.status || 'pending';
		stats.byStatus[status] = (stats.byStatus[status] || 0) + 1;

		// By priority
		const priority = task.priority || 'normal';
		stats.byPriority[priority] = (stats.byPriority[priority] || 0) + 1;

		// With subtasks
		if (task.subtasks && task.subtasks.length > 0) {
			stats.withSubtasks++;
		}

		// With dependencies
		if (task.dependencies && task.dependencies.length > 0) {
			stats.withDependencies++;
		}
	});

	// Calculate completion rate
	const completed = stats.byStatus.done || 0;
	stats.completionRate = stats.total > 0 ? Math.round((completed / stats.total) * 100) : 0;

	return stats;
}

/**
 * Validate task data structure
 * @param {Object} task - Task to validate
 * @returns {Object} Validation result
 */
export function validateTask(task) {
	const errors = [];
	const warnings = [];

	// Required fields
	if (!task.id) {
		errors.push('Task ID is required');
	}

	if (!task.title) {
		errors.push('Task title is required');
	}

	// Validate ID format
	if (task.id && !/^[\w.-]+$/.test(task.id)) {
		warnings.push('Task ID contains invalid characters');
	}

	// Validate status
	const validStatuses = ['pending', 'in-progress', 'done', 'deferred', 'cancelled', 'blocked'];
	if (task.status && !validStatuses.includes(task.status)) {
		warnings.push(`Invalid status: ${task.status}. Valid values: ${validStatuses.join(', ')}`);
	}

	// Validate priority
	const validPriorities = ['low', 'normal', 'high', 'critical'];
	if (task.priority && !validPriorities.includes(task.priority)) {
		warnings.push(`Invalid priority: ${task.priority}. Valid values: ${validPriorities.join(', ')}`);
	}

	// Validate subtasks
	if (task.subtasks && Array.isArray(task.subtasks)) {
		task.subtasks.forEach((subtask, index) => {
			if (!subtask.id) {
				warnings.push(`Subtask ${index + 1} missing ID`);
			}
			if (!subtask.title) {
				warnings.push(`Subtask ${index + 1} missing title`);
			}
		});
	}

	// Validate dependencies
	if (task.dependencies && Array.isArray(task.dependencies)) {
		task.dependencies.forEach((dep, index) => {
			if (typeof dep !== 'string') {
				warnings.push(`Dependency ${index + 1} should be a string (task ID)`);
			}
		});
	}

	return {
		valid: errors.length === 0,
		errors,
		warnings
	};
}

/**
 * Check if tasks file exists and is valid
 * @param {string} tasksPath - Path to tasks file
 * @returns {Promise<Object>} Validation result
 */
export async function validateTasksFile(tasksPath = DEFAULT_TASKS_PATH) {
	try {
		const fullPath = path.resolve(tasksPath);

		// Check if file exists
		await fs.access(fullPath);

		// Try to load and parse
		const tasks = await loadTasks(tasksPath);

		// Validate each task
		const validationResults = tasks.map(task => ({
			taskId: task.id,
			...validateTask(task)
		}));

		const invalidTasks = validationResults.filter(result => !result.valid);
		const tasksWithWarnings = validationResults.filter(result => result.warnings.length > 0);

		return {
			fileExists: true,
			parseable: true,
			taskCount: tasks.length,
			invalidTasks: invalidTasks.length,
			tasksWithWarnings: tasksWithWarnings.length,
			validationResults,
			valid: invalidTasks.length === 0
		};

	} catch (error) {
		if (error.code === 'ENOENT') {
			return {
				fileExists: false,
				parseable: false,
				error: 'Tasks file not found',
				valid: false
			};
		}

		return {
			fileExists: true,
			parseable: false,
			error: error.message,
			valid: false
		};
	}
}