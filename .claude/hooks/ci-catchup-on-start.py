#!/usr/bin/env python3
"""
Hook: ci-catchup-on-start
Event: SessionStart
Purpose:
  - Auto-backfill `.claude/cache/ci-failures.jsonl` с recent FAILURE runs
    которые могли упасть пока Claude Code сессия была offline.
  - Closes gap: Monitor `bkozphbx9` session-bound, между сессиями нет
    auto-trigger для `scripts/ci_failure_cache.py`. SessionStart catchup
    приводит cache в актуальное состояние при каждом запуске.
  - Detached subprocess (timeout 30s background) — никогда не блокирует
    session bootstrap. Emit systemMessage с кратким status.
Timeout: 5s (hook itself; background subprocess до 30s).

Opt-out:
  - env `CI_CATCHUP_DISABLE=1` → hook skip
  - env `CI_CATCHUP_LIMIT=N` → override default --catchup=20

Graceful degradation: gh CLI down / no network → silent skip.
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "ci_failure_cache.py"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
BACKGROUND_TIMEOUT_S = 30


class CiCatchupOnStart(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("CI_CATCHUP_DISABLE") == "1":
            return None
        if not SCRIPT_PATH.exists() or not VENV_PYTHON.exists():
            return None

        limit = os.environ.get("CI_CATCHUP_LIMIT", "20")
        try:
            int(limit)
        except ValueError:
            limit = "20"

        try:
            subprocess.Popen(  # noqa: S603 — fixed argv, no shell
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
            f"[CI-CATCHUP] backfill spawned (limit={limit}, bg, timeout {BACKGROUND_TIMEOUT_S}s) — "
            f"cache: .claude/cache/ci-failures.jsonl"
        )


if __name__ == "__main__":
    CiCatchupOnStart().run()
