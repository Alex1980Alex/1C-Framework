/**
 * github-export-service.js
 * Core service for exporting Task Master tasks to GitHub issues
 * Part of Task #101.1 - Implement GitHub API Export Service
 */

import { RateLimiter } from '../utils/rate-limiter.js';
import { GitHubAPIError, ValidationError, AuthenticationError } from './github-errors.js';

/**
 * Core service for exporting tasks to GitHub issues via REST API
 */
export class GitHubExportService {
	constructor(token, options = {}) {
		if (!token) {
			throw new AuthenticationError('GitHub Personal Access Token is required');
		}

		this.token = token;
		this.baseURL = options.baseURL || 'https://api.github.com';
		this.userAgent = options.userAgent || 'TaskMaster-GitHub-Export/1.0';

		// Rate limiter to respect GitHub API limits (5000 requests per hour)
		this.rateLimiter = new RateLimiter({
			tokensPerInterval: 5000,
			interval: 'hour'
		});

		// Headers for all API requests
		this.headers = {
			'Authorization': `token ${this.token}`,
			'Accept': 'application/vnd.github.v3+json',
			'User-Agent': this.userAgent,
			'Content-Type': 'application/json'
		};
	}

	/**
	 * Main export method - exports a task to GitHub issue
	 * @param {Object} task - Task Master task object
	 * @param {string} repoOwner - GitHub repository owner
	 * @param {string} repoName - GitHub repository name
	 * @param {Object} exportOptions - Export configuration options
	 * @returns {Promise<Object>} Export result with issue details
	 */
	async exportTask(task, repoOwner, repoName, exportOptions = {}) {
		try {
			// Validate inputs
			this.validateExportInputs(task, repoOwner, repoName);

			// Check if task already has GitHub link and handle accordingly
			if (task.metadata?.githubIssue && !exportOptions.force) {
				throw new ValidationError(
					`Task ${task.id} is already exported to GitHub issue. Use --force to override.`
				);
			}

			// Validate repository access
			await this.validateRepositoryAccess(repoOwner, repoName);

			// Format task content for GitHub issue
			const issueData = this.formatTaskAsIssue(task, exportOptions);

			// Create GitHub issue
			const issue = await this.createGitHubIssue(repoOwner, repoName, issueData);

			// Update task with GitHub link (this will be handled by link manager)
			const linkResult = {
				issueUrl: issue.html_url,
				issueNumber: issue.number,
				repository: `${repoOwner}/${repoName}`
			};

			return {
				success: true,
				task: task,
				issue: {
					id: issue.id,
					number: issue.number,
					url: issue.html_url,
					title: issue.title,
					state: issue.state,
					created_at: issue.created_at
				},
				repository: `${repoOwner}/${repoName}`,
				exportOptions: exportOptions,
				linkData: linkResult
			};

		} catch (error) {
			console.error(`GitHub export failed for task ${task.id}:`, error.message);
			return {
				success: false,
				error: error.message,
				task: task,
				repository: `${repoOwner}/${repoName}`
			};
		}
	}

	/**
	 * Validate export inputs
	 * @param {Object} task - Task object
	 * @param {string} repoOwner - Repository owner
	 * @param {string} repoName - Repository name
	 */
	validateExportInputs(task, repoOwner, repoName) {
		if (!task || !task.id || !task.title) {
			throw new ValidationError('Invalid task object - must have id and title');
		}

		if (!repoOwner || !repoName) {
			throw new ValidationError('Repository owner and name are required');
		}

		if (typeof repoOwner !== 'string' || typeof repoName !== 'string') {
			throw new ValidationError('Repository owner and name must be strings');
		}

		// Validate GitHub repository name format
		const repoPattern = /^[a-zA-Z0-9._-]+$/;
		if (!repoPattern.test(repoOwner) || !repoPattern.test(repoName)) {
			throw new ValidationError('Invalid repository owner or name format');
		}
	}

