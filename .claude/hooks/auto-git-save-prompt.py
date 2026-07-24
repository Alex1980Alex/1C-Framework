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
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

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

# Shared pause sentinel (same file as auto-git-save.py + posttooluse-auto-git-save.py).
# When present, this UserPromptSubmit hook skips its auto-commit. Files stay
# uncommitted; user (or post-pause auto-save) takes responsibility.
PAUSE_FILE = Path(_HOOK_DIR).parent / "cache" / "auto-git-save.paused"


def _is_paused() -> bool:
    """Return True if the shared pause sentinel exists."""
    return PAUSE_FILE.is_file()


# --- Helpers ---


def _load_state() -> dict:
    """Load last commit timestamp from state file."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, encoding="utf-8") as f:
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
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3,
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
        # step 0: clear an orphaned .git/index.lock (crashed git left it behind;
        # live incident 2026-07-24). Fresh locks are untouched.
        from shared.auto_save_core import clear_stale_index_lock

        clear_stale_index_lock(str(PROJECT_ROOT))
        # Stage files
        staged_files: list[str] = []
        for fp in files:
            try:
                r = subprocess.run(
                    ["git", "add", "--", fp],
                    timeout=3,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    cwd=str(PROJECT_ROOT),
                )
                if r.returncode == 0:
                    staged_files.append(fp)
            except subprocess.TimeoutExpired:
                pass

        staged = len(staged_files)
        if staged == 0:
            return {"success": False, "error": "git add failed"}

        # ruff-format staged .py so auto-commits stay CI-clean (this path
        # bypasses pre-commit). Best-effort, never blocks.
        from shared.auto_save_core import format_staged_python

        format_staged_python(str(PROJECT_ROOT), staged_files)

        # Commit (amend-absorb 2026-06-12: незапушенный auto-commit HEAD
        # того же prefix поглощается --amend; гейты в auto_save_core)
        from shared.auto_save_core import (
            format_commit_message,
            get_amendable_head,
            merge_for_message,
        )

        head_files = get_amendable_head(str(PROJECT_ROOT), prefix="chore: auto-commit")
        if head_files is not None:
            msg = format_commit_message(
                merge_for_message(head_files, staged_files), prefix="chore: auto-commit"
            )
            commit_cmd = ["git", "commit", "--amend", "-m", msg]
        else:
            msg = format_commit_message(staged_files, prefix="chore: auto-commit")
            commit_cmd = ["git", "commit", "-m", msg]
        commit = subprocess.run(
            commit_cmd,
            timeout=10,
            capture_output=True,
            text=True,
            encoding="utf-8",
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


def _canary_log(msg: str) -> None:
    """Write canary log to diagnose if hook is invoked at all."""
    try:
        canary = Path(_HOOK_DIR).parent / "cache" / "auto-git-save-prompt-canary.log"
        canary.parent.mkdir(parents=True, exist_ok=True)
        with open(canary, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def main():
    """UserPromptSubmit hook: check and auto-commit uncommitted tracked files."""
    # Invocation timer
    try:
        from shared.invocation_logger import InvocationTimer

        timer = InvocationTimer("auto-git-save-prompt", event="UserPromptSubmit").start()
    except Exception:
        timer = None

    _canary_log("ENTER main()")
    try:
        # Read stdin (required by protocol, but we don't use prompt content)
        try:
            raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        _canary_log(f"stdin read ok, len={len(raw)}")

        # Honor shared pause sentinel — same file as the two PostToolUse hooks.
        # All three auto-save lines (auto-git-save.py, posttooluse-auto-git-save.py,
        # this one) gate on `.claude/cache/auto-git-save.paused`. Closed the third
        # leak after the 2026-05-14 incident where fea9ed253 fired through pause.
        if _is_paused():
            _canary_log("SKIP paused")
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        # Check cooldown
        if _is_in_cooldown():
            _canary_log("SKIP cooldown")
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        # Check for uncommitted tracked files
        files = _get_uncommitted_tracked_files()
        _canary_log(f"files={len(files)}: {files[:5]}")
        if not files:
            _canary_log("SKIP no files")
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        # Auto-commit
        result = _auto_commit(files)
        _canary_log(f"commit result: {result}")

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
        _canary_log("EXIT 0")
        if timer:
            timer.log(outcome="message" if result.get("success") else "allow")
        sys.exit(0)

    except Exception as exc:
        # Graceful degradation: never block user prompt
        _canary_log(f"EXCEPTION: {exc}")
        if timer:
            timer.log(outcome="error", error=f"{type(exc).__name__}: {exc}")
        sys.exit(0)


if __name__ == "__main__":
    main()
