/**
 * link-manager.js
 * Bidirectional link management system for Task Master and GitHub Issues
 * Part of Task #101.3 - Build Bidirectional Link Management System
 */

import fs from 'fs/promises';
import path from 'path';

/**
 * Manages bidirectional links between Task Master tasks and GitHub issues
 * Provides persistent storage, conflict resolution, and synchronization capabilities
 */
export class GitHubLinkManager {
	constructor(options = {}) {
		this.options = {
			linkStorePath: options.linkStorePath || '.taskmaster/github-links.json',
			backupEnabled: options.backupEnabled !== false,
			maxBackups: options.maxBackups || 5,
			autoSync: options.autoSync !== false,
			conflictResolution: options.conflictResolution || 'manual',
			...options
		};

		// In-memory link store
		this.links = new Map();

		// Link metadata and statistics
		this.metadata = {
			lastSync: null,
			totalLinks: 0,
			activeLinks: 0,
			conflicts: [],
			lastUpdate: null
		};

		// Initialize if not already done
		this.initialized = false;
	}

	/**
	 * Initialize the link manager
	 * @returns {Promise<void>}
	 */
	async initialize() {
		if (this.initialized) return;

		try {
			await this.loadLinks();
			this.initialized = true;
		} catch (error) {
			// If file doesn't exist, create empty store
			if (error.code === 'ENOENT') {
				await this.saveLinks();
				this.initialized = true;
			} else {
				throw error;
			}
		}
	}

	/**
	 * Create a bidirectional link between a task and GitHub issue
	 * @param {string} taskId - Task Master task ID
	 * @param {Object} issueInfo - GitHub issue information
	 * @param {Object} options - Link creation options
	 * @returns {Promise<Object>} Link creation result
	 */
	async createLink(taskId, issueInfo, options = {}) {
		await this.initialize();

		const linkId = this.generateLinkId(taskId, issueInfo.owner, issueInfo.repo, issueInfo.number);

		// Check for existing links
		const existingLink = this.findLinkByTask(taskId) || this.findLinkByIssue(issueInfo);

		if (existingLink && !options.force) {
			return {
				success: false,
				error: 'Link already exists',
				existingLink,
				conflictType: 'duplicate_link'
			};
		}

		const link = {
			id: linkId,
			taskId,
			github: {
				owner: issueInfo.owner,
				repo: issueInfo.repo,
				number: issueInfo.number,
				url: issueInfo.url || this.buildIssueUrl(issueInfo.owner, issueInfo.repo, issueInfo.number),
				title: issueInfo.title,
				state: issueInfo.state || 'open'
			},
			metadata: {
				createdAt: new Date().toISOString(),
				createdBy: options.createdBy || 'system',
				exportOptions: options.exportOptions || {},
				lastSync: new Date().toISOString(),
				syncStatus: 'active',
				version: '1.0.0'
			},
			status: 'active'
		};

		// Handle existing link conflicts
		if (existingLink) {
			const resolution = await this.resolveConflict(existingLink, link, options);
			if (!resolution.proceed) {
				return {
					success: false,
					error: 'Conflict resolution failed',
					conflict: resolution,
					conflictType: 'resolution_failed'
				};
			}

			// Apply conflict resolution
			if (resolution.action === 'replace') {
				await this.removeLink(existingLink.id);
			} else if (resolution.action === 'merge') {
				link.metadata = { ...existingLink.metadata, ...link.metadata };
				await this.removeLink(existingLink.id);
			}
		}

		// Store the link
		this.links.set(linkId, link);
		this.updateMetadata();

		await this.saveLinks();

		return {
			success: true,
			link,
			linkId,
			action: existingLink ? 'replaced' : 'created'
		};
	}

