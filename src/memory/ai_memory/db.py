"""Shared SQLite access for the episodic store (``data/memory_ai.db``).

Single source of truth for (roadmap 260612 P0.3/P0.4):

- **path resolution** — ``MEMORY_AI_DB_PATH`` env override, the same variable the
  MCP server and the orchestrator's propagation handler already honored; every
  reader/writer must resolve through here so unit chains never touch the
  production DB;
- **connection setup** — WAL journal + busy_timeout so concurrent writers
  (W1 ``save_important_message`` / W2 Stop-hook / W4 propagation) neither lose
  rows nor leak ``database is locked`` to callers (chain A8).

Deliberately stdlib-only so hooks and scripts can import it without pulling
MCP/Qdrant dependencies.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "memory_ai.db"

# SQLite waits this long for a competing writer before raising "database is
# locked". 5s comfortably covers the Stop-hook + MCP-server overlap window.
BUSY_TIMEOUT_MS = 5000


def resolve_db_path() -> Path:
    """Episodic DB path; ``MEMORY_AI_DB_PATH`` overrides (test isolation)."""
    override = os.environ.get("MEMORY_AI_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def connect(db_path: str | Path | None = None, timeout: float = 5.0) -> sqlite3.Connection:
    """``sqlite3.connect`` with WAL + busy_timeout applied.

    PRAGMA failures are swallowed: a read-only filesystem or an exotic build
    must degrade to plain rollback-journal behaviour, not break the caller.
    """
    conn = sqlite3.connect(str(db_path or resolve_db_path()), timeout=timeout)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    except sqlite3.Error:
        pass
    return conn


__all__ = ["BUSY_TIMEOUT_MS", "DEFAULT_DB_PATH", "connect", "resolve_db_path"]
