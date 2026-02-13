"""Audit logging (Phase 40).

Full audit trail: who asked, what was found, what was answered.
SQLite-backed for compliance and debugging.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AuditLogger:
    """Persistent audit log for all RAG operations."""

    def __init__(self, db_path: str | Path = "data/audit.db"):
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                user_id TEXT DEFAULT '',
                query TEXT DEFAULT '',
                agent TEXT DEFAULT '',
                strategy TEXT DEFAULT '',
                results_count INTEGER DEFAULT 0,
                answer_preview TEXT DEFAULT '',
                sources TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                ip_address TEXT DEFAULT '',
                session_id TEXT DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)
        """)
        self._conn.commit()
        logger.info("[AUDIT] Logger initialized: %s", self._db_path)

    def log(
        self,
        event_type: str,
        query: str = "",
        agent: str = "",
        strategy: str = "",
        results_count: int = 0,
        answer_preview: str = "",
        sources: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: str = "",
        ip_address: str = "",
        session_id: str = "",
    ) -> None:
        """Record an audit event."""
        if self._conn is None:
            return
        self._conn.execute(
            """
            INSERT INTO audit_log (timestamp, event_type, user_id, query,
                agent, strategy, results_count, answer_preview, sources,
                metadata, ip_address, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                event_type,
                user_id,
                query,
                agent,
                strategy,
                results_count,
                answer_preview[:500],
                json.dumps(sources or [], ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False),
                ip_address,
                session_id,
            ),
        )
        self._conn.commit()

    def get_recent(self, limit: int = 100) -> list[dict]:
        """Get recent audit entries."""
        if self._conn is None:
            return []
        rows = self._conn.execute(
            """
            SELECT id, timestamp, event_type, user_id, query, agent,
                   strategy, results_count, answer_preview, sources,
                   metadata, ip_address, session_id
            FROM audit_log ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "event_type": r[2],
                "user_id": r[3],
                "query": r[4],
                "agent": r[5],
                "strategy": r[6],
                "results_count": r[7],
                "answer_preview": r[8],
                "sources": json.loads(r[9]) if r[9] else [],
                "metadata": json.loads(r[10]) if r[10] else {},
                "ip_address": r[11],
                "session_id": r[12],
            }
            for r in rows
        ]

    def get_by_user(self, user_id: str, limit: int = 50) -> list[dict]:
        """Get audit entries for a specific user."""
        if self._conn is None:
            return []
        rows = self._conn.execute(
            """
            SELECT id, timestamp, event_type, query, agent, strategy,
                   results_count, answer_preview
            FROM audit_log WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "event_type": r[2],
                "query": r[3],
                "agent": r[4],
                "strategy": r[5],
                "results_count": r[6],
                "answer_preview": r[7],
            }
            for r in rows
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        if self._conn is None:
            return {}

        total = self._conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

        by_event = self._conn.execute("""
            SELECT event_type, COUNT(*) FROM audit_log
            GROUP BY event_type ORDER BY COUNT(*) DESC
        """).fetchall()

        by_agent = self._conn.execute("""
            SELECT agent, COUNT(*) FROM audit_log
            WHERE agent != ''
            GROUP BY agent ORDER BY COUNT(*) DESC
        """).fetchall()

        unique_users = self._conn.execute("""
            SELECT COUNT(DISTINCT user_id) FROM audit_log WHERE user_id != ''
        """).fetchone()[0]

        return {
            "total_events": total,
            "unique_users": unique_users,
            "by_event_type": {r[0]: r[1] for r in by_event},
            "by_agent": {r[0]: r[1] for r in by_agent},
        }