	/**
	 * Remove a bidirectional link
	 * @param {string} linkId - Link ID to remove
	 * @param {Object} options - Removal options
	 * @returns {Promise<Object>} Removal result
	 */
	async removeLink(linkId, options = {}) {
		await this.initialize();

		const link = this.links.get(linkId);
		if (!link) {
			return {
				success: false,
				error: 'Link not found',
				linkId
			};
		}

		// Create backup if enabled
		if (this.options.backupEnabled) {
			await this.createBackup(`before_remove_${linkId}`);
		}

		// Mark as removed instead of deleting for audit trail
		if (options.softDelete !== false) {
			link.status = 'removed';
			link.metadata.removedAt = new Date().toISOString();
			link.metadata.removedBy = options.removedBy || 'system';
			link.metadata.removalReason = options.reason || 'manual_removal';
		} else {
			this.links.delete(linkId);
		}

		this.updateMetadata();
		await this.saveLinks();

		return {
			success: true,
			link,
			action: options.softDelete !== false ? 'soft_deleted' : 'permanently_deleted'
		};
	}

	/**
	 * Update an existing link
	 * @param {string} linkId - Link ID to update
	 * @param {Object} updates - Updates to apply
	 * @returns {Promise<Object>} Update result
	 */
	async updateLink(linkId, updates) {
		await this.initialize();

		const link = this.links.get(linkId);
		if (!link) {
			return {
				success: false,
				error: 'Link not found',
				linkId
			};
		}

		// Create backup before update
		if (this.options.backupEnabled) {
			await this.createBackup(`before_update_${linkId}`);
		}

		// Apply updates
		if (updates.github) {
			link.github = { ...link.github, ...updates.github };
		}

		if (updates.metadata) {
			link.metadata = { ...link.metadata, ...updates.metadata };
		}

		if (updates.status) {
			link.status = updates.status;
		}

		// Update sync timestamp
		link.metadata.lastSync = new Date().toISOString();
		link.metadata.lastUpdate = new Date().toISOString();

		this.updateMetadata();
		await this.saveLinks();

		return {
			success: true,
			link,
			action: 'updated'
		};
	}

	/**
	 * Find link by Task Master task ID
	 * @param {string} taskId - Task ID to search for
	 * @returns {Object|null} Found link or null
	 */
	findLinkByTask(taskId) {
		for (const link of this.links.values()) {
			if (link.taskId === taskId && link.status === 'active') {
				return link;
			}
		}
		return null;
	}

	/**
	 * Find link by GitHub issue information
	 * @param {Object} issueInfo - GitHub issue info
	 * @returns {Object|null} Found link or null
	 */
	findLinkByIssue(issueInfo) {
		for (const link of this.links.values()) {
			if (link.github.owner === issueInfo.owner &&
				link.github.repo === issueInfo.repo &&
				link.github.number === issueInfo.number &&
				link.status === 'active') {
				return link;
			}
		}
		return null;
	}

	/**
	 * Find link by URL
	 * @param {string} url - GitHub issue URL
	 * @returns {Object|null} Found link or null
	 */
	findLinkByUrl(url) {
		for (const link of this.links.values()) {
			if (link.github.url === url && link.status === 'active') {
				return link;
			}
		}
		return null;
	}

	/**
	 * Get all active links
	 * @param {Object} filters - Optional filters
	 * @returns {Array} Array of active links
	 */
	getAllLinks(filters = {}) {
		const allLinks = Array.from(this.links.values());

		let filteredLinks = allLinks.filter(link => {
			if (filters.status && link.status !== filters.status) return false;
			if (filters.owner && link.github.owner !== filters.owner) return false;
			if (filters.repo && link.github.repo !== filters.repo) return false;
			if (filters.taskPrefix && !link.taskId.startsWith(filters.taskPrefix)) return false;
			return true;
		});

		// Sort by creation date (newest first)
		filteredLinks.sort((a, b) =>
			new Date(b.metadata.createdAt) - new Date(a.metadata.createdAt)
		);

		return filteredLinks;
	}

