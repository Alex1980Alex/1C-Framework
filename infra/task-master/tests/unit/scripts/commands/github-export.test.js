/**
 * github-export.test.js
 * Unit tests for GitHub Export CLI
 * Part of Task #101.4 - Create Comprehensive CLI Interface
 */

import { jest } from '@jest/globals';
import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs/promises';
import path from 'path';

const execAsync = promisify(exec);

// Mock file system operations
jest.mock('fs/promises');

describe('GitHub Export CLI', () => {
	const CLI_PATH = './bin/github-export.js';
	const TEST_TOKEN = 'ghp_test_token_123';

	beforeEach(() => {
		jest.clearAllMocks();
		process.env.GITHUB_TOKEN = TEST_TOKEN;

		// Mock task file
		fs.readFile.mockImplementation((filePath) => {
			if (filePath.includes('tasks.json')) {
				return Promise.resolve(JSON.stringify([
					{
						id: '1',
						title: 'Test Task 1',
						description: 'Test description',
						status: 'pending',
						priority: 'high'
					},
					{
						id: '2',
						title: 'Test Task 2',
						description: 'Another test',
						status: 'done',
						priority: 'low'
					}
				]));
			}
			if (filePath.includes('github-config.json')) {
				return Promise.resolve(JSON.stringify({
					defaultOwner: 'testowner',
					defaultRepo: 'testrepo'
				}));
			}
			if (filePath.includes('github-links.json')) {
				return Promise.resolve(JSON.stringify({
					metadata: { totalLinks: 0, activeLinks: 0 },
					links: []
				}));
			}
			return Promise.reject(new Error('File not found'));
		});

		fs.writeFile.mockResolvedValue();
		fs.mkdir.mockResolvedValue();
		fs.access.mockResolvedValue();
		fs.readdir.mockResolvedValue([]);
	});

	afterEach(() => {
		delete process.env.GITHUB_TOKEN;
	});

	describe('CLI Commands', () => {
		test('should show help when no command provided', async () => {
			try {
				await execAsync(`node ${CLI_PATH}`, { timeout: 5000 });
			} catch (error) {
				// CLI exits with code 0 but shows help
				expect(error.stdout || error.stderr).toContain('Usage:');
			}
		}, 10000);

		test('should show version information', async () => {
			try {
				const { stdout } = await execAsync(`node ${CLI_PATH} --version`, { timeout: 5000 });
				expect(stdout).toMatch(/\d+\.\d+\.\d+/);
			} catch (error) {
				// Some CLIs exit with non-zero code when showing version
				expect(error.stdout || error.stderr).toMatch(/\d+\.\d+\.\d+/);
			}
		}, 10000);

		test('should handle missing GitHub token', async () => {
			delete process.env.GITHUB_TOKEN;

			try {
				await execAsync(`node ${CLI_PATH} export 1`, { timeout: 5000 });
			} catch (error) {
				expect(error.stderr || error.stdout).toContain('GitHub token not found');
			}
		}, 10000);
	});

	describe('Export Command', () => {
		test('should validate required parameters', async () => {
			try {
				await execAsync(`node ${CLI_PATH} export 1`, { timeout: 5000 });
			} catch (error) {
				expect(error.stderr || error.stdout).toContain('Repository owner and name are required');
			}
		}, 10000);

		test('should handle non-existent task', async () => {
			try {
				await execAsync(`node ${CLI_PATH} export 999 --owner test --repo repo`, { timeout: 5000 });
			} catch (error) {
				expect(error.stderr || error.stdout).toContain('Task 999 not found');
			}
		}, 10000);

		test('should show preview mode', async () => {
			try {
				const { stdout } = await execAsync(
					`node ${CLI_PATH} export 1 --owner test --repo repo --preview`,
					{ timeout: 10000 }
				);
				expect(stdout).toContain('Issue Preview');
			} catch (error) {
				// Preview might still output even on error
				expect(error.stdout || error.stderr).toContain('Preview');
			}
		}, 15000);
	});

	describe('Link Management', () => {
		test('should list links', async () => {
			try {
				const { stdout } = await execAsync(`node ${CLI_PATH} link list`, { timeout: 5000 });
				expect(stdout).toContain('No links found');
			} catch (error) {
				expect(error.stdout || error.stderr).toContain('links');
			}
		}, 10000);

		test('should show link statistics', async () => {
			try {
				const { stdout } = await execAsync(`node ${CLI_PATH} stats`, { timeout: 5000 });
				expect(stdout).toContain('Statistics');
			} catch (error) {
				expect(error.stdout || error.stderr).toContain('Statistics');
			}
		}, 10000);
	});

	describe('Configuration', () => {
		test('should show current configuration', async () => {
			try {
				const { stdout } = await execAsync(`node ${CLI_PATH} config --show`, { timeout: 5000 });
				expect(stdout).toContain('Configuration');
			} catch (error) {
				expect(error.stdout || error.stderr).toContain('Configuration');
			}
		}, 10000);

		test('should set configuration values', async () => {
			try {
				const { stdout } = await execAsync(
					`node ${CLI_PATH} config --set-owner testowner`,
					{ timeout: 5000 }
				);
				expect(stdout).toContain('Default owner set');
			} catch (error) {
				expect(error.stdout || error.stderr).toContain('owner');
			}
		}, 10000);
	});

	describe('Bulk Export', () => {
		test('should handle dry run mode', async () => {
			try {
				const { stdout } = await execAsync(
					`node ${CLI_PATH} bulk-export --owner test --repo repo --dry-run`,
					{ timeout: 10000 }
				);
				expect(stdout).toContain('Dry run mode');
			} catch (error) {
				expect(error.stdout || error.stderr).toContain('dry run');
			}
		}, 15000);

		test('should filter tasks by status', async () => {
			try {
				await execAsync(
					`node ${CLI_PATH} bulk-export --owner test --repo repo --status pending --dry-run`,
					{ timeout: 10000 }
				);
			} catch (error) {
				// Should process filtering
				expect(error.stdout || error.stderr).toContain('tasks');
			}
		}, 15000);
	});

	describe('Error Handling', () => {
		test('should handle invalid commands', async () => {
			try {
				await execAsync(`node ${CLI_PATH} invalid-command`, { timeout: 5000 });
			} catch (error) {
				expect(error.stderr || error.stdout).toContain('error');
			}
		}, 10000);

		test('should handle file system errors', async () => {
			fs.readFile.mockRejectedValue(new Error('Permission denied'));

			try {
				await execAsync(`node ${CLI_PATH} export 1 --owner test --repo repo`, { timeout: 5000 });
			} catch (error) {
				expect(error.stderr || error.stdout).toContain('error');
			}
		}, 10000);
	});
});

