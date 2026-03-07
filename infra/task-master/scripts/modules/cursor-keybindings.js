/**
 * cursor-keybindings.js
 * Cursor keybindings installation and management for Task Master
 */

import fs from 'fs';
import path from 'path';
import os from 'os';
import chalk from 'chalk';
import boxen from 'boxen';

/**
 * Detect the operating system and return Cursor keybindings path
 */
function getCursorKeybindingsPath() {
	const platform = os.platform();
	const homeDir = os.homedir();
	
	switch (platform) {
		case 'win32':
			return path.join(homeDir, 'AppData', 'Roaming', 'Cursor', 'User', 'keybindings.json');
		case 'darwin':
			return path.join(homeDir, 'Library', 'Application Support', 'Cursor', 'User', 'keybindings.json');
		case 'linux':
			return path.join(homeDir, '.config', 'Cursor', 'User', 'keybindings.json');
		default:
			throw new Error(`Unsupported operating system: ${platform}`);
	}
}

/**
 * Default Task Master keybindings for Cursor
 */
function getDefaultTaskMasterKeybindings() {
	return [
		{
			"key": "ctrl+shift+t ctrl+shift+n",
			"command": "workbench.action.terminal.sendSequence",
			"args": {
				"text": "npx task-master next --json\r"
			},
			"when": "terminalFocus",
			"description": "Task Master: Get next task (JSON)"
		},
		{
			"key": "ctrl+shift+t ctrl+shift+l",
			"command": "workbench.action.terminal.sendSequence",
			"args": {
				"text": "npx task-master list --json\r"
			},
			"when": "terminalFocus",
			"description": "Task Master: List all tasks (JSON)"
		},
		{
			"key": "ctrl+shift+t ctrl+shift+s",
			"command": "workbench.action.terminal.sendSequence",
			"args": {
				"text": "npx task-master show "
			},
			"when": "terminalFocus",
			"description": "Task Master: Show task details (enter ID)"
		},
		{
			"key": "ctrl+shift+t ctrl+shift+c",
			"command": "workbench.action.terminal.sendSequence",
			"args": {
				"text": "npx task-master set-status --id= --status=done"
			},
			"when": "terminalFocus",
			"description": "Task Master: Mark task as complete (enter ID)"
		},
		{
			"key": "ctrl+shift+t ctrl+shift+t",
			"command": "workbench.action.terminal.sendSequence",
			"args": {
				"text": "npx task-master tags --json\r"
			},
			"when": "terminalFocus",
			"description": "Task Master: List tags (JSON)"
		}
	];
}

/**
 * Create backup of existing keybindings file
 */
function createBackup(keybindingsPath) {
	const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
	const backupPath = `${keybindingsPath}.backup.${timestamp}`;
	
	if (fs.existsSync(keybindingsPath)) {
		fs.copyFileSync(keybindingsPath, backupPath);
		console.log(chalk.green(`✓ Backup created: ${backupPath}`));
		return backupPath;
	}
	
	return null;
}

/**
 * Read existing keybindings file
 */
function readExistingKeybindings(keybindingsPath) {
	if (!fs.existsSync(keybindingsPath)) {
		return [];
	}
	
	try {
		const content = fs.readFileSync(keybindingsPath, 'utf8');
		return JSON.parse(content);
	} catch (error) {
		console.warn(chalk.yellow(`Warning: Could not parse existing keybindings: ${error.message}`));
		return [];
	}
}

/**
 * Check if Task Master keybinding already exists
 */
function hasTaskMasterKeybinding(keybindings, newKeybinding) {
	return keybindings.some(kb => 
		kb.key === newKeybinding.key || 
		(kb.description && kb.description.includes('Task Master'))
	);
}

/**
 * Remove existing Task Master keybindings
 */
function removeExistingTaskMasterKeybindings(keybindings) {
	return keybindings.filter(kb => 
		!(kb.description && kb.description.includes('Task Master'))
	);
}

/**
 * Merge keybindings and handle duplicates
 */
function mergeKeybindings(existingKeybindings, newKeybindings, options = {}) {
	let merged = [...existingKeybindings];
	const { force = false } = options;
	
	if (force) {
		// Remove all existing Task Master keybindings
		merged = removeExistingTaskMasterKeybindings(merged);
	}
	
	const added = [];
	const skipped = [];
	
	for (const newKeybinding of newKeybindings) {
		if (!force && hasTaskMasterKeybinding(merged, newKeybinding)) {
			skipped.push(newKeybinding);
		} else {
			merged.push(newKeybinding);
			added.push(newKeybinding);
		}
	}
	
	return { merged, added, skipped };
}

