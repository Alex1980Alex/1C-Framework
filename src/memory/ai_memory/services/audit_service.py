"""
Audit Service — In-memory + JSONL audit logging for memory operations.

Simplified from unified-memory-mcp/src/services/audit.py (488 lines).
Changes:
- Removed TimescaleDB dependency — JSONL file only
- Removed external models dependency — self-contained dataclasses
- SQLite available for structured queries (optional)

Version: 2.0 (2026-04-04) — P1 migration
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    SEARCH = "search"
    LINK = "link"
    PROPAGATE = "propagate"
    MERGE = "merge"
    ROLLBACK = "rollback"
    EXPORT = "export"
    CONFIG_CHANGE = "config_change"
    HEALTH_CHECK = "health_check"


@dataclass
class AuditLogEntry:
    """Single audit log entry."""

    id: str
    timestamp: datetime
    action: AuditAction
    resource_type: str
    resource_id: str | None = None
    session_id: str | None = None
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    success: bool = True
    error_message: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "session_id": self.session_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "success": self.success,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditLogEntry":
        data = data.copy()
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if isinstance(data.get("action"), str):
            data["action"] = AuditAction(data["action"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AuditQuery:
    """Query parameters for audit log."""

    resource_type: str | None = None
    resource_id: str | None = None
    session_id: str | None = None
    action: AuditAction | None = None
    success_only: bool = False
    start_time: datetime | None = None
    end_time: datetime | None = None
    offset: int = 0
    limit: int = 50


class AuditService:
    """
    Audit logging service with JSONL persistence.

    Storage: JSONL file (append-only) + in-memory buffer.
    Immediate persist for destructive actions (DELETE, ROLLBACK, CONFIG_CHANGE).
    Periodic flush for other actions.
    """

    def __init__(
        self,
        storage_path: str | Path | None = None,
        retention_days: int = 90,
        max_buffer_size: int = 1000,
    ):
        self.storage_path = Path(storage_path or "data/audit/audit.jsonl")
        self.retention_days = retention_days
        self.max_buffer_size = max_buffer_size

        self._buffer: list[AuditLogEntry] = []
        self._lock = asyncio.Lock()
        self._stats: dict[str, int] = defaultdict(int)

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("AuditService initialized: %s", self.storage_path)

    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        session_id: str | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLogEntry:
        """Record an audit event."""
        entry = AuditLogEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            session_id=session_id,
            old_value=old_value,
            new_value=new_value,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        async with self._lock:
            self._buffer.append(entry)
            self._stats["total"] += 1
            self._stats[action.value] += 1
            if not success:
                self._stats["errors"] += 1

            # Immediate persist for destructive actions
            if action in (AuditAction.DELETE, AuditAction.ROLLBACK, AuditAction.CONFIG_CHANGE):
                await self._persist_entry(entry)

            # Auto-flush when buffer is full. We already hold self._lock here, so call
            # the lock-free variant — _flush_buffer() would re-acquire the non-reentrant
            # asyncio.Lock and deadlock at exactly max_buffer_size (§27 P0 D0.3 hardening).
            if len(self._buffer) >= self.max_buffer_size:
                self._flush_buffer_unlocked()

        return entry

    async def query(self, query: AuditQuery) -> list[AuditLogEntry]:
        """Query audit log entries with filters."""
        all_entries = await self._load_entries()
        all_entries.extend(self._buffer)

        filtered = []
        for entry in all_entries:
            if query.resource_type and entry.resource_type != query.resource_type:
                continue
            if query.resource_id and entry.resource_id != query.resource_id:
                continue
            if query.session_id and entry.session_id != query.session_id:
                continue
            if query.action and entry.action != query.action:
                continue
            if query.success_only and not entry.success:
                continue
            if query.start_time and entry.timestamp < query.start_time:
                continue
            if query.end_time and entry.timestamp > query.end_time:
                continue
            filtered.append(entry)

        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered[query.offset : query.offset + query.limit]

    async def get_recent(
        self, limit: int = 50, action: AuditAction | None = None
    ) -> list[AuditLogEntry]:
        """Get recent audit entries."""
        return await self.query(AuditQuery(action=action, limit=limit))

    async def get_by_resource(
        self, resource_type: str, resource_id: str, limit: int = 100
    ) -> list[AuditLogEntry]:
        """Get audit history for a specific resource."""
        return await self.query(
            AuditQuery(resource_type=resource_type, resource_id=resource_id, limit=limit)
        )

    async def get_errors(self, limit: int = 100) -> list[AuditLogEntry]:
        """Get failed operations."""
        all_entries = await self._load_entries()
        all_entries.extend(self._buffer)
        # Deduplicate by ID (immediate-persist entries may be in both)
        seen: set[str] = set()
        unique: list[AuditLogEntry] = []
        for e in all_entries:
            if e.id not in seen:
                seen.add(e.id)
                unique.append(e)
        errors = [e for e in unique if not e.success]
        errors.sort(key=lambda e: e.timestamp, reverse=True)
        return errors[:limit]

    async def get_stats(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> dict[str, Any]:
        """Get audit log statistics."""
        all_entries = await self._load_entries()
        all_entries.extend(self._buffer)

        if start_time:
            all_entries = [e for e in all_entries if e.timestamp >= start_time]
        if end_time:
            all_entries = [e for e in all_entries if e.timestamp <= end_time]

        by_action: dict[str, int] = defaultdict(int)
        by_resource: dict[str, int] = defaultdict(int)
        error_count = 0

        for entry in all_entries:
            by_action[entry.action.value] += 1
            by_resource[entry.resource_type] += 1
            if not entry.success:
                error_count += 1

        return {
            "total_entries": len(all_entries),
            "error_count": error_count,
            "error_rate": error_count / len(all_entries) if all_entries else 0.0,
            "by_action": dict(by_action),
            "by_resource_type": dict(by_resource),
            "buffer_size": len(self._buffer),
            "retention_days": self.retention_days,
        }

    async def cleanup(self) -> int:
        """Remove entries older than retention_days. Returns count removed."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        async with self._lock:
            before = len(self._buffer)
            self._buffer = [e for e in self._buffer if e.timestamp >= cutoff]
            buffer_removed = before - len(self._buffer)

        # Rewrite storage file
        stored = await self._load_entries()
        valid = [e for e in stored if e.timestamp >= cutoff]
        storage_removed = len(stored) - len(valid)

        if storage_removed > 0:
            try:
                with open(self.storage_path, "w", encoding="utf-8") as f:
                    for entry in valid:
                        f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            except Exception as e:
                logger.error("Failed to rewrite audit storage: %s", e)
                return buffer_removed

        total = buffer_removed + storage_removed
        if total > 0:
            logger.info("Cleaned up %d old audit entries", total)
        return total

    async def flush(self) -> int:
        """Flush buffer to disk."""
        return await self._flush_buffer()

    # ----- Private -----

    async def _persist_entry(self, entry: AuditLogEntry) -> None:
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to persist audit entry: %s", e)

    async def _flush_buffer(self) -> int:
        async with self._lock:
            return self._flush_buffer_unlocked()

    def _flush_buffer_unlocked(self) -> int:
        """Write + clear the buffer. Caller MUST already hold ``self._lock`` (or be
        single-threaded teardown). Split out so ``log()``'s auto-flush — which already
        holds the lock — does not re-acquire the non-reentrant lock (deadlock)."""
        if not self._buffer:
            return 0
        count = len(self._buffer)
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                for entry in self._buffer:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            self._buffer.clear()
        except Exception as e:
            logger.error("Failed to flush audit buffer: %s", e)
            return 0
        return count

    async def _load_entries(self) -> list[AuditLogEntry]:
        entries: list[AuditLogEntry] = []
        if not self.storage_path.exists():
            return entries
        try:
            with open(self.storage_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(AuditLogEntry.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except Exception as e:
            logger.error("Failed to load audit entries: %s", e)
        return entries


__all__ = [
    "AuditAction",
    "AuditLogEntry",
    "AuditQuery",
    "AuditService",
]
