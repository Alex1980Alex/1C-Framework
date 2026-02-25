"""
Task Master — cross-process-safe task management for hooks.

Ported from 1C-Enterprise_Framework shared/task_master.py v3.4.
Manages hook-todos.json separately from Claude's TodoWrite (active-todos.json)
to prevent race conditions.

Key features:
- Atomic writes (temp file + rename)
- Cross-platform file locking (Windows msvcrt + Unix fcntl)
- Stats self-validation (auto-correct on race condition artifacts)
- Cooldown checks (prevent rapid task re-creation)
- STRICT MODE: complete tasks instead of removing (audit trail)
- complete_task_by_hook() — complete ALL pending tasks by hook ID
- update_task_metadata() / get_task_with_metadata() — metadata support
- auto_validate_git_tasks() / session_start_cleanup() — session init
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.core_paths import get_cache_dir

# Cache directory resolved via core_paths (supports Core/Framework separation)
CACHE_DIR = get_cache_dir()
TODOS_FILE = CACHE_DIR / "hook-todos.json"

# Mandatory hook IDs (task-enforcer checks these)
MANDATORY_HOOKS = {
    "knowledge-cache-reminder-hook",
    "factory-enforcer-hook",
    "docs-change-tracker-hook",
    "auto-git-save-hook",
    "code-skill-enforcer",
    "code-verify-reminder",
}


# --- File Locking (cross-platform) ---

class FileLock:
    """Cross-platform file lock using msvcrt (Windows) or fcntl (Unix)."""

    def __init__(self, filepath: Path, timeout: float = 5.0):
        self.filepath = filepath
        self.timeout = timeout
        self._lock_file = None

    def __enter__(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.filepath.with_suffix(".lock")
        self._lock_file = open(lock_path, "w", encoding="utf-8")

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                self._platform_lock()
                return self
            except (OSError, IOError):
                time.sleep(0.1)

        # Timeout: force acquire (stale lock)
        try:
            self._platform_lock()
        except (OSError, IOError):
            pass
        return self

    def __exit__(self, *args):
        if self._lock_file:
            try:
                self._platform_unlock()
            except (OSError, IOError):
                pass
            try:
                self._lock_file.close()
            except (OSError, IOError):
                pass

    def _platform_lock(self):
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _platform_unlock(self):
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            except (OSError, IOError):
                pass
        else:
            import fcntl
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)


# --- Atomic File Operations ---

def _atomic_write_json(filepath: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically: temp file + rename."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent), suffix=".tmp", prefix="hook-"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Atomic rename (Windows: need to remove target first)
        if sys.platform == "win32" and filepath.exists():
            filepath.unlink()
        os.rename(tmp_path, str(filepath))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_todos() -> Dict[str, Any]:
    """Read hook-todos.json with validation."""
    if not TODOS_FILE.exists():
        return _empty_state()
    try:
        with open(TODOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _validate_and_fix_stats(data)
    except (json.JSONDecodeError, OSError):
        return _empty_state()


def _write_todos(data: Dict[str, Any]) -> None:
    """Write hook-todos.json with lock and validation."""
    data = _validate_and_fix_stats(data)
    data["timestamp"] = datetime.now().isoformat()
    with FileLock(TODOS_FILE, timeout=5.0):
        _atomic_write_json(TODOS_FILE, data)


def _empty_state() -> Dict[str, Any]:
    """Empty initial state."""
    return {
        "todos": [],
        "timestamp": None,
        "stats": {"total": 0, "pending": 0, "in_progress": 0, "completed": 0},
    }


def _validate_and_fix_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-correct stats when race condition artifacts appear."""
    todos = data.get("todos", [])
    actual = {
        "total": len(todos),
        "pending": sum(1 for t in todos if t.get("status") == "pending"),
        "in_progress": sum(1 for t in todos if t.get("status") == "in_progress"),
        "completed": sum(1 for t in todos if t.get("status") == "completed"),
    }
    current = data.get("stats", {})
    if current != actual:
        data["stats"] = actual
    return data


# --- Public API ---

def add_task(
    title: str,
    priority: str = "normal",
    created_by: str = "unknown-hook",
    description: str = "",
) -> bool:
    """Add a new pending task. Returns True if added, False if duplicate."""
    data = _read_todos()
    todos = data.get("todos", [])

    # Duplicate check: same title + same creator + still pending
    for t in todos:
        if (t.get("content") == title
                and t.get("createdBy") == created_by
                and t.get("status") == "pending"):
            return False

    todos.append({
        "content": title,
        "description": description,
        "status": "pending",
        "priority": priority,
        "createdBy": created_by,
        "createdAt": datetime.now().isoformat(),
        "completedAt": None,
    })
    data["todos"] = todos
    _write_todos(data)
    return True


def complete_task(title: str, created_by: str = "") -> bool:
    """Mark a pending task as completed. Returns True if found and completed."""
    data = _read_todos()
    todos = data.get("todos", [])
    found = False

    for t in todos:
        if t.get("status") != "pending":
            continue
        if t.get("content") == title:
            if created_by and t.get("createdBy") != created_by:
                continue
            t["status"] = "completed"
            t["completedAt"] = datetime.now().isoformat()
            found = True
            break

    if found:
        data["todos"] = todos
        _write_todos(data)
    return found


