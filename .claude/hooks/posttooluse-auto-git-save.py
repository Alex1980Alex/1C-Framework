#!/usr/bin/env python3
"""
Hook: posttooluse-auto-git-save
Event: PostToolUse
Matcher: Write|Edit
Purpose: Instant git add + commit after Write/Edit with debounce (5s).
         Replaces the 15s-delay UserPromptSubmit workaround.
         Commits only tracked code files (not .claude/cache, data/, etc).
Timeout: 10s
"""

import json
import os
import subprocess
import sys
import time

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

_DEBOUNCE_FILE = os.path.join(os.path.dirname(_HOOK_DIR), "cache", "git-save-debounce.json")
_PAUSE_FILE = os.path.join(os.path.dirname(_HOOK_DIR), "cache", "auto-git-save.paused")
_DEBOUNCE_SECONDS = 5.0
_MAX_PENDING = 20


def _is_paused() -> bool:
    """Mirror of auto-git-save.py pause logic — checks sentinel file presence.

    Same sentinel as auto-git-save.py so user has one switch for both hooks.
    Treats any-existing sentinel as paused (TTL parsing happens in the other
    hook; here we conservatively pause whenever the file exists).
    """
    return os.path.isfile(_PAUSE_FILE)


# Paths that should NOT trigger auto-git-save
SKIP_PATTERNS = [
    ".claude/cache/",
    ".claude/data/",
    "__pycache__",
    ".venv/",
    "node_modules/",
    ".git/",
    "data/delegation-outcomes.jsonl",
    "data/hook-invocations.jsonl",
    "data/hook-latency.jsonl",
    # §18 Progress Log → deliberate `docs(roadmap): progress log` commit, not
    # chore: auto-save preempt (roadmap 260523 §19.3). git-commit-enforcer is
    # the safety net (watches docs/).
    "docs/roadmap/",
]


def _should_track(file_path: str) -> bool:
    """Check if file should be auto-committed."""
    normalized = file_path.replace("\\", "/")
    for pattern in SKIP_PATTERNS:
        if pattern in normalized:
            return False
    # Only track code files
    code_extensions = {
        ".py",
        ".js",
        ".ts",
        ".bsl",
        ".md",
        ".json",
        ".toml",
        ".yml",
        ".yaml",
        ".xml",
        ".html",
        ".css",
    }
    _, ext = os.path.splitext(normalized)
    return ext.lower() in code_extensions


def _load_pending() -> dict:
    """Load debounce state."""
    try:
        if os.path.isfile(_DEBOUNCE_FILE):
            with open(_DEBOUNCE_FILE, encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return {"files": [], "last_commit": 0}


def _save_pending(data: dict) -> None:
    """Save debounce state."""
    try:
        os.makedirs(os.path.dirname(_DEBOUNCE_FILE), exist_ok=True)
        with open(_DEBOUNCE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass


def _git_commit(files: list[str]) -> bool:
    """Stage and commit files. Returns True on success."""
    if not files:
        return False
    try:
        project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
        # step 0: clear an orphaned .git/index.lock (crashed git left it behind;
        # live incident 2026-07-24). Fresh locks are untouched.
        from shared.auto_save_core import clear_stale_index_lock

        clear_stale_index_lock(project_dir)
        # git add each file
        for f in files:
            subprocess.run(
                ["git", "add", f],
                capture_output=True,
                timeout=10,
                cwd=project_dir,
            )
        # Keep auto-commits CI-clean: ruff-format staged .py before committing
        # (this path uses --no-verify, bypassing pre-commit). Best-effort.
        from shared.auto_save_core import format_staged_python

        format_staged_python(project_dir, files)
        # Count staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=project_dir,
        )
        if not result.stdout.strip():
            return False
        # Commit (amend-absorb 2026-06-12: незапушенный auto-save HEAD
        # поглощается --amend вместо стопки коммитов; гейты в auto_save_core)
        from shared.auto_save_core import (
            format_commit_message,
            get_amendable_head,
            merge_for_message,
        )

        head_files = get_amendable_head(project_dir)
        if head_files is not None:
            msg = format_commit_message(merge_for_message(head_files, files))
            commit_cmd = ["git", "commit", "--amend", "-m", msg, "--no-verify"]
        else:
            msg = format_commit_message(files)
            commit_cmd = ["git", "commit", "-m", msg, "--no-verify"]
        subprocess.run(
            commit_cmd,
            capture_output=True,
            timeout=15,
            cwd=project_dir,
        )
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


class PostToolUseAutoGitSave(BaseHook):
    """PostToolUse hook for Write|Edit: instant git save with debounce."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_input = inp.tool_input
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, AttributeError):
                return None

        if not isinstance(tool_input, dict):
            return None

        file_path = tool_input.get("file_path", "")
        if not file_path or not _should_track(file_path):
            return None

        # Honor the shared pause sentinel (same file as auto-git-save.py +
        # auto-git-save-prompt.py). Without this the debounce path committed
        # straight through a `forever` pause — `_is_paused()` stayed defined but
        # its call site was lost in a refactor (regression). auto-git-save.py
        # still tracks the file on its own PostToolUse, so nothing is dropped;
        # the commit just waits for resume. Guard: tests/unit/test_auto_save_pause.py.
        if _is_paused():
            return None

        # Load debounce state
        pending = _load_pending()
        now = time.time()

        # Add file to pending list
        files = pending.get("files", [])
        if file_path not in files:
            files.append(file_path)
        if len(files) > _MAX_PENDING:
            files = files[-_MAX_PENDING:]

        last_commit = pending.get("last_commit", 0)
        elapsed = now - last_commit

        if elapsed < _DEBOUNCE_SECONDS:
            # Within debounce window — save and wait
            _save_pending(
                {
                    "files": files,
                    "last_commit": last_commit,
                }
            )
            return None

        # Debounce expired — commit
        success = _git_commit(files)
        if success:
            _save_pending(
                {
                    "files": [],
                    "last_commit": now,
                }
            )
        else:
            # Commit failed — keep pending
            _save_pending(
                {
                    "files": files,
                    "last_commit": last_commit,
                }
            )

        return None


if __name__ == "__main__":
    PostToolUseAutoGitSave().run()
