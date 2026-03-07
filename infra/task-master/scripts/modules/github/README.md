# GitHub Integration Module

## Overview

The GitHub integration module provides functionality for exporting Task Master tasks to GitHub issues with bidirectional linking capabilities. This module is part of Task #101 - Implement GitHub Issue Export Feature with Bidirectional Linking.

## Features

- **GitHub API Export Service**: Core service for exporting tasks to GitHub issues
- **Rate Limiting**: Respect GitHub API rate limits automatically
- **Error Handling**: Comprehensive error handling for various failure scenarios
- **Content Formatting**: Convert Task Master tasks to well-formatted GitHub issues
- **Bidirectional Linking**: Maintain links between tasks and GitHub issues
- **Validation**: Validate repositories, permissions, and input data

## Installation

The GitHub module is part of the Task Master package. No additional installation is required.

### Dependencies

- Node.js 16+ (for fetch API support)
- GitHub Personal Access Token with repository access

## Quick Start

```javascript
import { GitHubExportService, TaskGitHubFormatter } from './scripts/modules/github/index.js';

// Initialize the service with your GitHub token
const githubService = new GitHubExportService('your_github_token_here');

// Export a task to GitHub issue
const task = {
  id: '1',
  title: 'Implement user authentication',
  description: 'Add secure user authentication system',
  priority: 'high',
  status: 'pending'
};

const result = await githubService.exportTask(
  task,
  'owner',        // GitHub repository owner
  'repository',   // GitHub repository name
  {
    labels: ['enhancement', 'task-master'],
    assignees: ['developer1'],
    includeSubtasks: true
  }
);

if (result.success) {
  console.log(`Issue created: ${result.issue.url}`);
} else {
  console.error(`Export failed: ${result.error}`);
}
```

## API Reference

### GitHubExportService

#### Constructor

```javascript
new GitHubExportService(token, options = {})
```

**Parameters:**
- `token` (string): GitHub Personal Access Token
- `options` (object): Optional configuration
  - `baseURL` (string): GitHub API base URL (default: 'https://api.github.com')
  - `userAgent` (string): User agent for API requests

**Example:**
```javascript
const service = new GitHubExportService('ghp_your_token', {
  baseURL: 'https://api.github.example.com',
  userAgent: 'MyApp/1.0'
});
```

#### Methods

##### exportTask(task, repoOwner, repoName, exportOptions)

Export a Task Master task to GitHub issue.

**Parameters:**
- `task` (object): Task Master task object
- `repoOwner` (string): GitHub repository owner
- `repoName` (string): GitHub repository name
- `exportOptions` (object): Export configuration options

**Export Options:**
- `title` (string): Override issue title
- `labels` (array): GitHub labels to apply
- `assignees` (array): GitHub usernames to assign
- `milestone` (number): GitHub milestone ID
- `includeSubtasks` (boolean): Include subtasks as checklist
- `projectName` (string): Project name for reference
- `force` (boolean): Override existing GitHub links

**Returns:** Promise<Object>

**Example:**
```javascript
const result = await service.exportTask(
  task,
  'octocat',
  'Hello-World',
  {
    labels: ['bug', 'high-priority'],
    assignees: ['octocat'],
    includeSubtasks: true,
    force: false
  }
);
```

##### previewExport(task, options)

Preview issue content without creating it.

**Parameters:**
- `task` (object): Task Master task object
- `options` (object): Export options (same as exportTask)

**Returns:** Object with preview data

**Example:**
```javascript
const preview = service.previewExport(task, {
  labels: ['enhancement'],
  includeSubtasks: true
});

console.log('Issue Title:', preview.title);
console.log('Issue Body:', preview.body);
```

##### validateRepositoryAccess(repoOwner, repoName)

Validate repository access and permissions.

**Parameters:**
- `repoOwner` (string): Repository owner
- `repoName` (string): Repository name

**Returns:** Promise<void> (throws on validation failure)

### TaskGitHubFormatter

The `TaskGitHubFormatter` class provides advanced content formatting for converting Task Master tasks to GitHub-compatible markdown with customizable templates and formatting options.

#### Constructor

```javascript
new TaskGitHubFormatter(options = {})
```

**Parameters:**
- `options` (object): Optional configuration
  - `defaultTemplate` (string): Default template to use ('standard', 'detailed', 'minimal', 'bug', 'feature', 'epic')
  - `includeMetadata` (boolean): Include task metadata (default: true)
  - `markdownStyle` (string): Markdown style preference (default: 'github')
  - `maxBodyLength` (number): Maximum body length (default: 65536)
  - `truncateStrategy` (string): Truncation strategy ('smart', 'simple', 'summary')
  - `enableTables` (boolean): Enable table formatting (default: true)
  - `enableEmoji` (boolean): Enable emoji in headers (default: false)

**Example:**
```javascript
const formatter = new TaskGitHubFormatter({
  defaultTemplate: 'detailed',
  enableEmoji: true,
  maxBodyLength: 32000
});
```

#### Methods

##### formatTask(task, options)

