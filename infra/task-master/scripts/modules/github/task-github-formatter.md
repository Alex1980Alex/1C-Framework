# Task-to-GitHub Content Formatter

The `TaskGitHubFormatter` is a comprehensive content formatting system that converts Task Master tasks into GitHub-compatible markdown format with customizable templates and advanced formatting options.

## Features

- **Multiple Templates**: Standard, detailed, minimal, bug, feature, epic, and custom templates
- **Smart Content Optimization**: Automatic truncation, summarization, and length management
- **Advanced Label Generation**: Auto-detection of task types, priorities, and sizes
- **Emoji Support**: Optional emoji indicators for priorities and task types
- **Customizable Sections**: Modular section system with template variables
- **Content Formatting**: Markdown optimization, code block formatting, table support
- **Preview Mode**: Preview formatting without creating actual issues

## Quick Start

```javascript
import TaskGitHubFormatter from './task-github-formatter.js';

const formatter = new TaskGitHubFormatter();

// Format a task with default template
const result = formatter.formatTask(task);

// Use specific template with options
const result = formatter.formatTask(task, {
  template: 'feature',
  enableEmoji: true,
  projectName: 'My Project'
});
```

## Templates

### Built-in Templates

#### Standard Template
Default template with comprehensive sections:
- Header with task title
- Metadata (ID, priority, status)
- Description
- Implementation details
- Subtasks checklist
- Dependencies
- Testing strategy

#### Detailed Template
Enhanced version with additional fields:
- All standard sections
- Acceptance criteria
- Complexity and estimated hours
- Extended metadata fields

#### Minimal Template
Compact format for simple tasks:
- Header
- Basic metadata (ID, priority)
- Description
- Subtasks only

#### Bug Template
Specialized for bug reports:
- Bug description
- Reproduction steps
- Expected vs actual behavior
- Technical details
- Verification steps

#### Feature Template
For feature requests and enhancements:
- User story section
- Feature description
- Acceptance criteria
- Implementation plan
- Development tasks
- Testing plan

#### Epic Template
For large initiatives:
- Epic overview
- Business value
- Success metrics
- Epic components
- Dependencies
- Rollout plan

### Custom Templates

Create custom templates with specific sections:

```javascript
const customTemplate = {
  description: 'Sprint planning template',
  sections: [
    { type: 'header', enabled: true },
    { type: 'metadata', enabled: true, fields: ['id', 'priority', 'estimatedHours'] },
    {
      type: 'custom',
      enabled: true,
      content: '## Sprint Goal\n{{task.sprintGoal}}'
    },
    { type: 'subtasks', enabled: true, title: 'Sprint Tasks' }
  ]
};

formatter.addCustomTemplate('sprint', customTemplate);
```

## Configuration Options

### Formatter Options

```javascript
const formatter = new TaskGitHubFormatter({
  defaultTemplate: 'standard',     // Default template to use
  includeMetadata: true,           // Include task metadata
  markdownStyle: 'github',         // Markdown flavor
  maxBodyLength: 65536,            // GitHub issue body limit
  truncateStrategy: 'smart',       // smart, simple, summary
  enableTables: true,              // Enable table formatting
  enableEmoji: false               // Enable emoji indicators
});
```

### Formatting Options

```javascript
const result = formatter.formatTask(task, {
  template: 'detailed',            // Template to use
  title: 'Custom Issue Title',     // Override generated title
  titlePattern: 'prefixed',        // simple, prefixed, typed, priority, status
  enableEmoji: true,               // Enable emojis for this task
  labels: ['custom-label'],        // Additional labels
  assignees: ['user1', 'user2'],   // GitHub assignees
  milestone: 5,                    // Milestone number
  projectName: 'My Project',       // Project reference
  autoLabels: true,                // Auto-generate labels
  showSubtaskPriority: false,      // Show priority in subtasks
  truncateStrategy: 'smart'        // Override truncation
});
```

## Section Types

### Core Sections

- **header**: Task title with optional emoji
- **metadata**: Task properties (ID, priority, status, etc.)
- **description**: Task description
- **details**: Implementation details
- **subtasks**: Checkbox list of subtasks
- **dependencies**: List of dependent tasks
- **testing**: Testing strategy
- **acceptance**: Acceptance criteria

### Template-Specific Sections

- **custom**: Custom content with template variables
- **userStory**: User story format
- **reproduction**: Bug reproduction steps
- **expected**: Expected behavior
- **actual**: Actual behavior
- **environment**: Environment details
- **vision**: Epic vision statement
- **goals**: Epic goals
- **milestones**: Epic milestones

## Label Generation

### Auto-Generated Labels

The formatter automatically generates labels based on:

- **Priority**: `priority:high`, `priority:critical`, etc.
- **Status**: `status:in-progress`, `status:blocked`, etc.
- **Complexity**: `complexity:medium`, `complexity:high`, etc.
- **Type Detection**: `bug`, `enhancement`, `documentation`, `testing`, `refactoring`
- **Size Detection**: `size:small`, `size:medium`, `size:large`

### Type Detection Rules

