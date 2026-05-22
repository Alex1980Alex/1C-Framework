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

from src.bsl.project_discovery import find_project_for_relpath  # noqa: E402
from src.framework_search.config import EXT_TO_LANGUAGE, MAX_FILE_BYTES, REPO_ROOT  # noqa: E402
from src.framework_search.file_walker import _matches_skip  # noqa: E402

LOG_PATH = PROJECT_ROOT / "cache" / "framework_search_reindex.log"
BSL_LOG_PATH = PROJECT_ROOT / "cache" / "bsl_reindex.log"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
INDEX_SCRIPT = PROJECT_ROOT / "scripts" / "index_framework.py"
BSL_INDEX_SCRIPT = PROJECT_ROOT / "scripts" / "reindex_bsl_qwen3.py"
# BSL common modules can legitimately be 1-2 MB; use a higher cap than the
# framework MAX_FILE_BYTES (512 KB tuned for Python/MD).
BSL_MAX_FILE_BYTES = 4 * 1024 * 1024  # 4 MB


def _changed_files(since_ref: str) -> list[str]:
    """Return repo-relative POSIX paths changed in <since_ref>..HEAD.

    Uses --diff-filter=ACMRT (added/copied/modified/renamed/type-changed),
    excluding deletions (which would be handled by next reindex's stale-delete).
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "--diff-filter=ACMRT", f"{since_ref}..HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return []
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def _split_bsl_and_framework(paths: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    """Partition changed files into framework_search and BSL pipelines.

    Returns:
        (framework_paths, bsl_groups) where bsl_groups is a list of dicts
        {"project": <abs path str>, "files": [<abs path str>, ...]} grouped
        by 1С project root so each spawn handles a single project.

    Framework: matches EXT_TO_LANGUAGE + passes SKIP_PATTERNS + size cap.
    BSL: matches '.bsl' + lives under a directory containing
         `.bsl-language-server.json` (the BSL project marker).
    """
    framework: list[str] = []
    bsl_by_project: dict[str, list[str]] = {}

    for rel in paths:
        abs_path = REPO_ROOT / rel
        if not abs_path.exists() or not abs_path.is_file():
            continue
        ext = Path(rel).suffix.lower()

        # BSL branch: .bsl under a marker-defined project root.
        if ext == ".bsl":
            project = _bsl_project_root(rel)
            if project is not None:
                try:
                    if abs_path.stat().st_size > BSL_MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                bsl_by_project.setdefault(str(project), []).append(str(abs_path))
                continue

        # Framework branch: standard extension + skip filter
        if _matches_skip(rel):
            continue
        if ext not in EXT_TO_LANGUAGE:
            continue
        try:
            if abs_path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        framework.append(rel)

    bsl_groups = [{"project": p, "files": fs} for p, fs in bsl_by_project.items()]
    return framework, bsl_groups


def _bsl_project_root(rel: str) -> Path | None:
    """Resolve repo-relative path to its BSL project root via marker discovery.

    A BSL project root is any directory containing `.bsl-language-server.json`.
    Walks UP from the file location to find the nearest such directory.

    Returns the absolute project root, or None if the path is not under a
    BSL project (e.g., framework code, docs, test fixtures).
    """
    return find_project_for_relpath(rel, REPO_ROOT)


def _spawn_detached_cmd(cmd: list[str], log_path: Path, header: str) -> None:
    """Launch a command in a detached background process.

    On Windows: creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    so the child survives the parent's exit and the terminal isn't tied to it.
    On POSIX: start_new_session=True (setsid).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "ab", buffering=0)
    log_fh.write(f"\n=== {os.getpid()} -> {header} ===\n".encode("utf-8", errors="ignore"))

    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=log_fh,
            creationflags=flags,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=log_fh,
            start_new_session=True,
            close_fds=True,
        )


def _spawn_framework_reindex(paths: list[str]) -> None:
    cmd = [
        str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable,
        str(INDEX_SCRIPT),
        "--paths",
        *paths,
    ]
    sample = paths[:3]
    header = f"framework reindex {len(paths)} files: {sample}{'...' if len(paths) > 3 else ''}"
    _spawn_detached_cmd(cmd, LOG_PATH, header)


def _spawn_bsl_reindex(project: str, files: list[str]) -> None:
    """Per-project BSL incremental reindex into bsl_code_v4_late.

    Uses --embedder qwen3-tei (HTTP backend) instead of qwen3-st to avoid
    GPU contention: TEI Docker already holds the only Qwen3-Embedding-8B
    FP16 copy (16 GB) — running qwen3-st would try to load a second copy
    and OOM on RTX 3090 24 GB.

    Trade-off: TEI returns pooled vectors only (no Late Chunking support),
    so incremental chunks land in bsl_code_v4_late with std pooling while
    the rest of the collection is Late-pooled. Quality impact estimated
    ~5-10% on those specific recently-edited symbols vs full Late re-pass.
    Acceptable for hot-path UX; user can re-align via manual full reindex
    when convenient (see roadmap §23 production command).
    """
    cmd = [
        str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable,
        str(BSL_INDEX_SCRIPT),
        "--project",
        project,
        "--paths",
        *files,
        "--embedder",
        "qwen3-tei",
        "--collection",
        "bsl_code_v4_late",
        "--batch-size",
        "32",
    ]
    sample = files[:3]
    header = (
        f"BSL reindex project={Path(project).name} "
        f"{len(files)} files: {[Path(f).name for f in sample]}"
        f"{'...' if len(files) > 3 else ''}"
    )
    _spawn_detached_cmd(cmd, BSL_LOG_PATH, header)


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-reindex helper for git hooks")
    ap.add_argument(
        "--since-ref",
        default="HEAD~1",
        help="Diff base (default HEAD~1 for post-commit; pass ORIG_HEAD for post-merge)",
    )
    ap.add_argument(
        "--max-files",
        type=int,
        default=200,
        help="Skip auto-reindex if more than N files changed (initial commit, "
        "branch switch with huge diff). Default 200.",
    )
    args = ap.parse_args()

    # First commit edge case: HEAD~1 doesn't exist.
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--verify", args.since_ref],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
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
            fh.write(f"\n=== skip auto-reindex: {len(changed)} files > max {args.max_files} ===\n")
        return 0

    framework_paths, bsl_groups = _split_bsl_and_framework(changed)
    if not framework_paths and not bsl_groups:
        return 0

    try:
        if framework_paths:
            _spawn_framework_reindex(framework_paths)
        for group in bsl_groups:
            _spawn_bsl_reindex(group["project"], group["files"])
    except Exception:
        # Spawn failures (missing venv Python, Popen error) must not block git commits.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
