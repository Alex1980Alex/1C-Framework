#!/usr/bin/env python3
"""
Hook: auto-git-save-prompt
Event: UserPromptSubmit
Matcher: (none — fires on every user message, no matcher support for UserPromptSubmit)
Purpose: Workaround for PostToolUse hooks not firing (Claude Code bug #6305, #10450).
         Checks for uncommitted tracked files on each user message and auto-commits.

Timeout: 15s

Flow:
  1. User sends message → hook fires
  2. git status --porcelain → filter tracked files
  3. If uncommitted tracked files exist:
     a. Check cooldown (don't commit too often)
     b. git add + git commit
     c. Return systemMessage with commit info
  4. If no uncommitted files → exit silently

Workaround rationale:
  PostToolUse hooks have a known bug in Claude Code where the trigger mechanism
  doesn't fire tool-related hooks (works on macOS, Windows, Linux, WSL2, Termux).
  UserPromptSubmit hooks work reliably on all platforms.
  Trade-off: commit happens at next user message, not immediately after file edit.

See: https://github.com/anthropics/claude-code/issues/6305
     https://github.com/anthropics/claude-code/issues/10450
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = Path(_HOOK_DIR).resolve().parent.parent

# --- Configuration (same as auto-git-save.py) ---
# Gitignore-first approach: git status --porcelain already respects .gitignore.
# Only these patterns are additionally excluded (hook internal state files).
IGNORE_PATTERNS = [
    "hook-todos.json",
    "hook-todos.lock",
    "active-todos.json",
    "auto-git-save-state.json",
    "auto-git-save-debug.log",
]

# Cooldown: seconds between auto-commits (prevent rapid commits)
COOLDOWN_SECONDS = 30

# State file for cooldown tracking
STATE_FILE = Path(_HOOK_DIR).parent / "cache" / "auto-git-save-prompt-state.json"


# --- Helpers ---

def _load_state() -> dict:
    """Load last commit timestamp from state file."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    """Save state to file."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _is_in_cooldown() -> bool:
    """Check if we're within cooldown period."""
    state = _load_state()
    last_commit = state.get("last_commit_time", 0)
    return (time.time() - last_commit) < COOLDOWN_SECONDS


def _should_track(filepath: str) -> bool:
    """Check if file should be tracked.

    Gitignore-first: any file visible to git is tracked, except
    internal hook state files listed in IGNORE_PATTERNS.
    """
    name = Path(filepath).name
    return name not in IGNORE_PATTERNS


def _get_uncommitted_tracked_files() -> list[str]:
    """Get uncommitted files that match our tracking criteria."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
            capture_output=True, text=True, timeout=3,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().splitlines():
            if not line or len(line) < 2:
                continue
            # Git porcelain format: XY PATH (positions 0-1 = status, then space + path)
            # Use line[2:].lstrip() to handle both "M  path" and " M path" reliably
            # With core.quotepath=false, git outputs raw UTF-8 paths
            # (no octal \320\236 escapes that .replace("\\","/") would mangle)
            filepath = line[2:].lstrip().strip('"').replace("\\", "/")
            if filepath and _should_track(filepath):
                files.append(filepath)
        return files
    except Exception:
        return []


def _auto_commit(files: list[str]) -> dict:
    """Perform git add + git commit for tracked files."""
    start = time.time()
    try:
        # Stage files
        staged = 0
        for fp in files:
            try:
                r = subprocess.run(
                    ["git", "add", "--", fp],
                    timeout=3, capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT),
                )
                if r.returncode == 0:
                    staged += 1
            except subprocess.TimeoutExpired:
                pass

        if staged == 0:
            return {"success": False, "error": "git add failed"}

        # Commit
        msg = f"chore: auto-commit {staged} file(s) changed"
        commit = subprocess.run(
            ["git", "commit", "-m", msg],
            timeout=10, capture_output=True, text=True,
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

            # Update cooldown state
            _save_state({"last_commit_time": time.time(), "last_hash": commit_hash})

            return {
                "success": True,
                "staged": staged,
                "hash": commit_hash,
                "duration": round(time.time() - start, 2),
            }
        else:
            return {"success": False, "error": commit.stderr[:200]}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# --- Main ---

def main():
    """UserPromptSubmit hook: check and auto-commit uncommitted tracked files."""
    try:
        # Read stdin (required by protocol, but we don't use prompt content)
        try:
            raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""

        # Check cooldown
        if _is_in_cooldown():
            sys.exit(0)

        # Check for uncommitted tracked files
        files = _get_uncommitted_tracked_files()
        if not files:
            sys.exit(0)

        # Auto-commit
        result = _auto_commit(files)

        if result.get("success"):
            # Output systemMessage so Claude knows about the commit
            output = {
                "additionalContext": (
                    f"[AUTO-GIT-SAVE] Автокоммит при промпте: "
                    f"{result['staged']} файл(ов), hash: {result['hash']}"
                ),
            }
            sys.stdout.buffer.write(json.dumps(output, ensure_ascii=False).encode("utf-8"))
            sys.stdout.buffer.write(b"\n")
            sys.stdout.buffer.flush()

        # Always exit 0 (never block user prompt)
        sys.exit(0)

    except Exception:
        # Graceful degradation: never block user prompt
        sys.exit(0)


if __name__ == "__main__":
    main()
