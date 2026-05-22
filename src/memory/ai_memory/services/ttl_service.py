"""TTL (Time-To-Live) management service for memory subsystem.

Tracks TTL for memory entries with automatic cleanup.
JSONL persistence with in-memory cache.

Migrated from: unified-memory-mcp/src/services/ttl.py (435 lines)
Simplified: replaced aiofiles with sync open, inlined models.

Version: 1.0 (2026-04-04) -- P2 migration
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TTLPolicy(str, Enum):
    """TTL policy presets."""

    NEVER = "never"
    SHORT = "short"  # 1 hour
    MEDIUM = "medium"  # 24 hours
    LONG = "long"  # 7 days
    EXTENDED = "extended"  # 30 days
    CUSTOM = "custom"


# Policy -> duration mapping
_POLICY_DURATIONS: dict[TTLPolicy, int | None] = {
    TTLPolicy.NEVER: None,
    TTLPolicy.SHORT: 3600,
    TTLPolicy.MEDIUM: 86400,
    TTLPolicy.LONG: 604800,
    TTLPolicy.EXTENDED: 2592000,
    TTLPolicy.CUSTOM: None,  # must provide ttl_seconds
}


def _policy_seconds(policy: TTLPolicy, ttl_seconds: int | None = None) -> int | None:
    """Get seconds for a policy. Returns None for NEVER."""
    if policy == TTLPolicy.NEVER:
        return None
    if policy == TTLPolicy.CUSTOM:
        return ttl_seconds or 604800  # default 7 days
    return _POLICY_DURATIONS.get(policy)


@dataclass
class TTLEntry:
    """A TTL tracking entry."""

    id: str
    entity_id: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    ttl_policy: TTLPolicy = TTLPolicy.LONG
    access_count: int = 0
    last_accessed_at: datetime | None = None
    extended_count: int = 0

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def record_access(self) -> None:
        self.access_count += 1
        self.last_accessed_at = datetime.now()

    def extend_ttl(self, seconds: int) -> None:
        base = self.expires_at or datetime.now()
        self.expires_at = base + timedelta(seconds=seconds)
        self.extended_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "ttl_policy": self.ttl_policy.value,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at.isoformat()
            if self.last_accessed_at
            else None,
            "extended_count": self.extended_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TTLEntry":
        data = dict(data)
        if isinstance(data.get("ttl_policy"), str):
            data["ttl_policy"] = TTLPolicy(data["ttl_policy"])
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("expires_at") and isinstance(data["expires_at"], str):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        if data.get("last_accessed_at") and isinstance(data["last_accessed_at"], str):
            data["last_accessed_at"] = datetime.fromisoformat(data["last_accessed_at"])
        if data.get("expires_at") is None:
            data["expires_at"] = None
        if data.get("last_accessed_at") is None:
            data["last_accessed_at"] = None
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CleanupResult:
    """Result of a TTL cleanup operation."""

    success: bool = True
    removed_count: int = 0
    expired_count: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


class TTLService:
    """
    TTL management service with JSONL persistence.

    Usage:
        svc = TTLService(storage_path=Path("data/ttl.jsonl"))
        entry = await svc.register("entity-1", TTLPolicy.LONG)
        assert not await svc.is_expired("entity-1")
        expired_ids = await svc.cleanup_expired()
    """

    def __init__(
        self,
        storage_path: Path,
        auto_cleanup_interval_seconds: int = 3600,
        enable_auto_cleanup: bool = True,
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self.auto_cleanup_interval = auto_cleanup_interval_seconds
        self.enable_auto_cleanup = enable_auto_cleanup
        self._cleanup_task: asyncio.Task | None = None

        self._entries: dict[str, TTLEntry] = {}  # id -> entry
        self._entity_index: dict[str, str] = {}  # entity_id -> entry id
        self._loaded = False

        logger.info("TTLService initialized: %s", self.storage_path)

    async def _ensure_loaded(self) -> None:
        """Load data from storage on first access."""
        if self._loaded:
            return

        if self.storage_path.exists():
            try:
                with open(self.storage_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            entry = TTLEntry.from_dict(data)
                            self._entries[entry.id] = entry
                            self._entity_index[entry.entity_id] = entry.id
                        except (json.JSONDecodeError, KeyError):
                            continue
                logger.info("Loaded %d TTL entries", len(self._entries))
            except Exception as e:
                logger.error("Failed to load TTL entries: %s", e)

        self._loaded = True

    def _save_entry(self, entry: TTLEntry) -> None:
        """Append entry to JSONL file."""
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to save TTL entry: %s", e)

    def _rewrite_storage(self) -> None:
        """Rewrite entire JSONL file (after cleanup)."""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                for entry in self._entries.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to rewrite TTL storage: %s", e)

    async def register(
        self,
        entity_id: str,
        policy: TTLPolicy = TTLPolicy.LONG,
        ttl_seconds: int | None = None,
    ) -> TTLEntry:
        """Register a TTL entry for an entity."""
        await self._ensure_loaded()

        seconds = _policy_seconds(policy, ttl_seconds)
        expires_at = datetime.now() + timedelta(seconds=seconds) if seconds is not None else None

        entry = TTLEntry(
            id=str(uuid.uuid4()),
            entity_id=entity_id,
            expires_at=expires_at,
            ttl_policy=policy,
        )

        self._entries[entry.id] = entry
        self._entity_index[entity_id] = entry.id
        self._save_entry(entry)

        logger.debug(
            "Registered TTL for %s: policy=%s, expires=%s", entity_id, policy.value, expires_at
        )
        return entry

    async def get_entry(self, entity_id: str) -> TTLEntry | None:
        """Get TTL entry by entity_id."""
        await self._ensure_loaded()
        entry_id = self._entity_index.get(entity_id)
        if entry_id:
            return self._entries.get(entry_id)
        return None

    async def is_expired(self, entity_id: str) -> bool:
        """Check if an entity has expired."""
        entry = await self.get_entry(entity_id)
        if entry is None:
            return True  # unknown = expired
        return entry.is_expired()

    async def record_access(self, entity_id: str) -> TTLEntry | None:
        """Record access to an entity. Updates access count."""
        await self._ensure_loaded()
        entry = await self.get_entry(entity_id)
        if entry:
            entry.record_access()
            self._rewrite_storage()
            return entry
        return None

    async def extend_ttl(self, entity_id: str, seconds: int) -> TTLEntry | None:
        """Extend TTL for an entity."""
        await self._ensure_loaded()
        entry = await self.get_entry(entity_id)
        if entry:
            entry.extend_ttl(seconds)
            self._rewrite_storage()
            logger.info("Extended TTL for %s by %ds", entity_id, seconds)
            return entry
        return None

    async def set_policy(
        self, entity_id: str, policy: TTLPolicy, ttl_seconds: int | None = None
    ) -> TTLEntry | None:
        """Change TTL policy for an entity."""
        await self._ensure_loaded()
        entry = await self.get_entry(entity_id)
        if entry is None:
            return None

        entry.ttl_policy = policy
        seconds = _policy_seconds(policy, ttl_seconds)
        entry.expires_at = (
            datetime.now() + timedelta(seconds=seconds) if seconds is not None else None
        )
        self._rewrite_storage()
        return entry

    async def get_expired(self) -> list[TTLEntry]:
        """Get all expired entries."""
        await self._ensure_loaded()
        return [e for e in self._entries.values() if e.is_expired()]

    async def cleanup_expired(self) -> list[str]:
        """Remove all expired entries. Returns list of removed entity_ids."""
        await self._ensure_loaded()

        expired = await self.get_expired()
        removed = []

        for entry in expired:
            entity_id = entry.entity_id
            if entry.id in self._entries:
                del self._entries[entry.id]
            if self._entity_index.get(entity_id) == entry.id:
                del self._entity_index[entity_id]
            removed.append(entity_id)

        if removed:
            self._rewrite_storage()

        logger.info("Cleanup: removed %d/%d expired entries", len(removed), len(expired))
        return removed

    async def get_stats(self) -> dict[str, Any]:
        """Return TTL statistics."""
        await self._ensure_loaded()

        total = len(self._entries)
        expired = len(await self.get_expired())
        never_expire = sum(1 for e in self._entries.values() if e.expires_at is None)

        by_policy: dict[str, int] = {}
        for entry in self._entries.values():
            p = entry.ttl_policy.value
            by_policy[p] = by_policy.get(p, 0) + 1

        return {
            "total_entries": total,
            "expired": expired,
            "never_expire": never_expire,
            "by_policy": by_policy,
            "auto_cleanup_enabled": self.enable_auto_cleanup,
        }

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if not self.enable_auto_cleanup:
            return
        if self._cleanup_task and not self._cleanup_task.done():
            return

        async def cleanup_loop():
            while True:
                await asyncio.sleep(self.auto_cleanup_interval)
                try:
                    removed = await self.cleanup_expired()
                    if removed:
                        logger.info("Auto-cleanup: removed %d entries", len(removed))
                except Exception as e:
                    logger.error("Auto-cleanup failed: %s", e)

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Auto-cleanup task started (interval=%ds)", self.auto_cleanup_interval)

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("Auto-cleanup task stopped")


__all__ = ["CleanupResult", "TTLEntry", "TTLPolicy", "TTLService"]
