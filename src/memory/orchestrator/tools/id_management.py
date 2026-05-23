"""ID Management Tool — UUIDv7 generation, conflict resolution, batch operations.

Wraps the unified_id module with higher-level operations for MCP tool exposure:
generating IDs with UUIDv7 timestamps, resolving ID conflicts, and batch
registration.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from ..unified_id import (
    IDRegistry,
    MemoryType,
    SourceServer,
    UnifiedID,
    get_registry,
)

logger = logging.getLogger(__name__)


def _uuid7() -> str:
    """Generate a UUIDv7 (time-ordered, random suffix).

    UUIDv7 encodes a Unix timestamp in the most-significant 48 bits,
    providing natural chronological ordering when used as a primary key.
    """
    timestamp_ms = int(time.time() * 1000)
    rand_a = uuid.uuid4().int >> 76  # 12 random bits
    rand_b = uuid.uuid4().int >> 66  # 62 random bits
    # Build UUIDv7: 48-bit timestamp | 4-bit version(7) | 12-bit rand_a | 2-bit variant | 62-bit rand_b
    uuid_int: int = (timestamp_ms & 0xFFFFFFFFFFFF) << 80
    uuid_int |= 0x7 << 76  # version 7
    uuid_int |= (rand_a & 0xFFF) << 64
    uuid_int |= 0x2 << 62  # variant 10
    uuid_int |= rand_b & 0x3FFFFFFFFFFFFFFF
    return str(uuid.UUID(int=uuid_int))


class IDManagementTool:
    """Manage unified IDs — generation, resolution, conflict handling.

    Provides MCP-friendly operations over the unified ID namespace:

    - **generate**: Create new UUIDv7-based unified IDs.
    - **resolve**: Look up original ID from unified ID (or reverse).
    - **resolve_conflict**: Handle ID collisions between subsystems.
    - **batch_register**: Register multiple IDs at once.
    - **stats**: Get ID registry statistics.

    Usage::

        tool = IDManagementTool()
        result = await tool.execute(
            operation="generate",
            source="memory-ai",
            memory_type="episodic",
        )
    """

    def __init__(self, registry: IDRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    async def execute(
        self,
        operation: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute an ID management operation.

        Args:
            operation: One of ``generate``, ``resolve``, ``reverse_lookup``,
                ``resolve_conflict``, ``batch_register``, ``stats``.
            **kwargs: Operation-specific parameters.

        Returns:
            Operation result dict.
        """
        if operation == "generate":
            return self._generate(**kwargs)
        elif operation == "resolve":
            return self._resolve(**kwargs)
        elif operation == "reverse_lookup":
            return self._reverse_lookup(**kwargs)
        elif operation == "resolve_conflict":
            return self._resolve_conflict(**kwargs)
        elif operation == "batch_register":
            return self._batch_register(**kwargs)
        elif operation == "stats":
            return self._stats()
        else:
            return {"error": f"Unknown operation: {operation}"}

    def _generate(
        self,
        source: str = "orchestrator",
        memory_type: str | None = None,
        count: int = 1,
        **_: Any,
    ) -> dict[str, Any]:
        """Generate new UUIDv7-based unified IDs."""
        src = SourceServer.from_string(source)
        mt = MemoryType.from_string(memory_type) if memory_type else src.memory_type
        ids = []
        for _ in range(min(count, 100)):
            uid_str = _uuid7()
            unified = UnifiedID(memory_type=mt, source=src, identifier=uid_str)
            self._registry.register(unified)
            ids.append(unified.to_dict())
        return {
            "operation": "generate",
            "count": len(ids),
            "ids": ids,
        }

    def _resolve(self, unified_id: str = "", **_: Any) -> dict[str, Any]:
        """Resolve a unified ID to its original ID."""
        original = self._registry.resolve(unified_id)
        if original is None:
            return {
                "operation": "resolve",
                "unified_id": unified_id,
                "found": False,
            }
        return {
            "operation": "resolve",
            "unified_id": unified_id,
            "original_id": original,
            "found": True,
        }

    def _reverse_lookup(self, source: str = "", original_id: str = "", **_: Any) -> dict[str, Any]:
        """Look up unified ID from source + original ID."""
        src = SourceServer.from_string(source)
        unified = self._registry.lookup(src, original_id)
        if unified is None:
            return {
                "operation": "reverse_lookup",
                "source": source,
                "original_id": original_id,
                "found": False,
            }
        return {
            "operation": "reverse_lookup",
            "source": source,
            "original_id": original_id,
            "unified_id": unified,
            "found": True,
        }

    def _resolve_conflict(
        self,
        id_a: str = "",
        id_b: str = "",
        strategy: str = "keep_newer",
        **_: Any,
    ) -> dict[str, Any]:
        """Resolve a conflict between two IDs claiming to represent the same entity.

        Strategies:
            - ``keep_newer``: Keep the ID with the more recent timestamp.
            - ``keep_a`` / ``keep_b``: Explicitly choose one.
            - ``merge``: Register both and create a mapping.
        """
        try:
            uid_a = UnifiedID.parse(id_a)
            uid_b = UnifiedID.parse(id_b)
        except ValueError as e:
            return {"operation": "resolve_conflict", "error": str(e)}

        if strategy == "keep_a":
            winner, loser = uid_a, uid_b
        elif strategy == "keep_b":
            winner, loser = uid_b, uid_a
        elif strategy == "keep_newer":
            if uid_a.created_at >= uid_b.created_at:
                winner, loser = uid_a, uid_b
            else:
                winner, loser = uid_b, uid_a
        elif strategy == "merge":
            self._registry.register(uid_a)
            self._registry.register(uid_b)
            return {
                "operation": "resolve_conflict",
                "strategy": "merge",
                "kept": [uid_a.unified, uid_b.unified],
            }
        else:
            return {"operation": "resolve_conflict", "error": f"Unknown strategy: {strategy}"}

        self._registry.register(winner)
        return {
            "operation": "resolve_conflict",
            "strategy": strategy,
            "winner": winner.unified,
            "loser": loser.unified,
        }

    def _batch_register(
        self,
        items: list[dict[str, str]] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Register multiple IDs in batch.

        Each item should have ``source``, ``original_id``, and optionally ``memory_type``.
        """
        items = items or []
        tuples = []
        for item in items:
            src = SourceServer.from_string(item["source"])
            mt = MemoryType.from_string(item["memory_type"]) if "memory_type" in item else None
            tuples.append((src, item["original_id"], mt))

        registered = self._registry.batch_register(tuples)
        return {
            "operation": "batch_register",
            "count": len(registered),
            "ids": [uid.to_dict() for uid in registered],
        }

    def _stats(self) -> dict[str, Any]:
        """Get ID registry statistics."""
        stats = self._registry.stats()
        stats["operation"] = "stats"
        return stats


__all__ = ["IDManagementTool"]
