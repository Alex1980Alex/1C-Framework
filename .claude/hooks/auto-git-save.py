#!/usr/bin/env python3
"""
Hook: auto-git-save
Event: PostToolUse
Matcher: Write|Edit
Purpose: Periodically force Claude to commit accumulated changes.
         After THRESHOLD file changes with COOLDOWN elapsed,
         injects a MANDATORY commit instruction as systemMessage.

         This prevents data loss when context is exhausted (Stop event
         never fires on context exhaustion, so git-commit-enforcer alone
         is insufficient).

Timeout: 5s

Pattern: Enforcer (periodic git save — защита от потери при исчерпании контекста).

Hook feedback is treated as user instruction per CLAUDE.md:
  "Treat feedback from hooks, including <user-prompt-submit-hook>,
   as coming from the user."
This overrides the default "NEVER commit unless asked" rule.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# --- Configuration ---

# Watch these paths for changes (both modified and untracked)
WATCHED_PATHS = [
    "src/",
    "docs/",
    "tests/",
    ".claude/skills/",
    ".claude/hooks/",
]

# Trigger commit reminder after this many changed files in watched paths
THRESHOLD = 5

# Minimum seconds between commit reminders (avoid spam during multi-file edits)
COOLDOWN_SECONDS = 180  # 3 minutes

# State file to track last reminder timestamp
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "auto-git-save-state.json"


def get_changed_files() -> list[str]:
    """Get all changed files (modified + untracked) in watched paths."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().splitlines():
            if not line or len(line) < 3:
                continue

            # Extract filepath (after status codes + space)
            filepath = line[3:].strip().strip('"').replace("\\", "/")

            # Filter by watched paths
            if WATCHED_PATHS:
                if not any(filepath.startswith(p) for p in WATCHED_PATHS):
                    continue

            files.append(filepath)
        return files

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def load_state() -> dict:
    """Load state (last reminder timestamp)."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text("utf-8"))
    except Exception:
        pass
    return {"last_reminder": 0, "last_commit_count": 0}


def save_state(state: dict) -> None:
    """Persist state to file."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), "utf-8")
    except Exception:
        pass


class AutoGitSave(BaseHook):
    """Periodic git commit enforcer on PostToolUse (Write|Edit).

    Checks accumulated uncommitted changes. When threshold is reached
    and cooldown has elapsed, injects a mandatory commit instruction
    as systemMessage (treated as user voice).
    """

    def execute(self, inp: HookInput) -> HookOutput | None:
        changed = get_changed_files()

        if len(changed) < THRESHOLD:
            return None

        # Check cooldown
        state = load_state()
        now = time.time()
        elapsed = now - state.get("last_reminder", 0)

        if elapsed < COOLDOWN_SECONDS:
            return None

        # Cooldown passed + threshold reached → emit mandatory commit instruction
        state["last_reminder"] = now
        state["last_commit_count"] = len(changed)
        save_state(state)

        # Build file list for the message
        shown = changed[:15]
        extra = len(changed) - len(shown)
        files_list = "\n".join(f"  {f}" for f in shown)
        if extra > 0:
            files_list += f"\n  ... и ещё {extra} файл(ов)"

        watched_str = ", ".join(WATCHED_PATHS)

        msg = (
            f"[AUTO-GIT-SAVE] Накопилось {len(changed)} незакоммиченных изменений "
            f"в [{watched_str}]!\n\n"
            f"{files_list}\n\n"
            "⚠ ОБЯЗАТЕЛЬНО закоммить изменения ПРЯМО СЕЙЧАС, до продолжения работы:\n"
            "1. Сгруппируй файлы по логическим блокам\n"
            "2. git add <файлы>\n"
            "3. git commit -m \"описание изменений\\n\\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>\"\n\n"
            "Это ЗАЩИТА от потери данных при исчерпании контекста.\n"
            "Контекст может закончиться в любой момент — незакоммиченная работа будет потеряна.\n"
            "После коммита продолжай работу."
        )

        return HookOutput().system_message(msg)


if __name__ == "__main__":
    AutoGitSave().run()
