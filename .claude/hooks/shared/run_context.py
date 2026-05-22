"""Slash-command run context — cross-hook correlation by run_id.

Stores `{session_id: {run_id, command, started_at}}` so multiple Claude Code
sessions can run concurrent slash commands without colliding.

Used by:
- slash-command-tracker (UserPromptExpansion) — set_run() at command start
- mcp-invocation-logger (PreToolUse/PostToolUse) — get_run_id() to tag MCP calls
- slash-command-tracker (Stop) — clear_run() at command end

Storage: data/.current-runs.json (small map, atomic-write via tmp+rename).
Size guard: any session entry older than MAX_AGE_HOURS is dropped on read
(stale entries from crashed Claude sessions never accumulate).

Graceful degradation: every helper swallows exceptions and returns sentinel
values — logging must never block the parent hook.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

MAX_AGE_HOURS = 12
TMP_GC_AGE_SECONDS = 3600  # cleanup orphan .tmp files older than 1 hour
LOCK_TIMEOUT_SECONDS = 2.0
LOCK_RETRY_DELAY = 0.05

# Resolve platform locking backend once at import time. Repeated try/import in
# the lock context manager would still work (CPython caches sys.modules) but
# adds noise — flags are clearer at the call site.
try:
    import msvcrt as _msvcrt  # type: ignore[import-not-found]

    _HAS_MSVCRT = True
except ImportError:
    _msvcrt = None  # type: ignore[assignment]
    _HAS_MSVCRT = False

try:
    import fcntl as _fcntl  # type: ignore[import-not-found]

    _HAS_FCNTL = True
except ImportError:
    _fcntl = None  # type: ignore[assignment]
    _HAS_FCNTL = False

_MAP_FILE: Path | None = None


def _get_map_file() -> Path:
    """Resolve data/.current-runs.json path. Cached after first call."""
    global _MAP_FILE
    if _MAP_FILE is not None:
        return _MAP_FILE

    try:
        from shared.core_paths import get_project_dir

        project_root = get_project_dir().parent
    except ImportError:
        # Fallback: hooks/shared/ -> hooks/ -> .claude/ -> project/
        project_root = Path(__file__).resolve().parent.parent.parent.parent

    _MAP_FILE = project_root / "data" / ".current-runs.json"
    return _MAP_FILE


@contextlib.contextmanager
def _file_lock(filepath: Path) -> Iterator[bool]:
    """Best-effort exclusive lock around the map file.

    Uses msvcrt.locking on Windows, fcntl.flock on POSIX. Lock is held on a
    sidecar `.lock` file (separate from the data file so locking doesn't
    interfere with the atomic rename in _write_map).

    Yields True if the lock was acquired, False on timeout or unsupported
    platform — callers can still proceed (degrades to old non-locked behavior),
    so concurrent overwrites only become more likely, not actually broken.

    Open/setup failures are handled BEFORE entering the protected block, so
    there is exactly one `yield` reachable per invocation — a generator-based
    contextmanager with two yields would raise RuntimeError if the caller's
    body propagated an exception.
    """
    lock_path = filepath.with_suffix(filepath.suffix + ".lock")

    # Setup phase — any OSError here means we never acquired anything,
    # so yield False once and exit. No fd, no lock to release.
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        yield False
        return

    # Acquire phase — try to grab the lock; either way we yield exactly once.
    locked = False
    try:
        deadline = time.time() + LOCK_TIMEOUT_SECONDS
        if _HAS_MSVCRT:
            while time.time() < deadline:
                try:
                    _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    time.sleep(LOCK_RETRY_DELAY)
        elif _HAS_FCNTL:
            while time.time() < deadline:
                try:
                    _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                    locked = True
                    break
                except OSError:
                    time.sleep(LOCK_RETRY_DELAY)
        # else: no locking backend — caller proceeds unprotected.

        yield locked
    finally:
        if locked:
            try:
                if _HAS_MSVCRT:
                    _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
                elif _HAS_FCNTL:
                    _fcntl.flock(fd, _fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
            pass


def _gc_orphan_tmp(directory: Path) -> None:
    """Remove .current-runs.*.tmp files older than TMP_GC_AGE_SECONDS.

    Orphans appear when a process is killed between mkstemp and os.replace.
    The 1-hour threshold is way longer than any legitimate atomic-write
    sequence, so live writes are never collected.
    """
    try:
        cutoff = time.time() - TMP_GC_AGE_SECONDS
        for tmp in directory.glob(".current-runs.*.tmp"):
            try:
                if tmp.stat().st_mtime < cutoff:
                    tmp.unlink()
            except OSError:
                continue
    except OSError:
        pass


def _read_map() -> dict:
    """Read map, dropping entries older than MAX_AGE_HOURS."""
    filepath = _get_map_file()
    if not filepath.exists():
        return {}
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        cutoff = datetime.now() - timedelta(hours=MAX_AGE_HOURS)
        fresh = {}
        for sid, entry in data.items():
            try:
                started = datetime.fromisoformat(entry.get("started_at", ""))
                if started >= cutoff:
                    fresh[sid] = entry
            except (ValueError, TypeError):
                continue
        return fresh
    except (json.JSONDecodeError, OSError):
        return {}


def _write_map(data: dict) -> None:
    """Atomic write: tmp file + rename, so concurrent reads never see partial JSON.

    Also opportunistically cleans orphan .tmp files from killed processes — the
    GC pass is cheap (single glob) and runs only when we're already touching
    this directory.
    """
    filepath = _get_map_file()
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        _gc_orphan_tmp(filepath.parent)
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".current-runs.", suffix=".tmp", dir=str(filepath.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, filepath)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError:
        pass


def set_run(session_id: str, run_id: str, command: str) -> None:
    """Register a slash-command run for the given Claude session.

    Read-modify-write is wrapped in _file_lock so concurrent Claude sessions
    don't drop each other's entries. Falls back to unprotected RMW if locking
    is unavailable — same risk as the old code, never strictly worse.
    """
    if not session_id or not run_id:
        return
    try:
        with _file_lock(_get_map_file()):
            data = _read_map()
            data[session_id] = {
                "run_id": run_id,
                "command": command,
                "started_at": datetime.now().isoformat(),
            }
            _write_map(data)
    except Exception:
        pass


def get_run_id(session_id: str) -> str:
    """Return run_id for the active slash-command in this session, or '' if none."""
    if not session_id:
        return ""
    try:
        data = _read_map()
        entry = data.get(session_id) or {}
        return str(entry.get("run_id", ""))
    except Exception:
        return ""


def get_run(session_id: str) -> dict:
    """Return full entry {run_id, command, started_at} or empty dict."""
    if not session_id:
        return {}
    try:
        data = _read_map()
        return dict(data.get(session_id) or {})
    except Exception:
        return {}


def clear_run(session_id: str) -> dict:
    """Remove and return the entry for this session (Stop hook).

    Locked RMW for the same reason as set_run.
    """
    if not session_id:
        return {}
    try:
        with _file_lock(_get_map_file()):
            data = _read_map()
            entry = data.pop(session_id, {})
            _write_map(data)
            return dict(entry)
    except Exception:
        return {}
