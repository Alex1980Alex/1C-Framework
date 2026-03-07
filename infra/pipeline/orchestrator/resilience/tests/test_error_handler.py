"""Tests for error_handler module."""

import pytest
import asyncio
from datetime import datetime

from .error_handler import (
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    PipelineError,
    RecoverableError,
    FatalError,
    DegradationLevel,
    DegradationState,
    GracefulDegradationHandler,
    ErrorAggregator,
    with_graceful_degradation,
)


class TestErrorSeverity:
    """Tests for ErrorSeverity enum."""

    def test_numeric_values(self):
        """Test numeric value ordering."""
        assert ErrorSeverity.LOW.numeric_value == 1
        assert ErrorSeverity.MEDIUM.numeric_value == 2
        assert ErrorSeverity.HIGH.numeric_value == 3
        assert ErrorSeverity.CRITICAL.numeric_value == 4

    def test_comparison(self):
        """Test severity comparison."""
        assert ErrorSeverity.LOW < ErrorSeverity.MEDIUM
        assert ErrorSeverity.MEDIUM < ErrorSeverity.HIGH
        assert ErrorSeverity.HIGH < ErrorSeverity.CRITICAL
        assert ErrorSeverity.LOW <= ErrorSeverity.LOW


class TestErrorContext:
    """Tests for ErrorContext dataclass."""

    def test_basic_creation(self):
        """Test basic error context creation."""
        ctx = ErrorContext(
            error_id="test-001",
            error_type="ValueError",
            message="Test error message",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
        )

        assert ctx.error_id == "test-001"
        assert ctx.error_type == "ValueError"
        assert ctx.message == "Test error message"
        assert ctx.severity == ErrorSeverity.MEDIUM
        assert ctx.category == ErrorCategory.VALIDATION
        assert ctx.is_recoverable is True

    def test_from_exception(self):
        """Test creating context from exception."""
        try:
            raise ValueError("Test value error")
        except ValueError as e:
            ctx = ErrorContext.from_exception(e, error_id="exc-001")

        assert ctx.error_id == "exc-001"
        assert ctx.error_type == "ValueError"
        assert "Test value error" in ctx.message
        assert ctx.severity == ErrorSeverity.MEDIUM
        assert ctx.category == ErrorCategory.VALIDATION
        assert ctx.original_exception is not None

    def test_auto_classify_critical(self):
        """Test auto-classification of critical errors."""
        try:
            raise MemoryError("Out of memory")
        except MemoryError as e:
            ctx = ErrorContext.from_exception(e, error_id="mem-001")

        assert ctx.severity == ErrorSeverity.CRITICAL
        assert ctx.is_recoverable is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        ctx = ErrorContext(
            error_id="dict-001",
            error_type="TestError",
            message="Test message",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.INTERNAL,
        )

        d = ctx.to_dict()

        assert d["error_id"] == "dict-001"
        assert d["severity"] == "low"
        assert d["category"] == "internal"
        assert "timestamp" in d


class TestPipelineErrors:
    """Tests for pipeline error classes."""

    def test_pipeline_error(self):
        """Test base PipelineError."""
        error = PipelineError("Test error")
        assert str(error) == "Test error"
        assert error.is_recoverable is True

    def test_recoverable_error(self):
        """Test RecoverableError."""
        error = RecoverableError("Recoverable", retry_after=5.0)
        assert error.is_recoverable is True
        assert error.retry_after == 5.0

    def test_fatal_error(self):
        """Test FatalError."""
        error = FatalError("Fatal error")
        assert error.is_recoverable is False


