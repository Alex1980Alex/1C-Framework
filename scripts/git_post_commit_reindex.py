#!/usr/bin/env python3
"""
Git post-commit / post-merge auto-reindex helper for framework_search.

Reads changed files from git, filters via the framework_search SKIP_PATTERNS
+ EXT_TO_LANGUAGE rules, then spawns scripts/index_framework.py --paths ...
DETACHED in the background so the git command completes immediately.

Spawns silently — diagnostic output goes to a rotating log file at
cache/framework_search_reindex.log so the user's terminal stays clean.

Modes:
    post-commit:  --since-ref HEAD~1   → diff HEAD~1..HEAD
    post-merge:   --since-ref ORIG_HEAD → diff ORIG_HEAD..HEAD
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.framework_search.config import EXT_TO_LANGUAGE, MAX_FILE_BYTES, REPO_ROOT  # noqa: E402
from src.framework_search.file_walker import _matches_skip  # noqa: E402

LOG_PATH = PROJECT_ROOT / "cache" / "framework_search_reindex.log"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
INDEX_SCRIPT = PROJECT_ROOT / "scripts" / "index_framework.py"


def _changed_files(since_ref: str) -> list[str]:
    """Return repo-relative POSIX paths changed in <since_ref>..HEAD.

    Uses --diff-filter=ACMRT (added/copied/modified/renamed/type-changed),
    excluding deletions (which would be handled by next reindex's stale-delete).
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "--diff-filter=ACMRT",
             f"{since_ref}..HEAD"],
            cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return []
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def _filter_indexable(paths: list[str]) -> list[str]:
    """Keep only paths that are indexable per framework_search rules."""
    out: list[str] = []
    for rel in paths:
        if _matches_skip(rel):
            continue
        ext = Path(rel).suffix.lower()
        if ext not in EXT_TO_LANGUAGE:
            continue
        abs_path = REPO_ROOT / rel
        if not abs_path.exists() or not abs_path.is_file():
            continue
        try:
            if abs_path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        out.append(rel)
    return out


def _spawn_detached(paths: list[str]) -> None:
    """Launch index_framework.py in a detached background process.

    On Windows: creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    so the child survives the parent's exit and the terminal isn't tied to it.
    On POSIX: start_new_session=True (setsid).
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable,
        str(INDEX_SCRIPT),
        "--paths", *paths,
    ]

    log_fh = open(LOG_PATH, "ab", buffering=0)
    log_fh.write(
        f"\n=== {os.getpid()} -> reindex {len(paths)} files: {paths[:3]}{'...' if len(paths) > 3 else ''} ===\n"
        .encode("utf-8", errors="ignore")
    )

    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL, stdout=log_fh, stderr=log_fh,
            creationflags=flags, close_fds=True,
        )
    else:
        subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL, stdout=log_fh, stderr=log_fh,
            start_new_session=True, close_fds=True,
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-reindex helper for git hooks")
    ap.add_argument(
        "--since-ref", default="HEAD~1",
        help="Diff base (default HEAD~1 for post-commit; pass ORIG_HEAD for post-merge)",
    )
    ap.add_argument(
        "--max-files", type=int, default=200,
        help="Skip auto-reindex if more than N files changed (initial commit, "
             "branch switch with huge diff). Default 200.",
    )
    args = ap.parse_args()

    # First commit edge case: HEAD~1 doesn't exist.
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--verify", args.since_ref],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return 0  # silent: nothing to compare against

    changed = _changed_files(args.since_ref)
    if not changed:
        return 0
    if len(changed) > args.max_files:
        # Bulk operation — let MCP lazy-check or manual reindex handle it.
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(
                f"\n=== skip auto-reindex: {len(changed)} files > max {args.max_files} ===\n"
            )
        return 0

    indexable = _filter_indexable(changed)
    if not indexable:
        return 0

    _spawn_detached(indexable)
    return 0


if __name__ == "__main__":
    sys.exit(main())
