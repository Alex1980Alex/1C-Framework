#!/usr/bin/env python3
"""Stop hook: fire-and-forget post-merge CI check + auto-revert.

Spawns `scripts/pr_check_post_merge.py --apply` in detached background.
Cooldown: 10 minutes (avoid hammering gh API on every Stop).

Per roadmap 260523 §17 "Maximum autopilot" CI automation tier:
post-merge auto-revert активирован как Stop-hook (chapter 40.4 P3.4 wiring).

References:
- scripts/pr_check_post_merge.py (the actual revert worker)
- .claude/hooks/shared/pr_notifier.py (SMTP notification on revert)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COOLDOWN_FILE = PROJECT_ROOT / ".claude" / "cache" / "post-merge-revert-cooldown"
COOLDOWN_SECONDS = 600  # 10 min

SCRIPT = PROJECT_ROOT / "scripts" / "pr_check_post_merge.py"
PYTHON = sys.executable


def _on_cooldown() -> bool:
    if not COOLDOWN_FILE.exists():
        return False
    try:
        age = time.time() - COOLDOWN_FILE.stat().st_mtime
        return age < COOLDOWN_SECONDS
    except OSError:
        return False


def _mark_cooldown() -> None:
    try:
        COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOLDOWN_FILE.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    """Stop hook entry. Always exits 0 — never blocks Stop."""
    if not SCRIPT.exists():
        return 0
    if _on_cooldown():
        return 0
    if os.environ.get("AUTO_PR_ENABLED", "0") != "1":
        return 0
    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS
            subprocess.Popen(
                [PYTHON, str(SCRIPT), "--apply"],
                cwd=str(PROJECT_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                [PYTHON, str(SCRIPT), "--apply"],
                cwd=str(PROJECT_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        _mark_cooldown()
    except (OSError, ValueError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
