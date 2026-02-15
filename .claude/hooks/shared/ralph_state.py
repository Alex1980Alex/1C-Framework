"""Centralized Ralph Wiggum state management.

Provides atomic read/write for Ralph flag files:
- .ralph_active       — flag: Ralph loop is active
- .ralph_criteria.json — structured completion criteria
- .ralph_wiggum_count  — iteration counter

Used by both ralph_activator.py (writes) and ralph_wiggum_stop.py (reads).

Paths resolved via core_paths (supports Core in ~/.claude/ + Framework in .claude/).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from shared.core_paths import get_state_dir

_STATE_DIR: Path | None = None

DEFAULT_MAX_ITERATIONS = 15
STALE_HOURS = 2  # Auto-deactivate after 2 hours


def _get_state_dir() -> Path:
    """Lazy-resolve state directory (cached after first call)."""
    global _STATE_DIR
    if _STATE_DIR is None:
        _STATE_DIR = get_state_dir()
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
    return _STATE_DIR


def _active_file() -> Path:
    return _get_state_dir() / ".ralph_active"


def _criteria_file() -> Path:
    return _get_state_dir() / ".ralph_criteria.json"


def _iteration_file() -> Path:
    return _get_state_dir() / ".ralph_wiggum_count"


def is_active() -> bool:
    """Check if Ralph loop is currently active."""
    return _active_file().exists()


def activate(
    task_type: str,
    prompt_excerpt: str,
    criteria: list[str],
    max_iterations: int = 10,
) -> None:
    """Activate Ralph mode with structured criteria.

    Creates .ralph_active flag and .ralph_criteria.json.
    Resets iteration counter to 0.
    """
    _active_file().touch()

    data = {
        "task_type": task_type,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_excerpt": prompt_excerpt[:200],
        "completion_criteria": criteria,
        "max_iterations": max_iterations,
    }
    _atomic_write_json(_criteria_file(), data)
    set_iteration(0)


def deactivate() -> None:
    """Deactivate Ralph mode. Removes all state files."""
    for f in (_active_file(), _criteria_file(), _iteration_file()):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


def get_criteria() -> dict | None:
    """Read structured criteria. Returns None if file missing."""
    try:
        return json.loads(_criteria_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def get_iteration() -> int:
    """Get current iteration count."""
    try:
        return int(_iteration_file().read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError, OSError):
        return 0


def set_iteration(count: int) -> None:
    """Set iteration counter."""
    _iteration_file().write_text(str(count), encoding="utf-8")


def increment_iteration() -> int:
    """Increment and return new iteration count."""
    count = get_iteration() + 1
    set_iteration(count)
    return count


def get_max_iterations() -> int:
    """Get max iterations from criteria or default."""
    criteria = get_criteria()
    if criteria:
        return criteria.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    return DEFAULT_MAX_ITERATIONS


def is_stale() -> bool:
    """Check if activation is older than STALE_HOURS."""
    criteria = get_criteria()
    if not criteria:
        return False
    try:
        activated = datetime.fromisoformat(criteria["activated_at"])
        elapsed = datetime.now(timezone.utc) - activated
        return elapsed.total_seconds() > STALE_HOURS * 3600
    except (KeyError, ValueError):
        return False


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically via temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix=".ralph_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
