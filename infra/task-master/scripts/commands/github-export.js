#!/usr/bin/env node

/**
 * github-export.js
 * Comprehensive CLI interface for GitHub integration
 * Part of Task #101.4 - Create Comprehensive CLI Interface
 */

import { Command } from 'commander';
import chalk from 'chalk';
import inquirer from 'inquirer';
import ora from 'ora';
import Table from 'cli-table3';
import fs from 'fs/promises';
import path from 'path';

import { GitHubExportService, TaskGitHubFormatter, GitHubLinkManager } from '../modules/github/index.js';
import { loadTasks, saveTasks } from '../core/task-storage.js';

const program = new Command();

// Global configuration
let config = {
	githubToken: process.env.GITHUB_TOKEN,
	defaultOwner: null,
	defaultRepo: null,
	defaultTemplate: 'standard',
	linkStorePath: '.taskmaster/github-links.json'
};

/**
 * Load configuration from file or environment
 */
async function loadConfig() {
	try {
		const configPath = '.taskmaster/github-config.json';
		const configData = await fs.readFile(configPath, 'utf8');
		const fileConfig = JSON.parse(configData);
		config = { ...config, ...fileConfig };
	} catch (error) {
		// Config file doesn't exist, use defaults
	}

	// Validate required configuration
	if (!config.githubToken) {
		console.error(chalk.red('❌ GitHub token not found. Set GITHUB_TOKEN environment variable or use --token option.'));
		process.exit(1);
	}
}

/**
 * Save configuration to file
 */
async function saveConfig() {
	try {
		const configPath = '.taskmaster/github-config.json';
		await fs.mkdir(path.dirname(configPath), { recursive: true });
		await fs.writeFile(configPath, JSON.stringify(config, null, 2));
	} catch (error) {
		console.error(chalk.yellow('⚠️  Warning: Could not save configuration'));
	}
}

/**
 * Initialize services
 */
function initializeServices() {
	const githubService = new GitHubExportService(config.githubToken);
	const formatter = new TaskGitHubFormatter();
	const linkManager = new GitHubLinkManager({
		linkStorePath: config.linkStorePath
	});

	return { githubService, formatter, linkManager };
}

/**
 * Export single task command
 */
