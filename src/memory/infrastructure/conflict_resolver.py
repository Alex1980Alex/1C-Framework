"""Resolves concurrent update conflicts in a memory system.

Provides strategies for resolving conflicts when multiple updates target the
same entity or field simultaneously. Supports last-write-wins, source priority,
field-level merging, and manual conflict flagging.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConflictStrategy(Enum):
    """Strategies for resolving concurrent update conflicts."""

    LAST_WRITE_WINS = "last_write_wins"
    SOURCE_PRIORITY = "source_priority"
    MERGE_FIELDS = "merge_fields"
    MANUAL = "manual"


@dataclass
class ConflictRecord:
    """Represents a single field-level conflict between two concurrent updates."""

    entity_id: str
    field_name: str
    current_value: Any
    incoming_value: Any
    current_timestamp: datetime
    incoming_timestamp: datetime
    current_source: str
    incoming_source: str


@dataclass
class ConflictResult:
    """Outcome of a conflict resolution attempt."""

    resolved: bool
    strategy_used: ConflictStrategy
    resolved_value: Any
    conflicts: list[ConflictRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConflictResolver:
    """Resolves concurrent update conflicts using configurable strategies.

    Parameters
    ----------
    default_strategy:
        The fallback strategy when none is specified in ``resolve()``.
    source_priorities:
        Ordered list of source identifiers where the first element has the
        highest priority. Used by the ``SOURCE_PRIORITY`` strategy.
    """

    def __init__(
        self,
        default_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        source_priorities: list[str] | None = None,
    ) -> None:
        self._default_strategy = default_strategy
        self._source_priorities: list[str] = list(source_priorities) if source_priorities else []
        self._source_priority_map: dict[str, int] = {
            src: idx for idx, src in enumerate(self._source_priorities)
        }

    # -- Public API ----------------------------------------------------------

    def resolve(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
        strategy: ConflictStrategy | None = None,
    ) -> ConflictResult:
        """Resolve a full-entity conflict between *current* and *incoming*.

        Both dicts may contain special keys:
        - ``"_entity_id"`` — identifier of the entity
        - ``"_timestamp"`` — datetime of the update
        - ``"_source"`` — string identifier of the update source
        """
        effective = strategy if strategy is not None else self._default_strategy

        entity_id = current.get("_entity_id", incoming.get("_entity_id", "unknown"))
        current_ts: datetime = current.get("_timestamp", datetime.min.replace(tzinfo=UTC))
        incoming_ts: datetime = incoming.get("_timestamp", datetime.min.replace(tzinfo=UTC))
        current_src: str = current.get("_source", "")
        incoming_src: str = incoming.get("_source", "")

        if effective == ConflictStrategy.LAST_WRITE_WINS:
            return self._resolve_last_write_wins(
                current, incoming, current_ts, incoming_ts, entity_id
            )

        if effective == ConflictStrategy.SOURCE_PRIORITY:
            return self._resolve_source_priority(
                current, incoming, current_src, incoming_src, entity_id
            )

        if effective == ConflictStrategy.MERGE_FIELDS:
            return self._resolve_merge_fields(
                current,
                incoming,
                current_ts,
                incoming_ts,
                current_src,
                incoming_src,
                entity_id,
            )

        if effective == ConflictStrategy.MANUAL:
            return self._resolve_manual(
                current,
                incoming,
                current_ts,
                incoming_ts,
                current_src,
                incoming_src,
                entity_id,
            )

        return ConflictResult(resolved=False, strategy_used=effective, resolved_value=None)

    def resolve_field(
        self,
        field_name: str,
        current_val: Any,
        incoming_val: Any,
        current_ts: datetime,
        incoming_ts: datetime,
        current_src: str,
        incoming_src: str,
    ) -> tuple[Any, bool]:
        """Resolve a single field conflict.

        Returns ``(resolved_value, was_conflict)``."""
        if current_val == incoming_val:
            return current_val, False

        strategy = self._default_strategy

        if strategy == ConflictStrategy.LAST_WRITE_WINS:
            winner = incoming_val if incoming_ts >= current_ts else current_val
            return winner, True

        if strategy == ConflictStrategy.SOURCE_PRIORITY:
            winner = self._pick_by_source_priority(
                current_val, incoming_val, current_src, incoming_src
            )
            return winner, True

        return incoming_val, True

    def merge_dicts(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
    ) -> tuple[dict[str, Any], list[ConflictRecord]]:
        """Merge two dicts. Non-overlapping keys kept from both.

        For overlapping keys the incoming value is kept and a ConflictRecord emitted.
        """
        merged: dict[str, Any] = dict(current)
        conflicts: list[ConflictRecord] = []

        current_ts: datetime = current.get("_timestamp", datetime.min.replace(tzinfo=UTC))
        incoming_ts: datetime = incoming.get("_timestamp", datetime.min.replace(tzinfo=UTC))
        current_src: str = current.get("_source", "")
        incoming_src: str = incoming.get("_source", "")
        entity_id: str = current.get("_entity_id", incoming.get("_entity_id", "unknown"))

        for key, incoming_val in incoming.items():
            if key.startswith("_"):
                merged[key] = incoming_val
                continue

            if key in merged and merged[key] != incoming_val:
                conflicts.append(
                    ConflictRecord(
                        entity_id=entity_id,
                        field_name=key,
                        current_value=merged[key],
                        incoming_value=incoming_val,
                        current_timestamp=current_ts,
                        incoming_timestamp=incoming_ts,
                        current_source=current_src,
                        incoming_source=incoming_src,
                    ),
                )
            merged[key] = incoming_val

        return merged, conflicts

    # -- Strategy implementations --------------------------------------------

    def _resolve_last_write_wins(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
        current_ts: datetime,
        incoming_ts: datetime,
        entity_id: str,
    ) -> ConflictResult:
        winner = incoming if incoming_ts >= current_ts else current
        return ConflictResult(
            resolved=True,
            strategy_used=ConflictStrategy.LAST_WRITE_WINS,
            resolved_value=dict(winner),
            metadata={"entity_id": entity_id},
        )

    def _resolve_source_priority(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
        current_src: str,
        incoming_src: str,
        entity_id: str,
    ) -> ConflictResult:
        winner = self._pick_by_source_priority(current, incoming, current_src, incoming_src)
        winning_src = current_src if winner is current else incoming_src
        return ConflictResult(
            resolved=True,
            strategy_used=ConflictStrategy.SOURCE_PRIORITY,
            resolved_value=dict(winner),
            metadata={"entity_id": entity_id, "winning_source": winning_src},
        )

    def _resolve_merge_fields(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
        current_ts: datetime,
        incoming_ts: datetime,
        current_src: str,
        incoming_src: str,
        entity_id: str,
    ) -> ConflictResult:
        merged, conflicts = self.merge_dicts(current, incoming)
        return ConflictResult(
            resolved=len(conflicts) == 0,
            strategy_used=ConflictStrategy.MERGE_FIELDS,
            resolved_value=merged,
            conflicts=conflicts,
            metadata={"entity_id": entity_id, "conflict_count": len(conflicts)},
        )

    def _resolve_manual(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
        current_ts: datetime,
        incoming_ts: datetime,
        current_src: str,
        incoming_src: str,
        entity_id: str,
    ) -> ConflictResult:
        conflicts: list[ConflictRecord] = []
        all_keys = set(current.keys()) | set(incoming.keys())
        for key in sorted(all_keys):
            if key.startswith("_"):
                continue
            c_val = current.get(key)
            i_val = incoming.get(key)
            if c_val != i_val:
                conflicts.append(
                    ConflictRecord(
                        entity_id=entity_id,
                        field_name=key,
                        current_value=c_val,
                        incoming_value=i_val,
                        current_timestamp=current_ts,
                        incoming_timestamp=incoming_ts,
                        current_source=current_src,
                        incoming_source=incoming_src,
                    ),
                )
        return ConflictResult(
            resolved=False,
            strategy_used=ConflictStrategy.MANUAL,
            resolved_value=None,
            conflicts=conflicts,
            metadata={"entity_id": entity_id, "message": "Manual resolution required"},
        )

    # -- Helpers -------------------------------------------------------------

    def _pick_by_source_priority(
        self,
        current_val: Any,
        incoming_val: Any,
        current_src: str,
        incoming_src: str,
    ) -> Any:
        """Return the value whose source has higher priority. Ties favor current."""
        current_rank = self._source_priority_map.get(current_src, len(self._source_priorities))
        incoming_rank = self._source_priority_map.get(incoming_src, len(self._source_priorities))
        if incoming_rank < current_rank:
            return incoming_val
        return current_val


__all__ = [
    "ConflictRecord",
    "ConflictResolver",
    "ConflictResult",
    "ConflictStrategy",
]
