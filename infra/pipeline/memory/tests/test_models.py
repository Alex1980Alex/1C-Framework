"""Tests for memory models."""

import pytest
from datetime import datetime

from models import (
    MemoryEntry,
    MemoryType,
    PatternType,
    Pattern,
    ErrorRecord,
    ErrorSeverity,
    Recommendation,
    RecommendationType,
    LearningContext,
)


class TestMemoryEntry:
    """Tests for MemoryEntry dataclass."""

    def test_create_memory_entry(self):
        """Test creating a memory entry."""
        entry = MemoryEntry(
            id="test_1",
            content="Test content",
            memory_type=MemoryType.GENERAL,
            importance=0.7,
        )

        assert entry.id == "test_1"
        assert entry.content == "Test content"
        assert entry.memory_type == MemoryType.GENERAL
        assert entry.importance == 0.7
        assert entry.tags == []
        assert entry.metadata == {}

    def test_memory_entry_with_tags(self):
        """Test memory entry with tags."""
        entry = MemoryEntry(
            id="test_2",
            content="Tagged content",
            memory_type=MemoryType.CODE,
            importance=0.5,
            tags=["python", "testing"],
        )

        assert "python" in entry.tags
        assert "testing" in entry.tags

    def test_memory_entry_to_dict(self):
        """Test converting to dictionary."""
        entry = MemoryEntry(
            id="test_3",
            content="Dict test",
            memory_type=MemoryType.PATTERN,
            importance=0.8,
            metadata={"key": "value"},
        )

        result = entry.to_dict()

        assert result["id"] == "test_3"
        assert result["content"] == "Dict test"
        assert result["memory_type"] == "pattern"
        assert result["importance"] == 0.8
        assert result["metadata"]["key"] == "value"

    def test_memory_entry_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "id": "test_4",
            "content": "From dict",
            "memory_type": "error",
            "importance": 0.9,
            "tags": ["tag1"],
            "metadata": {},
        }

        entry = MemoryEntry.from_dict(data)

        assert entry.id == "test_4"
        assert entry.memory_type == MemoryType.ERROR
        assert entry.importance == 0.9


class TestPattern:
    """Tests for Pattern dataclass."""

    def test_create_pattern(self):
        """Test creating a pattern."""
        pattern = Pattern(
            id="pat_1",
            name="test_pattern",
            pattern_type=PatternType.IMPLEMENTATION,
            description="Test pattern description",
            problem="Test problem",
            solution="Test solution",
        )

        assert pattern.id == "pat_1"
        assert pattern.name == "test_pattern"
        assert pattern.pattern_type == PatternType.IMPLEMENTATION
        assert pattern.success_count == 0
        assert pattern.failure_count == 0

    def test_pattern_success_rate(self):
        """Test success rate calculation."""
        pattern = Pattern(
            id="pat_2",
            name="rate_test",
            pattern_type=PatternType.BUG_FIX,
            description="Bug fix pattern",
            problem="Problem",
            solution="Solution",
            success_count=8,
            failure_count=2,
        )

        assert pattern.success_rate == 0.8

    def test_pattern_success_rate_no_uses(self):
        """Test success rate with no uses."""
        pattern = Pattern(
            id="pat_3",
            name="no_uses",
            pattern_type=PatternType.REFACTORING,
            description="Refactoring pattern",
            problem="Problem",
            solution="Solution",
        )

        assert pattern.success_rate == 0.0

    def test_pattern_confidence_score(self):
        """Test confidence score calculation."""
        pattern = Pattern(
            id="pat_4",
            name="confidence_test",
            pattern_type=PatternType.ARCHITECTURE,
            description="Architecture pattern",
            problem="Problem",
            solution="Solution",
            success_count=50,
            failure_count=5,
        )

        # With 55 uses and ~91% success rate
        assert pattern.confidence_score > 0.8

    def test_pattern_to_dict(self):
        """Test pattern serialization."""
        pattern = Pattern(
            id="pat_5",
            name="serialize",
            pattern_type=PatternType.TESTING,
            description="Testing pattern",
            problem="Test problem",
            solution="Test solution",
            tags=["test"],
        )

        result = pattern.to_dict()

        assert result["id"] == "pat_5"
        assert result["pattern_type"] == "testing"
        assert "test" in result["tags"]

    def test_pattern_from_dict(self):
        """Test pattern deserialization."""
        data = {
            "id": "pat_6",
            "name": "deserialize",
            "pattern_type": "optimization",
            "description": "Optimization pattern",
            "problem": "Slow query",
            "solution": "Add index",
            "success_count": 10,
            "failure_count": 1,
        }

        pattern = Pattern.from_dict(data)

        assert pattern.id == "pat_6"
        assert pattern.pattern_type == PatternType.OPTIMIZATION
        assert pattern.success_count == 10

    def test_pattern_to_memory_entry(self):
        """Test converting pattern to memory entry."""
        pattern = Pattern(
            id="pat_7",
            name="to_memory",
            pattern_type=PatternType.INTEGRATION,
            description="Integration pattern",
            problem="Integration issue",
            solution="Use adapter",
        )

        entry = pattern.to_memory_entry()

        assert entry.memory_type == MemoryType.PATTERN
        assert "Integration issue" in entry.content
        assert "Use adapter" in entry.content