program
	.command('export <taskId>')
	.description('Export a specific task to GitHub issue')
	.option('-o, --owner <owner>', 'GitHub repository owner')
	.option('-r, --repo <repo>', 'GitHub repository name')
	.option('-t, --template <template>', 'Formatting template (standard, detailed, minimal, bug, feature, epic)', 'standard')
	.option('--title <title>', 'Custom issue title')
	.option('--labels <labels>', 'Comma-separated labels')
	.option('--assignees <assignees>', 'Comma-separated assignees')
	.option('--milestone <milestone>', 'Milestone number', parseInt)
	.option('--project <project>', 'Project name for reference')
	.option('--force', 'Force export even if task already linked')
	.option('--preview', 'Preview issue content without creating')
	.option('--token <token>', 'GitHub token (overrides config)')
	.action(async (taskId, options) => {
		try {
			if (options.token) config.githubToken = options.token;
			await loadConfig();

			const owner = options.owner || config.defaultOwner;
			const repo = options.repo || config.defaultRepo;

			if (!owner || !repo) {
				console.error(chalk.red('❌ Repository owner and name are required. Use --owner and --repo options or set defaults.'));
				process.exit(1);
			}

			const { githubService, formatter, linkManager } = initializeServices();
			await linkManager.initialize();

			// Load tasks
			const spinner = ora('Loading tasks...').start();
			const tasks = await loadTasks();
			const task = tasks.find(t => t.id === taskId);

			if (!task) {
				spinner.fail(`Task ${taskId} not found`);
				process.exit(1);
			}

			spinner.succeed(`Task ${taskId} loaded`);

			// Check for existing links
			const existingLink = linkManager.findLinkByTask(taskId);
			if (existingLink && !options.force) {
				console.log(chalk.yellow(`⚠️  Task ${taskId} is already linked to ${existingLink.github.url}`));
				const { proceed } = await inquirer.prompt([{
					type: 'confirm',
					name: 'proceed',
					message: 'Do you want to force export and replace the existing link?',
					default: false
				}]);

				if (!proceed) {
					console.log(chalk.gray('Export cancelled.'));
					process.exit(0);
				}
				options.force = true;
			}

			// Prepare export options
			const exportOptions = {
				template: options.template,
				title: options.title,
				labels: options.labels ? options.labels.split(',').map(l => l.trim()) : [],
				assignees: options.assignees ? options.assignees.split(',').map(a => a.trim()) : [],
				milestone: options.milestone,
				projectName: options.project,
				force: options.force
			};

			// Preview mode
			if (options.preview) {
				console.log(chalk.blue('\n📋 Issue Preview:'));
				const preview = formatter.preview(task, exportOptions);

				console.log(chalk.bold('\nTitle:'));
				console.log(preview.title);

				console.log(chalk.bold('\nLabels:'));
				console.log(preview.labels.join(', ') || 'None');

				console.log(chalk.bold('\nBody:'));
				console.log(preview.body);

				console.log(chalk.bold('\nStatistics:'));
				console.log(`- Title length: ${preview.stats.titleLength}`);
				console.log(`- Body length: ${preview.stats.bodyLength}`);
				console.log(`- Label count: ${preview.stats.labelCount}`);
				console.log(`- Within limits: ${preview.stats.isWithinLimits ? '✅' : '❌'}`);

				return;
			}

			// Export to GitHub
			spinner.start('Exporting to GitHub...');

			const result = await githubService.exportTask(task, owner, repo, exportOptions);

			if (result.success) {
				spinner.succeed('Export successful!');

				// Create bidirectional link
				const linkResult = await linkManager.createLink(taskId, {
					owner,
					repo,
					number: result.issue.number,
					url: result.issue.url,
					title: result.issue.title,
					state: result.issue.state
				}, {
					force: options.force,
					exportOptions,
					createdBy: 'cli'
				});

				if (linkResult.success) {
					console.log(chalk.green(`✅ Bidirectional link created: ${linkResult.linkId}`));
				} else {
					console.log(chalk.yellow(`⚠️  Link creation failed: ${linkResult.error}`));
				}

				console.log(chalk.blue(`\n🔗 GitHub Issue: ${result.issue.url}`));
				console.log(chalk.gray(`   Issue #${result.issue.number}: ${result.issue.title}`));

			} else {
				spinner.fail('Export failed');
				console.error(chalk.red(`❌ ${result.error}`));
				process.exit(1);
			}

		} catch (error) {
			console.error(chalk.red(`❌ Export failed: ${error.message}`));
			process.exit(1);
		}
	});

/**
 * Bulk export command
 */
