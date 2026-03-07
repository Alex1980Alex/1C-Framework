# GitHub CLI Integration

## Overview

The Task Master GitHub Export CLI provides comprehensive command-line functionality for integrating Task Master tasks with GitHub Issues. This document covers installation, configuration, and usage of the CLI interface.

## Quick Start

### Installation

The CLI is included with Task Master AI. Install globally:

```bash
npm install -g task-master-ai
```

Or use locally:

```bash
cd your-project
npx task-master-ai
```

### Authentication

Set your GitHub Personal Access Token:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

### Basic Usage

```bash
# Export a single task
task-master-github export 1.2 --owner myorg --repo myrepo

# Bulk export tasks
task-master-github bulk-export --owner myorg --repo myrepo --status pending

# Manage links
task-master-github link list
task-master-github link sync

# View statistics
task-master-github stats

# Configure defaults
task-master-github config --set-owner myorg --set-repo myrepo
```

## Available Commands

### `export <taskId>`

Export a specific task to GitHub issue.

**Example:**
```bash
task-master-github export 1.2 \
  --owner myorg \
  --repo myrepo \
  --template feature \
  --labels "enhancement,sprint-1" \
  --assignees "dev1,dev2"
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

### `bulk-export`

Export multiple tasks to GitHub issues.

**Example:**
```bash
task-master-github bulk-export \
  --owner myorg \
  --repo myrepo \
  --status pending \
  --priority high \
  --labels "sprint-1" \
  --dry-run
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

### `link` Commands

#### `link list`

List all task-GitHub links.

**Example:**
```bash
# List all active links
task-master-github link list

# List links for specific repository
task-master-github link list --owner myorg --repo myrepo

# Export as JSON
task-master-github link list --format json > links.json

# Export as CSV
task-master-github link list --format csv > links.csv
```

**Options:**
- `--status <status>` - Filter by status (active, removed)
- `--owner <owner>` - Filter by repository owner
- `--repo <repo>` - Filter by repository name
- `--format <format>` - Output format (table, json, csv)

#### `link sync`

Synchronize links with GitHub state.

**Example:**
```bash
# Sync all links
task-master-github link sync

# Sync specific repository
task-master-github link sync --owner myorg --repo myrepo
```

**Options:**
- `--owner <owner>` - Sync links for specific owner
- `--repo <repo>` - Sync links for specific repository
- `--token <token>` - GitHub token

#### `link remove <taskId>`

Remove link for a specific task.

**Example:**
```bash
# Soft delete (mark as removed)
task-master-github link remove 1.2

# Permanent deletion
task-master-github link remove 1.2 --permanent
```

**Options:**
- `--permanent` - Permanently delete link (default: soft delete)

### `stats`

Show GitHub integration statistics.

**Example:**
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

**Examples:**
```bash
# Show current configuration
task-master-github config --show

# Set defaults
task-master-github config --set-owner myorg --set-repo myrepo

# Set default template
task-master-github config --set-template detailed
```

**Options:**
- `--set-owner <owner>` - Set default repository owner
- `--set-repo <repo>` - Set default repository name
- `--set-template <template>` - Set default template
- `--show` - Show current configuration

## Templates

### Available Templates

- **standard** - Default template with all standard sections
- **detailed** - Comprehensive template with acceptance criteria
- **minimal** - Compact template with essential information only
- **bug** - Bug report template with reproduction steps
- **feature** - Feature request template with user stories
- **epic** - Epic template for large initiatives

### Template Content

Each template includes configurable sections:

- **Header** - Task title with optional emoji
- **Metadata** - Task ID, priority, status, complexity
- **Description** - Task description
- **Implementation Details** - Technical implementation notes
- **Subtasks** - Checkbox list of subtasks
- **Dependencies** - Related task dependencies
- **Testing Strategy** - Testing approach
- **Acceptance Criteria** - Definition of done

## Configuration

### Configuration File

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

### Environment Variables

- `GITHUB_TOKEN` - Personal Access Token for GitHub API
- `GITHUB_API_URL` - Custom GitHub API URL (default: https://api.github.com)

### Required Token Permissions

Your GitHub token needs:
- `repo` - Full control of private repositories
- `read:org` - Read organization membership (for validation)

## Link Storage

Bidirectional links are stored in `.taskmaster/github-links.json`:

```json
{
  "metadata": {
    "lastSync": "2024-01-15T10:30:00Z",
    "totalLinks": 5,
    "activeLinks": 4,
    "conflicts": []
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

## Workflows

### Single Task Export Workflow

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

### Sprint/Bulk Export Workflow

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

### Link Maintenance Workflow

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

## Error Handling

### Common Error Messages

**Authentication Errors:**
```
❌ GitHub token not found. Set GITHUB_TOKEN environment variable or use --token option.
```

**Repository Errors:**
```
❌ Repository owner and name are required. Use --owner and --repo options or set defaults.
```

**Task Errors:**
```
❌ Task 1.2 not found. Make sure Task Master is initialized.
```

**Link Conflicts:**
```
⚠️ Task 1.2 is already linked to https://github.com/myorg/myrepo/issues/123
```

### Troubleshooting

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

## Best Practices

1. **Set Defaults** - Configure default owner/repo to avoid repetitive flags
2. **Use Templates** - Choose appropriate templates for different task types
3. **Preview First** - Use `--preview` to verify formatting before export
4. **Sync Regularly** - Keep links synchronized with GitHub state
5. **Backup Links** - Export link data regularly for backup
6. **Monitor Stats** - Check statistics to track integration health

## API Reference

For programmatic access, see the [GitHub Integration API documentation](./github-integration-api.md).

## Version Compatibility

- Task Master AI: v0.26.0+
- Node.js: 18.0.0+
- GitHub API: v3 (REST)
- GitHub Enterprise: Supported

## Support

For issues and feature requests, visit the [Task Master repository](https://github.com/eyaltoledano/claude-task-master).