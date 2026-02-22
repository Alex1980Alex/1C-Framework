"""
Session Skill State — track recommended/activated skills per session.

Prevents redundant skill recommendations within the same session (1 hour).
Used by skill-router.py (record recommendations) and skill-usage-metrics.py
(record activations).

State file: .claude/cache/session-skills.json
Format:
{
    "started_at": "2026-02-21T13:00:00",
    "recommended": {"langchain-core": "2026-02-21T13:26:51", ...},
    "activated": {"langchain-core": "2026-02-21T13:26:52", ...}
}

Based on task_master.py patterns: atomic writes, FileLock, graceful degradation.
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Set

from shared.core_paths import get_cache_dir

CACHE_DIR = get_cache_dir()
SESSION_FILE = CACHE_DIR / "session-skills.json"

# Session timeout: if older than this, treat as new session
SESSION_TIMEOUT_SECONDS = 3600  # 1 hour


# --- File Locking (reuse pattern from task_master) ---

class _FileLock:
    """Lightweight file lock for session state."""

    def __init__(self, filepath: Path, timeout: float = 3.0):
        self.filepath = filepath
        self.timeout = timeout
        self._lock_file = None

    def __enter__(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.filepath.with_suffix(".lock")
        self._lock_file = open(lock_path, "w", encoding="utf-8")
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                self._platform_lock()
                return self
            except (OSError, IOError):
                time.sleep(0.05)
        return self  # Timeout: proceed anyway

    def __exit__(self, *args):
        if self._lock_file:
            try:
                self._platform_unlock()
            except (OSError, IOError):
                pass
            try:
                self._lock_file.close()
            except (OSError, IOError):
                pass

    def _platform_lock(self):
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _platform_unlock(self):
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            except (OSError, IOError):
                pass
        else:
            import fcntl
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)


# --- Atomic Write ---

def _atomic_write(filepath: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically: temp file + rename."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent), suffix=".tmp", prefix="session-"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if sys.platform == "win32" and filepath.exists():
            filepath.unlink()
        os.rename(tmp_path, str(filepath))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# --- Session State ---

def _read_state() -> Dict[str, Any]:
    """Read session state, return empty if missing/corrupt/expired."""
    if not SESSION_FILE.exists():
        return _empty_state()
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Check session expiry
        started = data.get("started_at", "")
        if started:
            started_dt = datetime.fromisoformat(started)
            if datetime.now() - started_dt > timedelta(seconds=SESSION_TIMEOUT_SECONDS):
                return _empty_state()  # Session expired
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return _empty_state()


def _write_state(data: Dict[str, Any]) -> None:
    """Write session state with lock."""
    with _FileLock(SESSION_FILE, timeout=3.0):
        _atomic_write(SESSION_FILE, data)


def _empty_state() -> Dict[str, Any]:
    """Fresh session state."""
    return {
        "started_at": datetime.now().isoformat(),
        "recommended": {},
        "activated": {},
    }


# --- Public API ---

def record_recommendation(skill_names: list[str]) -> None:
    """Record that skills were recommended in this session."""
    data = _read_state()
    now = datetime.now().isoformat()
    for name in skill_names:
        if name not in data.get("recommended", {}):
            data.setdefault("recommended", {})[name] = now
    _write_state(data)


def record_activation(skill_name: str) -> None:
    """Record that a skill was actually activated via Skill() tool."""
    data = _read_state()
    data.setdefault("activated", {})[skill_name] = datetime.now().isoformat()
    _write_state(data)


def get_already_recommended() -> Set[str]:
    """Get set of skills already recommended in this session."""
    data = _read_state()
    return set(data.get("recommended", {}).keys())


def get_already_activated() -> Set[str]:
    """Get set of skills already activated in this session."""
    data = _read_state()
    return set(data.get("activated", {}).keys())


def get_activation_rate() -> float:
    """Calculate activation rate: activated / recommended."""
    data = _read_state()
    recommended = len(data.get("recommended", {}))
    activated = len(data.get("activated", {}))
    if recommended == 0:
        return 0.0
    return activated / recommended


def get_session_metrics() -> Dict[str, Any]:
    """Get full session metrics for dashboard and monitoring.

    Returns dict with:
      - session_started: ISO timestamp
      - total_recommended: int
      - total_activated: int
      - activation_rate: float (0.0 - 1.0)
      - unactivated: list of skill names recommended but not activated
      - recommended_list: list of all recommended skill names
      - activated_list: list of all activated skill names
    """
    data = _read_state()
    recommended = data.get("recommended", {})
    activated = data.get("activated", {})

    return {
        "session_started": data.get("started_at", ""),
        "total_recommended": len(recommended),
        "total_activated": len(activated),
        "activation_rate": len(activated) / max(len(recommended), 1),
        "unactivated": sorted(set(recommended.keys()) - set(activated.keys())),
        "recommended_list": sorted(recommended.keys()),
        "activated_list": sorted(activated.keys()),
    }


def reset_session() -> None:
    """Force reset session state (for testing or new session)."""
    _write_state(_empty_state())