class TestErrorRecord:
    """Tests for ErrorRecord dataclass."""

    def test_create_error_record(self):
        """Test creating an error record."""
        error = ErrorRecord(
            id="err_1",
            error_type="TypeError",
            error_message="Cannot read property",
            severity=ErrorSeverity.HIGH,
            context="Accessing object property",
        )

        assert error.id == "err_1"
        assert error.error_type == "TypeError"
        assert error.severity == ErrorSeverity.HIGH
        assert error.is_resolved is False

    def test_error_with_resolution(self):
        """Test error with resolution."""
        error = ErrorRecord(
            id="err_2",
            error_type="ValueError",
            error_message="Invalid input",
            severity=ErrorSeverity.MEDIUM,
            context="Processing user input",
            fix_applied="Added validation",
            resolved_at=datetime.now(),
        )

        assert error.is_resolved is True

    def test_error_resolution_time(self):
        """Test resolution tracking with time_to_fix."""
        error = ErrorRecord(
            id="err_3",
            error_type="RuntimeError",
            error_message="Crash",
            severity=ErrorSeverity.CRITICAL,
            context="Application running",
            fix_applied="Fixed crash",
            time_to_fix_minutes=150.0,  # 2.5 hours
        )

        assert error.is_resolved is True
        assert error.time_to_fix_minutes == 150.0

    def test_error_to_dict(self):
        """Test error serialization."""
        error = ErrorRecord(
            id="err_4",
            error_type="SyntaxError",
            error_message="Unexpected token",
            severity=ErrorSeverity.HIGH,
            context="Parsing code",
            root_cause="Missing semicolon",
        )

        result = error.to_dict()

        assert result["id"] == "err_4"
        assert result["severity"] == "high"
        assert result["root_cause"] == "Missing semicolon"

    def test_error_from_dict(self):
        """Test error deserialization."""
        data = {
            "id": "err_5",
            "error_type": "IOError",
            "error_message": "File not found",
            "severity": "low",
            "context": "Reading file",
        }

        error = ErrorRecord.from_dict(data)

        assert error.id == "err_5"
        assert error.severity == ErrorSeverity.LOW

    def test_error_to_memory_entry(self):
        """Test converting error to memory entry."""
        error = ErrorRecord(
            id="err_6",
            error_type="ConnectionError",
            error_message="Connection refused",
            severity=ErrorSeverity.HIGH,
            context="Connecting to server",
            prevention_hint="Check network connectivity",
        )

        entry = error.to_memory_entry()

        assert entry.memory_type == MemoryType.ERROR
        assert "ConnectionError" in entry.content


