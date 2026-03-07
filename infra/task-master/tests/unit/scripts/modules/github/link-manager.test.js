/**
 * link-manager.test.js
 * Unit tests for Bidirectional Link Management System
 * Part of Task #101.3 - Build Bidirectional Link Management System
 */

import { jest } from '@jest/globals';
import fs from 'fs/promises';
import path from 'path';
import { GitHubLinkManager } from '../../../../../scripts/modules/github/link-manager.js';

// Mock filesystem operations
jest.mock('fs/promises');

describe('GitHubLinkManager', () => {
	let linkManager;
	let mockGitHubService;

	const mockIssueInfo = {
		owner: 'testowner',
		repo: 'testrepo',
		number: 123,
		url: 'https://github.com/testowner/testrepo/issues/123',
		title: 'Test Issue',
		state: 'open'
	};

	const mockTaskId = '1.2.3';

	beforeEach(() => {
		jest.clearAllMocks();

		linkManager = new GitHubLinkManager({
			linkStorePath: './test-links.json',
			backupEnabled: false // Disable backups for tests
		});

		mockGitHubService = {
			getIssue: jest.fn()
		};

		// Mock successful file operations by default
		fs.readFile.mockResolvedValue(JSON.stringify({
			metadata: {
				lastSync: null,
				totalLinks: 0,
				activeLinks: 0,
				conflicts: [],
				lastUpdate: null
			},
			links: [],
			version: '1.0.0'
		}));

		fs.writeFile.mockResolvedValue();
		fs.mkdir.mockResolvedValue();
		fs.readdir.mockResolvedValue([]);
	});

	describe('Constructor', () => {
		test('should create link manager with default options', () => {
			const manager = new GitHubLinkManager();

			expect(manager.options.linkStorePath).toBe('.taskmaster/github-links.json');
			expect(manager.options.backupEnabled).toBe(true);
			expect(manager.options.maxBackups).toBe(5);
			expect(manager.options.autoSync).toBe(true);
			expect(manager.options.conflictResolution).toBe('manual');
		});

		test('should accept custom options', () => {
			const manager = new GitHubLinkManager({
				linkStorePath: './custom-links.json',
				backupEnabled: false,
				maxBackups: 10,
				conflictResolution: 'replace_existing'
			});

			expect(manager.options.linkStorePath).toBe('./custom-links.json');
			expect(manager.options.backupEnabled).toBe(false);
			expect(manager.options.maxBackups).toBe(10);
			expect(manager.options.conflictResolution).toBe('replace_existing');
		});

		test('should initialize with empty state', () => {
			expect(linkManager.links.size).toBe(0);
			expect(linkManager.metadata.totalLinks).toBe(0);
			expect(linkManager.metadata.activeLinks).toBe(0);
			expect(linkManager.initialized).toBe(false);
		});
	});

	describe('initialize', () => {
		test('should load existing links from file', async () => {
			const existingData = {
				metadata: { totalLinks: 1, activeLinks: 1 },
				links: [{
					id: 'test:owner/repo#1',
					taskId: '1',
					github: { owner: 'owner', repo: 'repo', number: 1 },
					status: 'active'
				}]
			};

			fs.readFile.mockResolvedValueOnce(JSON.stringify(existingData));

			await linkManager.initialize();

			expect(linkManager.initialized).toBe(true);
			expect(linkManager.links.size).toBe(1);
			expect(linkManager.metadata.totalLinks).toBe(1);
		});

		test('should create empty store if file does not exist', async () => {
			const error = new Error('File not found');
			error.code = 'ENOENT';
			fs.readFile.mockRejectedValueOnce(error);

			await linkManager.initialize();

			expect(linkManager.initialized).toBe(true);
			expect(fs.writeFile).toHaveBeenCalled();
		});

		test('should throw error for other file system errors', async () => {
			const error = new Error('Permission denied');
			error.code = 'EACCES';
			fs.readFile.mockRejectedValueOnce(error);

			await expect(linkManager.initialize()).rejects.toThrow('Permission denied');
		});

		test('should not reinitialize if already initialized', async () => {
			await linkManager.initialize();
			const loadSpy = jest.spyOn(linkManager, 'loadLinks');

			await linkManager.initialize();

			expect(loadSpy).not.toHaveBeenCalled();
		});
	});

	describe('createLink', () => {
		beforeEach(async () => {
			await linkManager.initialize();
		});

		test('should create new link successfully', async () => {
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo);

			expect(result.success).toBe(true);
			expect(result.link.taskId).toBe(mockTaskId);
			expect(result.link.github.owner).toBe('testowner');
			expect(result.link.github.repo).toBe('testrepo');
			expect(result.link.github.number).toBe(123);
			expect(result.link.status).toBe('active');
			expect(result.action).toBe('created');
		});

		test('should generate correct link ID', async () => {
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo);

			expect(result.linkId).toBe('1.2.3:testowner/testrepo#123');
		});

		test('should build GitHub URL if not provided', async () => {
			const issueWithoutUrl = { ...mockIssueInfo };
			delete issueWithoutUrl.url;

			const result = await linkManager.createLink(mockTaskId, issueWithoutUrl);

			expect(result.link.github.url).toBe('https://github.com/testowner/testrepo/issues/123');
		});

		test('should reject duplicate links without force option', async () => {
			// Create first link
			await linkManager.createLink(mockTaskId, mockIssueInfo);

			// Try to create duplicate
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo);

			expect(result.success).toBe(false);
			expect(result.error).toBe('Link already exists');
			expect(result.conflictType).toBe('duplicate_link');
		});

		test('should replace existing link with force option', async () => {
			// Create first link
			await linkManager.createLink(mockTaskId, mockIssueInfo);

			// Force replace
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo, { force: true });

			expect(result.success).toBe(true);
			expect(result.action).toBe('replaced');
		});

		test('should include export options in metadata', async () => {
			const exportOptions = { template: 'bug', labels: ['critical'] };
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo, {
				exportOptions
			});

			expect(result.link.metadata.exportOptions).toEqual(exportOptions);
		});

		test('should set creation metadata', async () => {
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo, {
				createdBy: 'test-user'
			});

			expect(result.link.metadata.createdBy).toBe('test-user');
			expect(result.link.metadata.createdAt).toBeDefined();
			expect(result.link.metadata.lastSync).toBeDefined();
			expect(result.link.metadata.version).toBe('1.0.0');
		});
	});

	describe('removeLink', () => {
		let linkId;

		beforeEach(async () => {
			await linkManager.initialize();
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo);
			linkId = result.linkId;
		});

		test('should soft delete link by default', async () => {
			const result = await linkManager.removeLink(linkId);

			expect(result.success).toBe(true);
			expect(result.action).toBe('soft_deleted');

			const link = linkManager.links.get(linkId);
			expect(link.status).toBe('removed');
			expect(link.metadata.removedAt).toBeDefined();
		});

		test('should permanently delete with softDelete=false', async () => {
			const result = await linkManager.removeLink(linkId, { softDelete: false });

			expect(result.success).toBe(true);
			expect(result.action).toBe('permanently_deleted');
			expect(linkManager.links.has(linkId)).toBe(false);
		});

		test('should fail for non-existent link', async () => {
			const result = await linkManager.removeLink('non-existent');

			expect(result.success).toBe(false);
			expect(result.error).toBe('Link not found');
		});

		test('should include removal reason and user', async () => {
			const result = await linkManager.removeLink(linkId, {
				removedBy: 'test-user',
				reason: 'task_completed'
			});

			const link = linkManager.links.get(linkId);
			expect(link.metadata.removedBy).toBe('test-user');
			expect(link.metadata.removalReason).toBe('task_completed');
		});
	});

	describe('updateLink', () => {
		let linkId;

		beforeEach(async () => {
			await linkManager.initialize();
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo);
			linkId = result.linkId;
		});

		test('should update link successfully', async () => {
			const updates = {
				github: { state: 'closed', title: 'Updated Title' },
				metadata: { customField: 'value' }
			};

			const result = await linkManager.updateLink(linkId, updates);

			expect(result.success).toBe(true);
			expect(result.action).toBe('updated');

			const link = linkManager.links.get(linkId);
			expect(link.github.state).toBe('closed');
			expect(link.github.title).toBe('Updated Title');
			expect(link.metadata.customField).toBe('value');
			expect(link.metadata.lastUpdate).toBeDefined();
		});

		test('should fail for non-existent link', async () => {
			const result = await linkManager.updateLink('non-existent', {});

			expect(result.success).toBe(false);
			expect(result.error).toBe('Link not found');
		});

		test('should update sync timestamp', async () => {
			const originalSync = linkManager.links.get(linkId).metadata.lastSync;

			// Wait a bit to ensure timestamp difference
			await new Promise(resolve => setTimeout(resolve, 1));

			await linkManager.updateLink(linkId, { status: 'active' });

			const updatedSync = linkManager.links.get(linkId).metadata.lastSync;
			expect(updatedSync).not.toBe(originalSync);
		});
	});

	describe('findLinks', () => {
		beforeEach(async () => {
			await linkManager.initialize();

			// Create multiple test links
			await linkManager.createLink('1', { ...mockIssueInfo, number: 1 });
			await linkManager.createLink('2', { ...mockIssueInfo, number: 2, state: 'closed' });
			await linkManager.createLink('3', { owner: 'other', repo: 'repo', number: 3, state: 'open' });
		});

		test('should find link by task ID', () => {
			const link = linkManager.findLinkByTask('1');

			expect(link).toBeDefined();
			expect(link.taskId).toBe('1');
		});

		test('should find link by issue info', () => {
			const link = linkManager.findLinkByIssue({ ...mockIssueInfo, number: 2 });

			expect(link).toBeDefined();
			expect(link.github.number).toBe(2);
		});

		test('should find link by URL', () => {
			const url = 'https://github.com/testowner/testrepo/issues/1';
			const link = linkManager.findLinkByUrl(url);

			expect(link).toBeDefined();
			expect(link.github.number).toBe(1);
		});

		test('should return null for non-existent links', () => {
			expect(linkManager.findLinkByTask('999')).toBeNull();
			expect(linkManager.findLinkByIssue({ owner: 'none', repo: 'none', number: 999 })).toBeNull();
			expect(linkManager.findLinkByUrl('https://github.com/none/none/issues/999')).toBeNull();
		});
	});

	describe('getAllLinks', () => {
		beforeEach(async () => {
			await linkManager.initialize();

			// Create test links
			await linkManager.createLink('1', { ...mockIssueInfo, number: 1 });
			await linkManager.createLink('2', { ...mockIssueInfo, number: 2 });
			await linkManager.createLink('3', { owner: 'other', repo: 'other', number: 3 });

			// Remove one link
			const link2Id = '2:testowner/testrepo#2';
			await linkManager.removeLink(link2Id);
		});

		test('should return all active links by default', () => {
			const links = linkManager.getAllLinks();

			expect(links).toHaveLength(2);
			expect(links.every(l => l.status === 'active')).toBe(true);
		});

		test('should filter by status', () => {
			const removedLinks = linkManager.getAllLinks({ status: 'removed' });

			expect(removedLinks).toHaveLength(1);
			expect(removedLinks[0].status).toBe('removed');
		});

		test('should filter by owner', () => {
			const ownerLinks = linkManager.getAllLinks({ owner: 'testowner' });

			expect(ownerLinks).toHaveLength(1);
			expect(ownerLinks[0].github.owner).toBe('testowner');
		});

		test('should filter by repository', () => {
			const repoLinks = linkManager.getAllLinks({ repo: 'testrepo' });

			expect(repoLinks).toHaveLength(1);
			expect(repoLinks[0].github.repo).toBe('testrepo');
		});

		test('should filter by task prefix', () => {
			const prefixLinks = linkManager.getAllLinks({ taskPrefix: '1' });

			expect(prefixLinks).toHaveLength(1);
			expect(prefixLinks[0].taskId).toBe('1');
		});
	});

	describe('syncWithGitHub', () => {
		let linkId;

		beforeEach(async () => {
			await linkManager.initialize();
			const result = await linkManager.createLink(mockTaskId, mockIssueInfo);
			linkId = result.linkId;
		});

		test('should sync successfully with no changes', async () => {
			mockGitHubService.getIssue.mockResolvedValue({
				title: 'Test Issue',
				state: 'open'
			});

			const result = await linkManager.syncWithGitHub(mockGitHubService);

			expect(result.success).toBe(true);
			expect(result.synced).toBe(1);
			expect(result.failed).toBe(0);
			expect(result.updates).toHaveLength(0);
		});

		test('should detect and apply changes', async () => {
			mockGitHubService.getIssue.mockResolvedValue({
				title: 'Updated Issue Title',
				state: 'closed'
			});

			const result = await linkManager.syncWithGitHub(mockGitHubService);

			expect(result.success).toBe(true);
			expect(result.synced).toBe(1);
			expect(result.updates).toHaveLength(1);

			const update = result.updates[0];
			expect(update.updates.title).toBe('Updated Issue Title');
			expect(update.updates.state).toBe('closed');

			const link = linkManager.links.get(linkId);
			expect(link.github.title).toBe('Updated Issue Title');
			expect(link.github.state).toBe('closed');
		});

		test('should handle sync errors', async () => {
			mockGitHubService.getIssue.mockRejectedValue(new Error('API Error'));

			const result = await linkManager.syncWithGitHub(mockGitHubService);

			expect(result.success).toBe(true);
			expect(result.synced).toBe(0);
			expect(result.failed).toBe(1);
			expect(result.errors).toHaveLength(1);

			const link = linkManager.links.get(linkId);
			expect(link.metadata.syncStatus).toBe('failed');
			expect(link.metadata.syncError).toBe('API Error');
		});
	});

	describe('resolveConflict', () => {
		const existingLink = { id: 'existing', taskId: '1' };
		const newLink = { id: 'new', taskId: '1' };

		test('should resolve with replace_existing strategy', async () => {
			linkManager.options.conflictResolution = 'replace_existing';

			const result = await linkManager.resolveConflict(existingLink, newLink, {});

			expect(result.proceed).toBe(true);
			expect(result.action).toBe('replace');
		});

		test('should resolve with merge_metadata strategy', async () => {
			linkManager.options.conflictResolution = 'merge_metadata';

			const result = await linkManager.resolveConflict(existingLink, newLink, {});

			expect(result.proceed).toBe(true);
			expect(result.action).toBe('merge');
		});

		test('should resolve with keep_existing strategy', async () => {
			linkManager.options.conflictResolution = 'keep_existing';

			const result = await linkManager.resolveConflict(existingLink, newLink, {});

			expect(result.proceed).toBe(false);
			expect(result.action).toBe('keep');
		});

		test('should resolve with force_if_requested and force=true', async () => {
			linkManager.options.conflictResolution = 'force_if_requested';

			const result = await linkManager.resolveConflict(existingLink, newLink, { force: true });

			expect(result.proceed).toBe(true);
			expect(result.action).toBe('replace');
		});

		test('should require manual resolution by default', async () => {
			linkManager.options.conflictResolution = 'manual';

			const result = await linkManager.resolveConflict(existingLink, newLink, {});

			expect(result.proceed).toBe(false);
			expect(result.action).toBe('manual_required');
			expect(linkManager.metadata.conflicts).toHaveLength(1);
		});
	});

	describe('getStatistics', () => {
		beforeEach(async () => {
			await linkManager.initialize();

			// Create diverse test data
			await linkManager.createLink('1', { ...mockIssueInfo, number: 1 });
			await linkManager.createLink('2', { ...mockIssueInfo, number: 2 });
			await linkManager.createLink('3', { owner: 'other', repo: 'other', number: 3 });

			// Remove one link
			const linkId = '2:testowner/testrepo#2';
			await linkManager.removeLink(linkId);
		});

		test('should calculate correct statistics', () => {
			const stats = linkManager.getStatistics();

			expect(stats.total).toBe(3);
			expect(stats.active).toBe(2);
			expect(stats.removed).toBe(1);
			expect(stats.byRepository['testowner/testrepo']).toBe(1);
			expect(stats.byRepository['other/other']).toBe(1);
			expect(stats.byStatus.active).toBe(2);
			expect(stats.byStatus.removed).toBe(1);
		});

		test('should find oldest and newest links', () => {
			const stats = linkManager.getStatistics();

			expect(stats.oldestLink).toBeDefined();
			expect(stats.newestLink).toBeDefined();
			expect(stats.oldestLink.taskId).toBe('1');
			expect(stats.newestLink.taskId).toBe('3');
		});
	});

	describe('exportLinks', () => {
		beforeEach(async () => {
			await linkManager.initialize();
			await linkManager.createLink('1', { ...mockIssueInfo, number: 1 });
			await linkManager.createLink('2', { ...mockIssueInfo, number: 2 });
		});

		test('should export to JSON format', () => {
			const exported = linkManager.exportLinks('json');
			const data = JSON.parse(exported);

			expect(data.links).toHaveLength(2);
			expect(data.metadata).toBeDefined();
			expect(data.count).toBe(2);
			expect(data.exportedAt).toBeDefined();
		});

		test('should export to CSV format', () => {
			const exported = linkManager.exportLinks('csv');

			expect(exported).toContain('Task ID,GitHub Owner');
			expect(exported).toContain('testowner');
			expect(exported).toContain('testrepo');
		});

		test('should export to Markdown format', () => {
			const exported = linkManager.exportLinks('markdown');

			expect(exported).toContain('# Task Master ↔ GitHub Links');
			expect(exported).toContain('testowner/testrepo');
			expect(exported).toContain('Task 1');
		});

		test('should throw error for unsupported format', () => {
			expect(() => linkManager.exportLinks('xml')).toThrow('Unsupported export format: xml');
		});
	});

	describe('importLinks', () => {
		beforeEach(async () => {
			await linkManager.initialize();
		});

		test('should import valid JSON data', async () => {
			const importData = {
				links: [
					{
						taskId: '1',
						github: { owner: 'test', repo: 'repo', number: 1, state: 'open' },
						metadata: { createdBy: 'import' }
					}
				]
			};

			const result = await linkManager.importLinks(JSON.stringify(importData));

			expect(result.success).toBe(true);
			expect(result.imported).toBe(1);
			expect(result.skipped).toBe(0);
			expect(result.errors).toHaveLength(0);
		});

		test('should handle import conflicts', async () => {
			// Create existing link
			await linkManager.createLink('1', mockIssueInfo);

			const importData = {
				links: [
					{
						taskId: '1',
						github: mockIssueInfo,
						metadata: { createdBy: 'import' }
					}
				]
			};

			const result = await linkManager.importLinks(JSON.stringify(importData));

			expect(result.imported).toBe(0);
			expect(result.skipped).toBe(1);
			expect(result.conflicts).toHaveLength(1);
		});

		test('should handle invalid JSON', async () => {
			const result = await linkManager.importLinks('invalid json');

			expect(result.success).toBe(false);
			expect(result.errors).toHaveLength(1);
		});
	});

	describe('Utility Methods', () => {
		test('should generate correct link ID', () => {
			const linkId = linkManager.generateLinkId('1.2', 'owner', 'repo', 123);
			expect(linkId).toBe('1.2:owner/repo#123');
		});

		test('should build correct GitHub URL', () => {
			const url = linkManager.buildIssueUrl('owner', 'repo', 123);
			expect(url).toBe('https://github.com/owner/repo/issues/123');
		});

		test('should update metadata correctly', () => {
			linkManager.links.set('test1', { status: 'active' });
			linkManager.links.set('test2', { status: 'removed' });

			linkManager.updateMetadata();

			expect(linkManager.metadata.totalLinks).toBe(2);
			expect(linkManager.metadata.activeLinks).toBe(1);
			expect(linkManager.metadata.lastUpdate).toBeDefined();
		});
	});

	describe('File Operations', () => {
		test('should save links to file', async () => {
			await linkManager.initialize();
			await linkManager.createLink(mockTaskId, mockIssueInfo);

			await linkManager.saveLinks();

			expect(fs.writeFile).toHaveBeenCalledWith(
				expect.stringContaining('test-links.json'),
				expect.stringContaining('"links"'),
				'utf8'
			);
		});

		test('should create directory if it does not exist', async () => {
			await linkManager.saveLinks();

			expect(fs.mkdir).toHaveBeenCalledWith(
				expect.any(String),
				{ recursive: true }
			);
		});
	});
});