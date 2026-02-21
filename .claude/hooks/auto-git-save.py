#!/usr/bin/env python3
"""
Hook: auto-git-save
Event: PostToolUse
Matcher: Write|Edit|Bash
Purpose: Track changed files and auto-commit when threshold reached.
         Ported from 1C-Enterprise_Framework git-commit-reminder.py v2.16.

Timeout: 15s (needs time for sync git commit)

Pattern: Sync Commit + Enforcer.

Flow:
  1. Write/Edit file → track file → threshold reached?
     YES → sync git add + git commit → complete task
     NO  → create/update mandatory task + systemMessage
  2. Bash "git commit" → validate cache → complete task if clean
  3. Every call: sync_pending_tasks_with_git() cleans zombie tasks

Key features (ported from Enterprise):
  - Sync commit at threshold (default 3 files)
  - Zombie task prevention (sync with git status)
  - Validate cache (detect external commits)
  - Adaptive timeout (based on file count)
  - Adaptive cooldown (prevent rapid re-creation)
  - File tracking in task metadata (single source of truth)

NOT ported (not needed):
  - Z.AI smart commit messages (not available)
  - Multi-repo support (single repo project)
  - Metrics module (simplified timeout calculation)

Hook feedback is treated as user instruction per CLAUDE.md.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput
from shared.task_master import (
    add_task,
    complete_task_by_hook,
    get_pending_tasks,
    get_task_with_metadata,
    has_recent_completion,
    update_task_metadata,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

HOOK_ID = "auto-git-save-hook"

# --- Configuration ---

# Threshold: auto-commit when this many files are tracked
SYNC_COMMIT_THRESHOLD = int(os.environ.get("CLAUDE_COMMIT_THRESHOLD", "3"))

# Timeout: base + per-file seconds
SYNC_COMMIT_TIMEOUT_BASE = int(os.environ.get("CLAUDE_COMMIT_TIMEOUT_BASE", "5"))
SYNC_COMMIT_TIMEOUT_PER_FILE = int(os.environ.get("CLAUDE_COMMIT_TIMEOUT_PER_FILE", "1"))

# Cooldown: minutes after completion before creating new task
COOLDOWN_BASE_MINUTES = int(os.environ.get("CLAUDE_COMMIT_COOLDOWN_BASE", "2"))

# Tracked extensions
TRACKED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".bsl", ".bat", ".sh",
    ".json", ".yaml", ".yml", ".toml", ".xml",
    ".md",
}

# Paths to ignore
IGNORE_PATHS = [
    "temp/", "cache/", "__pycache__", "node_modules", ".git/",
    "active-todos.json", "hook-todos.json",
]

# Watch these paths for changes
WATCHED_PATHS = [
    "src/",
    "docs/",
    "tests/",
    ".claude/skills/",
    ".claude/hooks/",
]


# --- Helpers ---

def should_track_file(file_path: str) -> bool:
    """Check if file should be tracked for git commit."""
    path_lower = file_path.lower().replace("\\", "/")
    for ignore in IGNORE_PATHS:
        if ignore in path_lower:
            return False
    ext = Path(file_path).suffix.lower()
    if ext not in TRACKED_EXTENSIONS:
        return False
    # Check watched paths
    rel = _get_relative_path(file_path)
    if rel and WATCHED_PATHS:
        return any(rel.startswith(p) for p in WATCHED_PATHS)
    return True


def _get_relative_path(file_path: str) -> str | None:
    """Get path relative to PROJECT_ROOT. None if outside."""
    try:
        p = Path(file_path).resolve()
        return str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except (ValueError, OSError):
        return None


def get_uncommitted_files() -> list[str]:
    """Get uncommitted files in watched paths via git status."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []
        files = []
        for line in result.stdout.strip().splitlines():
            if not line or len(line) < 3:
                continue
            filepath = line[3:].strip().strip('"').replace("\\", "/")
            if WATCHED_PATHS:
                if not any(filepath.startswith(p) for p in WATCHED_PATHS):
                    continue
            files.append(filepath)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def calculate_timeout(file_count: int) -> int:
    """Calculate adaptive timeout based on file count."""
    base = SYNC_COMMIT_TIMEOUT_BASE + (file_count * SYNC_COMMIT_TIMEOUT_PER_FILE)
    return max(15, min(base, 120))  # 15s min, 120s max


def load_modified_files() -> dict:
    """Load tracked files from task metadata (primary) or empty."""
    task = get_task_with_metadata(HOOK_ID)
    if task and task.get("metadata", {}).get("files"):
        return task["metadata"]
    return {"files": [], "first_change": None, "last_change": None}


