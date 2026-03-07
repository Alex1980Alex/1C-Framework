/**
 * task-github-formatter.test.js
 * Unit tests for Task-to-GitHub Content Formatter
 * Part of Task #101.2 - Create Task-to-GitHub Content Formatter
 */

import { jest } from '@jest/globals';
import { TaskGitHubFormatter } from '../../../../../scripts/modules/github/task-github-formatter.js';

describe('TaskGitHubFormatter', () => {
	let formatter;

	const mockTask = {
		id: '1',
		title: 'Implement user authentication',
		description: 'Set up JWT-based authentication system with login and logout functionality',
		details: 'Use bcrypt for password hashing, JWT for token generation, and implement proper session management.',
		priority: 'high',
		status: 'pending',
		complexity: 'medium',
		estimatedHours: 8,
		subtasks: [
			{ id: '1.1', title: 'Set up JWT library', status: 'done' },
			{ id: '1.2', title: 'Implement login endpoint', status: 'pending' },
			{ id: '1.3', title: 'Add session management', status: 'pending' }
		],
		dependencies: ['2', '3'],
		testStrategy: 'Unit tests for auth functions, integration tests for login flow',
		acceptanceCriteria: [
			'Users can log in with valid credentials',
			'Invalid credentials are rejected',
			'Sessions expire after timeout'
		],
		userStory: 'As a user, I want to securely log into the application',
		businessValue: 'Enables secure access control for the platform'
	};

	beforeEach(() => {
		formatter = new TaskGitHubFormatter();
	});

	describe('Constructor', () => {
		test('should create formatter with default options', () => {
			expect(formatter.options.defaultTemplate).toBe('standard');
			expect(formatter.options.includeMetadata).toBe(true);
			expect(formatter.options.maxBodyLength).toBe(65536);
		});

		test('should accept custom options', () => {
			const customFormatter = new TaskGitHubFormatter({
				defaultTemplate: 'minimal',
				enableEmoji: true,
				maxBodyLength: 1000
			});

			expect(customFormatter.options.defaultTemplate).toBe('minimal');
			expect(customFormatter.options.enableEmoji).toBe(true);
			expect(customFormatter.options.maxBodyLength).toBe(1000);
		});

		test('should have all predefined templates', () => {
			expect(formatter.templates).toHaveProperty('standard');
			expect(formatter.templates).toHaveProperty('detailed');
			expect(formatter.templates).toHaveProperty('minimal');
			expect(formatter.templates).toHaveProperty('bug');
			expect(formatter.templates).toHaveProperty('feature');
			expect(formatter.templates).toHaveProperty('epic');
		});
	});

	describe('formatTask', () => {
		test('should format basic task with standard template', () => {
			const result = formatter.formatTask(mockTask);

			expect(result).toHaveProperty('title');
			expect(result).toHaveProperty('body');
			expect(result).toHaveProperty('labels');
			expect(result).toHaveProperty('metadata');
			expect(result.metadata.taskId).toBe('1');
			expect(result.metadata.template).toBe('standard');
		});

		test('should use custom title when provided', () => {
			const result = formatter.formatTask(mockTask, {
				title: 'Custom Issue Title'
			});

			expect(result.title).toBe('Custom Issue Title');
		});

		test('should include assignees and milestone when provided', () => {
			const result = formatter.formatTask(mockTask, {
				assignees: ['user1', 'user2'],
				milestone: 5
			});

			expect(result.assignees).toEqual(['user1', 'user2']);
			expect(result.milestone).toBe(5);
		});
	});

	describe('generateTitle', () => {
		test('should generate simple title', () => {
			const title = formatter.generateTitle(mockTask, { titlePattern: 'simple' });
			expect(title).toBe('Implement user authentication');
		});

		test('should generate prefixed title', () => {
			const title = formatter.generateTitle(mockTask, { titlePattern: 'prefixed' });
			expect(title).toBe('[Task 1] Implement user authentication');
		});

		test('should generate typed title', () => {
			const title = formatter.generateTitle(mockTask, { titlePattern: 'typed' });
			expect(title).toBe('[ENHANCEMENT] Implement user authentication');
		});

		test('should generate priority title', () => {
			const title = formatter.generateTitle(mockTask, { titlePattern: 'priority' });
			expect(title).toBe('[HIGH] Implement user authentication');
		});

		test('should generate status title', () => {
			const title = formatter.generateTitle(mockTask, { titlePattern: 'status' });
			expect(title).toBe('[PENDING] Implement user authentication');
		});

		test('should use custom title when provided', () => {
			const title = formatter.generateTitle(mockTask, { title: 'Custom Title' });
			expect(title).toBe('Custom Title');
		});
	});

	describe('generateBody', () => {
		test('should generate body with standard template', () => {
			const template = formatter.getTemplate('standard');
			const body = formatter.generateBody(mockTask, template, {});

			expect(body).toContain('# Implement user authentication');
			expect(body).toContain('**Task Master ID**: 1');
			expect(body).toContain('**Priority**: high');
			expect(body).toContain('## Description');
			expect(body).toContain('JWT-based authentication system');
			expect(body).toContain('## Implementation Details');
			expect(body).toContain('bcrypt for password hashing');
			expect(body).toContain('## Subtasks');
			expect(body).toContain('- [x] Set up JWT library');
			expect(body).toContain('- [ ] Implement login endpoint');
			expect(body).toContain('## Dependencies');
			expect(body).toContain('- Task #2');
			expect(body).toContain('*Exported from Task Master*');
		});

		test('should generate body with minimal template', () => {
			const template = formatter.getTemplate('minimal');
			const body = formatter.generateBody(mockTask, template, {});

			expect(body).toContain('# Implement user authentication');
			expect(body).toContain('**Task Master ID**: 1');
			expect(body).toContain('## Description');
			expect(body).toContain('## Tasks');
			expect(body).not.toContain('## Implementation Details');
			expect(body).not.toContain('## Testing Strategy');
		});

		test('should include emoji when enabled', () => {
			const template = formatter.getTemplate('standard');
			const body = formatter.generateBody(mockTask, template, { enableEmoji: true });

			expect(body).toContain('✨ Implement user authentication');
		});

		test('should include project name in footer', () => {
			const template = formatter.getTemplate('standard');
			const body = formatter.generateBody(mockTask, template, { projectName: 'My Project' });

			expect(body).toContain('**Task Master Reference**: Task #1 in project "My Project"');
		});
	});

	describe('generateLabels', () => {
		test('should generate auto labels based on task properties', () => {
			const labels = formatter.generateLabels(mockTask, {});

			expect(labels).toContain('priority:high');
			expect(labels).toContain('complexity:medium');
			expect(labels).toContain('enhancement');
			expect(labels).toContain('size:medium');
		});

		test('should include custom labels', () => {
			const labels = formatter.generateLabels(mockTask, {
				labels: ['custom-label', 'team:backend']
			});

			expect(labels).toContain('custom-label');
			expect(labels).toContain('team:backend');
			expect(labels).toContain('priority:high');
		});

		test('should disable auto labels when requested', () => {
			const labels = formatter.generateLabels(mockTask, {
				autoLabels: false,
				labels: ['manual-label']
			});

			expect(labels).toEqual(['manual-label']);
		});
	});

	describe('detectTaskType', () => {
		test('should detect bug type', () => {
			const bugTask = { title: 'Fix login bug', description: 'Error in authentication' };
			const type = formatter.detectTaskType(bugTask);
			expect(type).toBe('bug');
		});

		test('should detect enhancement type', () => {
			const enhancementTask = { title: 'Add new feature', description: 'Implement dashboard' };
			const type = formatter.detectTaskType(enhancementTask);
			expect(type).toBe('enhancement');
		});

		test('should detect documentation type', () => {
			const docTask = { title: 'Update README', description: 'Document API endpoints' };
			const type = formatter.detectTaskType(docTask);
			expect(type).toBe('documentation');
		});

		test('should detect testing type', () => {
			const testTask = { title: 'Add unit tests', description: 'Test coverage for auth' };
			const type = formatter.detectTaskType(testTask);
			expect(type).toBe('testing');
		});

		test('should detect refactoring type', () => {
			const refactorTask = { title: 'Refactor auth module', description: 'Optimize performance' };
			const type = formatter.detectTaskType(refactorTask);
			expect(type).toBe('refactoring');
		});

		test('should return null for unknown type', () => {
			const unknownTask = { title: 'Generic task', description: 'Some work' };
			const type = formatter.detectTaskType(unknownTask);
			expect(type).toBeNull();
		});
	});

	describe('detectTaskSize', () => {
		test('should detect large size', () => {
			const largeTask = {
				estimatedHours: 50,
				subtasks: new Array(12).fill({}),
				details: 'Long implementation details...'
			};
			const size = formatter.detectTaskSize(largeTask);
			expect(size).toBe('size:large');
		});

		test('should detect medium size', () => {
			const mediumTask = {
				estimatedHours: 10,
				subtasks: new Array(5).fill({}),
				details: 'Medium length implementation details that are longer than 100 characters to trigger medium size detection'
			};
			const size = formatter.detectTaskSize(mediumTask);
			expect(size).toBe('size:medium');
		});

		test('should detect small size', () => {
			const smallTask = {
				estimatedHours: 1,
				subtasks: []
			};
			const size = formatter.detectTaskSize(smallTask);
			expect(size).toBe('size:small');
		});
	});

	describe('getTaskEmoji', () => {
		test('should return critical priority emoji', () => {
			const criticalTask = { ...mockTask, priority: 'critical' };
			const emoji = formatter.getTaskEmoji(criticalTask);
			expect(emoji).toBe('🚨 ');
		});

		test('should return high priority emoji', () => {
			const highTask = { ...mockTask, priority: 'high' };
			const emoji = formatter.getTaskEmoji(highTask);
			expect(emoji).toBe('⚡ ');
		});

		test('should return type-based emoji', () => {
			const bugTask = { title: 'Fix bug', description: 'Fix error' };
			const emoji = formatter.getTaskEmoji(bugTask);
			expect(emoji).toBe('🐛 ');
		});

		test('should return default emoji', () => {
			const genericTask = { title: 'Generic task' };
			const emoji = formatter.getTaskEmoji(genericTask);
			expect(emoji).toBe('📋 ');
		});
	});

	describe('formatText', () => {
		test('should normalize line endings', () => {
			const text = 'Line 1\r\nLine 2\rLine 3';
			const formatted = formatter.formatText(text, {});
			expect(formatted).toBe('Line 1\nLine 2\nLine 3');
		});

		test('should format code blocks', () => {
			const text = '```js\nconsole.log("hello");\n```';
			const formatted = formatter.formatText(text, {});
			expect(formatted).toContain('```js\nconsole.log("hello");\n```');
		});

		test('should fix list formatting', () => {
			const text = '  * Item 1\n  + Item 2\n  - Item 3';
			const formatted = formatter.formatText(text, {});
			expect(formatted).toContain('  - Item 1\n  - Item 2\n  - Item 3');
		});
	});

	describe('optimizeContent', () => {
		test('should return content unchanged if within limits', () => {
			const content = 'Short content';
			const optimized = formatter.optimizeContent(content, { maxBodyLength: 1000 });
			expect(optimized).toBe(content);
		});

		test('should apply smart truncation', () => {
			const longContent = 'A'.repeat(1000);
			const optimized = formatter.optimizeContent(longContent, {
				maxBodyLength: 500,
				truncateStrategy: 'smart'
			});

			expect(optimized.length).toBeLessThan(500);
			expect(optimized).toContain('[Content truncated - see full details in Task Master]');
		});

		test('should apply simple truncation', () => {
			const longContent = 'A'.repeat(1000);
			const optimized = formatter.optimizeContent(longContent, {
				maxBodyLength: 500,
				truncateStrategy: 'simple'
			});

			expect(optimized.length).toBeLessThan(500);
			expect(optimized).toContain('[Content truncated due to length limits]');
		});
	});

	describe('Templates', () => {
		test('should have standard template with correct sections', () => {
			const template = formatter.getTemplate('standard');

			expect(template.name).toBe('standard');
			expect(template.sections).toHaveLength(7);
			expect(template.sections[0].type).toBe('header');
			expect(template.sections[1].type).toBe('metadata');
			expect(template.sections[2].type).toBe('description');
		});

		test('should have detailed template with acceptance criteria', () => {
			const template = formatter.getTemplate('detailed');

			expect(template.name).toBe('detailed');
			expect(template.sections.some(s => s.type === 'acceptance')).toBe(true);
		});

		test('should have minimal template with fewer sections', () => {
			const template = formatter.getTemplate('minimal');

			expect(template.name).toBe('minimal');
			expect(template.sections).toHaveLength(4);
		});

		test('should have bug template with reproduction steps', () => {
			const template = formatter.getTemplate('bug');

			expect(template.name).toBe('bug');
			expect(template.sections.some(s => s.content && s.content.includes('Reproduction Steps'))).toBe(true);
		});

		test('should have feature template with user story', () => {
			const template = formatter.getTemplate('feature');

			expect(template.name).toBe('feature');
			expect(template.sections.some(s => s.content && s.content.includes('User Story'))).toBe(true);
		});

		test('should have epic template with business value', () => {
			const template = formatter.getTemplate('epic');

			expect(template.name).toBe('epic');
			expect(template.sections.some(s => s.content && s.content.includes('Business Value'))).toBe(true);
		});
	});

	describe('addCustomTemplate', () => {
		test('should add custom template', () => {
			const customConfig = {
				description: 'Custom test template',
				sections: [
					{ type: 'header', enabled: true },
					{ type: 'description', enabled: true }
				]
			};

			formatter.addCustomTemplate('custom', customConfig);

			expect(formatter.templates).toHaveProperty('custom');
			expect(formatter.templates.custom.description).toBe('Custom test template');
			expect(formatter.templates.custom.sections).toHaveLength(2);
		});
	});

	describe('preview', () => {
		test('should generate preview with statistics', () => {
			const preview = formatter.preview(mockTask);

			expect(preview).toHaveProperty('title');
			expect(preview).toHaveProperty('body');
			expect(preview).toHaveProperty('labels');
			expect(preview).toHaveProperty('stats');
			expect(preview.stats).toHaveProperty('titleLength');
			expect(preview.stats).toHaveProperty('bodyLength');
			expect(preview.stats).toHaveProperty('labelCount');
			expect(preview.stats).toHaveProperty('isWithinLimits');
			expect(preview.stats.isWithinLimits).toBe(true);
		});

		test('should detect when content exceeds limits', () => {
			const formatter = new TaskGitHubFormatter({ maxBodyLength: 100 });
			const preview = formatter.preview(mockTask);

			expect(preview.stats.isWithinLimits).toBe(false);
		});
	});

	describe('Section Generation', () => {
		test('should generate metadata section with selected fields', () => {
			const section = {
				type: 'metadata',
				enabled: true,
				fields: ['id', 'priority', 'status']
			};

			const content = formatter.generateSection(mockTask, section, { includeMetadata: true });

			expect(content).toContain('**Task Master ID**: 1');
			expect(content).toContain('**Priority**: high');
			expect(content).toContain('**Status**: pending');
			expect(content).not.toContain('**Complexity**');
		});

		test('should generate subtasks section with checkboxes', () => {
			const section = {
				type: 'subtasks',
				enabled: true,
				title: 'Subtasks'
			};

			const content = formatter.generateSection(mockTask, section, {});

			expect(content).toContain('## Subtasks');
			expect(content).toContain('- [x] Set up JWT library');
			expect(content).toContain('- [ ] Implement login endpoint');
		});

		test('should generate acceptance criteria as checklist', () => {
			const section = {
				type: 'acceptance',
				enabled: true,
				title: 'Acceptance Criteria'
			};

			const content = formatter.generateSection(mockTask, section, {});

			expect(content).toContain('## Acceptance Criteria');
			expect(content).toContain('- [ ] Users can log in with valid credentials');
			expect(content).toContain('- [ ] Invalid credentials are rejected');
		});

		test('should generate custom section with template variables', () => {
			const taskWithCustomFields = {
				...mockTask,
				userStory: 'As a user, I want to log in securely'
			};

			const section = {
				type: 'custom',
				enabled: true,
				content: '## User Story\n{{task.userStory}}'
			};

			const content = formatter.generateSection(taskWithCustomFields, section, {});

			expect(content).toContain('## User Story');
			expect(content).toContain('As a user, I want to log in securely');
		});

		test('should return null for disabled sections', () => {
			const section = {
				type: 'description',
				enabled: false
			};

			const content = formatter.generateSection(mockTask, section, {});
			expect(content).toBeNull();
		});

		test('should return null for missing data', () => {
			const taskWithoutDescription = { ...mockTask };
			delete taskWithoutDescription.description;

			const section = {
				type: 'description',
				enabled: true
			};

			const content = formatter.generateSection(taskWithoutDescription, section, {});
			expect(content).toBeNull();
		});
	});

	describe('Edge Cases', () => {
		test('should handle task without optional fields', () => {
			const minimalTask = {
				id: '1',
				title: 'Simple task'
			};

			const result = formatter.formatTask(minimalTask);

			expect(result.title).toBe('[Task 1] Simple task');
			expect(result.body).toContain('# Simple task');
			expect(result.labels).toBeInstanceOf(Array);
		});

		test('should handle empty subtasks array', () => {
			const taskWithEmptySubtasks = {
				...mockTask,
				subtasks: []
			};

			const result = formatter.formatTask(taskWithEmptySubtasks);
			expect(result.body).not.toContain('## Subtasks');
		});

		test('should handle null/undefined dependencies', () => {
			const taskWithoutDeps = {
				...mockTask,
				dependencies: null
			};

			const result = formatter.formatTask(taskWithoutDeps);
			expect(result.body).not.toContain('## Dependencies');
		});

		test('should handle very long content', () => {
			const taskWithLongContent = {
				...mockTask,
				description: 'A'.repeat(70000)
			};

			const result = formatter.formatTask(taskWithLongContent);
			expect(result.body.length).toBeLessThanOrEqual(65536);
		});
	});
});