	/**
	 * Synchronize links with GitHub state
	 * @param {Object} githubService - GitHub service instance
	 * @param {Object} options - Sync options
	 * @returns {Promise<Object>} Sync result
	 */
	async syncWithGitHub(githubService, options = {}) {
		await this.initialize();

		const syncResults = {
			success: true,
			synced: 0,
			failed: 0,
			conflicts: [],
			updates: [],
			errors: []
		};

		const activeLinks = this.getAllLinks({ status: 'active' });

		for (const link of activeLinks) {
			try {
				// Fetch current issue state from GitHub
				const issueData = await githubService.getIssue(
					link.github.owner,
					link.github.repo,
					link.github.number
				);

				// Check for differences
				const updates = {};
				let hasChanges = false;

				if (issueData.title !== link.github.title) {
					updates.title = issueData.title;
					hasChanges = true;
				}

				if (issueData.state !== link.github.state) {
					updates.state = issueData.state;
					hasChanges = true;
				}

				// Update link if changes detected
				if (hasChanges) {
					await this.updateLink(link.id, {
						github: updates,
						metadata: {
							lastSync: new Date().toISOString(),
							syncStatus: 'updated'
						}
					});

					syncResults.updates.push({
						linkId: link.id,
						taskId: link.taskId,
						updates
					});
				}

				syncResults.synced++;

			} catch (error) {
				syncResults.failed++;
				syncResults.errors.push({
					linkId: link.id,
					taskId: link.taskId,
					error: error.message
				});

				// Mark link as sync failed
				await this.updateLink(link.id, {
					metadata: {
						lastSync: new Date().toISOString(),
						syncStatus: 'failed',
						syncError: error.message
					}
				});
			}
		}

		// Update global sync metadata
		this.metadata.lastSync = new Date().toISOString();
		await this.saveLinks();

		return syncResults;
	}

	/**
	 * Resolve conflicts between existing and new links
	 * @param {Object} existingLink - Existing link
	 * @param {Object} newLink - New link being created
	 * @param {Object} options - Resolution options
	 * @returns {Promise<Object>} Conflict resolution result
	 */
	async resolveConflict(existingLink, newLink, options) {
		const conflict = {
			type: 'link_conflict',
			existingLink,
			newLink,
			timestamp: new Date().toISOString()
		};

		// Automatic resolution strategies
		switch (this.options.conflictResolution) {
			case 'replace_existing':
				return {
					proceed: true,
					action: 'replace',
					conflict
				};

			case 'merge_metadata':
				return {
					proceed: true,
					action: 'merge',
					conflict
				};

			case 'keep_existing':
				return {
					proceed: false,
					action: 'keep',
					conflict
				};

			case 'force_if_requested':
				if (options.force) {
					return {
						proceed: true,
						action: 'replace',
						conflict
					};
				}
				return {
					proceed: false,
					action: 'manual_required',
					conflict
				};

			case 'manual':
			default:
				// Store conflict for manual resolution
				this.metadata.conflicts.push(conflict);
				return {
					proceed: false,
					action: 'manual_required',
					conflict
				};
		}
	}

	/**
	 * Get statistics about links
	 * @returns {Object} Link statistics
	 */
	getStatistics() {
		const allLinks = Array.from(this.links.values());

		const stats = {
			total: allLinks.length,
			active: allLinks.filter(l => l.status === 'active').length,
			removed: allLinks.filter(l => l.status === 'removed').length,
			byRepository: {},
			byStatus: {},
			syncStatus: {},
			oldestLink: null,
			newestLink: null,
			conflictsCount: this.metadata.conflicts.length
		};

		// Group by repository
		allLinks.forEach(link => {
			if (link.status === 'active') {
				const repoKey = `${link.github.owner}/${link.github.repo}`;
				stats.byRepository[repoKey] = (stats.byRepository[repoKey] || 0) + 1;
			}
		});

		// Group by status
		allLinks.forEach(link => {
			stats.byStatus[link.status] = (stats.byStatus[link.status] || 0) + 1;
		});

		// Group by sync status
		allLinks.forEach(link => {
			const syncStatus = link.metadata.syncStatus || 'unknown';
			stats.syncStatus[syncStatus] = (stats.syncStatus[syncStatus] || 0) + 1;
		});

		// Find oldest and newest links
		if (allLinks.length > 0) {
			const activeLinks = allLinks.filter(l => l.status === 'active');
			if (activeLinks.length > 0) {
				activeLinks.sort((a, b) => new Date(a.metadata.createdAt) - new Date(b.metadata.createdAt));
				stats.oldestLink = activeLinks[0];
				stats.newestLink = activeLinks[activeLinks.length - 1];
			}
		}

		return stats;
	}

