#!/usr/bin/env python3
"""
Hook: ci-catchup-on-stop
Event: Stop
Purpose:
  Mid-session CI intake (pipeline-hole H2, 2026-06-12): ci-catchup-on-start
  бэкфиллит `.claude/cache/ci-failures.jsonl` только на SessionStart, поэтому
  провал CI, случившийся ВО ВРЕМЯ сессии (push → run → failure), не попадал
  в cache до следующей сессии. Этот хук спавнит тот же detached
  `ci_failure_cache.py --catchup` на Stop — с cooldown 15 мин, чтобы частые
  Stop'ы не дёргали gh API.

  НИКОГДА не блокирует Stop (advisory, exit 0 всегда).

Opt-out: env `CI_CATCHUP_DISABLE=1` (общий с on-start вариантом).
Timeout: 5s (сам хук; фоновый subprocess живёт своей жизнью).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "ci_failure_cache.py"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
COOLDOWN_FILE = PROJECT_ROOT / ".claude" / "cache" / "ci-catchup-stop-last.txt"
COOLDOWN_SECONDS = 15 * 60


class CiCatchupOnStop(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("CI_CATCHUP_DISABLE") == "1":
            return None
        if not SCRIPT_PATH.exists() or not VENV_PYTHON.exists():
            return None

        # Cooldown: не чаще раза в 15 минут (Stop срабатывает часто)
        try:
            if (
                COOLDOWN_FILE.exists()
                and time.time() - COOLDOWN_FILE.stat().st_mtime < COOLDOWN_SECONDS
            ):
                return None
            COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
            COOLDOWN_FILE.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            return None

        limit = os.environ.get("CI_CATCHUP_LIMIT", "20")
        try:
            int(limit)
        except ValueError:
            limit = "20"

        try:
            subprocess.Popen(
                [str(VENV_PYTHON), str(SCRIPT_PATH), "--catchup", limit],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(PROJECT_ROOT),
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                    if sys.platform == "win32"
                    else 0
                ),
            )
        except (OSError, ValueError):
            return None

        return HookOutput().system_message(
            f"[CI-CATCHUP-STOP] mid-session backfill spawned (limit={limit}, cooldown 15m)"
        )


if __name__ == "__main__":
    CiCatchupOnStop().run()
