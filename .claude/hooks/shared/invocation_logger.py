"""Hook invocation logger — JSONL append-only structured logging.

Logs every hook invocation to data/hook-invocations.jsonl.
Format: one JSON object per line (JSONL — append-only, crash-safe).
Rotation: when file exceeds 10MB, rename to .1 and start fresh.

Used by:
- BaseHook.run() — automatic for all 15 BaseHook-derived hooks
- Standalone hooks — via log_invocation() direct call
  (ralph_wiggum_stop, git-commit-enforcer, docs-change-enforcer,
   task-enforcer, auto-git-save-prompt, skill-eval-enforcer-shell)

Entry format:
  {"ts":"ISO","hook":"SkillRouter","event":"UserPromptSubmit",
   "tool":null,"elapsed_ms":45,"outcome":"message",
   "session":"abc123","error":null}

Based on task_master.py patterns: graceful degradation, never block.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# --- Path resolution (cached) ---

_LOG_FILE: Optional[Path] = None
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
    event: Optional[str] = None,
    tool: Optional[str] = None,
    elapsed_ms: int = 0,
    outcome: str = "allow",
    session_id: str = "",
    error: Optional[str] = None,
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
    """

    def __init__(self, hook: str, event: Optional[str] = None):
        self.hook = hook
        self.event = event
        self.tool: Optional[str] = None
        self.session_id: str = ""
        self._start: float = 0.0

    def start(self) -> "InvocationTimer":
        self._start = time.time()
        return self

    def elapsed_ms(self) -> int:
        return int((time.time() - self._start) * 1000)

    def log(self, outcome: str = "allow", error: Optional[str] = None) -> None:
        log_invocation(
            hook=self.hook,
            event=self.event,
            tool=self.tool,
            elapsed_ms=self.elapsed_ms(),
            outcome=outcome,
            session_id=self.session_id,
            error=error,
        )