def save_modified_files(data: dict) -> None:
    """Save tracked files into task metadata."""
    from datetime import datetime
    data["last_change"] = datetime.now().isoformat()
    if not data.get("first_change"):
        data["first_change"] = data["last_change"]
    update_task_metadata(HOOK_ID, data, merge=False)


# --- Core: Sync Commit ---

def perform_sync_commit(modified_files: list[str], timeout: int | None = None) -> dict:
    """Execute git add + git commit SYNCHRONOUSLY.

    Returns dict with success status and metadata.
    """
    start = time.time()
    if timeout is None:
        timeout = calculate_timeout(len(modified_files))

    try:
        # Step 1: Check git status
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            timeout=2, capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )
        if status.returncode != 0 or not status.stdout.strip():
            return {"success": False, "error": "No changes to commit"}

        # Step 2: Stage specific files
        staged = 0
        for fp in modified_files:
            try:
                r = subprocess.run(
                    ["git", "add", "--", fp],
                    timeout=5, capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT),
                )
                if r.returncode == 0:
                    staged += 1
            except subprocess.TimeoutExpired:
                pass

        if staged == 0:
            return {"success": False, "error": "git add failed for all files"}

        # Step 3: Commit with generic message
        count = len(modified_files)
        commit_msg = f"chore: auto-commit {count} file(s) changed"

        commit = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            timeout=timeout, capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )

        if commit.returncode == 0:
            # Extract hash
            commit_hash = "unknown"
            if commit.stdout:
                for part in commit.stdout.split():
                    clean = part.strip("[]")
                    if len(clean) >= 7 and clean.isalnum():
                        commit_hash = clean[:8]
                        break

            # Complete task
            complete_task_by_hook(
                hook_id=HOOK_ID,
                note=f"Committed: {commit_hash}",
            )

            return {
                "success": True,
                "committed": True,
                "files_count": count,
                "commit_hash": commit_hash,
                "commit_msg": commit_msg,
                "duration": time.time() - start,
            }
        else:
            return {
                "success": False,
                "error": f"git commit failed: {commit.stderr[:200]}",
            }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout after {timeout}s", "timeout": True}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# --- Core: Zombie Task Prevention ---

def sync_pending_tasks_with_git() -> int:
    """Sync pending tasks with actual git status.

    If ALL files from a task are already committed,
    mark the task as completed (zombie prevention).
    """
    try:
        uncommitted = set()
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return 0

        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    fp = parts[-1].replace("\\", "/")
                    uncommitted.add(fp)
                    uncommitted.add(Path(fp).name)

        # Check each pending task
        from shared.task_master import _read_todos, _write_todos
        from datetime import datetime

        data = _read_todos()
        todos = data.get("todos", [])
        cleaned = 0

        for t in todos:
            if t.get("createdBy") != HOOK_ID or t.get("status") != "pending":
                continue

            # Extract files from task content
            content = t.get("content", "")
            task_files = []
            if " - " in content:
                files_part = content.split(" - ", 1)[1]
                if " и ещё " in files_part:
                    files_part = files_part.split(" и ещё ")[0]
                task_files = [f.strip().replace("\\", "/") for f in files_part.split(",")]

            # Also check metadata
            meta = t.get("metadata", {})
            if meta.get("files"):
                task_files = meta["files"]

            # Check if any task file is still uncommitted
            has_uncommitted = False
            for tf in task_files:
                if tf in uncommitted or Path(tf).name in uncommitted:
                    has_uncommitted = True
                    break

            if task_files and not has_uncommitted:
                t["status"] = "completed"
                t["completedAt"] = datetime.now().isoformat()
                t["note"] = "Auto-synced: files already committed"
                cleaned += 1

        if cleaned > 0:
            _write_todos(data)
        return cleaned

    except Exception:
        return 0


# --- Core: Validate Cache ---

def validate_cache() -> list[str] | None:
    """Check which cached files are still uncommitted.

    Returns list of still-uncommitted files, or None on error.
    """
    try:
        cache_data = load_modified_files()
        cached_files = cache_data.get("files", [])
        if not cached_files:
            return []

        still_pending = []
        for fp in cached_files:
            try:
                r = subprocess.run(
                    ["git", "diff", "--quiet", "--", fp],
                    timeout=1, capture_output=True,
                    cwd=str(PROJECT_ROOT),
                )
                if r.returncode != 0:
                    still_pending.append(fp)
            except (subprocess.TimeoutExpired, Exception):
                still_pending.append(fp)

        return still_pending
    except Exception:
        return None


