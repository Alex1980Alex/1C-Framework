"""
Thread-safe SQLite writer for hook metrics.

Uses WAL mode for concurrent read/write.
Auto-creates tables on first write.
Fallback: if SQLite write fails, falls back to JSONL append.

DB path: data/hooks.db
"""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = _PROJECT_DIR / "data" / "hooks.db"
_FALLBACK_DIR = _PROJECT_DIR / "data"

_TABLES_CREATED = False


@contextmanager
def get_connection():
    """Get a WAL-mode SQLite connection with busy timeout."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    global _TABLES_CREATED
    if _TABLES_CREATED:
        return

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS hook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            hook TEXT NOT NULL,
            tool TEXT,
            latency_ms REAL,
            status TEXT DEFAULT 'ok',
            metadata TEXT
        );

        CREATE TABLE IF NOT EXISTS skill_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            skill TEXT NOT NULL,
            session_id TEXT,
            loaded INTEGER DEFAULT 1,
            prompt_id TEXT
        );

        CREATE TABLE IF NOT EXISTS delegation_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            content_type TEXT,
            response_time REAL,
            text_length INTEGER,
            quality_score REAL,
            attempt INTEGER DEFAULT 1,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            session_id TEXT,
            quality_details TEXT
        );

        CREATE TABLE IF NOT EXISTS quality_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            file_path TEXT NOT NULL,
            tool TEXT,
            issue_count INTEGER,
            issues TEXT
        );

        CREATE TABLE IF NOT EXISTS latency (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            hook TEXT NOT NULL,
            tool TEXT,
            latency_ms REAL NOT NULL,
            over_budget INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_hook_events_ts ON hook_events(ts);
        CREATE INDEX IF NOT EXISTS idx_delegation_ts ON delegation_outcomes(ts);
        CREATE INDEX IF NOT EXISTS idx_latency_hook ON latency(hook);
    """)
    _TABLES_CREATED = True


def _fallback_jsonl(filename: str, entry: dict) -> None:
    """Fallback: append to JSONL if SQLite fails."""
    try:
        path = _FALLBACK_DIR / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def log_hook_event(
    hook_name: str,
    tool_name: str = "",
    latency_ms: float = 0,
    status: str = "ok",
    metadata: dict | None = None,
) -> None:
    """Log a generic hook execution event."""
    ts = datetime.now().isoformat()
    entry = {
        "ts": ts, "hook": hook_name, "tool": tool_name,
        "latency_ms": round(latency_ms, 1), "status": status,
        "metadata": metadata,
    }
    try:
        with get_connection() as conn:
            _ensure_tables(conn)
            conn.execute(
                "INSERT INTO hook_events (ts, hook, tool, latency_ms, status, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, hook_name, tool_name, round(latency_ms, 1), status,
                 json.dumps(metadata) if metadata else None),
            )
    except Exception:
        _fallback_jsonl("hook-events-fallback.jsonl", entry)


def log_skill_usage(
    skill_name: str,
    session_id: str = "",
    loaded: bool = True,
    prompt_id: str = "",
) -> None:
    """Log a skill activation event."""
    ts = datetime.now().isoformat()
    entry = {
        "ts": ts, "skill": skill_name, "session_id": session_id,
        "loaded": loaded, "prompt_id": prompt_id,
    }
    try:
        with get_connection() as conn:
            _ensure_tables(conn)
            conn.execute(
                "INSERT INTO skill_usage (ts, skill, session_id, loaded, prompt_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, skill_name, session_id[:16] if session_id else "",
                 1 if loaded else 0, prompt_id),
            )
    except Exception:
        _fallback_jsonl("skill-usage-fallback.jsonl", entry)


def log_delegation(
    provider: str = "unknown",
    model: str = "unknown",
    content_type: str = "",
    response_time: float = 0,
    text_length: int = 0,
    quality_score: float = 0,
    attempt: int = 1,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    session_id: str = "",
    quality_details: dict | None = None,
) -> None:
    """Log a Z.AI delegation outcome."""
    ts = datetime.now().isoformat()
    entry = {
        "ts": ts, "provider": provider, "model": model,
        "content_type": content_type, "response_time": response_time,
        "text_length": text_length, "quality_score": quality_score,
        "attempt": attempt, "session_id": session_id,
    }
    try:
        with get_connection() as conn:
            _ensure_tables(conn)
            conn.execute(
                "INSERT INTO delegation_outcomes "
                "(ts, provider, model, content_type, response_time, text_length, "
                "quality_score, attempt, prompt_tokens, completion_tokens, "
                "session_id, quality_details) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, provider, model, content_type, round(response_time, 2),
                 text_length, round(quality_score, 2), attempt,
                 prompt_tokens, completion_tokens,
                 session_id[:16] if session_id else "",
                 json.dumps(quality_details) if quality_details else None),
            )
    except Exception:
        _fallback_jsonl("delegation-outcomes-fallback.jsonl", entry)


def log_quality_issue(
    file_path: str,
    tool: str = "",
    issue_count: int = 0,
    issues: list | None = None,
) -> None:
    """Log quality check results (ruff issues)."""
    ts = datetime.now().isoformat()
    entry = {
        "ts": ts, "file_path": file_path, "tool": tool,
        "issue_count": issue_count, "issues": issues,
    }
    try:
        with get_connection() as conn:
            _ensure_tables(conn)
            conn.execute(
                "INSERT INTO quality_issues (ts, file_path, tool, issue_count, issues) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, file_path, tool, issue_count,
                 json.dumps(issues) if issues else None),
            )
    except Exception:
        _fallback_jsonl("quality-issues-fallback.jsonl", entry)


def log_latency(
    hook_name: str,
    tool_name: str = "",
    latency_ms: float = 0,
    over_budget: bool = False,
) -> None:
    """Log hook latency measurement."""
    ts = datetime.now().isoformat()
    entry = {
        "ts": ts, "hook": hook_name, "tool": tool_name,
        "latency_ms": round(latency_ms, 1), "over_budget": over_budget,
    }
    try:
        with get_connection() as conn:
            _ensure_tables(conn)
            conn.execute(
                "INSERT INTO latency (ts, hook, tool, latency_ms, over_budget) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, hook_name, tool_name, round(latency_ms, 1),
                 1 if over_budget else 0),
            )
    except Exception:
        _fallback_jsonl("hook-latency-fallback.jsonl", entry)


def get_latency_stats(last_n: int = 100) -> dict:
    """Get latency statistics from SQLite."""
    try:
        with get_connection() as conn:
            _ensure_tables(conn)
            rows = conn.execute(
                "SELECT latency_ms FROM latency ORDER BY id DESC LIMIT ?",
                (last_n,),
            ).fetchall()
            if not rows:
                return {"count": 0}
            latencies = sorted(r[0] for r in rows)
            n = len(latencies)
            return {
                "count": n,
                "p50": latencies[n // 2],
                "p95": latencies[int(n * 0.95)],
                "p99": latencies[int(n * 0.99)],
                "max": latencies[-1],
                "over_budget": sum(1 for l in latencies if l > 200),
            }
    except Exception:
        return {"count": 0}