program
	.command('bulk-export')
	.description('Export multiple tasks to GitHub issues')
	.option('-o, --owner <owner>', 'GitHub repository owner')
	.option('-r, --repo <repo>', 'GitHub repository name')
	.option('-t, --template <template>', 'Formatting template', 'standard')
	.option('--filter <filter>', 'Task filter (status, priority, prefix)')
	.option('--status <status>', 'Export tasks with specific status')
	.option('--priority <priority>', 'Export tasks with specific priority')
	.option('--prefix <prefix>', 'Export tasks with ID prefix')
	.option('--labels <labels>', 'Comma-separated labels for all issues')
	.option('--project <project>', 'Project name for reference')
	.option('--dry-run', 'Show what would be exported without creating issues')
	.option('--force', 'Force export even if tasks already linked')
	.option('--token <token>', 'GitHub token')
	.action(async (options) => {
		try {
			if (options.token) config.githubToken = options.token;
			await loadConfig();

			const owner = options.owner || config.defaultOwner;
			const repo = options.repo || config.defaultRepo;

			if (!owner || !repo) {
				console.error(chalk.red('❌ Repository owner and name are required.'));
				process.exit(1);
			}

			const { githubService, formatter, linkManager } = initializeServices();
			await linkManager.initialize();

			// Load and filter tasks
			const spinner = ora('Loading tasks...').start();
			const allTasks = await loadTasks();

			let tasksToExport = allTasks.filter(task => {
				if (options.status && task.status !== options.status) return false;
				if (options.priority && task.priority !== options.priority) return false;
				if (options.prefix && !task.id.startsWith(options.prefix)) return false;

				// Skip already linked tasks unless force is specified
				if (!options.force && linkManager.findLinkByTask(task.id)) return false;

				return true;
			});

			spinner.succeed(`Found ${tasksToExport.length} tasks to export`);

			if (tasksToExport.length === 0) {
				console.log(chalk.yellow('No tasks found matching criteria.'));
				return;
			}

			// Show preview
			console.log(chalk.blue('\n📋 Tasks to export:'));
			const table = new Table({
				head: ['Task ID', 'Title', 'Status', 'Priority'],
				colWidths: [10, 50, 12, 12]
			});

			tasksToExport.forEach(task => {
				table.push([
					task.id,
					task.title.substring(0, 47) + (task.title.length > 47 ? '...' : ''),
					task.status || 'pending',
					task.priority || 'normal'
				]);
			});

			console.log(table.toString());

			if (options.dryRun) {
				console.log(chalk.gray('\n🔍 Dry run mode - no issues will be created.'));
				return;
			}

			// Confirm export
			const { confirm } = await inquirer.prompt([{
				type: 'confirm',
				name: 'confirm',
				message: `Export ${tasksToExport.length} tasks to ${owner}/${repo}?`,
				default: false
			}]);

			if (!confirm) {
				console.log(chalk.gray('Export cancelled.'));
				return;
			}

			// Export tasks
			const results = {
				successful: 0,
				failed: 0,
				errors: []
			};

			const exportOptions = {
				template: options.template,
				labels: options.labels ? options.labels.split(',').map(l => l.trim()) : [],
				projectName: options.project,
				force: options.force
			};

			for (const [index, task] of tasksToExport.entries()) {
				const taskSpinner = ora(`[${index + 1}/${tasksToExport.length}] Exporting ${task.id}...`).start();

				try {
					const result = await githubService.exportTask(task, owner, repo, exportOptions);

					if (result.success) {
						// Create link
						await linkManager.createLink(task.id, {
							owner,
							repo,
							number: result.issue.number,
							url: result.issue.url,
							title: result.issue.title,
							state: result.issue.state
						}, {
							force: options.force,
							exportOptions,
							createdBy: 'cli-bulk'
						});

						taskSpinner.succeed(`${task.id} → Issue #${result.issue.number}`);
						results.successful++;
					} else {
						taskSpinner.fail(`${task.id} failed: ${result.error}`);
						results.failed++;
						results.errors.push({ taskId: task.id, error: result.error });
					}

				} catch (error) {
					taskSpinner.fail(`${task.id} failed: ${error.message}`);
					results.failed++;
					results.errors.push({ taskId: task.id, error: error.message });
				}

				// Rate limiting delay
				await new Promise(resolve => setTimeout(resolve, 1000));
			}

			// Summary
			console.log(chalk.green(`\n✅ Export completed: ${results.successful} successful, ${results.failed} failed`));

			if (results.errors.length > 0) {
				console.log(chalk.red('\n❌ Failed exports:'));
				results.errors.forEach(({ taskId, error }) => {
					console.log(chalk.red(`   ${taskId}: ${error}`));
				});
			}

		} catch (error) {
			console.error(chalk.red(`❌ Bulk export failed: ${error.message}`));
			process.exit(1);
		}
	});

/**
 * Link management commands
 */
const linkCmd = program
	.command('link')
	.description('Manage bidirectional links between tasks and GitHub issues');