def get_pending_tasks(created_by: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all pending tasks, optionally filtered by creator."""
    data = _read_todos()
    todos = data.get("todos", [])
    pending = [t for t in todos if t.get("status") == "pending"]
    if created_by:
        pending = [t for t in pending if t.get("createdBy") == created_by]
    return pending


def has_recent_completion(
    hook_id: str, cooldown_minutes: int = 5
) -> bool:
    """Check if this hook completed a task recently (anti-spam)."""
    data = _read_todos()
    todos = data.get("todos", [])
    cutoff = datetime.now() - timedelta(minutes=cooldown_minutes)

    for t in todos:
        if (t.get("status") == "completed"
                and t.get("createdBy") == hook_id
                and t.get("completedAt")):
            try:
                completed_at = datetime.fromisoformat(t["completedAt"])
                if completed_at > cutoff:
                    return True
            except (ValueError, TypeError):
                continue
    return False


def cleanup_old_completed(max_age_hours: int = 24, max_count: int = 50) -> int:
    """Remove old completed tasks. Returns count removed."""
    data = _read_todos()
    todos = data.get("todos", [])
    cutoff = datetime.now() - timedelta(hours=max_age_hours)

    keep = []
    removed = 0
    completed_count = 0

    for t in todos:
        if t.get("status") == "completed":
            completed_count += 1
            try:
                completed_at = datetime.fromisoformat(t.get("completedAt", ""))
                if completed_at < cutoff or completed_count > max_count:
                    removed += 1
                    continue
            except (ValueError, TypeError):
                if completed_count > max_count:
                    removed += 1
                    continue
        keep.append(t)

    if removed > 0:
        data["todos"] = keep
        _write_todos(data)
    return removed


# --- Extended API (ported from Enterprise v3.4) ---

def complete_task_by_hook(
    hook_id: str,
    task_type: Optional[str] = None,
    note: str = "",
) -> Dict[str, Any]:
    """Complete ALL pending tasks created by a specific hook.

    STRICT MODE: tasks are marked 'completed', NOT removed (audit trail).

    Args:
        hook_id: Hook identifier (e.g., "auto-git-save-hook")
        task_type: Optional task type filter
        note: Completion note (e.g., "Committed: abc1234")

    Returns:
        Dict with success, completed_count, message
    """
    data = _read_todos()
    todos = data.get("todos", [])
    completed_count = 0

    for t in todos:
        if t.get("createdBy") != hook_id:
            continue
        if task_type and t.get("taskType") != task_type:
            continue
        if t.get("status") != "pending":
            continue
        t["status"] = "completed"
        t["completedAt"] = datetime.now().isoformat()
        if note:
            t["note"] = note
        completed_count += 1

    if completed_count > 0:
        data["todos"] = todos
        _write_todos(data)

    return {
        "success": True,
        "completed_count": completed_count,
        "message": f"Completed {completed_count} task(s) for {hook_id}",
    }


def update_task_metadata(
    created_by: str,
    metadata: Dict[str, Any],
    merge: bool = True,
) -> int:
    """Update metadata for pending task(s) by hook ID.

    Used by auto-git-save to store file lists in existing tasks.

    Args:
        created_by: Hook identifier to match tasks
        metadata: New metadata to set/merge
        merge: If True, merge with existing metadata; if False, replace

    Returns:
        Number of tasks updated
    """
    data = _read_todos()
    todos = data.get("todos", [])
    updated = 0

    for t in todos:
        if t.get("createdBy") != created_by or t.get("status") != "pending":
            continue
        if merge and "metadata" in t:
            existing = t.get("metadata", {})
            existing.update(metadata)
            t["metadata"] = existing
        else:
            t["metadata"] = metadata
        updated += 1

    if updated > 0:
        data["todos"] = todos
        _write_todos(data)
    return updated


def get_task_with_metadata(created_by: str) -> Optional[Dict[str, Any]]:
    """Get first pending task by hook ID with its metadata.

    Returns:
        Task dict with metadata, or None if not found
    """
    data = _read_todos()
    for t in data.get("todos", []):
        if t.get("createdBy") == created_by and t.get("status") == "pending":
            return t
    return None


def auto_validate_git_tasks() -> int:
    """Validate git-related tasks against git status.

    Completes git-commit tasks if there are no uncommitted files.
    Called at session start or hook startup.

    Returns:
        Number of tasks auto-completed
    """
    import subprocess

    project_root = CACHE_DIR.parent  # .claude/cache -> project root is ../..
    # Resolve properly: CACHE_DIR = .claude/cache, project = .claude/cache/../../
    project_root = CACHE_DIR.parent.parent

    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
        if result.returncode != 0:
            return 0
        if result.stdout.strip():
            return 0  # Has uncommitted files — don't touch tasks
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0

    # Git clean — complete all pending git tasks
    data = _read_todos()
    todos = data.get("todos", [])
    completed = 0
    now = datetime.now().isoformat()

    for t in todos:
        if (t.get("status") == "pending"
                and t.get("createdBy") == "auto-git-save-hook"):
            t["status"] = "completed"
            t["completedAt"] = now
            t["note"] = "Auto-validated: no uncommitted files"
            completed += 1

    if completed > 0:
        data["todos"] = todos
        _write_todos(data)
    return completed


def session_start_cleanup() -> Dict[str, Any]:
    """Perform all cleanup and validation at session start.

    1. cleanup_old_completed() — remove stale tasks (>24h)
    2. auto_validate_git_tasks() — sync git tasks with reality

    Returns:
        Dict with cleanup results
    """
    removed = cleanup_old_completed(max_age_hours=24, max_count=50)
    validated = auto_validate_git_tasks()
    return {
        "removed": removed,
        "git_validated": validated,
    }