class TestGracefulDegradationHandler:
    """Tests for GracefulDegradationHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler with low thresholds for testing."""
        return GracefulDegradationHandler(
            error_threshold_reduced=2,
            error_threshold_minimal=4,
            error_threshold_offline=6,
            recovery_interval_seconds=1.0,
        )

    def test_initial_state(self, handler):
        """Test initial state is FULL."""
        assert handler.current_level == DegradationLevel.FULL
        assert handler.state.error_count == 0

    @pytest.mark.asyncio
    async def test_degradation_on_errors(self, handler):
        """Test degradation as errors accumulate."""
        # First error - still FULL
        ctx1 = ErrorContext(
            error_id="err-1",
            error_type="Error",
            message="Error 1",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.INTERNAL,
        )
        level = await handler.handle_error(ctx1)
        assert level == DegradationLevel.FULL

        # Second error - transition to REDUCED
        ctx2 = ErrorContext(
            error_id="err-2",
            error_type="Error",
            message="Error 2",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.INTERNAL,
        )
        level = await handler.handle_error(ctx2)
        assert level == DegradationLevel.REDUCED

    @pytest.mark.asyncio
    async def test_critical_error_fails_immediately(self, handler):
        """Test critical error causes immediate FAILED state."""
        ctx = ErrorContext(
            error_id="critical-1",
            error_type="MemoryError",
            message="Critical error",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.RESOURCE,
        )
        level = await handler.handle_error(ctx)
        assert level == DegradationLevel.FAILED

    @pytest.mark.asyncio
    async def test_recovery(self, handler):
        """Test recovery to higher level."""
        # First degrade
        for i in range(3):
            ctx = ErrorContext(
                error_id=f"err-{i}",
                error_type="Error",
                message=f"Error {i}",
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.INTERNAL,
            )
            await handler.handle_error(ctx)

        assert handler.current_level != DegradationLevel.FULL

        # Wait and attempt recovery
        await asyncio.sleep(1.1)
        recovered = await handler.attempt_recovery()
        # Should have recovered one level
        assert recovered or handler.current_level != DegradationLevel.FAILED

    def test_reset(self, handler):
        """Test reset to FULL."""
        handler._state.level = DegradationLevel.MINIMAL
        handler._state.error_count = 5

        handler.reset()

        assert handler.current_level == DegradationLevel.FULL
        assert handler.state.error_count == 0

    def test_feature_management(self, handler):
        """Test feature enable/disable."""
        assert handler.is_feature_available("test_feature")

        handler.disable_feature("test_feature")
        assert not handler.is_feature_available("test_feature")

        handler.enable_feature("test_feature")
        assert handler.is_feature_available("test_feature")


class TestErrorAggregator:
    """Tests for ErrorAggregator."""

    def test_add_and_count(self):
        """Test adding errors and counting."""
        aggregator = ErrorAggregator(max_errors=10)

        for i in range(5):
            ctx = ErrorContext(
                error_id=f"agg-{i}",
                error_type="Error",
                message=f"Error {i}",
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.INTERNAL,
            )
            aggregator.add(ctx)

        assert aggregator.count == 5

    def test_max_errors_limit(self):
        """Test max errors limit."""
        aggregator = ErrorAggregator(max_errors=3)

        for i in range(5):
            ctx = ErrorContext(
                error_id=f"agg-{i}",
                error_type="Error",
                message=f"Error {i}",
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.INTERNAL,
            )
            aggregator.add(ctx)

        assert aggregator.count == 3

    def test_by_severity(self):
        """Test counting by severity."""
        aggregator = ErrorAggregator()

        for severity in [ErrorSeverity.LOW, ErrorSeverity.LOW, ErrorSeverity.HIGH]:
            ctx = ErrorContext(
                error_id="test",
                error_type="Error",
                message="Error",
                severity=severity,
                category=ErrorCategory.INTERNAL,
            )
            aggregator.add(ctx)

        counts = aggregator.by_severity()
        assert counts.get(ErrorSeverity.LOW) == 2
        assert counts.get(ErrorSeverity.HIGH) == 1

    def test_recent(self):
        """Test getting recent errors."""
        aggregator = ErrorAggregator()

        for i in range(10):
            ctx = ErrorContext(
                error_id=f"recent-{i}",
                error_type="Error",
                message=f"Error {i}",
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.INTERNAL,
            )
            aggregator.add(ctx)

        recent = aggregator.recent(3)
        assert len(recent) == 3
        assert recent[0].error_id == "recent-7"
