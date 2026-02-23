"""Hook Metrics SQLite Database - Phase 5 (Streamlit Dashboard).

Ingests hook invocation JSONL logs into SQLite for real-time dashboard queries.

Usage:
    from src.pdf_framework.observability.hook_metrics_db import HookMetricsDB

    db = HookMetricsDB()
    db.ingest_from_logs()  # Load data from JSONL files

    # Query APIs
    recent = db.get_recent_invocations(limit=100)
    metrics = db.get_hook_metrics(hours=24)
    skills = db.get_skill_metrics(hours=24)

Reference: GAP_P5_HOOK_OBSERVABILITY.md Phase 5
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# --- Path resolution ---

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_FILE = DATA_DIR / "hook-metrics.db"

INVOCATIONS_LOG = DATA_DIR / "hook-invocations.jsonl"
SKILL_ROUTER_LOG = DATA_DIR / "skill-router.log"
SKILL_USAGE_LOG = DATA_DIR / "skill-usage.log"
SKILL_ACCURACY_LOG = DATA_DIR / "skill-accuracy.jsonl"

# --- Schema ---

SCHEMA = """
-- Hook invocations from hook-invocations.jsonl
CREATE TABLE IF NOT EXISTS invocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    hook TEXT NOT NULL,
    event TEXT,
    tool TEXT,
    elapsed_ms INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    session TEXT,
    error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_invocations_timestamp ON invocations(timestamp);
CREATE INDEX IF NOT EXISTS idx_invocations_hook ON invocations(hook);
CREATE INDEX IF NOT EXISTS idx_invocations_session ON invocations(session);

-- Skill recommendations from skill-router.log
CREATE TABLE IF NOT EXISTS skill_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    skills TEXT NOT NULL,
    session TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_rec_timestamp ON skill_recommendations(timestamp);

-- Skill activations from skill-usage.log
CREATE TABLE IF NOT EXISTS skill_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    skill TEXT NOT NULL,
    session TEXT,
    source TEXT DEFAULT 'post-tool-use',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_act_timestamp ON skill_activations(timestamp);
CREATE INDEX IF NOT EXISTS idx_skill_act_skill ON skill_activations(skill);

-- Skill accuracy: per-prompt recommend→activate correlation
CREATE TABLE IF NOT EXISTS skill_accuracy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    prompt_id TEXT NOT NULL,
    skills TEXT,
    skill TEXT,
    prompt TEXT,
    source TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accuracy_prompt_id ON skill_accuracy(prompt_id);
