"""
Hook Lock — inter-hook synchronization via JSON lock file.

Adapted from 1C-Enterprise_Framework shared/hook_lock.py.
Prevents race conditions when multiple hooks fire simultaneously.

Usage:
    with hook_lock("my-hook-name", timeout=10) as acquired:
        if acquired:
            # Critical section
            pass
"""

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from shared.core_paths import get_cache_dir

# Lock file location resolved via core_paths (supports Core/Framework separation)
CACHE_DIR = get_cache_dir()
LOCK_FILE = CACHE_DIR / "hooks-lock.json"

# Stale lock threshold (seconds)
STALE_THRESHOLD = 30


def _read_lock() -> dict:
    """Read current lock state."""
    if not LOCK_FILE.exists():
        return {}
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_lock(data: dict) -> None:
    """Write lock state."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass


def _is_stale(lock_data: dict) -> bool:
    """Check if lock is stale (older than threshold)."""
    acquired_at = lock_data.get("acquired_at", "")
    if not acquired_at:
        return True
    try:
        lock_time = datetime.fromisoformat(acquired_at)
        elapsed = (datetime.now() - lock_time).total_seconds()
        return elapsed > STALE_THRESHOLD
    except (ValueError, TypeError):
        return True


def acquire_lock(hook_name: str, timeout: float = 10.0) -> bool:
    """Try to acquire the lock. Returns True if acquired."""
    deadline = time.time() + timeout

    while time.time() < deadline:
        lock_data = _read_lock()

        # Lock free or stale
        if not lock_data.get("holder") or _is_stale(lock_data):
            _write_lock({
                "holder": hook_name,
                "acquired_at": datetime.now().isoformat(),
                "pid": os.getpid(),
            })
            return True

        # Already held by us
        if lock_data.get("holder") == hook_name:
            return True

        time.sleep(0.1)

    return False


def release_lock(hook_name: str) -> bool:
    """Release the lock if held by this hook."""
    lock_data = _read_lock()
    if lock_data.get("holder") == hook_name:
        _write_lock({})
        return True
    return False


@contextmanager
def hook_lock(hook_name: str, timeout: float = 10.0):
    """Context manager for hook synchronization.

    Usage:
        with hook_lock("my-hook") as acquired:
            if acquired:
                # safe to proceed
    """
    acquired = False
    try:
        acquired = acquire_lock(hook_name, timeout)
        yield acquired
    finally:
        if acquired:
            release_lock(hook_name)