/**
 * Write keybindings to file
 */
function writeKeybindings(keybindingsPath, keybindings) {
	const dir = path.dirname(keybindingsPath);
	
	// Create directory if it doesn't exist
	if (!fs.existsSync(dir)) {
		fs.mkdirSync(dir, { recursive: true });
		console.log(chalk.green(`✓ Created directory: ${dir}`));
	}
	
	const content = JSON.stringify(keybindings, null, 2);
	fs.writeFileSync(keybindingsPath, content, 'utf8');
}

/**
 * Parse custom key combinations from JSON string
 */
function parseCustomKeys(customKeysString) {
	try {
		const customKeys = JSON.parse(customKeysString);
		if (!Array.isArray(customKeys)) {
			throw new Error('Custom keys must be an array');
		}
		return customKeys;
	} catch (error) {
		throw new Error(`Invalid custom keys JSON: ${error.message}`);
	}
}

/**
 * Display installation summary
 */
function displaySummary(results, options = {}) {
	const { added, skipped, backupPath } = results;
	const { dryRun = false } = options;
	
	const title = dryRun ? 'DRY RUN - Keybindings Installation Preview' : 'Keybindings Installation Complete';
	
	let summary = '';
	
	if (added.length > 0) {
		summary += chalk.green(`✓ ${added.length} Task Master keybinding(s) ${dryRun ? 'would be added' : 'added'}\n`);
		added.forEach(kb => {
			summary += chalk.gray(`  - ${kb.key}: ${kb.description}\n`);
		});
	}
	
	if (skipped.length > 0) {
		summary += chalk.yellow(`⚠ ${skipped.length} keybinding(s) ${dryRun ? 'would be skipped' : 'skipped'} (already exist)\n`);
		skipped.forEach(kb => {
			summary += chalk.gray(`  - ${kb.key}: ${kb.description}\n`);
		});
	}
	
	if (backupPath && !dryRun) {
		summary += chalk.blue(`📁 Backup created: ${path.basename(backupPath)}\n`);
	}
	
	if (!dryRun) {
		summary += '\n' + chalk.green('Task Master keybindings are now available in Cursor!');
		summary += '\n' + chalk.gray('Restart Cursor to ensure all keybindings are loaded.');
	} else {
		summary += '\n' + chalk.blue('Use --force to overwrite existing Task Master keybindings');
	}
	
	console.log(boxen(summary, {
		padding: 1,
		borderColor: dryRun ? 'blue' : 'green',
		borderStyle: 'round',
		title: title,
		titleAlignment: 'center'
	}));
}

/**
 * Main function to install Cursor keybindings
 */
async function installCursorKeybindings(options = {}) {
	const {
		dryRun = false,
		backup = true,
		customKeys = null,
		force = false
	} = options;
	
	console.log(chalk.blue('🔧 Installing Task Master keybindings for Cursor...'));
	
	// Detect OS and get keybindings path
	const keybindingsPath = getCursorKeybindingsPath();
	console.log(chalk.gray(`Keybindings file: ${keybindingsPath}`));
	
	// Get keybindings to install
	let keybindingsToInstall = getDefaultTaskMasterKeybindings();
	
	if (customKeys) {
		const custom = parseCustomKeys(customKeys);
		keybindingsToInstall = [...keybindingsToInstall, ...custom];
	}
	
	// Read existing keybindings
	const existingKeybindings = readExistingKeybindings(keybindingsPath);
	console.log(chalk.gray(`Found ${existingKeybindings.length} existing keybinding(s)`));
	
	// Create backup if requested and file exists
	let backupPath = null;
	if (backup && !dryRun && fs.existsSync(keybindingsPath)) {
		backupPath = createBackup(keybindingsPath);
	}
	
	// Merge keybindings
	const { merged, added, skipped } = mergeKeybindings(
		existingKeybindings, 
		keybindingsToInstall, 
		{ force }
	);
	
	// Write new keybindings (unless dry run)
	if (!dryRun) {
		writeKeybindings(keybindingsPath, merged);
		console.log(chalk.green(`✓ Keybindings written to: ${keybindingsPath}`));
	}
	
	// Display summary
	displaySummary({ added, skipped, backupPath }, { dryRun });
	
	return {
		success: true,
		keybindingsPath,
		added: added.length,
		skipped: skipped.length,
		backupPath,
		dryRun
	};
}

export {
	installCursorKeybindings,
	getCursorKeybindingsPath,
	getDefaultTaskMasterKeybindings
};