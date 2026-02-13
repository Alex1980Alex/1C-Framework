"""Eval History Store — persist metrics over time (Phase 21).

Author: Claude Code
Version: 1.0.0 - Phase 21: RAGAS Evaluation
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HistoryPoint(BaseModel):
    """A single data point in eval history."""

    run_id: str
    metric: str
    value: float
    version: str = ""
    timestamp: float = 0.0


class EvalHistoryStore:
    """Store and query evaluation metrics over time."""

    def __init__(self, db_path: str | Path = "data/eval_history.db"):
        self._db_path = Path(db_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Create tables."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS eval_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    version TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_eval_metric
                ON eval_history(metric, timestamp DESC)
            """)
            await db.commit()

        self._initialized = True

    async def store(
        self,
        report: Any = None,
        version: str = "",
        metrics: dict[str, float] | None = None,
    ) -> str:
        """Store evaluation metrics.

        Args:
            report: Evaluation report (optional)
            version: Version label
            metrics: Dict of metric_name → value

        Returns:
            run_id
        """
        if not self._initialized:
            await self.initialize()

        run_id = str(uuid.uuid4())[:8]
        ts = time.time()

        # Extract metrics from report or use provided dict
        if metrics is None:
            metrics = {}
            if report is not None:
                for attr in ["mrr", "recall", "precision", "f1", "faithfulness",
                             "context_precision", "answer_relevancy"]:
                    val = getattr(report, attr, None)
                    if val is not None:
                        metrics[attr] = float(val)

        if not metrics:
            # Store at least a placeholder
            metrics = {"stored": 1.0}

        async with aiosqlite.connect(self._db_path) as db:
            for metric, value in metrics.items():
                await db.execute(
                    "INSERT INTO eval_history (run_id, metric, value, version, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (run_id, metric, value, version, ts),
                )
            await db.commit()

        return run_id

    async def get_history(
        self, metric: str, days: int = 30,
    ) -> list[HistoryPoint]:
        """Get history for a specific metric."""
        if not self._initialized:
            await self.initialize()

        cutoff = time.time() - (days * 86400)

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT run_id, metric, value, version, timestamp "
                "FROM eval_history WHERE metric = ? AND timestamp >= ? "
                "ORDER BY timestamp DESC",
                (metric, cutoff),
            )
            rows = await cursor.fetchall()

        return [
            HistoryPoint(
                run_id=r[0], metric=r[1], value=r[2],
                version=r[3] or "", timestamp=r[4],
            )
            for r in rows
        ]
