"""Persistent event storage with JSONL hot buffer and SQLite cold storage.

Dual-layer architecture: recent events append to JSONL for fast writes,
periodic flush moves them to SQLite for efficient querying.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .event_bus import Event

logger = logging.getLogger(__name__)


@dataclass
class EventStoreConfig:
    """Configuration for EventStore."""

    hot_buffer_path: str = ""
    cold_db_path: str = ""
    auto_flush_threshold: int = 500
    flush_interval: float = 60.0
    max_hot_buffer_mb: float = 10.0


class EventStore:
    """Dual-layer event persistence: JSONL hot buffer + SQLite cold storage.

    Events are first appended to a JSONL file (hot buffer) for fast writes.
    A background task periodically flushes the hot buffer into SQLite for
    efficient querying and long-term storage.

    Usage::

        store = EventStore(EventStoreConfig(
            hot_buffer_path="data/events.jsonl",
            cold_db_path="data/events.db",
        ))
        await store.start()
        await store.append(event)
        results = await store.query(event_type="memory.save")
        await store.stop()
    """

    def __init__(self, config: EventStoreConfig) -> None:
        self._config = config
        self._hot_buffer_lock = asyncio.Lock()
        self._hot_count: int = 0
        self._flush_task: asyncio.Task[None] | None = None
        self._running: bool = False
        self._db: sqlite3.Connection | None = None

    # -- Lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Initialize storage and start periodic flush."""
        Path(self._config.hot_buffer_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self._config.cold_db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await asyncio.to_thread(self._open_db)
        self._hot_count = await asyncio.to_thread(self._count_hot_buffer)
        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        cold_count = await asyncio.to_thread(self._count_cold)
        logger.info("EventStore started — hot:%d cold:%d", self._hot_count, cold_count)

    async def stop(self) -> None:
        """Flush remaining events and shut down."""
        self._running = False
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        await self.flush()
        if self._db is not None:
            await asyncio.to_thread(self._db.close)
            self._db = None
        logger.info("EventStore stopped")

    # -- Public API ----------------------------------------------------------

    async def append(self, event: Event) -> None:
        """Append an event to the hot buffer."""
        async with self._hot_buffer_lock:
            await asyncio.to_thread(self._append_to_jsonl, event)
            self._hot_count += 1
        if self._hot_count >= self._config.auto_flush_threshold:
            logger.info("Auto-flush triggered at %d events", self._hot_count)
            await self.flush()

    async def flush(self) -> None:
        """Move hot buffer contents to SQLite cold storage."""
        async with self._hot_buffer_lock:
            if self._hot_count == 0:
                return
            events = await asyncio.to_thread(self._read_jsonl)
            if events:
                await asyncio.to_thread(self._insert_batch, events)
                await asyncio.to_thread(self._clear_jsonl)
                flushed = len(events)
                self._hot_count = 0
                logger.info("Flushed %d events to cold storage", flushed)

    async def query(
        self,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Query events from both hot and cold layers."""
        cold = await asyncio.to_thread(self._query_cold, event_type, start, end, limit)
        remaining = limit - len(cold)
        hot = await asyncio.to_thread(self._query_hot, event_type, start, end, remaining)
        combined = cold + hot
        combined.sort(key=lambda e: e.timestamp)
        return combined[:limit]

    async def replay(
        self,
        event_type: str | None = None,
        start: datetime | None = None,
        callback: Callable[[Event], Any] | None = None,
    ) -> int:
        """Replay stored events through a callback. Returns count replayed."""
        if callback is None:
            return 0
        events = await self.query(event_type=event_type, start=start, limit=100_000)
        count = 0
        for event in events:
            result = callback(event)
            if asyncio.iscoroutine(result):
                await result
            count += 1
        logger.info("Replayed %d events (type=%s)", count, event_type)
        return count

    async def get_stats(self) -> dict[str, Any]:
        """Return storage statistics."""
        cold_count = await asyncio.to_thread(self._count_cold)
        return {
            "total_events": self._hot_count + cold_count,
            "hot_buffer_size": self._hot_count,
            "cold_storage_size": cold_count,
        }

    # -- Background flush ----------------------------------------------------

    async def _periodic_flush(self) -> None:
        """Periodically flush hot buffer to cold storage."""
        try:
            while self._running:
                await asyncio.sleep(self._config.flush_interval)
                if self._running:
                    await self.flush()
        except asyncio.CancelledError:
            return

    # -- SQLite helpers (run in thread) --------------------------------------

    def _open_db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._config.cold_db_path, check_same_thread=False)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id   TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                data       TEXT NOT NULL DEFAULT '{}',
                timestamp  TEXT NOT NULL,
                source     TEXT
            )
            """
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events (timestamp)")
        db.commit()
        return db

    def _insert_batch(self, events: list[dict[str, Any]]) -> None:
        assert self._db is not None
        rows = [
            (
                e["event_id"],
                e["event_type"],
                json.dumps(e.get("data", {}), default=str),
                e["timestamp"],
                e.get("source"),
            )
            for e in events
        ]
        self._db.executemany(
            "INSERT OR IGNORE INTO events (event_id, event_type, data, timestamp, source) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        self._db.commit()

    def _query_cold(
        self,
        event_type: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[Event]:
        if self._db is None:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if start is not None:
            clauses.append("timestamp >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append("timestamp <= ?")
            params.append(end.isoformat())
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT event_id, event_type, data, timestamp, source FROM events{where} ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        cursor = self._db.execute(sql, params)
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def _count_cold(self) -> int:
        if self._db is None:
            return 0
        (n,) = self._db.execute("SELECT COUNT(*) FROM events").fetchone()
        return n

    # -- JSONL helpers (run in thread) ---------------------------------------

    def _append_to_jsonl(self, event: Event) -> None:
        with open(self._config.hot_buffer_path, "a", encoding="utf-8") as fh:
            fh.write(self._serialize_event(event) + "\n")

    def _read_jsonl(self) -> list[dict[str, Any]]:
        path = Path(self._config.hot_buffer_path)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    def _clear_jsonl(self) -> None:
        path = Path(self._config.hot_buffer_path)
        if path.exists():
            path.write_text("", encoding="utf-8")

    def _query_hot(
        self,
        event_type: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[Event]:
        if limit <= 0:
            return []
        path = Path(self._config.hot_buffer_path)
        if not path.exists():
            return []
        results: list[Event] = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if event_type is not None and obj.get("event_type") != event_type:
                    continue
                ts = datetime.fromisoformat(obj.get("timestamp", ""))
                if start is not None and ts < start:
                    continue
                if end is not None and ts > end:
                    continue
                results.append(self._row_to_event_from_dict(obj, ts))
                if len(results) >= limit:
                    break
        return results

    def _count_hot_buffer(self) -> int:
        path = Path(self._config.hot_buffer_path)
        if not path.exists():
            return 0
        count = 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    count += 1
        return count

    # -- Serialization -------------------------------------------------------

    @staticmethod
    def _serialize_event(event: Event) -> str:
        ts_str = (
            event.timestamp.isoformat()
            if isinstance(event.timestamp, datetime)
            else str(event.timestamp)
        )
        return json.dumps(
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "data": event.data,
                "timestamp": ts_str,
                "source": event.source,
            },
            default=str,
        )

    @staticmethod
    def _row_to_event(row: tuple[Any, ...]) -> Event:
        return Event(
            event_id=row[0],
            event_type=row[1],
            data=json.loads(row[2]),
            timestamp=datetime.fromisoformat(row[3]),
            source=row[4],
        )

    @staticmethod
    def _row_to_event_from_dict(obj: dict[str, Any], ts: datetime) -> Event:
        return Event(
            event_id=obj["event_id"],
            event_type=obj["event_type"],
            data=obj.get("data", {}),
            timestamp=ts,
            source=obj.get("source"),
        )


__all__ = ["EventStore", "EventStoreConfig"]
