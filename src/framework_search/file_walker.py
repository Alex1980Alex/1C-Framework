"""Discover files for indexing under configured roots, respecting skip patterns."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterator

from .config import (
    DEFAULT_INDEX_FILES,
    DEFAULT_INDEX_ROOTS,
    EXT_TO_LANGUAGE,
    MAX_FILE_BYTES,
    REPO_ROOT,
    SKIP_PATTERNS,
)

logger = logging.getLogger(__name__)


def _matches_skip(posix_path: str) -> bool:
    """Return True if the path matches any SKIP_PATTERNS rule.

    Two match modes:
      1. Substring (any position) — patterns like '/__pycache__/' that should
         match nested dirs (e.g. 'src/foo/__pycache__/x').
      2. Prefix without leading slash — for top-level skips like
         '/configuration/' to also catch 'configuration/...'
         since repo-relative POSIX paths don't have a leading slash.
    """
    low = posix_path.lower()
    for p in SKIP_PATTERNS:
        pl = p.lower()
        if pl in low:
            return True
        if pl.startswith("/") and low.startswith(pl[1:]):
            return True
    return False


def iter_indexable_files(
    roots: list[str] | None = None,
    extra_files: list[str] | None = None,
    repo_root: Path = REPO_ROOT,
) -> Iterator[tuple[Path, str, str]]:
    """Yield (absolute_path, posix_relative_path, language) for each file to index.

    Skips: SKIP_PATTERNS, files larger than MAX_FILE_BYTES, files with unknown
    extensions, symlinks pointing outside repo_root.
    """
    roots = roots if roots is not None else DEFAULT_INDEX_ROOTS
    extra_files = extra_files if extra_files is not None else DEFAULT_INDEX_FILES

    seen: set[Path] = set()

    # Walk root directories.
    for root in roots:
        root_path = (repo_root / root).resolve()
        if not root_path.exists() or not root_path.is_dir():
            logger.debug("file_walker: root %s missing, skipping", root)
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            # Prune skipped dirs in-place to avoid descending.
            dirnames[:] = [
                d for d in dirnames
                if not _matches_skip(_posix_rel(repo_root, Path(dirpath) / d) + "/")
            ]
            for fname in filenames:
                fp = Path(dirpath) / fname
                yield from _maybe_emit(repo_root, fp, seen)

    # Single-file roots.
    for f in extra_files:
        fp = (repo_root / f).resolve()
        if fp.exists() and fp.is_file():
            yield from _maybe_emit(repo_root, fp, seen)


def _maybe_emit(
    repo_root: Path, fp: Path, seen: set[Path],
) -> Iterator[tuple[Path, str, str]]:
    try:
        fp_resolved = fp.resolve()
    except OSError:
        return
    # Reject symlinks pointing outside the repo (docstring contract).
    try:
        fp_resolved.relative_to(repo_root)
    except ValueError:
        logger.debug("file_walker: %s resolves outside repo_root, skipping", fp)
        return
    if fp_resolved in seen:
        return
    seen.add(fp_resolved)

    rel = _posix_rel(repo_root, fp_resolved)
    if _matches_skip(rel):
        return

    ext = fp_resolved.suffix.lower()
    language = EXT_TO_LANGUAGE.get(ext)
    if not language:
        return

    try:
        size = fp_resolved.stat().st_size
    except OSError:
        return
    if size > MAX_FILE_BYTES:
        logger.debug("file_walker: %s too large (%d bytes), skipping", rel, size)
        return

    yield fp_resolved, rel, language


def _posix_rel(repo_root: Path, p: Path) -> str:
    try:
        return p.relative_to(repo_root).as_posix()
    except ValueError:
        return p.as_posix()