# --- Main Hook ---

class AutoGitSave(BaseHook):
    """Sync git commit hook with file tracking and zombie prevention.

    On Write|Edit: track file → threshold reached → sync commit.
    On Bash "git commit": validate cache → complete task.
    Every call: sync zombie tasks.
    """

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_name = inp.tool_name or ""
        tool_input = inp.tool_input or {}

        # Always sync zombie tasks first
        sync_pending_tasks_with_git()

        # --- Branch: Bash (detect git commit) ---
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if "git commit" not in command:
                return None

            # Validate which files are still uncommitted
            validated = validate_cache()
            if validated is not None and not validated:
                # All committed — complete task
                complete_task_by_hook(
                    hook_id=HOOK_ID,
                    note="Committed via Bash",
                )
                return HookOutput().system_message(
                    "[GIT COMMIT COMPLETED] Задача auto-git-save завершена."
                )
            return None

        # --- Branch: Write|Edit (track files) ---
        file_path = tool_input.get("file_path", "")
        if not file_path or not should_track_file(file_path):
            return None

        rel_path = _get_relative_path(file_path)
        if rel_path is None:
            return None

        # Load tracked files
        modified_data = load_modified_files()
        if rel_path not in modified_data["files"]:
            modified_data["files"].append(rel_path)

        file_count = len(modified_data["files"])

        # --- Threshold reached: SYNC COMMIT ---
        if file_count >= SYNC_COMMIT_THRESHOLD:
            timeout = calculate_timeout(file_count)
            result = perform_sync_commit(modified_data["files"], timeout=timeout)

            if result.get("success") and result.get("committed"):
                files_count = result.get("files_count", 0)
                commit_hash = result.get("commit_hash", "unknown")
                return HookOutput().system_message(
                    f"[AUTO-GIT-SAVE OK] Коммит выполнен: "
                    f"{files_count} файл(ов), hash: {commit_hash}"
                )
            else:
                # Commit failed — create task for manual commit
                error = result.get("error", "Unknown")
                self._ensure_task(modified_data)
                save_modified_files(modified_data)
                return HookOutput().system_message(
                    f"[AUTO-GIT-SAVE FAILED] {error}. "
                    "Создана задача для ручного коммита."
                )

        # --- Below threshold: track + create/update task ---
        save_modified_files(modified_data)
        is_new = self._ensure_task(modified_data)

        if is_new:
            remaining = SYNC_COMMIT_THRESHOLD - file_count
            msg = (
                f"[AUTO-GIT-SAVE] Отслежено файлов: {file_count}. "
                f"Ещё {remaining} до автокоммита.\n"
                "ДЕЙСТВИЕ: Добавь задачу 'Закоммитить незакоммиченные изменения' "
                "в свой TodoWrite список (status: pending)."
            )
            return HookOutput().system_message(msg)

        return None  # Task already exists, don't spam

    def _ensure_task(self, modified_data: dict) -> bool:
        """Create or update mandatory task. Returns True if new task created."""
        # Cooldown check
        file_count = len(modified_data.get("files", []))
        adaptive_cooldown = max(COOLDOWN_BASE_MINUTES, 6 - file_count)
        if has_recent_completion(hook_id=HOOK_ID, cooldown_minutes=adaptive_cooldown):
            return False

        # Check if uncommitted files actually exist
        uncommitted = get_uncommitted_files()
        if not uncommitted:
            complete_task_by_hook(hook_id=HOOK_ID, note="Auto-validated: no uncommitted files")
            return False

        # Check if task already exists
        pending = get_pending_tasks(created_by=HOOK_ID)
        if pending:
            # Update metadata with current file list
            update_task_metadata(HOOK_ID, modified_data, merge=False)
            return False

        # Create new task
        files = modified_data.get("files", [])
        if len(files) <= 3:
            files_str = ", ".join(files)
        else:
            files_str = f"{', '.join(files[:3])} и ещё {len(files) - 3}"

        add_task(
            title=f"Закоммитить незакоммиченные изменения - {files_str}",
            priority="high",
            created_by=HOOK_ID,
            description=(
                f"Незакоммиченные файлы ({len(files)}): {files_str}. "
                "Проверь git status, сгруппируй по логике, закоммить."
            ),
        )
        # Store files in metadata
        update_task_metadata(HOOK_ID, modified_data, merge=False)
        return True


if __name__ == "__main__":
    AutoGitSave().run()