CREATE INDEX IF NOT EXISTS idx_accuracy_timestamp ON skill_accuracy(timestamp);
"""


class HookMetricsDB:
    """SQLite database for hook metrics with thread-safe operations."""

    def __init__(self, db_path: Path | None = None):
        """Initialize database connection.

        Args:
            db_path: Custom database path (default: data/hook-metrics.db)
        """
        self._db_path = db_path or DB_FILE
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema and run migrations."""
        conn = self._get_conn()
        conn.executescript(SCHEMA)
        conn.commit()
        self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Add columns missing from older schema versions."""
        migrations = [
            ("skill_activations", "source", "TEXT DEFAULT 'post-tool-use'"),
            ("skill_accuracy", "source", "TEXT"),
        ]
        for table, column, col_type in migrations:
            try:
                conn.execute(f"SELECT {column} FROM {table} LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()

    def ingest_from_logs(self) -> dict[str, int]:
        """Ingest data from all JSONL/log files.

        Returns:
            Dict with counts of ingested records per source.
        """
        try:
            return {
                "invocations": self._ingest_invocations(),
                "recommendations": self._ingest_skill_router(),
                "activations": self._ingest_skill_usage(),
                "accuracy": self._ingest_skill_accuracy(),
            }
        except Exception:
            return {
                "invocations": 0,
                "recommendations": 0,
                "activations": 0,
                "accuracy": 0,
            }

    def _ingest_invocations(self) -> int:
        """Ingest hook-invocations.jsonl into database."""
        if not INVOCATIONS_LOG.exists():
            return 0

        conn = self._get_conn()
        cursor = conn.cursor()

        # Get last timestamp to avoid re-ingesting
        last_ts = cursor.execute(
            "SELECT MAX(timestamp) FROM invocations"
        ).fetchone()[0]

        count = 0
        try:
            with open(INVOCATIONS_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        ts = entry.get("ts")

                        # Skip if already ingested
                        if last_ts and ts <= last_ts:
                            continue

                        cursor.execute(
                            """INSERT INTO invocations
                               (timestamp, hook, event, tool, elapsed_ms, outcome, session, error)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                ts,
                                entry.get("hook"),
                                entry.get("event"),
                                entry.get("tool"),
                                entry.get("elapsed_ms", 0),
                                entry.get("outcome", "allow"),
                                entry.get("session"),
                                entry.get("error"),
                            ),
                        )
                        count += 1
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            return 0

        conn.commit()
        return count

    def _ingest_skill_router(self) -> int:
        """Ingest skill-router.log (pipe-delimited)."""
        if not SKILL_ROUTER_LOG.exists():
            return 0

        conn = self._get_conn()
        cursor = conn.cursor()

        last_ts = cursor.execute(
            "SELECT MAX(timestamp) FROM skill_recommendations"
        ).fetchone()[0]

        count = 0
        try:
            with open(SKILL_ROUTER_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.split(" | ")
                        ts_str = parts[0].strip()
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").isoformat()

                        if last_ts and ts <= last_ts:
                            continue

                        skills = ""
                        session = ""
                        for part in parts[1:]:
                            if "=" in part:
                                k, v = part.split("=", 1)
                                if k.strip() == "skills":
                                    skills = v.strip()
                                elif k.strip() == "session":
                                    session = v.strip()

                        if skills:
                            cursor.execute(
                                """INSERT INTO skill_recommendations
                                   (timestamp, skills, session)
                                   VALUES (?, ?, ?)""",
                                (ts, skills, session),
                            )
                            count += 1
                    except (ValueError, IndexError):
                        continue
        except OSError:
            return 0

        conn.commit()
        return count

    def _ingest_skill_usage(self) -> int:
        """Ingest skill-usage.log (pipe-delimited)."""
        if not SKILL_USAGE_LOG.exists():
            return 0

        conn = self._get_conn()
        cursor = conn.cursor()

        last_ts = cursor.execute(
            "SELECT MAX(timestamp) FROM skill_activations"
        ).fetchone()[0]

        count = 0
        try:
            with open(SKILL_USAGE_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.split(" | ")
                        ts_str = parts[0].strip()
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").isoformat()

                        if last_ts and ts <= last_ts:
                            continue

                        skill = ""
                        session = ""
                        source = "post-tool-use"
                        for part in parts[1:]:
                            if "=" in part:
                                k, v = part.split("=", 1)
                                k = k.strip()
                                if k == "skill":
                                    skill = v.strip()
                                elif k == "session":
                                    session = v.strip()
                                elif k == "source":
                                    source = v.strip()

                        if skill:
                            cursor.execute(
                                """INSERT INTO skill_activations
                                   (timestamp, skill, session, source)
                                   VALUES (?, ?, ?, ?)""",
                                (ts, skill, session, source),
                            )
                            count += 1
                    except (ValueError, IndexError):
                        continue
        except OSError:
            return 0

        conn.commit()
        return count

    def _ingest_skill_accuracy(self) -> int:
        """Ingest skill-accuracy.jsonl (JSONL with prompt_id correlation)."""
        if not SKILL_ACCURACY_LOG.exists():
            return 0

        conn = self._get_conn()
        cursor = conn.cursor()

        last_ts = cursor.execute(
            "SELECT MAX(timestamp) FROM skill_accuracy"
        ).fetchone()[0]

        count = 0
        try:
            with open(SKILL_ACCURACY_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        ts = entry.get("ts")

                        if last_ts and ts <= last_ts:
                            continue

                        etype = entry.get("type", "")
                        prompt_id = entry.get("prompt_id", "")
                        if not prompt_id:
                            continue

                        # For recommend: skills is a list
                        skills = ",".join(entry["skills"]) if etype == "recommend" else None
                        skill = entry.get("skill") if etype == "activate" else None
                        prompt = entry.get("prompt")

                        cursor.execute(
                            """INSERT INTO skill_accuracy
                               (timestamp, type, prompt_id, skills, skill, prompt)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (ts, etype, prompt_id, skills, skill, prompt),
                        )
                        count += 1
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            return 0

        conn.commit()
        return count

    # --- Query APIs ---

    def get_recent_invocations(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent hook invocations.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of invocation dicts.
        """
        cursor = self._get_conn().cursor()
        cursor.execute(
            """SELECT * FROM invocations
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_hook_metrics(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get per-hook metrics for time period.

        Args:
            hours: Number of hours to look back.

        Returns:
            List of dicts with hook metrics.
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        cursor = self._get_conn().cursor()
        cursor.execute(
            """SELECT
                   hook,
                   COUNT(*) as count,
                   AVG(elapsed_ms) as avg_ms,
                   MAX(elapsed_ms) as max_ms,
                   SUM(CASE WHEN outcome = 'block' THEN 1 ELSE 0 END) as blocks,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as errors
               FROM invocations
               WHERE timestamp >= ?
               GROUP BY hook
               ORDER BY count DESC""",
            (cutoff,),
        )

        results = []
        for row in cursor.fetchall():
            results.append({
                "hook": row["hook"],
                "count": row["count"],
                "avg_ms": round(row["avg_ms"] or 0, 1),
                "max_ms": row["max_ms"] or 0,
                "blocks": row["blocks"],
                "errors": row["errors"],
            })

        # Compute p95 per hook
        cursor.execute(
            """SELECT hook, elapsed_ms FROM invocations
               WHERE timestamp >= ?
               ORDER BY hook, elapsed_ms""",
            (cutoff,),
        )
        per_hook_times: dict[str, list[int]] = {}
        for row in cursor.fetchall():
            per_hook_times.setdefault(row["hook"], []).append(row["elapsed_ms"])

        for result in results:
            times = per_hook_times.get(result["hook"], [])
            if times:
                idx = min(int(len(times) * 0.95), len(times) - 1)
                result["p95_ms"] = times[idx]
            else:
                result["p95_ms"] = 0

        return results

    def get_skill_metrics(self, hours: int = 24) -> dict[str, Any]:
        """Get skill activation metrics.

        Args:
            hours: Number of hours to look back.

        Returns:
            Dict with skill metrics including activation rate.
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor = self._get_conn().cursor()

        # Count recommendations
        cursor.execute(
            """SELECT skills FROM skill_recommendations
               WHERE timestamp >= ?""",
            (cutoff,),
        )
        recommended = {}
        for row in cursor.fetchall():
            for skill in row["skills"].split(","):
                skill = skill.strip()
                if skill:
                    recommended[skill] = recommended.get(skill, 0) + 1

        # Count activations
        cursor.execute(
            """SELECT skill, COUNT(*) as count FROM skill_activations
               WHERE timestamp >= ?
               GROUP BY skill""",
            (cutoff,),
        )
        activated = {row["skill"]: row["count"] for row in cursor.fetchall()}

        total_recommended = sum(recommended.values())
        total_activated = sum(activated.values())

        return {
            "total_recommended": total_recommended,
            "total_activated": total_activated,
            "activation_rate": (
                (total_activated / total_recommended * 100) if total_recommended > 0 else 0.0
            ),
            "per_skill": {
                skill: {
                    "recommended": recommended.get(skill, 0),
                    "activated": activated.get(skill, 0),
                    "rate": (
                        (activated.get(skill, 0) / recommended[skill] * 100)
                        if skill in recommended and recommended[skill] > 0
                        else 0.0
                    ),
                }
                for skill in set(list(recommended.keys()) + list(activated.keys()))
            },
        }

    def get_accuracy_metrics(self, hours: int = 24) -> dict[str, Any]:
        """Get per-prompt skill accuracy metrics.

        Groups recommend/activate events by prompt_id to compute match rate.

        Args:
            hours: Number of hours to look back.

        Returns:
            Dict with accuracy metrics: total, matched, missed, match_rate,
            per_skill_precision.
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor = self._get_conn().cursor()

        # Get all accuracy entries in time window
        cursor.execute(
            """SELECT type, prompt_id, skills, skill, prompt
               FROM skill_accuracy
               WHERE timestamp >= ?
               ORDER BY timestamp""",
            (cutoff,),
        )

        by_prompt: dict[str, dict] = {}
        for row in cursor.fetchall():
            pid = row["prompt_id"]
            if pid not in by_prompt:
                by_prompt[pid] = {"recommended": [], "activated": [], "prompt": ""}

            if row["type"] == "recommend" and row["skills"]:
                by_prompt[pid]["recommended"] = [
                    s.strip() for s in row["skills"].split(",") if s.strip()
                ]
                by_prompt[pid]["prompt"] = row["prompt"] or ""
            elif row["type"] == "activate" and row["skill"]:
                if row["skill"] not in by_prompt[pid]["activated"]:
                    by_prompt[pid]["activated"].append(row["skill"])

        if not by_prompt:
            return {
                "total_prompts": 0,
                "matched_prompts": 0,
                "missed_prompts": 0,
                "match_rate": 0.0,
                "per_skill_precision": {},
            }

        matched = 0
        missed = 0
        skill_rec: dict[str, int] = {}
        skill_act: dict[str, int] = {}

        for data in by_prompt.values():
            rec_set = set(data["recommended"])
            act_set = set(data["activated"])

            for s in rec_set:
                skill_rec[s] = skill_rec.get(s, 0) + 1
                if s in act_set:
                    skill_act[s] = skill_act.get(s, 0) + 1

            if rec_set & act_set:
                matched += 1
            else:
                missed += 1

        total = matched + missed
        return {
            "total_prompts": total,
            "matched_prompts": matched,
            "missed_prompts": missed,
            "match_rate": round(matched / total * 100, 1) if total > 0 else 0.0,
            "per_skill_precision": {
                skill: {
                    "recommended": skill_rec[skill],
                    "activated": skill_act.get(skill, 0),
                    "precision": round(
                        skill_act.get(skill, 0) / skill_rec[skill] * 100, 1
                    ),
                }
                for skill in sorted(skill_rec.keys())
            },
        }

    def get_session_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent sessions with invocation counts.

        Args:
            limit: Maximum number of sessions.

        Returns:
            List of session dicts.
        """
        cursor = self._get_conn().cursor()
        cursor.execute(
            """SELECT
                   session,
                   MIN(timestamp) as first_seen,
                   MAX(timestamp) as last_seen,
                   COUNT(*) as invocations,
                   COUNT(DISTINCT hook) as hooks
               FROM invocations
               WHERE session IS NOT NULL AND session != ''
               GROUP BY session
               ORDER BY last_seen DESC
               LIMIT ?""",
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            # Calculate duration
            try:
                first = datetime.fromisoformat(row["first_seen"])
                last = datetime.fromisoformat(row["last_seen"])
                duration_min = round((last - first).total_seconds() / 60, 1)
            except (ValueError, TypeError):
                duration_min = 0

            results.append({
                "session": row["session"][:12] + "...",
                "full_session": row["session"],
                "invocations": row["invocations"],
                "hooks": row["hooks"],
                "duration_min": duration_min,
            })
        return results

    def get_error_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent error entries.

        Args:
            limit: Maximum number of errors.

        Returns:
            List of error dicts.
        """
        cursor = self._get_conn().cursor()
        cursor.execute(
            """SELECT * FROM invocations
               WHERE error IS NOT NULL
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_enforcement_metrics(self, hours: int = 24) -> dict[str, Any]:
        """Get enforcement breakdown by outcome per hook.

        Args:
            hours: Number of hours to look back.

        Returns:
            Dict with total blocks/allows, block rate, and per-hook breakdown.
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor = self._get_conn().cursor()

        cursor.execute(
            """SELECT hook, outcome, COUNT(*) as count
               FROM invocations
               WHERE timestamp >= ?
               GROUP BY hook, outcome
               ORDER BY hook, outcome""",
            (cutoff,),
        )

        per_hook: dict[str, dict[str, int]] = {}
        for row in cursor.fetchall():
            per_hook.setdefault(row["hook"], {})[row["outcome"]] = row["count"]

        total_blocks = sum(c.get("block", 0) for c in per_hook.values())
        total_allows = sum(c.get("allow", 0) for c in per_hook.values())
        total = total_blocks + total_allows

        return {
            "total_blocks": total_blocks,
            "total_allows": total_allows,
            "block_rate": round(total_blocks / total * 100, 1) if total > 0 else 0.0,
            "per_hook": per_hook,
        }

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            delattr(self._local, "conn")
