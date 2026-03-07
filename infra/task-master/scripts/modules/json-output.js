/**
 * json-output.js
 * JSON output functions for Task Master CLI commands
 */

import { readJSON, findTaskById } from './utils.js';
import findNextTask from './task-manager/find-next-task.js';

/**
 * Read complexity report file
 */
function readComplexityReport(complexityReportPath) {
	if (!complexityReportPath) return null;
	try {
		return readJSON(complexityReportPath);
	} catch (error) {
		return null;
	}
}

/**
 * Display next task in JSON format
 */
async function displayNextTaskJSON(tasksPath, complexityReportPath = null, context = {}) {
	const { projectRoot, tag } = context;

	// Read the tasks file with proper projectRoot for tag resolution
	const data = readJSON(tasksPath, projectRoot, tag);
	if (!data || !data.tasks) {
		const errorOutput = {
			error: 'No valid tasks found',
			success: false
		};
		console.log(JSON.stringify(errorOutput, null, 2));
		process.exit(1);
	}

	// Read complexity report once
	const complexityReport = readComplexityReport(complexityReportPath);

	// Find the next task
	const nextTask = findNextTask(data.tasks, complexityReport);

	if (!nextTask) {
		const output = {
			success: false,
			message: 'No eligible tasks found',
			reason: 'All pending tasks have unsatisfied dependencies, or all tasks are completed',
			nextTask: null,
			tag: tag || 'master'
		};
		console.log(JSON.stringify(output, null, 2));
		return;
	}

	// Create JSON output
	const output = {
		success: true,
		nextTask: {
			id: nextTask.id,
			title: nextTask.title,
			status: nextTask.status,
			priority: nextTask.priority,
			dependencies: nextTask.dependencies || [],
			complexity: nextTask.complexity || null,
			isSubtask: nextTask.parentId ? true : false,
			parentId: nextTask.parentId || null
		},
		tag: tag || 'master',
		timestamp: new Date().toISOString()
	};

	console.log(JSON.stringify(output, null, 2));
}

/**
 * Display task by ID in JSON format
 */
async function displayTaskByIdJSON(
	tasksPath,
	taskId,
	complexityReportPath = null,
	statusFilter = null,
	context = {}
) {
	const { projectRoot, tag } = context;

	// Read the tasks file with proper projectRoot for tag resolution
	const data = readJSON(tasksPath, projectRoot, tag);
	if (!data || !data.tasks) {
		const errorOutput = {
			error: 'No valid tasks found',
			success: false
		};
		console.log(JSON.stringify(errorOutput, null, 2));
		process.exit(1);
	}

	// Read complexity report once
	const complexityReport = readComplexityReport(complexityReportPath);

	// Find the task by ID, applying the status filter if provided
	const { task, originalSubtaskCount, originalSubtasks } = findTaskById(
		data.tasks,
		taskId,
		complexityReport,
		statusFilter
	);

	if (!task) {
		const output = {
			success: false,
			error: `Task with ID ${taskId} not found`,
			taskId: taskId,
			tag: tag || 'master'
		};
		console.log(JSON.stringify(output, null, 2));
		return;
	}

	// Create JSON output
	const output = {
		success: true,
		task: {
			id: task.id,
			title: task.title,
			description: task.description || null,
			status: task.status,
			priority: task.priority || 'medium',
			dependencies: task.dependencies || [],
			complexity: task.complexity || null,
			isSubtask: task.isSubtask || false,
			parentTask: task.parentTask || null,
			subtasks: task.subtasks ? task.subtasks.map(st => ({
				id: st.id,
				title: st.title,
				status: st.status || 'pending',
				dependencies: st.dependencies || [],
				complexity: st.complexity || null
			})) : [],
			originalSubtaskCount: originalSubtaskCount,
			filteredByStatus: statusFilter ? true : false,
			statusFilter: statusFilter || null
		},
		tag: tag || 'master',
		timestamp: new Date().toISOString()
	};

	console.log(JSON.stringify(output, null, 2));
}

/**
 * Display multiple tasks in JSON format
 */
async function displayMultipleTasksJSON(
	tasksPath,
	taskIds,
	complexityReportPath = null,
	statusFilter = null,
	context = {}
) {
	const { projectRoot, tag } = context;

	// Read the tasks file with proper projectRoot for tag resolution
	const data = readJSON(tasksPath, projectRoot, tag);
	if (!data || !data.tasks) {
		const errorOutput = {
			error: 'No valid tasks found',
			success: false
		};
		console.log(JSON.stringify(errorOutput, null, 2));
		process.exit(1);
	}

	// Read complexity report once
	const complexityReport = readComplexityReport(complexityReportPath);

	const tasks = [];
	const notFound = [];

	for (const taskId of taskIds) {
		const { task } = findTaskById(
			data.tasks,
			taskId,
			complexityReport,
			statusFilter
		);

		if (task) {
			tasks.push({
				id: task.id,
				title: task.title,
				description: task.description || null,
				status: task.status,
				priority: task.priority || 'medium',
				dependencies: task.dependencies || [],
				complexity: task.complexity || null,
				isSubtask: task.isSubtask || false,
				parentTask: task.parentTask || null,
				subtaskCount: task.subtasks ? task.subtasks.length : 0
			});
		} else {
			notFound.push(taskId);
		}
	}

	// Create JSON output
	const output = {
		success: tasks.length > 0,
		requestedCount: taskIds.length,
		foundCount: tasks.length,
		tasks: tasks,
		notFound: notFound,
		filteredByStatus: statusFilter ? true : false,
		statusFilter: statusFilter || null,
		tag: tag || 'master',
		timestamp: new Date().toISOString()
	};

	console.log(JSON.stringify(output, null, 2));
}

export {
	displayNextTaskJSON,
	displayTaskByIdJSON,
	displayMultipleTasksJSON
};