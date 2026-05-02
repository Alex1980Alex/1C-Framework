"""BSL/1С project discovery via .bsl-language-server.json marker.

A 1С/BSL project is any directory containing a `.bsl-language-server.json`
configuration file (the standard config from 1c-syntax/bsl-language-server).
The optional `configurationRoot` field within tells where BSL/XML sources
live relative to the marker.

This module replaces hardcoded conventions like "src/projects/configuration/"
with a discovery mechanism that works for both:
  - Task folders under `configuration/<TICKET>/` (existing layout)
  - EDT projects at repo root with nested layout, e.g.:
        ИБTransportManagementDevelop/
          .bsl-language-server.json   ← marker (configurationRoot="Конфигурация/src")
          Конфигурация/                ← EDT project
            .project
            src/                       ← actual BSL files
          docs/                        ← ТЗ
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

# Skip these directory names during discovery (case-sensitive parts match)
_DISCOVERY_SKIP_PARTS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    ".tmp", "dist", "build", ".obsidian", ".mypy_cache",
    ".ruff_cache", ".pytest_cache",
})

# Specific paths to exclude even though they have .bsl-language-server.json
# (test fixtures, etc.)
_EXCLUDE_PATH_SUBSTRINGS = (
    "tools/bsl-ls/test-workspace",
)


def _should_skip(rel_parts: tuple[str, ...]) -> bool:
    """True if any part is in the skip set or path matches an exclusion."""
    if any(p in _DISCOVERY_SKIP_PARTS for p in rel_parts):
        return True
    rel_posix = "/".join(rel_parts).lower()
    return any(s in rel_posix for s in _EXCLUDE_PATH_SUBSTRINGS)


def find_bsl_projects(repo_root: Path) -> List[Path]:
    """Find all BSL project roots under `repo_root`.

    A project root is any directory containing `.bsl-language-server.json`,
    excluding test workspaces and build/cache directories.

    Returns:
        Absolute paths to project root directories, sorted.
    """
    repo_root = repo_root.resolve()
    projects: List[Path] = []
    for marker in repo_root.rglob(".bsl-language-server.json"):
        try:
            rel_parts = marker.relative_to(repo_root).parts
        except ValueError:
            continue
        if _should_skip(rel_parts):
            continue
        projects.append(marker.parent.resolve())
    return sorted(projects)


def get_bsl_source_root(project: Path) -> Path:
    """Read `configurationRoot` from project's .bsl-language-server.json.

    Defaults to "src" (BSL Language Server default) if the field is missing
    or the file cannot be parsed.
    """
    cfg_path = project / ".bsl-language-server.json"
    config_root = "src"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        config_root = cfg.get("configurationRoot", "src")
    except (OSError, json.JSONDecodeError):
        pass
    return (project / config_root).resolve()


def find_project_for_path(target: Path, repo_root: Path) -> Optional[Path]:
    """Walk UP from `target` to find the nearest BSL project root.

    Returns the directory containing `.bsl-language-server.json`, or None
    if no project was found before reaching `repo_root` boundary.
    """
    target = target.resolve()
    repo_root = repo_root.resolve()
    cur = target if target.is_dir() else target.parent
    while True:
        if (cur / ".bsl-language-server.json").exists():
            return cur
        if cur == cur.parent:
            return None
        try:
            if not cur.is_relative_to(repo_root):
                return None
        except ValueError:
            return None
        cur = cur.parent


def find_project_for_relpath(rel: str, repo_root: Path) -> Optional[Path]:
    """Resolve a repo-relative POSIX path and find its BSL project.

    Used by tools that receive repo-relative paths from `git diff` output.
    """
    abs_path = (repo_root / rel).resolve()
    return find_project_for_path(abs_path, repo_root)
