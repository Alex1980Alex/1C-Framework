#!/usr/bin/env python3
"""
Hook: session-mypy-banner
Event: SessionStart
Purpose:
  - Read mypy-baseline.txt at repo root, count errors (line count).
  - If git available, compute delta vs main branch's baseline (best-effort).
  - Print informational systemMessage. NEVER blocks.

Pattern: pure-informational banner. Roadmap 260514 Phase 0
companion. Standalone — does not call mypy itself (slow). Reads
the pre-committed snapshot only.

Timeout: 5s (file read + 1-2 git commands)
Graceful degradation: any error -> silent allow (BaseHook.run handles).
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_FILE = PROJECT_ROOT / "mypy-baseline.txt"


def _count_baseline_errors() -> int | None:
    """Count non-empty, non-note lines in baseline file."""
    if not BASELINE_FILE.exists():
        return None
    try:
        with open(BASELINE_FILE, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return None


def _delta_vs_main() -> int | None:
    """Best-effort: line delta between HEAD and origin/main for baseline.

    Returns:
        Positive = baseline grew (more errors), negative = shrank, 0 = same,
        None if git unavailable / branch detached / file untracked.
    """
    try:
        r = subprocess.run(
            ["git", "diff", "--numstat", "origin/main", "--", "mypy-baseline.txt"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        added, removed, *_ = r.stdout.split()
        return int(added) - int(removed)
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


class SessionMypyBanner(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        count = _count_baseline_errors()
        if count is None:
            return None  # No baseline yet — silent

        delta = _delta_vs_main()
        if delta is None:
            msg = f"[mypy] baseline: {count} known errors (no main delta available)"
        elif delta == 0:
            msg = f"[mypy] baseline: {count} known errors (= main)"
        else:
            sign = "+" if delta > 0 else ""
            msg = f"[mypy] baseline: {count} known errors ({sign}{delta} vs main)"

        return HookOutput().system_message(msg)


if __name__ == "__main__":
    SessionMypyBanner().run()
