"""Query tracker for analytics (Phase 40).

Tracks all search/agent queries with timing, strategy, quality metrics.
SQLite-backed for persistence.
"""

import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QueryRecord(BaseModel):
    """A tracked query with metadata."""

    id: int = 0
    timestamp: str = ""
    query: str = ""
    strategy: str = ""
    agent: str = ""  # rag | analytical | research | multi_agent
    results_count: int = 0
    latency_ms: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    quality_score: float = 0.0  # if graded
    user_id: str = ""


class QueryTracker:
    """Track and store query analytics."""

    def __init__(self, db_path: str | Path = "data/analytics.db"):
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                query TEXT NOT NULL,
                strategy TEXT DEFAULT '',
                agent TEXT DEFAULT '',
                results_count INTEGER DEFAULT 0,
                latency_ms REAL DEFAULT 0,
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                quality_score REAL DEFAULT 0,
                user_id TEXT DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_queries_ts ON queries(timestamp)
        """)
        self._conn.commit()
        logger.info("[ANALYTICS] Query tracker initialized: %s", self._db_path)

    def track(
        self,
        query: str,
        strategy: str = "",
        agent: str = "",
        results_count: int = 0,
        latency_ms: float = 0.0,
        tokens_input: int = 0,
        tokens_output: int = 0,
        quality_score: float = 0.0,
        user_id: str = "",
    ) -> None:
        """Record a query event."""
        if self._conn is None:
            return
        self._conn.execute(
            """
            INSERT INTO queries (timestamp, query, strategy, agent,
                results_count, latency_ms, tokens_input, tokens_output,
                quality_score, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                query,
                strategy,
                agent,
                results_count,
                latency_ms,
                tokens_input,
                tokens_output,
                quality_score,
                user_id,
            ),
        )
        self._conn.commit()

    def get_stats(self, days: int = 7) -> dict[str, Any]:
        """Get aggregated analytics for the last N days."""
        if self._conn is None:
            return {}

        cutoff = datetime.now().isoformat()[:10]  # today
        row = self._conn.execute("""
            SELECT
                COUNT(*) as total_queries,
                AVG(latency_ms) as avg_latency,
                SUM(tokens_input) as total_tokens_in,
                SUM(tokens_output) as total_tokens_out,
                AVG(quality_score) as avg_quality,
                AVG(results_count) as avg_results
            FROM queries
        """).fetchone()

        # Top strategies
        strategies = self._conn.execute("""
            SELECT strategy, COUNT(*) as cnt
            FROM queries WHERE strategy != ''
            GROUP BY strategy ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        # Top agents
        agents = self._conn.execute("""
            SELECT agent, COUNT(*) as cnt
            FROM queries WHERE agent != ''
            GROUP BY agent ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        # Popular queries (last 100)
        popular = self._conn.execute("""
            SELECT query, COUNT(*) as cnt
            FROM queries
            GROUP BY query ORDER BY cnt DESC LIMIT 20
        """).fetchall()

        return {
            "total_queries": row[0] or 0,
            "avg_latency_ms": round(row[1] or 0, 1),
            "total_tokens_input": row[2] or 0,
            "total_tokens_output": row[3] or 0,
            "avg_quality": round(row[4] or 0, 3),
            "avg_results": round(row[5] or 0, 1),
            "top_strategies": [
                {"strategy": s[0], "count": s[1]} for s in strategies
            ],
            "top_agents": [
                {"agent": a[0], "count": a[1]} for a in agents
            ],
            "popular_queries": [
                {"query": q[0], "count": q[1]} for q in popular
            ],
        }

    def get_recent(self, limit: int = 50) -> list[dict]:
        """Get recent queries."""
        if self._conn is None:
            return []
        rows = self._conn.execute(
            """
            SELECT id, timestamp, query, strategy, agent,
                   results_count, latency_ms, tokens_input, tokens_output,
                   quality_score, user_id
            FROM queries ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "query": r[2],
                "strategy": r[3],
                "agent": r[4],
                "results_count": r[5],
                "latency_ms": round(r[6], 1),
                "tokens_input": r[7],
                "tokens_output": r[8],
                "quality_score": round(r[9], 3),
                "user_id": r[10],
            }
            for r in rows
        ]
