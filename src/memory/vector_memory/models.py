"""Data models for the self-learning pattern system.

Migrated from D:\\1C-Enterprise_Framework\\vector-memory-mcp\\src\\models\\patterns.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PatternType(Enum):
    """Types of learned patterns."""

    CODE_CONVENTION = "code-convention"
    WORKFLOW_PATTERN = "workflow-pattern"
    DEBUGGING_HEURISTIC = "debugging-heuristic"
    ARCHITECTURAL_PRINCIPLE = "architectural-principle"
    PROJECT_STRUCTURE = "project-structure"
    BSL_PATTERN = "bsl-pattern"


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
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "reference": self.reference,
            "weight": self.weight,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceSource":
        return cls(
            source_type=data["source_type"],
            reference=data["reference"],
            weight=data.get("weight", 1.0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
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
    evidence_sources: List[EvidenceSource] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    decay_rate: float = 0.05
    application_count: int = 0
    last_applied: Optional[datetime] = None
    version: int = 1
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return ConfidenceLevel.from_score(self.confidence)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_sources)

    def to_dict(self) -> Dict[str, Any]:
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
            "version": self.version,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearnedPattern":
        return cls(
            pattern_id=data["pattern_id"],
            pattern_type=PatternType(data["pattern_type"]),
            name=data.get("name", ""),
            description=data.get("description", ""),
            content=data["content"],
            confidence=data["confidence"],
            evidence_sources=[EvidenceSource.from_dict(e) for e in data.get("evidence_sources", [])],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            decay_rate=data.get("decay_rate", 0.05),
            application_count=data.get("application_count", 0),
            last_applied=datetime.fromisoformat(data["last_applied"]) if data.get("last_applied") else None,
            version=data.get("version", 1),
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

    def to_dict(self) -> Dict[str, Any]:
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
    patterns_by_type: Dict[str, int]
    patterns_by_confidence: Dict[str, int]
    recently_active: int = 0
    last_decay_run: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_patterns": self.total_patterns,
            "patterns_by_type": self.patterns_by_type,
            "patterns_by_confidence": self.patterns_by_confidence,
            "recently_active": self.recently_active,
            "last_decay_run": self.last_decay_run.isoformat() if self.last_decay_run else None,
        }
