/**
 * github-export-service.test.js
 * Unit tests for GitHub Export Service
 * Part of Task #101.1 - Implement GitHub API Export Service
 */

import { jest } from '@jest/globals';
import { GitHubExportService } from '../../../../../scripts/modules/github/github-export-service.js';
import {
	AuthenticationError,
	ValidationError,
	GitHubAPIError
} from '../../../../../scripts/modules/github/github-errors.js';

// Mock fetch globally
global.fetch = jest.fn();

describe('GitHubExportService', () => {
	let service;
	const mockToken = 'ghp_test_token_123';

	beforeEach(() => {
		service = new GitHubExportService(mockToken);
		jest.clearAllMocks();
	});

	describe('Constructor', () => {
		test('should create service with valid token', () => {
			expect(service.token).toBe(mockToken);
			expect(service.baseURL).toBe('https://api.github.com');
			expect(service.userAgent).toBe('TaskMaster-GitHub-Export/1.0');
		});

		test('should throw error for missing token', () => {
			expect(() => new GitHubExportService()).toThrow(AuthenticationError);
			expect(() => new GitHubExportService(null)).toThrow(AuthenticationError);
			expect(() => new GitHubExportService('')).toThrow(AuthenticationError);
		});

		test('should accept custom options', () => {
			const customService = new GitHubExportService(mockToken, {
				baseURL: 'https://api.github.example.com',
				userAgent: 'Custom-Agent/2.0'
			});

			expect(customService.baseURL).toBe('https://api.github.example.com');
			expect(customService.userAgent).toBe('Custom-Agent/2.0');
		});
	});

	describe('Input Validation', () => {
		test('should validate task object', () => {
			expect(() => service.validateExportInputs(null, 'owner', 'repo'))
				.toThrow(ValidationError);

			expect(() => service.validateExportInputs({}, 'owner', 'repo'))
				.toThrow(ValidationError);

			expect(() => service.validateExportInputs({ id: '1' }, 'owner', 'repo'))
				.toThrow(ValidationError);
		});

		test('should validate repository parameters', () => {
			const validTask = { id: '1', title: 'Test Task' };

			expect(() => service.validateExportInputs(validTask, '', 'repo'))
				.toThrow(ValidationError);

			expect(() => service.validateExportInputs(validTask, 'owner', ''))
				.toThrow(ValidationError);

			expect(() => service.validateExportInputs(validTask, null, 'repo'))
				.toThrow(ValidationError);
		});

		test('should validate repository name format', () => {
			const validTask = { id: '1', title: 'Test Task' };

			expect(() => service.validateExportInputs(validTask, 'owner with spaces', 'repo'))
				.toThrow(ValidationError);

			expect(() => service.validateExportInputs(validTask, 'owner', 'repo@invalid'))
				.toThrow(ValidationError);

			// Valid formats should not throw
			expect(() => service.validateExportInputs(validTask, 'valid-owner', 'valid.repo_name'))
				.not.toThrow();
		});
	});

	describe('Issue Formatting', () => {
		const mockTask = {
			id: '1',
			title: 'Test Task',
			description: 'This is a test task',
			details: 'Implementation details here',
			priority: 'high',
			status: 'pending',
			subtasks: [
				{ id: '1.1', title: 'Subtask 1', status: 'done' },
				{ id: '1.2', title: 'Subtask 2', status: 'pending' }
			]
		};

		test('should format basic task as issue', () => {
			const issueData = service.formatTaskAsIssue(mockTask);

			expect(issueData.title).toBe('[Task 1] Test Task');
			expect(issueData.body).toContain('# Test Task');
			expect(issueData.body).toContain('**Task Master ID**: 1');
			expect(issueData.body).toContain('**Priority**: high');
			expect(issueData.body).toContain('**Status**: pending');
			expect(issueData.body).toContain('## Description\nThis is a test task');
			expect(issueData.body).toContain('## Implementation Details\nImplementation details here');
		});

		test('should use custom title when provided', () => {
			const options = { title: 'Custom Issue Title' };
			const issueData = service.formatTaskAsIssue(mockTask, options);

			expect(issueData.title).toBe('Custom Issue Title');
		});

		test('should include subtasks when requested', () => {
			const options = { includeSubtasks: true };
			const issueData = service.formatTaskAsIssue(mockTask, options);

			expect(issueData.body).toContain('## Subtasks');
			expect(issueData.body).toContain('- [x] Subtask 1');
			expect(issueData.body).toContain('- [ ] Subtask 2');
		});

		test('should add labels when provided', () => {
			const options = { labels: ['bug', 'high-priority'] };
			const issueData = service.formatTaskAsIssue(mockTask, options);

			expect(issueData.labels).toEqual(['bug', 'high-priority']);
		});

		test('should add assignees when provided', () => {
			const options = { assignees: ['user1', 'user2'] };
			const issueData = service.formatTaskAsIssue(mockTask, options);

			expect(issueData.assignees).toEqual(['user1', 'user2']);
		});

		test('should include Task Master reference', () => {
			const issueData = service.formatTaskAsIssue(mockTask);

			expect(issueData.body).toContain('---\n*Exported from Task Master*');
			expect(issueData.body).toContain('**Task Master Reference**: Task #1');
		});

		test('should include project name in reference when provided', () => {
			const options = { projectName: 'My Project' };
			const issueData = service.formatTaskAsIssue(mockTask, options);

			expect(issueData.body).toContain('**Task Master Reference**: Task #1 in project "My Project"');
		});
	});

	describe('Preview Export', () => {
		test('should generate preview without making API calls', () => {
			const mockTask = {
				id: '1',
				title: 'Test Task',
				description: 'Test description'
			};

			const preview = service.previewExport(mockTask);

			expect(preview).toHaveProperty('title');
			expect(preview).toHaveProperty('body');
			expect(preview).toHaveProperty('labels');
			expect(preview).toHaveProperty('assignees');
			expect(preview).toHaveProperty('metadata');
			expect(preview.metadata.taskId).toBe('1');
		});

		test('should include all export options in preview', () => {
			const mockTask = { id: '1', title: 'Test Task' };
			const options = {
				labels: ['test'],
				assignees: ['user1'],
				milestone: 1,
				projectName: 'Test Project'
			};

			const preview = service.previewExport(mockTask, options);

			expect(preview.labels).toEqual(['test']);
			expect(preview.assignees).toEqual(['user1']);
			expect(preview.milestone).toBe(1);
			expect(preview.body).toContain('Test Project');
		});
	});

	describe('Error Handling', () => {
		test('should handle existing GitHub links', async () => {
			const mockTask = {
				id: '1',
				title: 'Test Task',
				metadata: {
					githubIssue: {
						url: 'https://github.com/owner/repo/issues/1',
						number: 1
					}
				}
			};

			const result = await service.exportTask(mockTask, 'owner', 'repo');

			expect(result.success).toBe(false);
			expect(result.error).toContain('already exported');
		});

		test('should allow force override of existing links', async () => {
			const mockTask = {
				id: '1',
				title: 'Test Task',
				metadata: {
					githubIssue: {
						url: 'https://github.com/owner/repo/issues/1',
						number: 1
					}
				}
			};

			// Mock successful API responses
			global.fetch
				.mockResolvedValueOnce({
					ok: true,
					json: async () => ({ has_issues: true })
				})
				.mockResolvedValueOnce({
					ok: true,
					json: async () => ({ login: 'testuser' })
				})
				.mockResolvedValueOnce({
					ok: true,
					json: async () => ({ permission: 'write' })
				})
				.mockResolvedValueOnce({
					ok: true,
					json: async () => ({
						id: 123,
						number: 1,
						html_url: 'https://github.com/owner/repo/issues/1',
						title: 'Test Issue',
						state: 'open',
						created_at: '2023-01-01T00:00:00Z'
					})
				});

			const result = await service.exportTask(mockTask, 'owner', 'repo', { force: true });

			expect(result.success).toBe(true);
		});
	});

	describe('API Request Building', () => {
		test('should build correct headers', () => {
			expect(service.headers).toEqual({
				'Authorization': `token ${mockToken}`,
				'Accept': 'application/vnd.github.v3+json',
				'User-Agent': 'TaskMaster-GitHub-Export/1.0',
				'Content-Type': 'application/json'
			});
		});

		test('should handle API request errors', async () => {
			global.fetch.mockRejectedValueOnce(new Error('Network error'));

			const mockTask = { id: '1', title: 'Test Task' };
			const result = await service.exportTask(mockTask, 'owner', 'repo');

			expect(result.success).toBe(false);
			expect(result.error).toContain('Network request failed');
		});
	});
});

describe('Rate Limiting Integration', () => {
	test('should respect rate limits', async () => {
		const service = new GitHubExportService('token');

		// Mock the rate limiter
		const mockRemoveTokens = jest.fn().mockResolvedValue();
		service.rateLimiter.removeTokens = mockRemoveTokens;

		// Mock successful API responses
		global.fetch
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ has_issues: true })
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ login: 'testuser' })
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ permission: 'write' })
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({
					id: 123,
					number: 1,
					html_url: 'https://github.com/owner/repo/issues/1',
					title: 'Test Issue',
					state: 'open',
					created_at: '2023-01-01T00:00:00Z'
				})
			});

		const mockTask = { id: '1', title: 'Test Task' };
		await service.exportTask(mockTask, 'owner', 'repo');

		// Should have called rate limiter before creating issue
		expect(mockRemoveTokens).toHaveBeenCalledWith(1);
	});
});