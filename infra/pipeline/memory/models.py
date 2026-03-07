"""
Data Models for Memory & Learning Module.

Sprint 3.3.1: Core Models

This module defines:
- MemoryEntry - base memory storage unit
- Pattern - successful implementation patterns
- ErrorRecord - error records for learning
- Recommendation - action recommendations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import json
import hashlib


# =============================================================================
# Enums
# =============================================================================

class MemoryType(Enum):
    """Type of memory entry."""
    PATTERN = "pattern"           # Successful implementation pattern
    ERROR = "error"               # Error record for learning
    CONTEXT = "context"           # Project/task context
    RECOMMENDATION = "recommendation"  # Generated recommendation
    EXECUTION = "execution"       # Execution history
    CODE = "code"                 # Code snippets
    GENERAL = "general"           # General knowledge


class PatternType(Enum):
    """Type of implementation pattern."""
    ARCHITECTURE = "architecture"     # Architectural pattern
    IMPLEMENTATION = "implementation" # Implementation pattern
    REFACTORING = "refactoring"       # Refactoring pattern
    BUG_FIX = "bug_fix"               # Bug fix pattern
    OPTIMIZATION = "optimization"     # Performance optimization
    INTEGRATION = "integration"       # Integration pattern
    TESTING = "testing"               # Testing pattern
    DOCUMENTATION = "documentation"   # Documentation pattern


class ErrorSeverity(Enum):
    """Severity level of errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationType(Enum):
    """Type of recommendation."""
    PATTERN_MATCH = "pattern_match"       # Based on pattern matching
    ERROR_PREVENTION = "error_prevention" # Based on error history
    BEST_PRACTICE = "best_practice"       # Based on best practices
    OPTIMIZATION = "optimization"         # Performance optimization
    SIMILAR_TASK = "similar_task"         # Based on similar tasks


# =============================================================================
# Base Memory Entry
# =============================================================================

@dataclass
class MemoryEntry:
    """Base class for all memory entries."""

    id: str
    memory_type: MemoryType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5  # 0.0 to 1.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    project_id: Optional[str] = None
    session_id: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "tags": self.tags,
            "importance": self.importance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "project_id": self.project_id,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            project_id=data.get("project_id"),
            session_id=data.get("session_id"),
        )

    def get_hash(self) -> str:
        """Get content hash for deduplication."""
        content_str = f"{self.memory_type.value}:{self.content}"
        return hashlib.md5(content_str.encode()).hexdigest()[:16]


# =============================================================================
# Pattern
# =============================================================================