	/**
	 * Validate repository access and permissions
	 * @param {string} repoOwner - Repository owner
	 * @param {string} repoName - Repository name
	 */
	async validateRepositoryAccess(repoOwner, repoName) {
		try {
			// Check repository existence and access
			const repoResponse = await this.makeAPIRequest(
				'GET',
				`/repos/${repoOwner}/${repoName}`
			);

			if (!repoResponse.ok) {
				if (repoResponse.status === 404) {
					throw new ValidationError(`Repository ${repoOwner}/${repoName} not found or not accessible`);
				} else if (repoResponse.status === 403) {
					throw new AuthenticationError('Insufficient permissions to access repository');
				}
				throw new GitHubAPIError(`Repository validation failed: ${repoResponse.statusText}`);
			}

			const repo = await repoResponse.json();

			// Check if issues are enabled
			if (repo.has_issues === false) {
				throw new ValidationError(`Issues are disabled for repository ${repoOwner}/${repoName}`);
			}

			// Check write permissions by testing if we can get the repository with push access
			const permissionsResponse = await this.makeAPIRequest(
				'GET',
				`/repos/${repoOwner}/${repoName}/collaborators/${await this.getCurrentUser()}/permission`
			);

			if (permissionsResponse.ok) {
				const permissions = await permissionsResponse.json();
				const hasWriteAccess = ['admin', 'write'].includes(permissions.permission);

				if (!hasWriteAccess) {
					throw new AuthenticationError('Write access required to create issues in this repository');
				}
			}

		} catch (error) {
			if (error instanceof ValidationError || error instanceof AuthenticationError) {
				throw error;
			}
			throw new GitHubAPIError(`Repository access validation failed: ${error.message}`);
		}
	}

	/**
	 * Get current authenticated user
	 * @returns {Promise<string>} Username of authenticated user
	 */
	async getCurrentUser() {
		const response = await this.makeAPIRequest('GET', '/user');
		if (!response.ok) {
			throw new AuthenticationError('Failed to get current user - check authentication token');
		}
		const user = await response.json();
		return user.login;
	}

	/**
	 * Format task as GitHub issue data
	 * @param {Object} task - Task Master task
	 * @param {Object} options - Export options
	 * @returns {Object} GitHub issue data
	 */
	formatTaskAsIssue(task, options = {}) {
		// Use custom title if provided, otherwise format with task ID
		const title = options.title || `[Task ${task.id}] ${task.title}`;

		// Build issue body
		let body = this.buildIssueBody(task, options);

		// Add Task Master reference
		body += this.generateTaskMasterReference(task.id, options.projectName);

		const issueData = {
			title: title,
			body: body
		};

		// Add optional fields if provided
		if (options.labels && Array.isArray(options.labels)) {
			issueData.labels = options.labels;
		}

		if (options.assignees && Array.isArray(options.assignees)) {
			issueData.assignees = options.assignees;
		}

		if (options.milestone) {
			issueData.milestone = options.milestone;
		}

		return issueData;
	}

	/**
	 * Build the main body content for GitHub issue
	 * @param {Object} task - Task Master task
	 * @param {Object} options - Export options
	 * @returns {string} Formatted issue body
	 */
	buildIssueBody(task, options = {}) {
		let body = `# ${task.title}\n\n`;

		// Add metadata section
		body += `**Task Master ID**: ${task.id}\n`;
		body += `**Priority**: ${task.priority || 'medium'}\n`;
		body += `**Status**: ${task.status || 'pending'}\n\n`;

		// Add description
		if (task.description) {
			body += `## Description\n${task.description}\n\n`;
		}

		// Add implementation details
		if (task.details) {
			body += `## Implementation Details\n${task.details}\n\n`;
		}

		// Add test strategy if available
		if (task.testStrategy) {
			body += `## Test Strategy\n${task.testStrategy}\n\n`;
		}

		// Handle subtasks
		if (task.subtasks && task.subtasks.length > 0 && options.includeSubtasks) {
			body += this.formatSubtasksAsChecklist(task.subtasks);
		}

		// Add dependencies if present
		if (task.dependencies && task.dependencies.length > 0) {
			body += `## Dependencies\n`;
			task.dependencies.forEach(dep => {
				body += `- Task #${dep}\n`;
			});
			body += '\n';
		}

		return body;
	}

