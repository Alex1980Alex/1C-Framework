"""Feedback Collector for Self-Learning (Phase 22).

Collects and stores user feedback on RAG responses.
Enables continuous improvement through learning from interactions.

Based on Vanna AI's self-learning pattern.

Author: Claude Code
Version: 1.0.0 - Phase 22: Self-Learning Feedback Loop
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.pdf_framework.config import Settings, get_settings

logger = logging.getLogger(__name__)


class FeedbackEntry(BaseModel):
    """A single feedback entry."""

    query: str
    answer: str
    feedback: str  # "positive", "negative", "neutral"
    strategy: str = ""
    score: float = 0.0  # Search score
    sources: list[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
    user_comment: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackStats(BaseModel):
    """Statistics about collected feedback."""

    total_feedback: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    positive_rate: float = 0.0
    strategy_performance: dict[str, dict[str, Any]] = Field(default_factory=dict)


class FeedbackCollector:
    """Collects and stores user feedback for self-learning."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        settings: Settings | None = None,
    ):
        """Initialize the feedback collector.

        Args:
            db_path: Path to SQLite database
            settings: Application settings
        """
        self._settings = settings or get_settings()
        self._db_path = Path(db_path or self._settings.data_dir / "feedback.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize the feedback database."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    feedback TEXT NOT NULL,
                    strategy TEXT,
                    score REAL,
                    sources TEXT,
                    timestamp REAL NOT NULL,
                    user_comment TEXT,
                    metadata TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_query ON feedback(query)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_strategy ON feedback(strategy)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp)
            """)
            conn.commit()
        finally:
            conn.close()

        logger.debug(f"[FEEDBACK] Database initialized: {self._db_path}")

    def add_feedback(self, entry: FeedbackEntry) -> int:
        """Add a feedback entry to the database.

        Args:
            entry: FeedbackEntry to store

        Returns:
            ID of inserted entry
        """
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback (
                    query, answer, feedback, strategy, score, sources,
                    timestamp, user_comment, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.query,
                entry.answer,
                entry.feedback,
                entry.strategy,
                entry.score,
                json.dumps(entry.sources),
                entry.timestamp,
                entry.user_comment,
                json.dumps(entry.metadata),
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

        logger.info(f"[FEEDBACK] Added {entry.feedback} feedback")

    def get_feedback(
        self,
        limit: int = 100,
        min_score: float | None = None,
        strategy: str | None = None,
    ) -> list[FeedbackEntry]:
        """Retrieve feedback entries.

        Args:
            limit: Maximum entries to retrieve
            min_score: Minimum search score
            strategy: Filter by strategy

        Returns:
            List of FeedbackEntry objects
        """
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()

            query = "SELECT * FROM feedback WHERE 1=1"
            params = []

            if min_score is not None:
                query += " AND score >= ?"
                params.append(min_score)

            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            entries = []
            for row in rows:
                entry = FeedbackEntry(
                    query=row[1],
                    answer=row[2],
                    feedback=row[3],
                    strategy=row[4] or "",
                    score=row[5] or 0.0,
                    sources=json.loads(row[6]) if row[6] else [],
                    timestamp=row[7],
                    user_comment=row[8] or "",
                    metadata=json.loads(row[9]) if row[9] else {},
                )
                entries.append(entry)

            return entries

        finally:
            conn.close()

    def get_positive_examples(
        self,
        strategy: str | None = None,
        limit: int = 50,
    ) -> list[FeedbackEntry]:
        """Get positive feedback entries as examples.

        Args:
            strategy: Filter by strategy
            limit: Maximum entries

        Returns:
            List of positive FeedbackEntry objects
        """
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()

            query = "SELECT * FROM feedback WHERE feedback = 'positive'"
            params = []

            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)

            query += " ORDER BY score DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            entries = []
            for row in rows:
                entry = FeedbackEntry(
                    query=row[1],
                    answer=row[2],
                    feedback=row[3],
                    strategy=row[4] or "",
                    score=row[5] or 0.0,
                    sources=json.loads(row[6]) if row[6] else [],
                    timestamp=row[7],
                    user_comment=row[8] or "",
                    metadata=json.loads(row[9]) if row[9] else {},
                )
                entries.append(entry)

            return entries

        finally:
            conn.close()

    def get_stats(self) -> FeedbackStats:
        """Get feedback statistics.

        Returns:
            FeedbackStats object
        """
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()

            # Total counts
            cursor.execute("SELECT feedback, COUNT(*) FROM feedback GROUP BY feedback")
            feedback_counts = dict(cursor.fetchall())

            total = sum(feedback_counts.values())
            positive = feedback_counts.get("positive", 0)
            negative = feedback_counts.get("negative", 0)
            neutral = feedback_counts.get("neutral", 0)

            # Strategy performance
            cursor.execute("""
                SELECT strategy, feedback, COUNT(*), AVG(score)
                FROM feedback
                GROUP BY strategy, feedback
            """)
            strategy_data = cursor.fetchall()

            strategy_performance = {}
            for strategy, feedback, count, avg_score in strategy_data:
                if strategy not in strategy_performance:
                    strategy_performance[strategy] = {
                        "total": 0,
                        "positive": 0,
                        "negative": 0,
                        "avg_score": 0.0,
                    }

                strategy_performance[strategy]["total"] += count
                if feedback == "positive":
                    strategy_performance[strategy]["positive"] += count
                elif feedback == "negative":
                    strategy_performance[strategy]["negative"] += count

                strategy_performance[strategy]["avg_score"] = avg_score

            return FeedbackStats(
                total_feedback=total,
                positive_count=positive,
                negative_count=negative,
                neutral_count=neutral,
                positive_rate=positive / total if total > 0 else 0.0,
                strategy_performance=strategy_performance,
            )

        finally:
            conn.close()

    def clear_old_feedback(self, days: int = 30):
        """Remove feedback entries older than specified days.

        Args:
            days: Days threshold
        """
        cutoff_time = time.time() - (days * 86400)

        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feedback WHERE timestamp < ?", (cutoff_time,))
            deleted = cursor.rowcount
            conn.commit()

            logger.info(f"[FEEDBACK] Cleared {deleted} old entries (>{days} days)")

        finally:
            conn.close()

    def export_feedback(self, output_path: str | Path):
        """Export feedback to JSON file.

        Args:
            output_path: Path to output file
        """
        entries = self.get_feedback(limit=10000)

        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(entries),
            "entries": [e.model_dump() for e in entries],
        }

        output_path = Path(output_path)
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"[FEEDBACK] Exported {len(entries)} entries to {output_path}")

    def import_feedback(self, input_path: str | Path):
        """Import feedback from JSON file.

        Args:
            input_path: Path to input file
        """
        input_path = Path(input_path)
        data = json.loads(input_path.read_text(encoding="utf-8"))

        count = 0
        for entry_data in data.get("entries", []):
            entry = FeedbackEntry(**entry_data)
            self.add_feedback(entry)
            count += 1

        logger.info(f"[FEEDBACK] Imported {count} entries from {input_path}")


def add_feedback(
    query: str,
    answer: str,
    feedback: str,
    strategy: str = "",
    score: float = 0.0,
) -> int:
    """Convenience function to add feedback.

    Args:
        query: User query
        answer: Generated answer
        feedback: "positive", "negative", or "neutral"
        strategy: Search strategy used
        score: Search score

    Returns:
        ID of inserted entry
    """
    collector = FeedbackCollector()
    entry = FeedbackEntry(
        query=query,
        answer=answer,
        feedback=feedback,
        strategy=strategy,
        score=score,
    )
    return collector.add_feedback(entry)