```javascript
// Bug detection
text.includes('bug') || text.includes('fix') || text.includes('error')

// Enhancement detection
text.includes('feature') || text.includes('implement') || text.includes('add')

// Documentation detection
text.includes('document') || text.includes('readme') || text.includes('guide')

// Testing detection
text.includes('test') || text.includes('spec') || text.includes('coverage')

// Refactoring detection
text.includes('refactor') || text.includes('cleanup') || text.includes('optimize')
```

### Size Detection Rules

```javascript
// Large: >40 hours OR >10 subtasks OR (>5 subtasks AND detailed)
// Medium: >8 hours OR >3 subtasks OR detailed
// Small: <=2 hours OR no subtasks
```

## Content Optimization

### Truncation Strategies

#### Smart Truncation
Preserves markdown structure and cuts at logical boundaries:

```javascript
const result = formatter.formatTask(task, {
  truncateStrategy: 'smart',
  maxBodyLength: 32000
});
```

#### Simple Truncation
Basic character limit with truncation notice:

```javascript
const result = formatter.formatTask(task, {
  truncateStrategy: 'simple'
});
```

#### Summary Generation
Creates summary view for very long content:

```javascript
const result = formatter.formatTask(task, {
  truncateStrategy: 'summary'
});
```

### Text Formatting

- **Line Ending Normalization**: Converts `\r\n` and `\r` to `\n`
- **Code Block Optimization**: Trims whitespace in code blocks
- **List Formatting**: Standardizes list bullets to `-`
- **Table Formatting**: Optimizes GitHub table format
- **Inline Code**: Fixes inline code formatting

## Template Variables

Use template variables in custom sections:

```javascript
{
  type: 'custom',
  enabled: true,
  content: `## Summary
Task: {{task.title}}
Priority: {{task.priority}}
Estimated: {{task.estimatedHours}} hours
Status: {{task.status}}

## Custom Fields
Sprint Goal: {{task.sprintGoal}}
Team: {{task.team}}`
}
```

Available variables:
- `{{task.fieldName}}` - Any task field
- `{{options.fieldName}}` - Any option field

## Preview Mode

Preview formatting without creating issues:

```javascript
const preview = formatter.preview(task, {
  template: 'detailed',
  enableEmoji: true
});

console.log('Title:', preview.title);
console.log('Labels:', preview.labels);
console.log('Stats:', preview.stats);
// Stats include: titleLength, bodyLength, labelCount, isWithinLimits
```

## Integration Examples

### Basic Export

```javascript
import TaskGitHubFormatter from './task-github-formatter.js';
import GitHubExportService from './github-export-service.js';

const formatter = new TaskGitHubFormatter();
const exporter = new GitHubExportService(token);

// Format and export
const formatted = formatter.formatTask(task, { template: 'feature' });
const issue = await exporter.createIssue('owner', 'repo', formatted);
```

### Batch Processing

```javascript
const tasks = await loadTasks();
const formatted = tasks.map(task => formatter.formatTask(task, {
  template: formatter.detectTaskType(task) === 'bug' ? 'bug' : 'standard',
  enableEmoji: true,
  projectName: 'Sprint 1'
}));

// Export all formatted tasks
for (const formattedTask of formatted) {
  await exporter.createIssue('owner', 'repo', formattedTask);
}
```

### Custom Workflow

```javascript
// Custom template for specific workflow
const sprintTemplate = {
  description: 'Sprint task template',
  sections: [
    { type: 'header', enabled: true },
    { type: 'metadata', enabled: true, fields: ['id', 'priority', 'estimatedHours'] },
    {
      type: 'custom',
      enabled: true,
      content: '## Sprint Information\n**Sprint**: {{task.sprint}}\n**Team**: {{task.team}}'
    },
    { type: 'description', enabled: true },
    { type: 'subtasks', enabled: true, title: 'Sprint Tasks' },
    {
      type: 'custom',
      enabled: true,
      content: '## Definition of Done\n{{task.definitionOfDone}}'
    }
  ]
};

formatter.addCustomTemplate('sprint', sprintTemplate);

// Use custom template
const result = formatter.formatTask(task, {
  template: 'sprint',
  projectName: 'Q1 2024'
});
```

## Error Handling

The formatter handles various edge cases gracefully:

- Missing or null fields
- Empty arrays (subtasks, dependencies)
- Very long content (automatic truncation)
- Invalid template names (falls back to standard)
- Malformed markdown (automatic cleanup)

## Best Practices

1. **Choose Appropriate Templates**: Use bug template for bugs, feature template for features, etc.
2. **Enable Auto-Labels**: Let the formatter detect and assign appropriate labels
3. **Use Project Names**: Include project context in footers
4. **Preview First**: Use preview mode to verify formatting before export
5. **Custom Templates**: Create custom templates for specific workflows
6. **Content Limits**: Be aware of GitHub's content limits and use truncation strategies
7. **Emoji Usage**: Use emojis sparingly and consistently across your project

## Performance Considerations

- Template processing is lightweight and fast
- Content optimization may add processing time for very large tasks
- Label generation includes text analysis which scales with content size
- Preview mode is faster than full formatting as it skips some optimizations

## Compatibility

- Designed for GitHub Issues API v3
- Compatible with GitHub Enterprise
- Markdown output follows GitHub Flavored Markdown (GFM)
- Respects GitHub's content limits and formatting requirements