	/**
	 * Format subtasks as GitHub checklist
	 * @param {Array} subtasks - Array of subtask objects
	 * @returns {string} Formatted subtasks section
	 */
	formatSubtasksAsChecklist(subtasks) {
		let subtasksSection = `## Subtasks\n`;

		subtasks.forEach(subtask => {
			const checked = subtask.status === 'done' ? 'x' : ' ';
			subtasksSection += `- [${checked}] ${subtask.title}`;

			if (subtask.description) {
				subtasksSection += ` - ${subtask.description}`;
			}

			subtasksSection += '\n';
		});

		subtasksSection += '\n';
		return subtasksSection;
	}

	/**
	 * Generate Task Master reference for GitHub issue
	 * @param {string} taskId - Task ID
	 * @param {string} projectName - Project name (optional)
	 * @returns {string} Reference text
	 */
	generateTaskMasterReference(taskId, projectName) {
		let reference = '\n---\n*Exported from Task Master*\n';
		reference += `**Task Master Reference**: Task #${taskId}`;

		if (projectName) {
			reference += ` in project "${projectName}"`;
		}

		reference += '\n';
		return reference;
	}

	/**
	 * Create GitHub issue via API
	 * @param {string} owner - Repository owner
	 * @param {string} repo - Repository name
	 * @param {Object} issueData - Issue data
	 * @returns {Promise<Object>} Created issue object
	 */
	async createGitHubIssue(owner, repo, issueData) {
		// Wait for rate limit if necessary
		await this.rateLimiter.removeTokens(1);

		const response = await this.makeAPIRequest(
			'POST',
			`/repos/${owner}/${repo}/issues`,
			issueData
		);

		if (!response.ok) {
			if (response.status === 401) {
				throw new AuthenticationError('Invalid GitHub token or insufficient permissions');
			} else if (response.status === 403) {
				throw new AuthenticationError('Forbidden - check repository permissions');
			} else if (response.status === 422) {
				const errorData = await response.json();
				throw new ValidationError(`Issue creation failed: ${errorData.message}`);
			}

			throw new GitHubAPIError(`Failed to create issue: ${response.status} ${response.statusText}`);
		}

		return await response.json();
	}

	/**
	 * Make HTTP request to GitHub API
	 * @param {string} method - HTTP method
	 * @param {string} endpoint - API endpoint (without base URL)
	 * @param {Object} data - Request body data (optional)
	 * @returns {Promise<Response>} Fetch response
	 */
	async makeAPIRequest(method, endpoint, data = null) {
		const url = `${this.baseURL}${endpoint}`;

		const requestOptions = {
			method: method,
			headers: this.headers
		};

		if (data && ['POST', 'PUT', 'PATCH'].includes(method)) {
			requestOptions.body = JSON.stringify(data);
		}

		try {
			const response = await fetch(url, requestOptions);
			return response;
		} catch (error) {
			throw new GitHubAPIError(`Network request failed: ${error.message}`);
		}
	}

	/**
	 * Preview issue content without creating it (dry run)
	 * @param {Object} task - Task Master task
	 * @param {Object} options - Export options
	 * @returns {Object} Preview data
	 */
	previewExport(task, options = {}) {
		const issueData = this.formatTaskAsIssue(task, options);

		return {
			title: issueData.title,
			body: issueData.body,
			labels: issueData.labels || [],
			assignees: issueData.assignees || [],
			milestone: issueData.milestone || null,
			metadata: {
				taskId: task.id,
				exportOptions: options
			}
		};
	}
}

export default GitHubExportService;