	/**
	 * Export links to various formats
	 * @param {string} format - Export format ('json', 'csv', 'markdown')
	 * @param {Object} options - Export options
	 * @returns {string} Exported data
	 */
	exportLinks(format = 'json', options = {}) {
		const links = this.getAllLinks(options.filters || {});

		switch (format) {
			case 'json':
				return JSON.stringify({
					metadata: this.metadata,
					links: links,
					exportedAt: new Date().toISOString(),
					count: links.length
				}, null, 2);

			case 'csv':
				return this.exportToCsv(links);

			case 'markdown':
				return this.exportToMarkdown(links);

			default:
				throw new Error(`Unsupported export format: ${format}`);
		}
	}

	/**
	 * Import links from external data
	 * @param {string} data - Data to import
	 * @param {string} format - Data format
	 * @param {Object} options - Import options
	 * @returns {Promise<Object>} Import result
	 */
	async importLinks(data, format = 'json', options = {}) {
		await this.initialize();

		const importResult = {
			success: true,
			imported: 0,
			skipped: 0,
			errors: [],
			conflicts: []
		};

		try {
			let linksToImport = [];

			switch (format) {
				case 'json':
					const jsonData = JSON.parse(data);
					linksToImport = jsonData.links || [];
					break;

				default:
					throw new Error(`Unsupported import format: ${format}`);
			}

			for (const linkData of linksToImport) {
				try {
					const result = await this.createLink(
						linkData.taskId,
						linkData.github,
						{
							force: options.force || false,
							createdBy: 'import',
							...linkData.metadata
						}
					);

					if (result.success) {
						importResult.imported++;
					} else {
						importResult.skipped++;
						if (result.conflictType) {
							importResult.conflicts.push({
								taskId: linkData.taskId,
								reason: result.error
							});
						}
					}

				} catch (error) {
					importResult.errors.push({
						taskId: linkData.taskId,
						error: error.message
					});
				}
			}

		} catch (error) {
			importResult.success = false;
			importResult.errors.push({
				general: error.message
			});
		}

		return importResult;
	}

	/**
	 * Generate unique link ID
	 * @param {string} taskId - Task ID
	 * @param {string} owner - Repository owner
	 * @param {string} repo - Repository name
	 * @param {number} number - Issue number
	 * @returns {string} Generated link ID
	 */
	generateLinkId(taskId, owner, repo, number) {
		return `${taskId}:${owner}/${repo}#${number}`;
	}

	/**
	 * Build GitHub issue URL
	 * @param {string} owner - Repository owner
	 * @param {string} repo - Repository name
	 * @param {number} number - Issue number
	 * @returns {string} GitHub issue URL
	 */
	buildIssueUrl(owner, repo, number) {
		return `https://github.com/${owner}/${repo}/issues/${number}`;
	}

	/**
	 * Update metadata statistics
	 */
	updateMetadata() {
		const allLinks = Array.from(this.links.values());
		this.metadata.totalLinks = allLinks.length;
		this.metadata.activeLinks = allLinks.filter(l => l.status === 'active').length;
		this.metadata.lastUpdate = new Date().toISOString();
	}

	/**
	 * Load links from storage
	 * @returns {Promise<void>}
	 */
	async loadLinks() {
		const linkStorePath = path.resolve(this.options.linkStorePath);

		try {
			const data = await fs.readFile(linkStorePath, 'utf8');
			const parsed = JSON.parse(data);

			// Load links into Map
			this.links.clear();
			if (parsed.links) {
				for (const link of parsed.links) {
					this.links.set(link.id, link);
				}
			}

			// Load metadata
			this.metadata = {
				...this.metadata,
				...parsed.metadata
			};

		} catch (error) {
			if (error.code !== 'ENOENT') {
				throw error;
			}
		}
	}

