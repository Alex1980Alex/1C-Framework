#!/usr/bin/env python3
"""
Hook: submodule-status-check
Event: SessionStart
Purpose:
  - Detect uncommitted changes inside registered git submodules.
  - Parent repo `git status` shows only pointer drift (m flag), hiding
    100+ files of work-in-progress (closes coverage Gap 1 from roadmap
    260515 §Phase B).
  - Emits systemMessage with per-submodule counts so user sees stale
    changes at session start.
  - Optional auto-commit via SUBMODULE_AUTO_COMMIT=1 env (default OFF —
    detection only; 1С BSL workflow needs manual review).
Timeout: 10s.

Graceful degradation: any error → silent allow (BaseHook.run wraps).
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GITMODULES_PATH = PROJECT_ROOT / ".gitmodules"
GIT_TIMEOUT_S = 5
MAX_SUBMODULES_DISPLAY = 5
AUTO_COMMIT_ENV = "SUBMODULE_AUTO_COMMIT"


class SubmoduleStatus(NamedTuple):
    path: str
    modified: int
    untracked: int

    @property
    def total(self) -> int:
        return self.modified + self.untracked

    @property
    def has_changes(self) -> bool:
        return self.total > 0


def _parse_gitmodules() -> list[str]:
    """Extract `path = ...` values from .gitmodules. Returns relative paths."""
    if not GITMODULES_PATH.exists():
        return []
    try:
        content = GITMODULES_PATH.read_text(encoding="utf-8")
    except OSError:
        return []
    return re.findall(r"^\s*path\s*=\s*(.+?)\s*$", content, flags=re.MULTILINE)


def _check_submodule(rel_path: str) -> SubmoduleStatus | None:
    """Run `git status --porcelain` inside submodule. Returns counts or None on error."""
    full_path = PROJECT_ROOT / rel_path
    if not full_path.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            cwd=str(full_path),
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None

    modified = 0
    untracked = 0
    for line in result.stdout.splitlines():
        if not line or len(line) < 3:
            continue
        flags = line[:2]
        if "?" in flags:
            untracked += 1
        else:
            modified += 1
    return SubmoduleStatus(path=rel_path, modified=modified, untracked=untracked)


def _auto_commit(status: SubmoduleStatus) -> bool:
    """Auto-commit all changes inside submodule. Returns True on success."""
    full_path = PROJECT_ROOT / status.path
    msg = (
        f"chore: auto-save {status.modified} modified, "
        f"{status.untracked} untracked file(s) [submodule-status-check]"
    )
    try:
        subprocess.run(
            ["git", "add", "-A"],
            capture_output=True,
            timeout=GIT_TIMEOUT_S,
            cwd=str(full_path),
        )
        result = subprocess.run(
            ["git", "commit", "-m", msg, "--no-verify"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S * 2,
            cwd=str(full_path),
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


class SubmoduleStatusCheck(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        paths = _parse_gitmodules()
        if not paths:
            return None

        dirty: list[SubmoduleStatus] = []
        for p in paths:
            status = _check_submodule(p)
            if status and status.has_changes:
                dirty.append(status)

        if not dirty:
            return None

        auto_commit = os.environ.get(AUTO_COMMIT_ENV) == "1"
        committed: list[str] = []
        if auto_commit:
            for s in dirty:
                if _auto_commit(s):
                    committed.append(s.path)

        # Build user-facing message
        total_files = sum(s.total for s in dirty)
        lines = [
            f"[SUBMODULE-STATUS] {len(dirty)} submodule(s) with uncommitted "
            f"changes ({total_files} files total)"
        ]
        for s in sorted(dirty, key=lambda x: -x.total)[:MAX_SUBMODULES_DISPLAY]:
            short = s.path.split("/")[-1][:40]
            marker = " [auto-committed]" if s.path in committed else ""
            lines.append(f"  - {short}: {s.modified} modified, {s.untracked} untracked{marker}")
        if len(dirty) > MAX_SUBMODULES_DISPLAY:
            lines.append(f"  ... and {len(dirty) - MAX_SUBMODULES_DISPLAY} more")
        if not auto_commit:
            lines.append("  (set SUBMODULE_AUTO_COMMIT=1 to auto-commit; default detection-only)")

        return HookOutput().system_message("\n".join(lines))


if __name__ == "__main__":
    SubmoduleStatusCheck().run()
