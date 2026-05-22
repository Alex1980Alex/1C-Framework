"""Entity versioning service for memory subsystem.

JSONL-based version storage with in-memory cache.
Supports create, history, rollback, and diff operations.

Migrated from: unified-memory-mcp/src/services/versioning.py (431 lines)
Simplified: removed TimescaleDB, inlined models, no external deps.

Version: 1.0 (2026-04-04) -- P2 migration
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Type of change that created a version."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ROLLBACK = "rollback"


@dataclass
class EntityVersion:
    """A single version of an entity."""

    id: str
    entity_id: str
    version: int
    content: dict[str, Any]
    change_type: ChangeType
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    change_summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "version": self.version,
            "content": self.content,
            "change_type": self.change_type.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "change_summary": self.change_summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityVersion":
        data = dict(data)
        if isinstance(data.get("change_type"), str):
            data["change_type"] = ChangeType(data["change_type"])
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class VersioningService:
    """
    JSONL-based entity versioning with rollback and diff.

    Thread-safe via asyncio.Lock. Immediate JSONL persist on destructive ops.

    Usage:
        svc = VersioningService(storage_path=Path("data/versions.jsonl"))
        v1 = await svc.create_version("entity-1", {"key": "val"}, ChangeType.CREATE)
        v2 = await svc.create_version("entity-1", {"key": "val2"}, ChangeType.UPDATE)
        history = await svc.get_version_history("entity-1")
        await svc.rollback_to_version("entity-1", 1)
    """

    def __init__(
        self,
        storage_path: Path,
        max_versions_per_entity: int = 100,
        auto_cleanup: bool = True,
    ):
        self.storage_path = Path(storage_path)
        self.max_versions = max_versions_per_entity
        self.auto_cleanup = auto_cleanup

        self._cache: dict[str, list[EntityVersion]] = {}
        self._lock = asyncio.Lock()

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("VersioningService initialized: %s", self.storage_path)

    async def create_version(
        self,
        entity_id: str,
        content: dict[str, Any],
        change_type: ChangeType | str,
        created_by: str = "",
        change_summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EntityVersion:
        """Create a new version of an entity."""
        if isinstance(change_type, str):
            change_type = ChangeType(change_type)
        async with self._lock:
            existing = self._cache.get(entity_id, [])
            version_number = len(existing) + 1

            version = EntityVersion(
                id=str(uuid.uuid4()),
                entity_id=entity_id,
                version=version_number,
                content=content,
                change_type=change_type,
                created_by=created_by,
                change_summary=change_summary,
                metadata=metadata or {},
            )

            if entity_id not in self._cache:
                self._cache[entity_id] = []
            self._cache[entity_id].append(version)

            await self._persist_version(version)

            if self.auto_cleanup and len(self._cache[entity_id]) > self.max_versions:
                await self._cleanup_old_versions(entity_id)

            logger.debug(
                "Created version %d for entity %s: %s",
                version_number,
                entity_id,
                change_type.value,
            )
            return version

    async def get_version_history(
        self,
        entity_id: str,
        limit: int = 50,
        change_types: list[ChangeType] | None = None,
        include_content: bool = True,
    ) -> list[EntityVersion]:
        """Get version history for an entity (newest first)."""
        versions = await self._get_versions(entity_id)

        if change_types:
            versions = [v for v in versions if v.change_type in change_types]

        versions = sorted(versions, key=lambda v: v.version, reverse=True)
        versions = versions[:limit]

        if not include_content:
            versions = [
                EntityVersion(
                    id=v.id,
                    entity_id=v.entity_id,
                    version=v.version,
                    content={},
                    change_type=v.change_type,
                    created_at=v.created_at,
                    created_by=v.created_by,
                    change_summary=v.change_summary,
                    metadata=v.metadata,
                )
                for v in versions
            ]

        return versions

    async def get_version(self, entity_id: str, version_number: int) -> EntityVersion | None:
        """Get a specific version of an entity."""
        versions = await self._get_versions(entity_id)
        for v in versions:
            if v.version == version_number:
                return v
        return None

    async def get_latest_version(self, entity_id: str) -> EntityVersion | None:
        """Get the latest version of an entity."""
        versions = await self._get_versions(entity_id)
        if not versions:
            return None
        return max(versions, key=lambda v: v.version)

    async def rollback_to_version(
        self,
        entity_id: str,
        target_version: int,
        rollback_by: str = "",
    ) -> EntityVersion | None:
        """Rollback entity to a specific version. Creates a new version with the target's content."""
        target = await self.get_version(entity_id, target_version)
        if target is None:
            logger.warning(
                "Cannot rollback: version %d not found for entity %s",
                target_version,
                entity_id,
            )
            return None

        latest = await self.get_latest_version(entity_id)
        from_version = latest.version if latest else 0

        return await self.create_version(
            entity_id=entity_id,
            content=target.content,
            change_type=ChangeType.ROLLBACK,
            created_by=rollback_by,
            change_summary=f"Rollback to version {target_version}",
            metadata={"rollback_from": from_version, "rollback_to": target_version},
        )

    async def compare_versions(
        self,
        entity_id: str,
        version_a: int,
        version_b: int,
    ) -> dict[str, Any]:
        """Compare two versions and return a diff."""
        v_a = await self.get_version(entity_id, version_a)
        v_b = await self.get_version(entity_id, version_b)

        if v_a is None or v_b is None:
            return {"error": "One or both versions not found"}

        diff: dict[str, Any] = {
            "version_a": version_a,
            "version_b": version_b,
            "entity_id": entity_id,
            "changes": [],
        }

        all_keys = set(v_a.content.keys()) | set(v_b.content.keys())
        for key in all_keys:
            val_a = v_a.content.get(key)
            val_b = v_b.content.get(key)
            if val_a != val_b:
                diff["changes"].append(
                    {
                        "key": key,
                        "old": val_a,
                        "new": val_b,
                        "type": (
                            "added" if val_a is None else "removed" if val_b is None else "modified"
                        ),
                    }
                )

        return diff

    async def get_stats(self) -> dict[str, Any]:
        """Return versioning statistics."""
        total_entities = len(self._cache)
        total_versions = sum(len(v) for v in self._cache.values())

        by_type: dict[str, int] = {ct.value: 0 for ct in ChangeType}
        for versions in self._cache.values():
            for v in versions:
                by_type[v.change_type.value] += 1

        return {
            "total_entities": total_entities,
            "total_versions": total_versions,
            "avg_versions_per_entity": round(total_versions / total_entities, 2)
            if total_entities > 0
            else 0,
            "max_versions_setting": self.max_versions,
            "by_change_type": by_type,
        }

    # --- Private methods ---

    async def _get_versions(self, entity_id: str) -> list[EntityVersion]:
        """Get versions for an entity, loading from storage if needed."""
        versions = self._cache.get(entity_id)
        if versions is None:
            versions = await self._load_versions(entity_id)
            self._cache[entity_id] = versions
        return versions

    async def _persist_version(self, version: EntityVersion) -> None:
        """Append version to JSONL file."""
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(version.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to persist version: %s", e)

    async def _load_versions(self, entity_id: str) -> list[EntityVersion]:
        """Load versions for an entity from JSONL storage."""
        versions = []
        if not self.storage_path.exists():
            return versions

        try:
            with open(self.storage_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("entity_id") == entity_id:
                            versions.append(EntityVersion.from_dict(data))
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            logger.error("Failed to load versions: %s", e)

        return versions

    async def _cleanup_old_versions(self, entity_id: str) -> int:
        """Remove old versions, keeping only the newest max_versions."""
        versions = self._cache.get(entity_id, [])
        if len(versions) <= self.max_versions:
            return 0

        versions = sorted(versions, key=lambda v: v.version, reverse=True)
        to_keep = versions[: self.max_versions]
        removed = len(versions) - len(to_keep)
        self._cache[entity_id] = to_keep
        logger.debug("Cleaned up %d old versions for entity %s", removed, entity_id)
        return removed

    async def load_all_from_storage(self) -> int:
        """Load all versions from storage into cache."""
        if not self.storage_path.exists():
            return 0

        count = 0
        try:
            with open(self.storage_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        version = EntityVersion.from_dict(data)
                        if version.entity_id not in self._cache:
                            self._cache[version.entity_id] = []
                        self._cache[version.entity_id].append(version)
                        count += 1
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            logger.error("Failed to load versions: %s", e)

        logger.info("Loaded %d versions for %d entities", count, len(self._cache))
        return count


__all__ = ["ChangeType", "EntityVersion", "VersioningService"]
