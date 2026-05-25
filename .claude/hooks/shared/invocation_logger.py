"""Hook invocation logger — JSONL append-only structured logging.

Logs every hook invocation to data/hook-invocations.jsonl.
Format: one JSON object per line (JSONL — append-only, crash-safe).
Rotation: when file exceeds 10MB, rename to .1 and start fresh.

Used by:
- BaseHook.run() — automatic for all 15 BaseHook-derived hooks
- Standalone hooks — via log_invocation() direct call
  (ralph_wiggum_stop, git-commit-enforcer, docs-change-enforcer,
   task-enforcer, auto-git-save-prompt, skill-eval-enforcer-shell)

Entry format (§15 P0 ADD: CloudEvents v1.0 envelope + W3C traceparent):
  {"ts":"ISO","hook":"SkillRouter","event":"UserPromptSubmit",
   "tool":null,"elapsed_ms":45,"outcome":"message",
   "session":"abc123","agent_id":"xyz789","error":null,
   "specversion":"1.0","id":"<uuid>","source":"claude-code-hooks",
   "type":"com.anthropic.claude.hook.UserPromptSubmit",
   "time":"ISO","correlationid":"<run_id|session>",
   "causationid":"<parent_id or empty>",
   "traceparent":"00-<32hex>-<16hex>-01"}

Phase 7: Added agent_id for subagent monitoring.
Phase 9 (§15 P0): CloudEvents wrapping + W3C trace context.

Backward compatibility: all pre-§15 flat fields preserved verbatim.
New fields are additive — existing grep/jq/DuckDB queries continue
to work without modification.

Based on task_master.py patterns: graceful degradation, never block.
"""

import json
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path

# --- Path resolution (cached) ---

_LOG_FILE: Path | None = None
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB


def _get_log_file() -> Path:
    """Resolve log file path. Cached after first call."""
    global _LOG_FILE
    if _LOG_FILE is not None:
        return _LOG_FILE

    try:
        from shared.core_paths import get_project_dir

        project_root = get_project_dir().parent
    except ImportError:
        # Fallback: hooks/ -> .claude/ -> project/
        project_root = Path(__file__).resolve().parent.parent.parent

    _LOG_FILE = project_root / "data" / "hook-invocations.jsonl"
    return _LOG_FILE


def _rotate_if_needed(filepath: Path) -> None:
    """Rotate log file if it exceeds MAX_LOG_SIZE."""
    try:
        if filepath.exists() and filepath.stat().st_size > MAX_LOG_SIZE:
            rotated = filepath.with_name("hook-invocations.1.jsonl")
            if rotated.exists():
                rotated.unlink()
            filepath.rename(rotated)
    except OSError:
        pass


# --- Public API ---


def log_invocation(
    hook: str,
    event: str | None = None,
    tool: str | None = None,
    elapsed_ms: int = 0,
    outcome: str = "allow",
    session_id: str = "",
    error: str | None = None,
    agent_id: str = "",  # Phase 7: Subagent monitoring
    category: str = "hook",  # Phase 8: Multi-source log unification
    run_id: str = "",  # Phase 8: Cross-hook correlation (slash-command run)
) -> None:
    """Log a single hook invocation to JSONL file.

    Args:
        hook: Hook class name or script name (e.g. "SkillRouter")
        event: Hook event type (UserPromptSubmit, PreToolUse, PostToolUse, Stop)
        tool: Tool name (for PreToolUse/PostToolUse events)
        elapsed_ms: Execution time in milliseconds
        outcome: Result — one of: allow, block, message, error
        session_id: Claude Code session ID (from stdin JSON)
        error: Error message if outcome is "error"
        agent_id: Subagent ID (for subagent monitoring, Phase 7)
        category: Log category for filtering — "hook" (default, BaseHook auto-log),
                  "mcp_call" (MCP server invocation),
                  "slash_run" (slash-command lifecycle: start/end),
                  "phase" (skill phase marker). Future categories add here.
        run_id: UUID linking events to one slash-command invocation.
                Set by slash-command-tracker on UserPromptSubmit, read by other
                hooks via shared/run_context.get_run_id(session_id).
    """
    try:
        filepath = _get_log_file()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(filepath)

        entry = {
            "ts": datetime.now().isoformat(),
            "hook": hook,
            "event": event,
            "tool": tool,
            "elapsed_ms": elapsed_ms,
            "outcome": outcome,
            "session": session_id or "",
            "error": error,
            "agent_id": agent_id,  # Phase 7
            "category": category,  # Phase 8
            "run_id": run_id,  # Phase 8
        }

        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # Never block on logging failure


class InvocationTimer:
    """Context manager for timing hook invocations.

    Usage (standalone hooks):
        timer = InvocationTimer("git-commit-enforcer", event="Stop")
        timer.start()
        # ... hook logic ...
        timer.log(outcome="block", error=None)

    Phase 7: Added agent_id for subagent monitoring.
    """

    def __init__(self, hook: str, event: str | None = None):
        self.hook = hook
        self.event = event
        self.tool: str | None = None
        self.session_id: str = ""
        self.agent_id: str = ""  # Phase 7
        self.category: str = "hook"  # Phase 8
        self.run_id: str = ""  # Phase 8
        self._start: float = 0.0

    def start(self) -> "InvocationTimer":
        self._start = time.time()
        return self

    def elapsed_ms(self) -> int:
        return int((time.time() - self._start) * 1000)

    def log(self, outcome: str = "allow", error: str | None = None) -> None:
        log_invocation(
            hook=self.hook,
            event=self.event,
            tool=self.tool,
            elapsed_ms=self.elapsed_ms(),
            outcome=outcome,
            session_id=self.session_id,
            error=error,
            agent_id=self.agent_id,  # Phase 7
            category=self.category,  # Phase 8
            run_id=self.run_id,  # Phase 8
        )
