"""Session memory store for Research Agent v2 (Phase 36).

SQLite-backed storage for research sessions, enabling:
- Resume interrupted research
- Reuse facts from previous sessions
- Track research history
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.pdf_framework.agents.research_v2.schemas import (
    EvidenceGraph,
    ResearchPlanTree,
    ResearchReport,
    ResearchSession,
)

logger = logging.getLogger(__name__)


class ResearchSessionStore:
    """Persistent store for research sessions."""

    def __init__(self, db_path: str | Path = "data/research_sessions.db"):
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        """Create the sessions table."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS research_sessions (
                session_id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                plan_json TEXT,
                evidence_json TEXT,
                report_json TEXT
            )
        """)
        self._conn.commit()
        logger.info("[SESSION] Initialized store: %s", self._db_path)

    def save(self, session: ResearchSession) -> None:
        """Save or update a research session."""
        if self._conn is None:
            return
        self._conn.execute(
            """
            INSERT OR REPLACE INTO research_sessions
            (session_id, question, created_at, updated_at, status,
             plan_json, evidence_json, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.question,
                session.created_at,
                datetime.now().isoformat(),
                session.status,
                session.plan.model_dump_json() if session.plan else None,
                session.evidence_graph.model_dump_json(),
                session.report.model_dump_json() if session.report else None,
            ),
        )
        self._conn.commit()

    def get(self, session_id: str) -> ResearchSession | None:
        """Retrieve a research session by ID."""
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT * FROM research_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def find_by_question(self, question: str, limit: int = 5) -> list[ResearchSession]:
        """Find previous sessions with similar questions."""
        if self._conn is None:
            return []
        # Simple keyword match — for production, use embedding similarity
        keywords = question.lower().split()[:5]
        conditions = " OR ".join(["LOWER(question) LIKE ?" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]
        rows = self._conn.execute(
            f"""
            SELECT * FROM research_sessions
            WHERE {conditions}
            ORDER BY updated_at DESC LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def list_recent(self, limit: int = 20) -> list[dict]:
        """List recent sessions (summary only)."""
        if self._conn is None:
            return []
        rows = self._conn.execute(
            """
            SELECT session_id, question, status, created_at, updated_at
            FROM research_sessions
            ORDER BY updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "session_id": r[0],
                "question": r[1],
                "status": r[2],
                "created_at": r[3],
                "updated_at": r[4],
            }
            for r in rows
        ]

    def _row_to_session(self, row: tuple) -> ResearchSession:
        """Convert a DB row to a ResearchSession."""
        plan = ResearchPlanTree(**json.loads(row[5])) if row[5] else None
        evidence = (
            EvidenceGraph(**json.loads(row[6]))
            if row[6]
            else EvidenceGraph()
        )
        report = ResearchReport(**json.loads(row[7])) if row[7] else None
        return ResearchSession(
            session_id=row[0],
            question=row[1],
            created_at=row[2],
            plan=plan,
            evidence_graph=evidence,
            report=report,
            status=row[4],
        )