linkCmd
	.command('list')
	.description('List all task-GitHub links')
	.option('--status <status>', 'Filter by status (active, removed)')
	.option('--owner <owner>', 'Filter by repository owner')
	.option('--repo <repo>', 'Filter by repository name')
	.option('--format <format>', 'Output format (table, json, csv)', 'table')
	.action(async (options) => {
		try {
			const { linkManager } = initializeServices();
			await linkManager.initialize();

			const filters = {
				status: options.status || 'active',
				owner: options.owner,
				repo: options.repo
			};

			const links = linkManager.getAllLinks(filters);

			if (links.length === 0) {
				console.log(chalk.yellow('No links found matching criteria.'));
				return;
			}

			switch (options.format) {
				case 'json':
					console.log(JSON.stringify(links, null, 2));
					break;

				case 'csv':
					console.log(linkManager.exportLinks('csv', { filters }));
					break;

				case 'table':
				default:
					const table = new Table({
						head: ['Task ID', 'Repository', 'Issue #', 'Issue Title', 'State', 'Created'],
						colWidths: [10, 20, 8, 30, 8, 12]
					});

					links.forEach(link => {
						table.push([
							link.taskId,
							`${link.github.owner}/${link.github.repo}`,
							link.github.number,
							(link.github.title || '').substring(0, 27) + ((link.github.title || '').length > 27 ? '...' : ''),
							link.github.state,
							new Date(link.metadata.createdAt).toLocaleDateString()
						]);
					});

					console.log(table.toString());
					console.log(chalk.gray(`\nTotal: ${links.length} links`));
					break;
			}

		} catch (error) {
			console.error(chalk.red(`❌ Failed to list links: ${error.message}`));
			process.exit(1);
		}
	});

linkCmd
	.command('sync')
	.description('Synchronize links with GitHub state')
	.option('--owner <owner>', 'Sync links for specific owner')
	.option('--repo <repo>', 'Sync links for specific repository')
	.option('--token <token>', 'GitHub token')
	.action(async (options) => {
		try {
			if (options.token) config.githubToken = options.token;
			await loadConfig();

			const { githubService, linkManager } = initializeServices();
			await linkManager.initialize();

			const spinner = ora('Synchronizing with GitHub...').start();

			const result = await linkManager.syncWithGitHub(githubService, {
				owner: options.owner,
				repo: options.repo
			});

			spinner.succeed('Synchronization completed');

			console.log(chalk.green(`✅ Synced: ${result.synced} links`));
			console.log(chalk.red(`❌ Failed: ${result.failed} links`));

			if (result.updates.length > 0) {
				console.log(chalk.blue(`\n📝 Updates detected:`));
				result.updates.forEach(update => {
					console.log(chalk.blue(`   ${update.taskId}: ${JSON.stringify(update.updates)}`));
				});
			}

			if (result.errors.length > 0) {
				console.log(chalk.red(`\n❌ Sync errors:`));
				result.errors.forEach(error => {
					console.log(chalk.red(`   ${error.taskId}: ${error.error}`));
				});
			}

		} catch (error) {
			console.error(chalk.red(`❌ Sync failed: ${error.message}`));
			process.exit(1);
		}
	});

linkCmd
	.command('remove <taskId>')
	.description('Remove link for a specific task')
	.option('--permanent', 'Permanently delete link (default: soft delete)')
	.action(async (taskId, options) => {
		try {
			const { linkManager } = initializeServices();
			await linkManager.initialize();

			const link = linkManager.findLinkByTask(taskId);
			if (!link) {
				console.error(chalk.red(`❌ No link found for task ${taskId}`));
				process.exit(1);
			}

			const { confirm } = await inquirer.prompt([{
				type: 'confirm',
				name: 'confirm',
				message: `Remove link for task ${taskId} (${link.github.url})?`,
				default: false
			}]);

			if (!confirm) {
				console.log(chalk.gray('Operation cancelled.'));
				return;
			}

			const result = await linkManager.removeLink(link.id, {
				softDelete: !options.permanent,
				removedBy: 'cli',
				reason: 'manual_removal'
			});

			if (result.success) {
				console.log(chalk.green(`✅ Link removed (${result.action})`));
			} else {
				console.error(chalk.red(`❌ Failed to remove link: ${result.error}`));
			}

		} catch (error) {
			console.error(chalk.red(`❌ Failed to remove link: ${error.message}`));
			process.exit(1);
		}
	});

/**
 * Statistics command
 */