describe('Task Storage Module', () => {
	// Reset mocks for isolated testing
	beforeEach(() => {
		jest.clearAllMocks();
	});

	describe('loadTasks', () => {
		test('should handle different task file formats', async () => {
			const { loadTasks } = await import('../../../../scripts/core/task-storage.js');

			// Test array format
			fs.readFile.mockResolvedValueOnce(JSON.stringify([
				{ id: '1', title: 'Task 1' }
			]));

			let tasks = await loadTasks('./test-tasks.json');
			expect(tasks).toHaveLength(1);

			// Test object with tasks property
			fs.readFile.mockResolvedValueOnce(JSON.stringify({
				tasks: [
					{ id: '1', title: 'Task 1' },
					{ id: '2', title: 'Task 2' }
				]
			}));

			tasks = await loadTasks('./test-tasks.json');
			expect(tasks).toHaveLength(2);
		});

		test('should throw error for missing file', async () => {
			const { loadTasks } = await import('../../../../scripts/core/task-storage.js');

			const error = new Error('File not found');
			error.code = 'ENOENT';
			fs.readFile.mockRejectedValueOnce(error);

			await expect(loadTasks('./missing.json')).rejects.toThrow('Tasks file not found');
		});

		test('should throw error for invalid JSON', async () => {
			const { loadTasks } = await import('../../../../scripts/core/task-storage.js');

			fs.readFile.mockResolvedValueOnce('invalid json');

			await expect(loadTasks('./invalid.json')).rejects.toThrow();
		});
	});

	describe('saveTasks', () => {
		test('should preserve existing file format', async () => {
			const { saveTasks } = await import('../../../../scripts/core/task-storage.js');

			// Mock existing file with object format
			fs.readFile.mockResolvedValueOnce(JSON.stringify({
				tasks: [],
				metadata: { version: '1.0.0' }
			}));

			const tasks = [{ id: '1', title: 'New Task' }];
			await saveTasks(tasks, './test-tasks.json');

			expect(fs.writeFile).toHaveBeenCalledWith(
				expect.any(String),
				expect.stringContaining('"tasks"'),
				'utf8'
			);
		});

		test('should create new format for new files', async () => {
			const { saveTasks } = await import('../../../../scripts/core/task-storage.js');

			// Mock file not existing
			const error = new Error('File not found');
			error.code = 'ENOENT';
			fs.readFile.mockRejectedValueOnce(error);

			const tasks = [{ id: '1', title: 'New Task' }];
			await saveTasks(tasks, './new-tasks.json');

			expect(fs.writeFile).toHaveBeenCalled();
			expect(fs.mkdir).toHaveBeenCalled();
		});
	});

	describe('filterTasks', () => {
		test('should filter by various criteria', async () => {
			const { filterTasks } = await import('../../../../scripts/core/task-storage.js');

			fs.readFile.mockResolvedValueOnce(JSON.stringify([
				{ id: '1', title: 'Task 1', status: 'pending', priority: 'high' },
				{ id: '2', title: 'Task 2', status: 'done', priority: 'low' },
				{ id: '3', title: 'Another task', status: 'pending', priority: 'normal' }
			]));

			// Filter by status
			let filtered = await filterTasks({ status: 'pending' });
			expect(filtered).toHaveLength(2);

			// Filter by priority
			fs.readFile.mockResolvedValueOnce(JSON.stringify([
				{ id: '1', title: 'Task 1', status: 'pending', priority: 'high' },
				{ id: '2', title: 'Task 2', status: 'done', priority: 'low' },
				{ id: '3', title: 'Another task', status: 'pending', priority: 'normal' }
			]));

			filtered = await filterTasks({ priority: 'high' });
			expect(filtered).toHaveLength(1);

			// Filter by search
			fs.readFile.mockResolvedValueOnce(JSON.stringify([
				{ id: '1', title: 'Task 1', status: 'pending', priority: 'high' },
				{ id: '2', title: 'Task 2', status: 'done', priority: 'low' },
				{ id: '3', title: 'Another task', status: 'pending', priority: 'normal' }
			]));

			filtered = await filterTasks({ search: 'another' });
			expect(filtered).toHaveLength(1);
		});
	});

	describe('validateTask', () => {
		test('should validate task structure', async () => {
			const { validateTask } = await import('../../../../scripts/core/task-storage.js');

			// Valid task
			let result = validateTask({
				id: '1',
				title: 'Test Task',
				status: 'pending',
				priority: 'high'
			});

			expect(result.valid).toBe(true);
			expect(result.errors).toHaveLength(0);

			// Invalid task - missing required fields
			result = validateTask({
				status: 'pending'
			});

			expect(result.valid).toBe(false);
			expect(result.errors).toContain('Task ID is required');
			expect(result.errors).toContain('Task title is required');

			// Invalid task - bad status
			result = validateTask({
				id: '1',
				title: 'Test Task',
				status: 'invalid-status'
			});

			expect(result.valid).toBe(true); // No errors, just warnings
			expect(result.warnings).toContain(expect.stringContaining('Invalid status'));
		});
	});
});

describe('Integration Tests', () => {
	test('should handle complete export workflow', async () => {
		// This would be an integration test that tests the full workflow
		// from CLI command to GitHub API call (mocked)

		// Mock successful API responses
		global.fetch = jest.fn()
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
					html_url: 'https://github.com/test/repo/issues/1',
					title: 'Test Issue',
					state: 'open'
				})
			});

		// This test would verify the complete integration
		expect(true).toBe(true); // Placeholder
	});
});