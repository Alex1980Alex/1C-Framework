"""Data models for the self-learning pattern system.

Also the payload-coercion contract (roadmap 260716 P0.1): store payloads are
UNTRUSTED input — written by 8+ producers (harvesters, route_and_save,
capture→confirm, admin scripts) across process boundaries and versions. A strict
``PatternType(payload[...])`` on read turned one drifted point into a total
failure of search_patterns / decay / ForgetGate (incident 2026-07-16). Writers
normalize before storing; readers coerce defensively anyway.

Stdlib-only by design: hooks (``pattern_harvest``) and ``confidence`` import this
module, so it must stay dependency-free.

Migrated from D:\\1C-Enterprise_Framework\\vector-memory-mcp\\src\\models\\patterns.py
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PatternType(Enum):
    """Types of learned patterns."""

    CODE_CONVENTION = "code-convention"
    WORKFLOW_PATTERN = "workflow-pattern"
    DEBUGGING_HEURISTIC = "debugging-heuristic"
    ARCHITECTURAL_PRINCIPLE = "architectural-principle"
    PROJECT_STRUCTURE = "project-structure"
    BSL_PATTERN = "bsl-pattern"

    @classmethod
    def coerce(cls, value: Any) -> "PatternType":
        """Map any writer-supplied value onto a canonical type. Never raises.

        Order: enum instance → exact/normalized enum value → alias table →
        DEFAULT_PATTERN_TYPE (None, empty and unknown all land there).
        """
        if isinstance(value, cls):
            return value
        if value is None:
            return DEFAULT_PATTERN_TYPE
        key = str(value).strip().lower().replace("_", "-")
        if not key:
            return DEFAULT_PATTERN_TYPE
        try:
            return cls(key)
        except ValueError:
            pass
        alias = _PATTERN_TYPE_ALIASES.get(key)
        return cls(alias) if alias else DEFAULT_PATTERN_TYPE


# Unknown/None/empty land here. Deliberately a NON-invariant type: junk must stay
# archivable by staleness (see confidence.is_invariant).
DEFAULT_PATTERN_TYPE = PatternType.WORKFLOW_PATTERN

# THE alias table — single source for every producer and consumer. Keys are
# normalized (lower, `_`→`-`). Two groups:
#   1. drift observed in `learned_patterns` (audit 260716 §2) — free-form types
#      written by capture→confirm→harvest before the write-contract existed;
#   2. memory-ai categories — previously duplicated in
#      `scripts/normalize_light_patterns.CATEGORY_MAP` and
#      `.claude/hooks/shared/reflection._CATEGORY_MAP`; both resolve here now.
# Add new aliases HERE, never in a caller-local map.
_PATTERN_TYPE_ALIASES: dict[str, str] = {
    # 1. observed drift
    "error-fix": "debugging-heuristic",
    "debugging": "debugging-heuristic",
    "1c-bsl": "bsl-pattern",
    "bsl": "bsl-pattern",
    "1c-query-optimization": "bsl-pattern",
    "1c-metadata-pattern": "bsl-pattern",
    "requirements": "workflow-pattern",
    "workflow": "workflow-pattern",
    "testing-workflow": "workflow-pattern",
    "refactor-pattern": "code-convention",
    "architecture-lesson": "architectural-principle",
    # 2. memory-ai categories
    "decision": "architectural-principle",
    "preference": "workflow-pattern",
    "bugfix": "debugging-heuristic",
    "implementation": "code-convention",
    "reference": "project-structure",
    "feedback": "workflow-pattern",
    "project": "project-structure",
}


def normalize_pattern_type(value: Any) -> tuple[str, str | None]:
    """Return ``(canonical_value, original_or_None)`` for a writer.

    ``original`` is non-None only when coercion actually changed something — the
    caller stores it in ``metadata.original_pattern_type`` so the provenance of a
    coerced write is never lost.
    """
    canonical = PatternType.coerce(value)
    if value is None:
        return canonical.value, None
    raw = value.value if isinstance(value, PatternType) else str(value).strip()
    return canonical.value, (raw if raw and raw != canonical.value else None)


def coerce_float(value: Any, default: float) -> float:
    """Payload float or ``default``. None/garbage/NaN/inf → default.

    NaN/inf are rejected too: they survive ``float()`` but poison the comparisons
    and sorting downstream (ranking, thresholds).
    """
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def coerce_int(value: Any, default: int) -> int:
    """Payload int or ``default``. None/garbage → default."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def coerce_dt(value: Any) -> datetime | None:
    """Parse an ISO timestamp payload field; None on absent/garbage/wrong type.

    Callers decide the fallback (skip the field, try the next key in a chain, or
    substitute now()) — this never raises and never invents a time.
    """
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class ConfidenceLevel(Enum):
    """Confidence levels with thresholds."""

    HIGH = (0.7, 1.0)
    MEDIUM = (0.4, 0.7)
    LOW = (0.1, 0.4)
    EXPIRED = (0.0, 0.1)

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        if score >= 0.7:
            return cls.HIGH
        elif score >= 0.4:
            return cls.MEDIUM
        elif score >= 0.1:
            return cls.LOW
        else:
            return cls.EXPIRED