@dataclass
class Pattern:
    """Represents a successful implementation pattern."""

    id: str
    name: str
    pattern_type: PatternType
    description: str

    # Pattern details
    problem: str                          # Problem being solved
    solution: str                         # Solution approach
    code_template: Optional[str] = None   # Code template if applicable

    # Context
    applicable_contexts: list[str] = field(default_factory=list)  # When to apply
    prerequisites: list[str] = field(default_factory=list)        # Required conditions

    # Metrics
    success_count: int = 0                # Times successfully applied
    failure_count: int = 0                # Times failed
    avg_time_saved_minutes: float = 0.0   # Average time saved

    # Metadata
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None      # Agent or user

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def confidence_score(self) -> float:
        """Calculate confidence based on usage and success."""
        usage_factor = min(1.0, (self.success_count + self.failure_count) / 10)
        return self.success_rate * usage_factor

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "pattern_type": self.pattern_type.value,
            "description": self.description,
            "problem": self.problem,
            "solution": self.solution,
            "code_template": self.code_template,
            "applicable_contexts": self.applicable_contexts,
            "prerequisites": self.prerequisites,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_time_saved_minutes": self.avg_time_saved_minutes,
            "success_rate": self.success_rate,
            "confidence_score": self.confidence_score,
            "tags": self.tags,
            "importance": self.importance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pattern":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            pattern_type=PatternType(data["pattern_type"]),
            description=data["description"],
            problem=data["problem"],
            solution=data["solution"],
            code_template=data.get("code_template"),
            applicable_contexts=data.get("applicable_contexts", []),
            prerequisites=data.get("prerequisites", []),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            avg_time_saved_minutes=data.get("avg_time_saved_minutes", 0.0),
            tags=data.get("tags", []),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            created_by=data.get("created_by"),
        )

    def to_memory_entry(self) -> MemoryEntry:
        """Convert to MemoryEntry for storage."""
        return MemoryEntry(
            id=self.id,
            memory_type=MemoryType.PATTERN,
            content=f"{self.name}: {self.description}\n\nProblem: {self.problem}\n\nSolution: {self.solution}",
            metadata=self.to_dict(),
            tags=self.tags + [self.pattern_type.value],
            importance=self.importance,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


# =============================================================================
# Error Record
# =============================================================================

@dataclass
class ErrorRecord:
    """Records an error for learning purposes."""

    id: str
    error_type: str                       # Exception type or error category
    error_message: str                    # Error message
    severity: ErrorSeverity

    # Context
    context: str                          # What was being done
    file_path: Optional[str] = None       # File where error occurred
    function_name: Optional[str] = None   # Function name
    line_number: Optional[int] = None     # Line number

    # Analysis
    root_cause: Optional[str] = None      # Identified root cause
    fix_applied: Optional[str] = None     # How it was fixed
    prevention_hint: Optional[str] = None # How to prevent in future

    # Metrics
    occurrence_count: int = 1             # How many times seen
    time_to_fix_minutes: Optional[float] = None  # Time spent fixing

    # Metadata
    tags: list[str] = field(default_factory=list)
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def is_resolved(self) -> bool:
        """Check if error is resolved."""
        return self.fix_applied is not None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "context": self.context,
            "file_path": self.file_path,
            "function_name": self.function_name,
            "line_number": self.line_number,
            "root_cause": self.root_cause,
            "fix_applied": self.fix_applied,
            "prevention_hint": self.prevention_hint,
            "occurrence_count": self.occurrence_count,
            "time_to_fix_minutes": self.time_to_fix_minutes,
            "is_resolved": self.is_resolved,
            "tags": self.tags,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorRecord":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            error_type=data["error_type"],
            error_message=data["error_message"],
            severity=ErrorSeverity(data["severity"]),
            context=data["context"],
            file_path=data.get("file_path"),
            function_name=data.get("function_name"),
            line_number=data.get("line_number"),
            root_cause=data.get("root_cause"),
            fix_applied=data.get("fix_applied"),
            prevention_hint=data.get("prevention_hint"),
            occurrence_count=data.get("occurrence_count", 1),
            time_to_fix_minutes=data.get("time_to_fix_minutes"),
            tags=data.get("tags", []),
            project_id=data.get("project_id"),
            session_id=data.get("session_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
        )

    def to_memory_entry(self) -> MemoryEntry:
        """Convert to MemoryEntry for storage."""
        return MemoryEntry(
            id=self.id,
            memory_type=MemoryType.ERROR,
            content=f"Error: {self.error_type}\n{self.error_message}\n\nContext: {self.context}",
            metadata=self.to_dict(),
            tags=self.tags + [self.error_type, self.severity.value],
            importance=0.3 + (0.2 * ["low", "medium", "high", "critical"].index(self.severity.value)),
            created_at=self.created_at,
            project_id=self.project_id,
            session_id=self.session_id,
        )


# =============================================================================
# Recommendation
# =============================================================================

@dataclass
class Recommendation:
    """Represents a recommendation for an action."""

    id: str
    recommendation_type: RecommendationType
    title: str
    description: str

    # Action details
    action: str                           # Recommended action
    rationale: str                        # Why this is recommended
    expected_benefit: str                 # Expected benefit

    # Source
    source_pattern_id: Optional[str] = None    # Pattern this is based on
    source_error_ids: list[str] = field(default_factory=list)  # Errors this prevents

    # Confidence
    confidence: float = 0.5               # 0.0 to 1.0
    priority: int = 1                     # 1 (highest) to 5 (lowest)

    # Metadata
    tags: list[str] = field(default_factory=list)
    context_query: Optional[str] = None   # Query that triggered this
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # When recommendation expires

    # Feedback
    was_applied: Optional[bool] = None
    was_helpful: Optional[bool] = None
    feedback_notes: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def is_expired(self) -> bool:
        """Check if recommendation is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "recommendation_type": self.recommendation_type.value,
            "title": self.title,
            "description": self.description,
            "action": self.action,
            "rationale": self.rationale,
            "expected_benefit": self.expected_benefit,
            "source_pattern_id": self.source_pattern_id,
            "source_error_ids": self.source_error_ids,
            "confidence": self.confidence,
            "priority": self.priority,
            "tags": self.tags,
            "context_query": self.context_query,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired,
            "was_applied": self.was_applied,
            "was_helpful": self.was_helpful,
            "feedback_notes": self.feedback_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Recommendation":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            recommendation_type=RecommendationType(data["recommendation_type"]),
            title=data["title"],
            description=data["description"],
            action=data["action"],
            rationale=data["rationale"],
            expected_benefit=data["expected_benefit"],
            source_pattern_id=data.get("source_pattern_id"),
            source_error_ids=data.get("source_error_ids", []),
            confidence=data.get("confidence", 0.5),
            priority=data.get("priority", 1),
            tags=data.get("tags", []),
            context_query=data.get("context_query"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            was_applied=data.get("was_applied"),
            was_helpful=data.get("was_helpful"),
            feedback_notes=data.get("feedback_notes"),
        )


# =============================================================================
# Learning Context
# =============================================================================

@dataclass
class LearningContext:
    """Context for learning operations."""

    project_id: str
    session_id: str
    current_task: Optional[str] = None
    current_agent: Optional[str] = None   # PM-SPEC, ARCHITECT, IMPLEMENTER, etc.

    # Current state
    files_modified: list[str] = field(default_factory=list)
    patterns_applied: list[str] = field(default_factory=list)
    errors_encountered: list[str] = field(default_factory=list)

    # Search context for recommendations
    keywords: list[str] = field(default_factory=list)
    object_types: list[str] = field(default_factory=list)  # 1C object types

    # Timing
    started_at: Optional[datetime] = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "session_id": self.session_id,
            "current_task": self.current_task,
            "current_agent": self.current_agent,
            "files_modified": self.files_modified,
            "patterns_applied": self.patterns_applied,
            "errors_encountered": self.errors_encountered,
            "keywords": self.keywords,
            "object_types": self.object_types,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }

    def get_search_query(self) -> str:
        """Build search query from context."""
        parts = []
        if self.current_task:
            parts.append(self.current_task)
        if self.keywords:
            parts.extend(self.keywords)
        if self.object_types:
            parts.extend(self.object_types)
        return " ".join(parts)