class TestRecommendation:
    """Tests for Recommendation dataclass."""

    def test_create_recommendation(self):
        """Test creating a recommendation."""
        rec = Recommendation(
            id="rec_1",
            recommendation_type=RecommendationType.PATTERN_MATCH,
            title="Use pattern X",
            description="Apply proven pattern X for similar tasks",
            action="Apply pattern X to solve Y",
            rationale="Pattern X is proven effective",
            expected_benefit="Reduces implementation time",
            confidence=0.85,
            priority=1,
        )

        assert rec.id == "rec_1"
        assert rec.recommendation_type == RecommendationType.PATTERN_MATCH
        assert rec.confidence == 0.85
        assert rec.priority == 1
        assert rec.was_applied is None

    def test_recommendation_acceptance(self):
        """Test recommendation acceptance tracking."""
        rec = Recommendation(
            id="rec_2",
            recommendation_type=RecommendationType.BEST_PRACTICE,
            title="Best practice",
            description="Apply recommended best practice",
            action="Do this",
            rationale="It's better",
            expected_benefit="Improved code quality",
            confidence=0.7,
            priority=2,
            was_applied=True,
            was_helpful=True,
        )

        assert rec.was_applied is True
        assert rec.was_helpful is True

    def test_recommendation_to_dict(self):
        """Test recommendation serialization."""
        rec = Recommendation(
            id="rec_3",
            recommendation_type=RecommendationType.ERROR_PREVENTION,
            title="Prevent error",
            description="Add validation to prevent errors",
            action="Add check",
            rationale="Avoid crash",
            expected_benefit="Avoid runtime errors",
            confidence=0.75,
            priority=1,
        )

        result = rec.to_dict()

        assert result["id"] == "rec_3"
        assert result["recommendation_type"] == "error_prevention"
        assert result["priority"] == 1

    def test_recommendation_from_dict(self):
        """Test recommendation deserialization."""
        data = {
            "id": "rec_4",
            "recommendation_type": "optimization",
            "title": "Optimize",
            "description": "Optimize performance-critical code",
            "action": "Improve performance",
            "rationale": "Faster is better",
            "expected_benefit": "Better performance",
            "confidence": 0.8,
            "priority": 3,
        }

        rec = Recommendation.from_dict(data)

        assert rec.id == "rec_4"
        assert rec.recommendation_type == RecommendationType.OPTIMIZATION
        assert rec.confidence == 0.8

    def test_recommendation_serialization(self):
        """Test recommendation serialization via to_dict."""
        rec = Recommendation(
            id="rec_5",
            recommendation_type=RecommendationType.OPTIMIZATION,
            title="Refactor module",
            description="Refactor module for better maintainability",
            action="Split into smaller functions",
            rationale="Improve maintainability",
            expected_benefit="Easier maintenance and testing",
            confidence=0.65,
            priority=2,
        )

        result = rec.to_dict()

        assert result["id"] == "rec_5"
        assert result["recommendation_type"] == "optimization"
        assert result["title"] == "Refactor module"
        assert result["priority"] == 2


class TestLearningContext:
    """Tests for LearningContext dataclass."""

    def test_create_context(self):
        """Test creating a learning context."""
        ctx = LearningContext(
            project_id="proj_1",
            session_id="sess_1",
        )

        assert ctx.project_id == "proj_1"
        assert ctx.session_id == "sess_1"
        assert ctx.current_task is None
        assert ctx.current_agent is None

    def test_context_with_task(self):
        """Test context with task info."""
        ctx = LearningContext(
            project_id="proj_2",
            session_id="sess_2",
            current_task="Implement feature X",
            current_agent="IMPLEMENTER",
        )

        assert ctx.current_task == "Implement feature X"
        assert ctx.current_agent == "IMPLEMENTER"

    def test_context_to_dict(self):
        """Test context serialization."""
        ctx = LearningContext(
            project_id="proj_3",
            session_id="sess_3",
            patterns_applied=["pat_1", "pat_2"],
            errors_encountered=["err_1"],
        )

        result = ctx.to_dict()

        assert result["project_id"] == "proj_3"
        assert len(result["patterns_applied"]) == 2
        assert len(result["errors_encountered"]) == 1

    def test_context_with_full_data(self):
        """Test context with all fields populated."""
        ctx = LearningContext(
            project_id="proj_4",
            session_id="sess_4",
            current_task="Fix bug",
            current_agent="QA",
            files_modified=["file1.bsl", "file2.bsl"],
            keywords=["keyword1", "keyword2"],
        )

        assert ctx.project_id == "proj_4"
        assert ctx.current_task == "Fix bug"
        assert ctx.current_agent == "QA"
        assert len(ctx.files_modified) == 2
        assert len(ctx.keywords) == 2
