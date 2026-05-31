"""§22 Confidence-Lifecycle Trace Log.

Single-file shared implementation for confidence mutation events (apply, reinforce,
decay, archive). Writers (reinforce.py, pattern_reinforce.py hooks) append structured
JSON lines. Fail-soft: no exception ever raised. Opt-out: CONFIDENCE_LOG_DISABLE=1.
Analogue to §24 (surfacing-trace.log).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOG_ENABLED = os.environ.get("CONFIDENCE_LOG_DISABLE") != "1"
_LOG_CAP_BYTES = 2_000_000


def _log_file() -> Path:
    """Return path to confidence-lifecycle.log, honoring CLAUDE_CACHE_DIR override."""
    cache_dir = os.environ.get("CLAUDE_CACHE_DIR")
    if cache_dir:
        base = Path(cache_dir)
    else:
        base = _PROJECT_ROOT / ".claude" / "cache"
    return base / "confidence-lifecycle.log"


def log_event(event: str, **fields: Any) -> None:
    """Append one JSON record to confidence-lifecycle.log.

    Args:
        event: Event type string (e.g. 'apply', 'reinforce', 'decay', 'archive').
        **fields: Additional JSON-serializable fields.
    """
    if not _LOG_ENABLED:
        return

    try:
        from datetime import datetime

        path = _log_file()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic size-rotation before append.
        try:
            if path.exists() and path.stat().st_size > _LOG_CAP_BYTES:
                data = path.read_bytes()
                tail_data = data[-(_LOG_CAP_BYTES // 2):]
                # Drop partial first line.
                idx = tail_data.find(b"\n")
                if idx != -1:
                    tail_data = tail_data[idx + 1:]

                # Write via tempfile for atomicity.
                fd, tmp_path = tempfile.mkstemp(
                    dir=path.parent,
                    suffix=".tmp",
                    prefix="conflog-"
                )
                try:
                    with os.fdopen(fd, "wb") as fh:
                        fh.write(tail_data)
                    os.replace(tmp_path, path)
                except Exception:
                    os.unlink(tmp_path)
                    raise
        except Exception:
            pass  # Rotation failure does not block append.

        # Build and append record.
        record = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "event": event,
        }
        record.update(fields)

        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Fully fail-soft: never raise.