	/**
	 * Save links to storage
	 * @returns {Promise<void>}
	 */
	async saveLinks() {
		const linkStorePath = path.resolve(this.options.linkStorePath);

		// Ensure directory exists
		await fs.mkdir(path.dirname(linkStorePath), { recursive: true });

		const data = {
			metadata: this.metadata,
			links: Array.from(this.links.values()),
			version: '1.0.0',
			savedAt: new Date().toISOString()
		};

		await fs.writeFile(linkStorePath, JSON.stringify(data, null, 2), 'utf8');
	}

	/**
	 * Create backup of current state
	 * @param {string} reason - Backup reason
	 * @returns {Promise<string>} Backup file path
	 */
	async createBackup(reason = 'manual') {
		const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
		const backupPath = `${this.options.linkStorePath}.backup.${timestamp}.${reason}.json`;

		const data = {
			metadata: this.metadata,
			links: Array.from(this.links.values()),
			backup: {
				reason,
				timestamp,
				version: '1.0.0'
			}
		};

		await fs.writeFile(backupPath, JSON.stringify(data, null, 2), 'utf8');

		// Clean up old backups
		await this.cleanupBackups();

		return backupPath;
	}

	/**
	 * Clean up old backup files
	 * @returns {Promise<void>}
	 */
	async cleanupBackups() {
		try {
			const dir = path.dirname(this.options.linkStorePath);
			const files = await fs.readdir(dir);
			const backupFiles = files
				.filter(f => f.includes('.backup.') && f.endsWith('.json'))
				.map(f => ({
					name: f,
					path: path.join(dir, f),
					stat: null
				}));

			// Get file stats
			for (const file of backupFiles) {
				try {
					file.stat = await fs.stat(file.path);
				} catch (error) {
					// Skip files that can't be read
				}
			}

			// Sort by modification time and keep only recent ones
			backupFiles
				.filter(f => f.stat)
				.sort((a, b) => b.stat.mtime - a.stat.mtime)
				.slice(this.options.maxBackups)
				.forEach(async (file) => {
					try {
						await fs.unlink(file.path);
					} catch (error) {
						// Ignore cleanup errors
					}
				});

		} catch (error) {
			// Ignore cleanup errors
		}
	}

	/**
	 * Export links to CSV format
	 * @param {Array} links - Links to export
	 * @returns {string} CSV data
	 */
	exportToCsv(links) {
		const headers = [
			'Task ID',
			'GitHub Owner',
			'GitHub Repo',
			'Issue Number',
			'Issue Title',
			'Issue State',
			'Issue URL',
			'Created At',
			'Last Sync',
			'Status'
		];

		const rows = links.map(link => [
			link.taskId,
			link.github.owner,
			link.github.repo,
			link.github.number,
			link.github.title || '',
			link.github.state,
			link.github.url,
			link.metadata.createdAt,
			link.metadata.lastSync,
			link.status
		]);

		const csvContent = [headers, ...rows]
			.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
			.join('\n');

		return csvContent;
	}

	/**
	 * Export links to Markdown format
	 * @param {Array} links - Links to export
	 * @returns {string} Markdown data
	 */
	exportToMarkdown(links) {
		const sections = [
			'# Task Master ↔ GitHub Links',
			'',
			`Generated on ${new Date().toLocaleString()}`,
			`Total links: ${links.length}`,
			''
		];

		if (links.length === 0) {
			sections.push('No links found.');
			return sections.join('\n');
		}

		sections.push('## Links');
		sections.push('');

		// Group by repository
		const byRepo = {};
		links.forEach(link => {
			const repoKey = `${link.github.owner}/${link.github.repo}`;
			if (!byRepo[repoKey]) byRepo[repoKey] = [];
			byRepo[repoKey].push(link);
		});

		Object.entries(byRepo).forEach(([repo, repoLinks]) => {
			sections.push(`### ${repo}`);
			sections.push('');

			repoLinks.forEach(link => {
				const status = link.github.state === 'open' ? '🟢' : '🔴';
				sections.push(`- ${status} **Task ${link.taskId}** → [#${link.github.number}](${link.github.url}) ${link.github.title || '(No title)'}`);
			});

			sections.push('');
		});

		return sections.join('\n');
	}
}

export default GitHubLinkManager;