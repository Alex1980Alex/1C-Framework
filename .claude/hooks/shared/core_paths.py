"""Core Paths — single source of truth for all hook infrastructure paths.

Resolves paths dynamically instead of relying on __file__ parent traversal.
This enables Core hooks to live in ~/.claude/ while Framework hooks live in
.claude/ — both share the same state files and cache.

Discovery order for each path:
1. Environment variable (explicit override)
2. Project-level .claude/ (if exists)
3. User-level ~/.claude/ (fallback)

State files (Ralph, hook-todos) ALWAYS use project-level .claude/ because
they are per-session, per-project.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Discovery ---

def _find_project_claude_dir() -> Path | None:
    """Find project-level .claude/ directory.

    Walks up from CWD (or CLAUDE_PROJECT_DIR) looking for .claude/.
    Returns None if not found.
    """
    start = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    current = Path(start).resolve()
    for _ in range(10):  # Max 10 levels up
        candidate = current / ".claude"
        if candidate.is_dir():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _user_claude_dir() -> Path:
    """User-level ~/.claude/ directory."""
    return Path.home() / ".claude"


# --- Public API: resolved paths ---

def get_project_dir() -> Path:
    """Project-level .claude/ (for state, cache, project hooks).

    Falls back to ~/.claude/ if no project found.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        p = Path(env).resolve() / ".claude"
        if p.is_dir():
            return p

    found = _find_project_claude_dir()
    if found:
        return found

    return _user_claude_dir()


def get_cache_dir() -> Path:
    """Cache directory for hook-todos, lock files.

    Always project-level: .claude/cache/
    """
    override = os.environ.get("CLAUDE_CACHE_DIR")
    if override:
        return Path(override).resolve()
    return get_project_dir() / "cache"


def get_state_dir() -> Path:
    """State directory for Ralph files (.ralph_active, etc.).

    Always project-level: .claude/hooks/ (backward compatible).
    Or overridden via CLAUDE_STATE_DIR.
    """
    override = os.environ.get("CLAUDE_STATE_DIR")
    if override:
        return Path(override).resolve()
    return get_project_dir() / "hooks"


def get_core_dir() -> Path:
    """Core hooks directory (base/, shared/).

    Priority:
    1. CLAUDE_CORE_DIR env var
    2. ~/.claude/hooks/ (user-level — after migration)
    3. .claude/hooks/ (project-level — before migration)
    """
    override = os.environ.get("CLAUDE_CORE_DIR")
    if override:
        return Path(override).resolve()

    # Check user-level first (post-migration)
    user = _user_claude_dir() / "hooks"
    if (user / "base").is_dir() and (user / "shared").is_dir():
        return user

    # Fallback: project-level (pre-migration)
    project = get_project_dir() / "hooks"
    if (project / "base").is_dir():
        return project

    return user  # Default to user-level even if not yet set up
