# Subagent Monitor — Phase 7 (P2)

**Purpose:** Monitor Claude Code subagents within platform constraints.

**Platform Limitations (GitHub Issues):**
- Subagents share session_id [#7881](https://github.com/anthropics/claude-code/issues/7881)
- No per-subagent metrics [#13994](https://github.com/anthropics/claude-code/issues/13994)
- Intermediate text not visible [#14859](https://github.com/anthropics/claude-code/issues/14859)

**Strategy:** Use invocation_logger with agent prefixes to distinguish subagent activity.

---

## How It Works

### Agent Prefix Pattern

Each subagent invocation logs with `agent:` prefix:

```json
{
  "ts": "2026-02-22T...",
  "hook": "agent:bsl-debugger",
  "event": "UserPromptSubmit",
  "elapsed_ms": 1234,
  "outcome": "message",
  "session": "shared-session-id",
  "agent_id": "unique-subagent-id"
}
```

### Monitoring Queries

```bash
# Filter by agent
grep '"hook": "agent:' data/hook-invocations.jsonl

# Count agent invocations
grep -o '"hook": "agent:[^"]*"' data/hook-invocations.jsonl | sort | uniq -c

# Agent timeline
python scripts/hook-dashboard.py --period 1h --section hooks
```

---

## Agent Types

| Agent | Prefix | Trigger | Monitor |
|-------|--------|---------|---------|
| BSL Debugger | `agent:bsl-debugger` | `/debug-bsl` | Latency, error rate |
| Documentor | `agent:document-1c-module` | `/document-1c-module` | Output size, docs created |
| Pipeline | `agent:pipeline` | `/pipeline` | Task completion rate |
| Search | `agent:unified-search` | `/unified-search` | Search latency, results |

---

## Integration with Hooks

### invocation_logger.py Modification

```python
def log_invocation(
    hook: str,
    event: str | None = None,
    tool: str | None = None,
    elapsed_ms: int = 0,
    outcome: str = "allow",
    session_id: str = "",
    error: str | None = None,
    agent_id: str = "",  # NEW
) -> None:
    entry = {
        "ts": datetime.now().isoformat(),
        "hook": hook,
        "event": event,
        "tool": tool,
        "elapsed_ms": elapsed_ms,
        "outcome": outcome,
        "session": session_id or "",
        "error": error,
        "agent_id": agent_id,  # NEW
    }
```

### Agent Wrapper

```python
# .claude/agents/wrapper.py
from shared.invocation_logger import log_invocation
import uuid

class AgentMonitor:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.agent_id = str(uuid.uuid4())[:8]

    def __enter__(self):
        log_invocation(
            hook=f"agent:{self.agent_name}",
            event="AgentStart",
            agent_id=self.agent_id,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        log_invocation(
            hook=f"agent:{self.agent_name}",
            event="AgentEnd",
            outcome="error" if exc_type else "ok",
            agent_id=self.agent_id,
            error=str(exc_val) if exc_val else None,
        )
```

---

## Dashboard Integration

### hook-dashboard.py Agent Filter

```python
def filter_agent_invocations(invocations, agent_name: str):
    return [inv for inv in invocations
            if inv.get("hook", "").startswith(f"agent:{agent_name}")]
```

### Agent-Specific Metrics

```bash
# Agent-specific dashboard
python scripts/hook-dashboard.py --agent bsl-debugger

# Agent comparison
python scripts/hook-dashboard.py --compare-agents
```

---

## Subagent-Safe Settings

### settings-subagent.json

Subagents run with reduced hook set to avoid infinite loops:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      "skill-router",
      "skill-eval-enforcer-shell"
    ],
    "PreToolUse": [
      "invocation-logger"
    ],
    "Stop": [
      "invocation-logger"
    ]
  },
  "agentMode": true,
  "disableLoopingHooks": true
}
```

### Auto-Switch Logic

```python
# In hook loader
if detect_subagent_context():
    settings = load_settings("settings-subagent.json")
else:
    settings = load_settings("settings.json")
```

---

## Testing

### Test Agent Invocation

```bash
# Trigger subagent
/pipeline "test task"

# Check logs
grep 'agent:pipeline' data/hook-invocations.jsonl | tail -5
```

### Verify Agent Separation

```python
# scripts/test_agent_separation.py
agents = parse_invocations("data/hook-invocations.jsonl")
by_agent = group_by(agents, key="agent_id")

# Verify unique agent_ids
assert len(set(a["agent_id"] for a in agents)) == len(by_agent)
```

---

## Limitations & Workarounds

| Limitation | Workaround |
|------------|------------|
| Shared session_id | Use `agent_id` for distinction |
| No per-agent metrics | Agent prefix in hook name |
| Intermediate text hidden | Log intermediate steps via `log_invocation` |
| No agent exit hooks | Use context manager wrapper |

---

## Future Improvements (Platform Dependent)

When platform limitations are resolved:

1. **Per-agent session IDs** — Direct agent attribution
2. **Agent lifecycle hooks** — `AgentStart` / `AgentEnd` events
3. **Intermediate output capture** — Full trace visibility
4. **Agent metrics API** — Built-in per-agent stats

Track issues:
- [#7881](https://github.com/anthropics/claude-code/issues/7881)
- [#13994](https://github.com/anthropics/claude-code/issues/13994)
- [#14859](https://github.com/anthropics/claude-code/issues/14859)
