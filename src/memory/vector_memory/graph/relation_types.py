"""Relation types for memory knowledge graph.

Defines 20 relation types with BSL-specific patterns, plus an in-memory registry.

Migrated from: unified-memory-mcp/src/graph/relation_types.py (532 lines)
No external dependencies.

Version: 1.0 (2026-04-04) -- P2 migration
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RelationDirection(str, Enum):
    """Direction of a relation."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BIDIRECTIONAL = "bidirectional"


class RelationWeight(str, Enum):
    """Weight category for a relation."""

    STRONG = "strong"  # 0.8-1.0
    MODERATE = "moderate"  # 0.4-0.7
    WEAK = "weak"  # 0.1-0.3

    NEGATIVE = "negative"  # -1.0-0.0

    DERIVED = "derived"  # computed


# Weight value ranges
_WEIGHT_RANGES: dict[RelationWeight, tuple[float, float]] = {
    RelationWeight.STRONG: (0.8, 1.0),
    RelationWeight.MODERATE: (0.4, 0.7),
    RelationWeight.WEAK: (0.1, 0.3),
    RelationWeight.NEGATIVE: (-1.0, 0.0),
    RelationWeight.DERIVED: (0.0, 1.0),
}


class RelationType(str, Enum):
    """20 relation types for memory knowledge graph."""

    # Structural relations
    DEPENDS_ON = "depends_on"
    CALLS = "calls"
    IMPLEMENTS = "implements"
    IMPORTS = "imports"
    REFERENCES = "references"

    INHERITS_FROM = "inherits_from"

    # Semantic relations
    RELATED_TO = "related_to"
    SIMILAR_TO = "similar_to"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    SPECIALIZES = "specializes"

    PART_OF = "part_of"

    # Temporal relations
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    SUPERSEDES = "supersed_by"
    TRIGGERED_BY = "triggered_by"

    OCCURS_WITH = "occurs_with"

    # Memory-specific
    LEARNED_FROM = "learned_from"
    REMEMBERS = "remembers"
    FORGETS = "forgets"
    ASSOCIATED_WITH = "associated_with"

    MENTIONS = "mentions"

    CONTRASTS_WITH = "contrasts_with"

    # BSL-specific
    USES_QUERY = "uses_query"
    USES_FORM = "uses_form"
    USES_API = "uses_api"
    HANDLES_EVENT = "handles_event"

    MODIFIES = "modifies"
    VALIDATES = "validates"

    POSTS = "posts"

    # Inverse relations (auto-generated)
    CALLED_BY = "called_by"
    TRIGGERS = "triggers"
    SUPERSEDED_BY = "superseded_by"


@dataclass
class Relation:
    """A single relation between two entities."""

    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 0.5
    direction: RelationDirection = RelationDirection.BIDIRECTIONAL
    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "weight": self.weight,
            "direction": self.direction.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Relation":
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=RelationType(data.get("relation_type", "related_to")),
            weight=data.get("weight", 0.5),
            direction=RelationDirection(data.get("direction", "bidirectional")),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", 0.0),
        )


# Auto-inverse mapping for relation types
_INVERSE_RELATIONS: dict[RelationType, RelationType] = {
    RelationType.CALLS: RelationType.CALLED_BY,
    RelationType.PRECEDES: RelationType.FOLLOWS,
    RelationType.SUPERSEDES: RelationType.SUPERSEDED_BY,
    RelationType.TRIGGERED_BY: RelationType.TRIGGERS,
}


class RelationRegistry:
    """
    In-memory registry of relations.

    Maintains source, target, and type indexes for efficient lookup.
    Auto-generates inverse relations where applicable.
    """

    def __init__(self):
        self._relations: list[Relation | None] = []
        self._by_source: dict[str, list[int]] = {}  # source_id -> [indices]
        self._by_target: dict[str, list[int]] = {}  # target_id -> [indices]
        self._by_type: dict[RelationType, list[int]] = {}  # type -> [indices]

        self._id_map: dict[str, int] = {}  # source:target:type -> index

    def add(self, relation: Relation) -> None:
        """Add a relation to the registry."""
        idx = len(self._relations)
        self._relations.append(relation)

        self._by_source.setdefault(relation.source_id, []).append(idx)
        self._by_target.setdefault(relation.target_id, []).append(idx)
        self._by_type.setdefault(relation.relation_type, []).append(idx)

        self._id_map[
            f"{relation.source_id}:{relation.target_id}:{relation.relation_type.value}"
        ] = idx

        self._maybe_add_inverse(relation)

    def _maybe_add_inverse(self, relation: Relation) -> None:
        """Auto-add inverse relation if applicable."""
        inverse_type = _INVERSE_RELATIONS.get(relation.relation_type)
        if inverse_type and relation.direction in (
            RelationDirection.OUTGOING,
            RelationDirection.BIDIRECTIONAL,
        ):
            inv = Relation(
                source_id=relation.target_id,
                target_id=relation.source_id,
                relation_type=inverse_type,
                weight=relation.weight,
                direction=RelationDirection.INCOMING,
            )
            key = f"{inv.source_id}:{inv.target_id}:{inv.relation_type.value}"
            if key not in self._id_map:
                self.add(inv)

    def get_by_source(self, source_id: str) -> list[Relation]:
        """Get all relations from a source."""
        indices = self._by_source.get(source_id, [])
        return [r for i in indices if (r := self._relations[i]) is not None]

    def get_by_target(self, target_id: str) -> list[Relation]:
        """Get all relations to a target."""
        indices = self._by_target.get(target_id, [])
        return [r for i in indices if (r := self._relations[i]) is not None]

    def get_by_type(self, relation_type: RelationType) -> list[Relation]:
        """Get all relations of a specific type."""
        indices = self._by_type.get(relation_type, [])
        return [r for i in indices if (r := self._relations[i]) is not None]

    def get_between(self, source_id: str, target_id: str) -> list[Relation]:
        """Get relations between two entities."""
        result = []
        for rel in self.get_by_source(source_id):
            if rel.target_id == target_id:
                result.append(rel)
        return result

    def remove(self, source_id: str, target_id: str, relation_type: RelationType) -> bool:
        """Remove a specific relation."""
        key = f"{source_id}:{target_id}:{relation_type.value}"
        idx = self._id_map.get(key)
        if idx is None:
            return False

        # Remove from indexes
        self._relations[idx] = None
        src_list = self._by_source.get(source_id, [])
        if idx in src_list:
            src_list.remove(idx)
        tgt_list = self._by_target.get(target_id, [])
        if idx in tgt_list:
            tgt_list.remove(idx)
        type_list = self._by_type.get(relation_type, [])
        if idx in type_list:
            type_list.remove(idx)
        del self._id_map[key]
        return True

    @property
    def all_relations(self) -> list[Relation]:
        """Get all non-None relations."""
        return [r for r in self._relations if r is not None]

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_relations": len([r for r in self._relations if r is not None]),
            "by_type": {t.value: len(ids) for t, ids in self._by_type.items()},
            "unique_sources": len(self._by_source),
            "unique_targets": len(self._by_target),
        }


__all__ = [
    "Relation",
    "RelationDirection",
    "RelationRegistry",
    "RelationType",
    "RelationWeight",
]