Format a task using the specified template and options.

**Parameters:**
- `task` (object): Task Master task object
- `options` (object): Formatting options
  - `template` (string): Template to use for formatting
  - `title` (string): Custom title override
  - `titlePattern` (string): Title pattern ('simple', 'prefixed', 'typed', 'priority', 'status')
  - `labels` (array): Custom labels to include
  - `assignees` (array): GitHub usernames to assign
  - `milestone` (number): GitHub milestone ID
  - `autoLabels` (boolean): Auto-generate labels from task properties
  - `projectName` (string): Project name for reference

**Returns:** Object with formatted issue data

**Example:**
```javascript
const formatted = formatter.formatTask(task, {
  template: 'feature',
  titlePattern: 'typed',
  labels: ['frontend', 'high-priority'],
  enableEmoji: true,
  projectName: 'User Management System'
});
```

##### preview(task, options)

Preview formatting without applying length limits or optimizations.

**Parameters:**
- `task` (object): Task Master task object
- `options` (object): Formatting options (same as formatTask)

**Returns:** Object with preview data and statistics

**Example:**
```javascript
const preview = formatter.preview(task, { template: 'detailed' });
console.log(`Title: ${preview.title}`);
console.log(`Body length: ${preview.stats.bodyLength}`);
console.log(`Within limits: ${preview.stats.isWithinLimits}`);
```

##### addCustomTemplate(name, config)

Add a custom template configuration.

**Parameters:**
- `name` (string): Template name
- `config` (object): Template configuration
  - `description` (string): Template description
  - `sections` (array): Array of section configurations

**Example:**
```javascript
formatter.addCustomTemplate('sprint', {
  description: 'Sprint planning template',
  sections: [
    { type: 'header', enabled: true },
    { type: 'metadata', enabled: true, fields: ['id', 'priority', 'estimatedHours'] },
    { type: 'description', enabled: true },
    { type: 'subtasks', enabled: true, title: 'Sprint Tasks' }
  ]
});
```

#### Available Templates

- **standard**: Default template with all standard sections
- **detailed**: Comprehensive template with acceptance criteria and additional metadata
- **minimal**: Compact template with essential information only
- **bug**: Bug report template with reproduction steps and expected/actual behavior
- **feature**: Feature request template with user stories and acceptance criteria
- **epic**: Epic template for large initiatives with business value and success metrics

#### Template Sections

Templates are composed of sections that can be enabled/disabled and customized:

- `header`: Task title with optional emoji
- `metadata`: Task metadata (ID, priority, status, complexity, etc.)
- `description`: Task description
- `details`: Implementation details
- `subtasks`: Subtask checklist
- `dependencies`: Task dependencies
- `testing`: Testing strategy
- `acceptance`: Acceptance criteria
- `custom`: Custom content with template variables

#### Auto-Generated Labels

The formatter automatically generates labels based on task properties:

- **Priority labels**: `priority:high`, `priority:critical`, etc.
- **Status labels**: `status:in-progress`, `status:blocked`, etc.
- **Type labels**: `bug`, `enhancement`, `documentation`, `testing`, `refactoring`
- **Size labels**: `size:small`, `size:medium`, `size:large`
- **Complexity labels**: `complexity:low`, `complexity:high`, etc.

### Rate Limiter

The `RateLimiter` class provides token bucket rate limiting for API requests.

```javascript
import { RateLimiter } from './scripts/modules/utils/rate-limiter.js';

// Create a rate limiter
const limiter = new RateLimiter({
  tokensPerInterval: 5000,
  interval: 'hour'
});

// Check if tokens are available
if (limiter.hasTokens(1)) {
  // Make API request
}

// Wait for tokens if necessary
await limiter.removeTokens(1);
```

#### Presets

```javascript
// GitHub API rate limiter (5000 requests/hour)
const githubLimiter = RateLimiter.forGitHubAPI();

// GitHub Search API rate limiter (30 requests/minute)
const searchLimiter = RateLimiter.forGitHubSearchAPI();
```

## Error Handling

The module provides specific error types for different failure scenarios:

```javascript
import {
  GitHubAPIError,
  AuthenticationError,
  ValidationError,
  RateLimitError,
  NetworkError,
  RepositoryError
} from './scripts/modules/github/index.js';

try {
  await service.exportTask(task, 'owner', 'repo');
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Authentication failed:', error.message);
  } else if (error instanceof ValidationError) {
    console.error('Validation error:', error.message);
  } else if (error instanceof RateLimitError) {
    console.error('Rate limit exceeded:', error.message);
    // Wait until rate limit resets
    const delay = getRetryDelay(error);
    await new Promise(resolve => setTimeout(resolve, delay));
  }
}
```

## Configuration

### Environment Variables

Set your GitHub token via environment variable:

```bash
export GITHUB_TOKEN=ghp_your_personal_access_token_here
```

### GitHub Token Permissions

Your GitHub Personal Access Token needs the following permissions:

- `repo` - Access to repositories (for creating issues)
- `read:org` - Read organization membership (for validation)

