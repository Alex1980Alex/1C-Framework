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

_DEBOUNCE_FILE = os.path.join(
    os.path.dirname(_HOOK_DIR), "cache", "git-save-debounce.json"
)
_DEBOUNCE_SECONDS = 5.0
_MAX_PENDING = 20

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
]


def _should_track(file_path: str) -> bool:
    """Check if file should be auto-committed."""
    normalized = file_path.replace("\\", "/")
    for pattern in SKIP_PATTERNS:
        if pattern in normalized:
            return False
    # Only track code files
    code_extensions = {
        ".py", ".js", ".ts", ".bsl", ".md", ".json",
        ".toml", ".yml", ".yaml", ".xml", ".html", ".css",
    }
    _, ext = os.path.splitext(normalized)
    return ext.lower() in code_extensions


def _load_pending() -> dict:
    """Load debounce state."""
    try:
        if os.path.isfile(_DEBOUNCE_FILE):
            with open(_DEBOUNCE_FILE, "r", encoding="utf-8") as f:
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
        # git add each file
        for f in files:
            subprocess.run(
                ["git", "add", f],
                capture_output=True, timeout=10,
                cwd=project_dir,
            )
        # Count staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True, text=True, timeout=10,
            cwd=project_dir,
        )
        if not result.stdout.strip():
            return False
        # Commit
        file_list = ", ".join(
            os.path.basename(f) for f in files[:3]
        )
        if len(files) > 3:
            file_list += f" +{len(files)-3} more"
        subprocess.run(
            [
                "git", "commit", "-m",
                f"chore: auto-save {file_list}",
                "--no-verify",
            ],
            capture_output=True, timeout=15,
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
            _save_pending({
                "files": files,
                "last_commit": last_commit,
            })
            return None

        # Debounce expired — commit
        success = _git_commit(files)
        if success:
            _save_pending({
                "files": [],
                "last_commit": now,
            })
        else:
            # Commit failed — keep pending
            _save_pending({
                "files": files,
                "last_commit": last_commit,
            })

        return None


if __name__ == "__main__":
    PostToolUseAutoGitSave().run()
