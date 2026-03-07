# GitHub Export CLI Documentation

## Overview

The GitHub Export CLI provides a comprehensive command-line interface for exporting Task Master tasks to GitHub issues with bidirectional linking capabilities.

## Installation

The CLI is included with Task Master AI. Install via npm:

```bash
npm install -g task-master-ai
```

Or use locally:

```bash
npx task-master-ai
```

## Authentication

Set your GitHub Personal Access Token as an environment variable:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Or pass it directly to commands:

```bash
task-master-github export 1 --token ghp_your_token_here --owner myorg --repo myrepo
```

### Required Token Permissions

Your GitHub token needs:
- `repo` - Full control of private repositories
- `read:org` - Read organization membership (for validation)

## Commands

### `export <taskId>`

Export a specific task to GitHub issue.

```bash
task-master-github export 1.2 --owner myorg --repo myrepo
```

**Options:**
- `-o, --owner <owner>` - GitHub repository owner
- `-r, --repo <repo>` - GitHub repository name
- `-t, --template <template>` - Formatting template (standard, detailed, minimal, bug, feature, epic)
- `--title <title>` - Custom issue title
- `--labels <labels>` - Comma-separated labels
- `--assignees <assignees>` - Comma-separated assignees
- `--milestone <milestone>` - Milestone number
- `--project <project>` - Project name for reference
- `--force` - Force export even if task already linked
- `--preview` - Preview issue content without creating
- `--token <token>` - GitHub token (overrides config)

**Examples:**

```bash
# Basic export
task-master-github export 1 --owner myorg --repo myrepo

# Export with custom template and labels
task-master-github export 2 --owner myorg --repo myrepo \
  --template bug \
  --labels "bug,critical" \
  --assignees "dev1,dev2"

# Preview without creating
task-master-github export 3 --owner myorg --repo myrepo --preview

# Force export (replace existing link)
task-master-github export 1 --owner myorg --repo myrepo --force
```

### `bulk-export`

Export multiple tasks to GitHub issues.

```bash
task-master-github bulk-export --owner myorg --repo myrepo
```

**Options:**
- `-o, --owner <owner>` - GitHub repository owner
- `-r, --repo <repo>` - GitHub repository name
- `-t, --template <template>` - Formatting template for all tasks
- `--filter <filter>` - Task filter (status, priority, prefix)
- `--status <status>` - Export tasks with specific status
- `--priority <priority>` - Export tasks with specific priority
- `--prefix <prefix>` - Export tasks with ID prefix
- `--labels <labels>` - Comma-separated labels for all issues
- `--project <project>` - Project name for reference
- `--dry-run` - Show what would be exported without creating
- `--force` - Force export even if tasks already linked
- `--token <token>` - GitHub token

**Examples:**

```bash
# Export all pending tasks
task-master-github bulk-export --owner myorg --repo myrepo \
  --status pending

# Dry run to see what would be exported
task-master-github bulk-export --owner myorg --repo myrepo \
  --priority high --dry-run

# Export tasks with specific prefix
task-master-github bulk-export --owner myorg --repo myrepo \
  --prefix "1.2" --labels "sprint-1"
```

### `link` Commands

Manage bidirectional links between tasks and GitHub issues.

#### `link list`

List all task-GitHub links.

```bash
task-master-github link list
```

**Options:**
- `--status <status>` - Filter by status (active, removed)
- `--owner <owner>` - Filter by repository owner
- `--repo <repo>` - Filter by repository name
- `--format <format>` - Output format (table, json, csv)

**Examples:**

```bash
# List all active links
task-master-github link list

# List links for specific repository
task-master-github link list --owner myorg --repo myrepo

# Export as JSON
task-master-github link list --format json

# Export as CSV
task-master-github link list --format csv > links.csv
```

#### `link sync`

Synchronize links with GitHub state.

```bash
task-master-github link sync
```

**Options:**
- `--owner <owner>` - Sync links for specific owner
- `--repo <repo>` - Sync links for specific repository
- `--token <token>` - GitHub token

**Examples:**

```bash
# Sync all links
task-master-github link sync

# Sync specific repository
task-master-github link sync --owner myorg --repo myrepo
```

#### `link remove <taskId>`

Remove link for a specific task.

```bash
task-master-github link remove 1.2
```

**Options:**
- `--permanent` - Permanently delete link (default: soft delete)

**Examples:**

```bash
# Soft delete (mark as removed)
task-master-github link remove 1.2

# Permanent deletion
task-master-github link remove 1.2 --permanent
```

### `stats`

Show GitHub integration statistics.

```bash
task-master-github stats
```

**Output includes:**
- Total links count
- Active vs removed links
- Links by repository
- Links by status
- Sync status information
- Timeline (oldest/newest links)

### `config`

Manage GitHub integration configuration.

```bash
task-master-github config --show
```

**Options:**
- `--set-owner <owner>` - Set default repository owner
- `--set-repo <repo>` - Set default repository name
- `--set-template <template>` - Set default template
- `--show` - Show current configuration

**Examples:**

```bash
# Show current configuration
task-master-github config --show

# Set defaults
task-master-github config --set-owner myorg --set-repo myrepo

# Set default template
task-master-github config --set-template detailed
```

## Templates

### Available Templates

- **standard** - Default template with all standard sections
- **detailed** - Comprehensive template with acceptance criteria
- **minimal** - Compact template with essential information only
- **bug** - Bug report template with reproduction steps
- **feature** - Feature request template with user stories
- **epic** - Epic template for large initiatives

### Template Sections

