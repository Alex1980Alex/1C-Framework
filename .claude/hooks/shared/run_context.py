"""Slash-command run context — cross-hook correlation by run_id.

Stores `{session_id: {run_id, command, started_at}}` so multiple Claude Code
sessions can run concurrent slash commands without colliding.

Used by:
- slash-command-tracker (UserPromptSubmit) — set_run() at command start
- mcp-invocation-logger (PreToolUse/PostToolUse) — get_run_id() to tag MCP calls
- slash-command-tracker (Stop) — clear_run() at command end

Storage: data/.current-runs.json (small map, atomic-write via tmp+rename).
Size guard: any session entry older than MAX_AGE_HOURS is dropped on read
(stale entries from crashed Claude sessions never accumulate).

Graceful degradation: every helper swallows exceptions and returns sentinel
values — logging must never block the parent hook.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

MAX_AGE_HOURS = 12

_MAP_FILE: Optional[Path] = None


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


def _read_map() -> dict:
    """Read map, dropping entries older than MAX_AGE_HOURS."""
    filepath = _get_map_file()
    if not filepath.exists():
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
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
    """Atomic write: tmp file + rename, so concurrent reads never see partial JSON."""
    filepath = _get_map_file()
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
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
    """Register a slash-command run for the given Claude session."""
    if not session_id or not run_id:
        return
    try:
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
    """Remove and return the entry for this session (Stop hook)."""
    if not session_id:
        return {}
    try:
        data = _read_map()
        entry = data.pop(session_id, {})
        _write_map(data)
        return dict(entry)
    except Exception:
        return {}
