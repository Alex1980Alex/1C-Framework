# Cursor Editor Integration for Task Master

This directory contains Cursor editor configuration files to enhance Task Master development workflow.

## Keybindings

The `keybindings.json` file provides convenient keyboard shortcuts for common Task Master operations.

### Available Shortcuts

All shortcuts use the prefix `Ctrl+Shift+T` followed by a letter:

| Shortcut | Command | Description |
|----------|---------|-------------|
| `Ctrl+Shift+T L` | `npx task-master list` | List all tasks in formatted view |
| `Ctrl+Shift+T J` | `npx task-master list --json` | List all tasks in JSON format |
| `Ctrl+Shift+T N` | `npx task-master next` | Get next available task |
| `Ctrl+Shift+T S` | `npx task-master show ` | Show specific task (leaves cursor for ID input) |
| `Ctrl+Shift+T P` | `npx task-master list --status=pending` | List pending tasks |
| `Ctrl+Shift+T D` | `npx task-master list --status=done` | List completed tasks |
| `Ctrl+Shift+T A` | `npx task-master add-task --prompt="` | Add new task (leaves cursor for description) |
| `Ctrl+Shift+T C` | `npx task-master list --compact` | List tasks in compact format |
| `Ctrl+Shift+T T` | `npx task-master tags` | Show available tags |
| `Ctrl+Shift+T H` | `npx task-master --help` | Show help information |
| `Ctrl+Shift+T U` | `npx task-master set-status --id=` | Update task status (leaves cursor for ID input) |
| `Ctrl+Shift+T R` | `npx task-master research "` | Start research query (leaves cursor for query input) |

### Usage Examples

1. **Quick task overview**: Press `Ctrl+Shift+T L` to see all tasks
2. **JSON integration**: Press `Ctrl+Shift+T J` to get machine-readable task list
3. **Find next work**: Press `Ctrl+Shift+T N` to get next available task
4. **Task details**: Press `Ctrl+Shift+T S`, then type task ID (e.g., "67") and press Enter
5. **Add new task**: Press `Ctrl+Shift+T A`, type description, close quote, and press Enter
6. **Update status**: Press `Ctrl+Shift+T U`, type task ID and status (e.g., "67 --status=done")

### Installation

1. Copy `keybindings.json` to your global Cursor keybindings:
   - Open Cursor
   - Go to File > Preferences > Keyboard Shortcuts
   - Click the "Open Keyboard Shortcuts (JSON)" icon
   - Merge the contents with your existing keybindings

2. Or use project-specific keybindings by keeping this file in the `.cursor/` directory

### JSON Output Integration

The new `--json` flag enables seamless integration with other tools:

```bash
# Get tasks as JSON for external processing
npx task-master list --json > tasks.json

# Filter specific status with JSON output
npx task-master list --status=pending --json | jq '.tasks[].title'

# Get task statistics
npx task-master list --json | jq '.stats'
```

### MCP Integration

These keybindings work seamlessly with the MCP (Model Context Protocol) integration for Claude Code:

```javascript
// In Claude Code, the JSON output can be processed directly
mcp__task_master_ai__get_tasks(); // Returns same JSON structure as CLI --json flag
```

## Advanced Usage

### Custom Workflows

Create your own keyboard shortcuts by modifying `keybindings.json`:

```json
{
  "key": "ctrl+shift+t x",
  "command": "workbench.action.terminal.sendSequence",
  "args": {
    "text": "npx task-master expand --id="
  },
  "when": "terminalFocus || !terminalFocus"
}
```

### Terminal Integration

All shortcuts work both when terminal is focused and when editing code, ensuring seamless workflow regardless of current focus.

### Performance Tips

- Use `Ctrl+Shift+T C` for quick overviews (compact format is faster)
- Use `Ctrl+Shift+T J` when you need to pipe output to other tools
- Use `Ctrl+Shift+T P` to focus only on pending work

## Troubleshooting

1. **Shortcuts not working**: Ensure Cursor has loaded the keybindings.json file
2. **Command not found**: Make sure Task Master is installed (`npm install -g task-master-ai`)
3. **Wrong directory**: Navigate to your Task Master project directory first

## Version Compatibility

- Task Master AI: v0.26.0+
- Cursor Editor: All versions
- JSON output: Requires Task Master with --json flag support (this implementation)