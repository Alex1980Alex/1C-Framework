"""Feedback Store — async CRUD for user feedback (Phase 22).

Author: Claude Code
Version: 1.0.0 - Phase 22: Self-Learning Feedback
"""

import logging
import time
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FeedbackEntry(BaseModel):
    """A feedback entry with numeric score (-1, 0, +1)."""

    feedback_id: str
    question: str
    answer: str
    score: int  # -1=negative, 0=neutral, 1=positive
    strategy: str = ""
    chunk_ids: list[str] = Field(default_factory=list)
    chunk_scores: list[float] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
    comment: str = ""


class FeedbackStore:
    """Async SQLite store for feedback entries."""

    def __init__(self, db_path: str | Path = "data/feedback.db"):
        self._db_path = Path(db_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Create tables."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    strategy TEXT,
                    chunk_ids TEXT,
                    chunk_scores TEXT,
                    timestamp REAL NOT NULL,
                    comment TEXT
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_fb_score
                ON feedback(score)
            """)
            await db.commit()

        self._initialized = True

    async def _ensure(self) -> None:
        if not self._initialized:
            await self.initialize()

    async def add(self, entry: FeedbackEntry) -> None:
        """Add a feedback entry."""
        await self._ensure()
        import json

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO feedback "
                "(feedback_id, question, answer, score, strategy, chunk_ids, chunk_scores, timestamp, comment) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.feedback_id,
                    entry.question,
                    entry.answer,
                    entry.score,
                    entry.strategy,
                    json.dumps(entry.chunk_ids),
                    json.dumps(entry.chunk_scores),
                    entry.timestamp,
                    entry.comment or "",
                ),
            )
            await db.commit()

    async def get_positive(self, limit: int = 50) -> list[FeedbackEntry]:
        """Get positive feedback entries (score > 0)."""
        return await self._get_by_score(1, limit)

    async def get_negative(self, limit: int = 50) -> list[FeedbackEntry]:
        """Get negative feedback entries (score < 0)."""
        return await self._get_by_score(-1, limit)

    async def _get_by_score(self, score: int, limit: int) -> list[FeedbackEntry]:
        await self._ensure()
        import json

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT feedback_id, question, answer, score, strategy, "
                "chunk_ids, chunk_scores, timestamp, comment "
                "FROM feedback WHERE score = ? ORDER BY timestamp DESC LIMIT ?",
                (score, limit),
            )
            rows = await cursor.fetchall()

        return [
            FeedbackEntry(
                feedback_id=r[0], question=r[1], answer=r[2], score=r[3],
                strategy=r[4] or "", chunk_ids=json.loads(r[5] or "[]"),
                chunk_scores=json.loads(r[6] or "[]"), timestamp=r[7],
                comment=r[8] or "",
            )
            for r in rows
        ]

    async def get_stats(self) -> dict[str, Any]:
        """Get feedback statistics."""
        await self._ensure()

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM feedback")
            total = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM feedback WHERE score > 0")
            positive = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM feedback WHERE score < 0")
            negative = (await cursor.fetchone())[0]

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "positive_rate": positive / total if total > 0 else 0.0,
        }