program
	.command('stats')
	.description('Show GitHub integration statistics')
	.action(async () => {
		try {
			const { linkManager } = initializeServices();
			await linkManager.initialize();

			const stats = linkManager.getStatistics();

			console.log(chalk.blue('\n📊 GitHub Integration Statistics\n'));

			// Overview
			console.log(chalk.bold('Overview:'));
			console.log(`  Total links: ${stats.total}`);
			console.log(`  Active links: ${stats.active}`);
			console.log(`  Removed links: ${stats.removed}`);
			console.log(`  Unresolved conflicts: ${stats.conflictsCount}`);

			// By repository
			if (Object.keys(stats.byRepository).length > 0) {
				console.log(chalk.bold('\nBy Repository:'));
				Object.entries(stats.byRepository).forEach(([repo, count]) => {
					console.log(`  ${repo}: ${count} links`);
				});
			}

			// By status
			console.log(chalk.bold('\nBy Status:'));
			Object.entries(stats.byStatus).forEach(([status, count]) => {
				console.log(`  ${status}: ${count} links`);
			});

			// By sync status
			if (Object.keys(stats.syncStatus).length > 0) {
				console.log(chalk.bold('\nSync Status:'));
				Object.entries(stats.syncStatus).forEach(([status, count]) => {
					console.log(`  ${status}: ${count} links`);
				});
			}

			// Timeline
			if (stats.oldestLink && stats.newestLink) {
				console.log(chalk.bold('\nTimeline:'));
				console.log(`  Oldest link: ${stats.oldestLink.taskId} (${new Date(stats.oldestLink.metadata.createdAt).toLocaleDateString()})`);
				console.log(`  Newest link: ${stats.newestLink.taskId} (${new Date(stats.newestLink.metadata.createdAt).toLocaleDateString()})`);
			}

		} catch (error) {
			console.error(chalk.red(`❌ Failed to get statistics: ${error.message}`));
			process.exit(1);
		}
	});

/**
 * Configuration command
 */
program
	.command('config')
	.description('Manage GitHub integration configuration')
	.option('--set-owner <owner>', 'Set default repository owner')
	.option('--set-repo <repo>', 'Set default repository name')
	.option('--set-template <template>', 'Set default template')
	.option('--show', 'Show current configuration')
	.action(async (options) => {
		try {
			await loadConfig();

			if (options.setOwner) {
				config.defaultOwner = options.setOwner;
				await saveConfig();
				console.log(chalk.green(`✅ Default owner set to: ${options.setOwner}`));
			}

			if (options.setRepo) {
				config.defaultRepo = options.setRepo;
				await saveConfig();
				console.log(chalk.green(`✅ Default repository set to: ${options.setRepo}`));
			}

			if (options.setTemplate) {
				config.defaultTemplate = options.setTemplate;
				await saveConfig();
				console.log(chalk.green(`✅ Default template set to: ${options.setTemplate}`));
			}

			if (options.show || (!options.setOwner && !options.setRepo && !options.setTemplate)) {
				console.log(chalk.blue('\n⚙️  Current Configuration:\n'));
				console.log(`  GitHub Token: ${config.githubToken ? '✅ Set' : '❌ Not set'}`);
				console.log(`  Default Owner: ${config.defaultOwner || 'Not set'}`);
				console.log(`  Default Repository: ${config.defaultRepo || 'Not set'}`);
				console.log(`  Default Template: ${config.defaultTemplate}`);
				console.log(`  Link Store Path: ${config.linkStorePath}`);
			}

		} catch (error) {
			console.error(chalk.red(`❌ Configuration failed: ${error.message}`));
			process.exit(1);
		}
	});

// Global options
program
	.version('1.0.0')
	.description('Task Master GitHub Integration CLI')
	.option('-v, --verbose', 'Verbose output')
	.option('--no-color', 'Disable colored output');

// Handle global options
program.hook('preAction', (thisCommand, actionCommand) => {
	if (thisCommand.opts().noColor) {
		chalk.level = 0;
	}
});

// Error handling
process.on('unhandledRejection', (error) => {
	console.error(chalk.red(`❌ Unhandled error: ${error.message}`));
	process.exit(1);
});

// Parse command line arguments
program.parse(process.argv);

// Show help if no command provided
if (!process.argv.slice(2).length) {
	program.outputHelp();
}