### Repository Requirements

- Repository must exist and be accessible
- Issues must be enabled
- User must have write access to the repository

## Task Data Structure

The service expects Task Master task objects with the following structure:

```javascript
{
  id: "1",              // Required: Task ID
  title: "Task title",  // Required: Task title
  description: "...",   // Optional: Task description
  details: "...",       // Optional: Implementation details
  priority: "high",     // Optional: Priority level
  status: "pending",    // Optional: Current status
  subtasks: [           // Optional: Array of subtasks
    {
      id: "1.1",
      title: "Subtask title",
      status: "done"
    }
  ],
  dependencies: ["2"],  // Optional: Array of dependency task IDs
  testStrategy: "...",  // Optional: Testing strategy
  metadata: {           // Optional: Additional metadata
    githubIssue: {      // Set after export
      url: "...",
      number: 123
    }
  }
}
```

## GitHub Issue Format

Exported tasks are formatted as GitHub issues with the following structure:

```markdown
# Task Title

**Task Master ID**: 1
**Priority**: high
**Status**: pending

## Description
Task description here

## Implementation Details
Implementation details here

## Subtasks
- [x] Completed subtask
- [ ] Pending subtask

## Dependencies
- Task #2

---
*Exported from Task Master*
**Task Master Reference**: Task #1 in project "My Project"
```

## Testing

Run the test suite:

```bash
# Run all GitHub module tests
npm test -- scripts/modules/github

# Run specific test files
npm test -- scripts/modules/github/github-export-service.test.js
npm test -- scripts/modules/utils/rate-limiter.test.js
```

## Best Practices

1. **Token Security**: Never commit GitHub tokens to version control
2. **Rate Limiting**: Use the built-in rate limiter to avoid API limits
3. **Error Handling**: Always handle authentication and validation errors
4. **Validation**: Validate repository access before bulk operations
5. **Dry Run**: Use `previewExport()` to test formatting before creating issues

## Examples

### Basic Export

```javascript
const service = new GitHubExportService(process.env.GITHUB_TOKEN);

const task = {
  id: '42',
  title: 'Fix authentication bug',
  description: 'Users cannot log in with special characters in password',
  priority: 'critical'
};

const result = await service.exportTask(task, 'myorg', 'myrepo');
console.log('Issue created:', result.issue.url);
```

### Export with Custom Formatting

```javascript
const result = await service.exportTask(
  task,
  'myorg',
  'myrepo',
  {
    title: '[BUG] Authentication Issue',
    labels: ['bug', 'critical', 'authentication'],
    assignees: ['lead-developer'],
    projectName: 'User Management System'
  }
);
```

### Advanced Formatting with TaskGitHubFormatter

```javascript
const formatter = new TaskGitHubFormatter({
  defaultTemplate: 'feature',
  enableEmoji: true,
  enableTables: true
});

// Format with bug template
const bugFormatted = formatter.formatTask(bugTask, {
  template: 'bug',
  titlePattern: 'typed',
  labels: ['bug', 'critical'],
  autoLabels: true
});

// Preview before exporting
const preview = formatter.preview(complexTask, {
  template: 'detailed',
  titlePattern: 'priority'
});

if (preview.stats.isWithinLimits) {
  const result = await service.exportTask(
    complexTask,
    'myorg',
    'myrepo',
    {
      ...preview,
      assignees: ['tech-lead']
    }
  );
}
```

### Custom Template Example

```javascript
// Create custom template for sprint planning
formatter.addCustomTemplate('sprint', {
  description: 'Sprint planning format',
  sections: [
    { type: 'header', enabled: true },
    { type: 'metadata', enabled: true, fields: ['id', 'priority', 'estimatedHours'] },
    { type: 'custom', enabled: true, content: '## Sprint Goal\n{{task.sprintGoal}}' },
    { type: 'description', enabled: true, title: 'User Story' },
    { type: 'acceptance', enabled: true, title: 'Definition of Done' },
    { type: 'subtasks', enabled: true, title: 'Implementation Tasks' }
  ]
});

// Use custom template
const sprintTask = {
  ...task,
  sprintGoal: 'Improve user authentication security',
  acceptanceCriteria: ['All tests pass', 'Code review completed', 'Documentation updated']
};

const formatted = formatter.formatTask(sprintTask, {
  template: 'sprint',
  enableEmoji: true,
  projectName: 'Sprint 2024.Q1'
});
```

### Batch Export with Rate Limiting

```javascript
const tasks = [...]; // Array of tasks

for (const task of tasks) {
  try {
    const result = await service.exportTask(task, 'myorg', 'myrepo');
    console.log(`✓ Exported task ${task.id}`);
  } catch (error) {
    console.error(`✗ Failed to export task ${task.id}:`, error.message);
  }

  // Rate limiter automatically handles delays
}
```

## Contributing

When contributing to the GitHub module:

1. Add tests for new functionality
2. Update this documentation
3. Follow the existing code style
4. Ensure all tests pass

## License

This module is part of Task Master and follows the same license terms.