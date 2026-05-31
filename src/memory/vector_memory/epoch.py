"""§24 — confidence-store epoch marker (cross-process cache-invalidation signal).

The ``memory-first-hook`` execution cache memoizes the surfacing pipeline by
``hash(query_tokens)`` for ``MEMORY_SURFACE_CACHE_TTL`` seconds.  Without an
invalidation signal a pattern archived / confidence-collapsed mid-TTL keeps
being surfaced (and re-reinforced) until the entry expires.

This module is that signal.  Every code path that mutates a learned-pattern's
confidence / archived state calls :func:`bump`, which writes ``time.time()`` to
a tiny shared file.  The hook reads it via :func:`read` (a cheap local stat +
read — **no Qdrant roundtrip**) and folds the value into its cache key, so any
mutation produces a fresh key -> instant cache miss -> recompute.

Why a timestamp and not a counter
---------------------------------
We only need the value to *change* on any mutation, not to be an exact count.
A timestamp is race-tolerant: two processes bumping concurrently both write a
near-equal ``time.time()`` and the last writer wins — no lost-increment bug,
and the key still changes.  A monotonic counter would need read-modify-write
coordination across the hook and the MCP server processes.

All functions are fail-soft: I/O errors never raise into a caller.  A failed
:func:`read` returns ``0.0`` (key degrades to the legacy TTL-only behaviour);
a failed :func:`bump` is silently dropped (worst case: one stale TTL window).
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

# Resolve <root> from this file: vector_memory/ -> memory/ -> src/ -> <root>
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _epoch_file() -> Path:
    """Path to the epoch marker. Honors CLAUDE_CACHE_DIR (tests / relocation)."""
    override = os.environ.get("CLAUDE_CACHE_DIR")
    base = Path(override).resolve() if override else (_PROJECT_ROOT / ".claude" / "cache")
    return base / "confidence-epoch.txt"


def bump() -> None:
    """Mark the confidence store as changed (atomic write of ``time.time()``).

    Call after any successful mutation of a learned-pattern's confidence or
    archived (``expired_at``) state. Fail-soft: swallows all exceptions.
    """
    try:
        path = _epoch_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replace so a concurrent reader never sees a half-written value.
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix="epoch-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(repr(time.time()))
            os.replace(tmp, str(path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        pass


def read() -> float:
    """Return the last-bump timestamp, or ``0.0`` if absent / unreadable.

    Cheap local read — never touches Qdrant. Fail-soft.
    """
    try:
        path = _epoch_file()
        if not path.exists():
            return 0.0
        return float(path.read_text(encoding="utf-8").strip() or 0.0)
    except Exception:
        return 0.0