Templates include configurable sections:

- **Header** - Task title with optional emoji
- **Metadata** - Task ID, priority, status, complexity
- **Description** - Task description
- **Implementation Details** - Technical implementation notes
- **Subtasks** - Checkbox list of subtasks
- **Dependencies** - Related task dependencies
- **Testing Strategy** - Testing approach
- **Acceptance Criteria** - Definition of done

### Custom Templates

You can create custom templates by extending the TaskGitHubFormatter in your code:

```javascript
import { TaskGitHubFormatter } from 'task-master-ai';

const formatter = new TaskGitHubFormatter();

formatter.addCustomTemplate('sprint', {
  description: 'Sprint planning template',
  sections: [
    { type: 'header', enabled: true },
    { type: 'metadata', enabled: true, fields: ['id', 'priority', 'estimatedHours'] },
    { type: 'custom', enabled: true, content: '## Sprint Goal\n{{task.sprintGoal}}' },
    { type: 'subtasks', enabled: true, title: 'Sprint Tasks' }
  ]
});
```

## Configuration File

The CLI stores configuration in `.taskmaster/github-config.json`:

```json
{
  "githubToken": "ghp_...",
  "defaultOwner": "myorg",
  "defaultRepo": "myrepo",
  "defaultTemplate": "standard",
  "linkStorePath": ".taskmaster/github-links.json"
}
```

## Link Storage

Bidirectional links are stored in `.taskmaster/github-links.json`:

```json
{
  "metadata": {
    "lastSync": "2024-01-15T10:30:00Z",
    "totalLinks": 5,
    "activeLinks": 4,
    "conflicts": [],
    "lastUpdate": "2024-01-15T10:30:00Z"
  },
  "links": [
    {
      "id": "1.2:myorg/myrepo#123",
      "taskId": "1.2",
      "github": {
        "owner": "myorg",
        "repo": "myrepo",
        "number": 123,
        "url": "https://github.com/myorg/myrepo/issues/123",
        "title": "Implement user authentication",
        "state": "open"
      },
      "metadata": {
        "createdAt": "2024-01-15T09:00:00Z",
        "createdBy": "cli",
        "lastSync": "2024-01-15T10:30:00Z",
        "syncStatus": "active"
      },
      "status": "active"
    }
  ]
}
```

## Error Handling

The CLI provides detailed error messages for common issues:

### Authentication Errors
```
❌ GitHub token not found. Set GITHUB_TOKEN environment variable or use --token option.
```

### Repository Errors
```
❌ Repository owner and name are required. Use --owner and --repo options or set defaults.
```

### Task Errors
```
❌ Task 1.2 not found. Make sure Task Master is initialized.
```

### Link Conflicts
```
⚠️  Task 1.2 is already linked to https://github.com/myorg/myrepo/issues/123
```

## Workflows

### Single Task Export

1. Configure defaults:
   ```bash
   task-master-github config --set-owner myorg --set-repo myrepo
   ```

2. Preview the export:
   ```bash
   task-master-github export 1.2 --preview
   ```

3. Export the task:
   ```bash
   task-master-github export 1.2 --template feature --labels "enhancement"
   ```

### Bulk Sprint Export

1. Export all pending tasks for a sprint:
   ```bash
   task-master-github bulk-export \
     --status pending \
     --labels "sprint-1,backend" \
     --project "User Management System"
   ```

2. Review the results:
   ```bash
   task-master-github link list --format table
   ```

3. Sync with GitHub to get latest state:
   ```bash
   task-master-github link sync
   ```

### Link Maintenance

1. Check link statistics:
   ```bash
   task-master-github stats
   ```

2. Sync all links:
   ```bash
   task-master-github link sync
   ```

3. Export link data:
   ```bash
   task-master-github link list --format csv > sprint-links.csv
   ```

4. Remove completed task links:
   ```bash
   task-master-github link remove 1.2
   ```

## Integration with Task Master

The GitHub CLI integrates seamlessly with Task Master commands:

```bash
# Create tasks
task-master parse-prd requirements.md

# Export to GitHub
task-master-github bulk-export --owner myorg --repo myrepo

# Continue task management
task-master next
task-master set-status --id=1.2 --status=done

# Sync GitHub state
task-master-github link sync
```

## Troubleshooting

### Common Issues

**Token Issues:**
- Ensure token has correct permissions
- Check token expiration
- Verify repository access

**File Issues:**
- Ensure Task Master is initialized (`.taskmaster/` directory exists)
- Check file permissions
- Verify tasks.json format

**Network Issues:**
- Check internet connectivity
- Verify GitHub API availability
- Check rate limiting

### Debug Mode

Enable verbose output with `--verbose`:

```bash
task-master-github export 1 --owner myorg --repo myrepo --verbose
```

### Rate Limiting

The CLI respects GitHub API rate limits:
- 5000 requests per hour for authenticated requests
- Automatic backoff and retry
- Progress indicators for bulk operations

## Best Practices

1. **Set Defaults** - Configure default owner/repo to avoid repetitive flags
2. **Use Templates** - Choose appropriate templates for different task types
3. **Preview First** - Use `--preview` to verify formatting before export
4. **Sync Regularly** - Keep links synchronized with GitHub state
5. **Backup Links** - Export link data regularly for backup
6. **Monitor Stats** - Check statistics to track integration health

## API Reference

For programmatic access, see the [GitHub Integration API documentation](./github-integration-api.md).

## Support

For issues and feature requests, visit the [Task Master repository](https://github.com/eyaltoledano/claude-task-master).