@dataclass
class EvidenceSource:
    """Source of evidence for pattern learning."""

    source_type: str  # "file", "commit", "conversation", "tool-use"
    reference: str
    weight: float = 1.0
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "reference": self.reference,
            "weight": self.weight,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceSource":
        # Tolerant parse: harvester-written points may carry {"source": "..."}
        # instead of source_type/reference — one such point must not kill a
        # whole search_patterns response (F6, roadmap 260610).
        return cls(
            source_type=data.get("source_type", "unknown"),
            reference=data.get("reference") or data.get("source", ""),
            weight=coerce_float(data.get("weight"), 1.0),
            # coerce_dt completes what F6 started: the docstring promised tolerance
            # while fromisoformat still raised on a garbage timestamp.
            timestamp=coerce_dt(data.get("timestamp")),
            metadata=data.get("metadata", {}),
        )


@dataclass
class LearnedPattern:
    """A learned pattern with confidence tracking."""

    pattern_id: str
    pattern_type: PatternType
    name: str
    description: str
    content: str
    confidence: float
    evidence_sources: list[EvidenceSource] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    decay_rate: float = 0.05
    application_count: int = 0
    last_applied: datetime | None = None
    succ: float = 0.0
    fail: float = 0.0
    last_decay_at: datetime | None = None
    expired_at: datetime | None = None
    version: int = 1
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return ConfidenceLevel.from_score(self.confidence)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.name,
            "evidence_sources": [e.to_dict() for e in self.evidence_sources],
            "evidence_count": self.evidence_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "decay_rate": self.decay_rate,
            "application_count": self.application_count,
            "last_applied": self.last_applied.isoformat() if self.last_applied else None,
            "succ": self.succ,
            "fail": self.fail,
            "last_decay_at": self.last_decay_at.isoformat() if self.last_decay_at else None,
            "expired_at": self.expired_at.isoformat() if self.expired_at else None,
            "version": self.version,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearnedPattern":
        # Tolerant by contract (see module docstring): `data` is store-shaped and
        # therefore untrusted. Mirrors server._pattern_from_payload — a drifted
        # type, a garbage timestamp or a null confidence must degrade the FIELD,
        # never raise and take a whole search/list response down with it.
        return cls(
            pattern_id=str(data.get("pattern_id") or ""),
            pattern_type=PatternType.coerce(data.get("pattern_type")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            content=data.get("content", ""),
            confidence=coerce_float(data.get("confidence"), 0.5),
            evidence_sources=[
                EvidenceSource.from_dict(e) for e in data.get("evidence_sources", [])
            ],
            created_at=coerce_dt(data.get("created_at")) or datetime.now(),
            updated_at=coerce_dt(data.get("updated_at")) or datetime.now(),
            decay_rate=coerce_float(data.get("decay_rate"), 0.05),
            application_count=coerce_int(data.get("application_count"), 0),
            last_applied=coerce_dt(data.get("last_applied")),
            succ=coerce_float(data.get("succ"), 0.0),
            fail=coerce_float(data.get("fail"), 0.0),
            last_decay_at=coerce_dt(data.get("last_decay_at")),
            expired_at=coerce_dt(data.get("expired_at")),
            version=coerce_int(data.get("version"), 1),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PatternSearchResult:
    """Result from pattern search."""

    pattern: LearnedPattern
    similarity_score: float
    adjusted_confidence: float
    combined_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern.to_dict(),
            "similarity_score": self.similarity_score,
            "adjusted_confidence": self.adjusted_confidence,
            "combined_score": self.combined_score,
        }


@dataclass
class LearningStats:
    """Statistics about the learning system."""

    total_patterns: int
    patterns_by_type: dict[str, int]
    patterns_by_confidence: dict[str, int]
    recently_active: int = 0
    last_decay_run: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_patterns": self.total_patterns,
            "patterns_by_type": self.patterns_by_type,
            "patterns_by_confidence": self.patterns_by_confidence,
            "recently_active": self.recently_active,
            "last_decay_run": self.last_decay_run.isoformat() if self.last_decay_run else None,
        }
