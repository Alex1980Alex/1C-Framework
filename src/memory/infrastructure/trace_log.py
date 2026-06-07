"""Generic per-process trace log (§27 P1) — shared JSONL writer.

One implementation of the §22 ``lifecycle_log`` / §26 ``ingest_metrics``
convention in a single place: atomic size-rotation, fail-soft, metadata-only,
per-log opt-out env + a global kill-switch. The P1 process logs (routing /
federated-read / propagation / circuit-breaker) write through it; §27 P3 folds
these into the unified CloudEvents envelope.

Conventions (do not break):
  - **Fail-soft** — never raises into a caller (file/JSON errors swallowed).
  - **Metadata only** — counts / ids / floats / truncated errors; NEVER content
    bodies (prompts / pattern text).
  - **Opt-out** — per-log ``disable_env`` + global ``MEMORY_TRACE_DISABLE=1``.
  - **Atomic size-rotation** at ~2 MB (keep the newest half).

Roadmap: ``docs/roadmap/260605_ROADMAP_MEMORY_FULL_OBSERVABILITY.md`` (§27 P1).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# infrastructure/ -> memory/ -> src/ -> <root>
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CAP_BYTES = 2_000_000


def _cache_dir() -> Path:
    """Resolve the cache dir per call (honors CLAUDE_CACHE_DIR for tests/relocation)."""
    override = os.environ.get("CLAUDE_CACHE_DIR")
    return Path(override) if override else _PROJECT_ROOT / ".claude" / "cache"


def _rotate(path: Path) -> None:
    """Atomic size-rotation: keep the newest half when the file exceeds the cap."""
    try:
        if path.exists() and path.stat().st_size > _CAP_BYTES:
            data = path.read_bytes()[-(_CAP_BYTES // 2) :]
            idx = data.find(b"\n")
            if idx != -1:
                data = data[idx + 1 :]  # drop partial first line
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix="trace-")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, str(path))
            except Exception:
                os.unlink(tmp)
                raise
    except Exception:
        pass  # rotation failure never blocks the append


def write_trace(
    log_filename: str,
    event: str,
    *,
    disable_env: str | None = None,
    **fields: Any,
) -> None:
    """Append one JSON record to ``.claude/cache/<log_filename>``. Fully fail-soft.

    Args:
        log_filename: target file name, e.g. ``"memory-routing.log"``.
        event: event type string.
        disable_env: env var that disables *this* log when set to ``"1"``.
        **fields: metadata-only JSON-serializable fields (NEVER content bodies).
    """
    if os.environ.get("MEMORY_TRACE_DISABLE") == "1":  # global kill-switch
        return
    if disable_env and os.environ.get(disable_env) == "1":
        return
    try:
        from datetime import datetime

        path = _cache_dir() / log_filename
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate(path)
        record: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "event": event,
        }
        record.update(fields)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # fully fail-soft: never raise


__all__ = ["write_trace"]
