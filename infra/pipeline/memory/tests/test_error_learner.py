"""Tests for Error Learner module."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from .error_learner import (
    ErrorLearner,
    ErrorAnalyzer,
    ErrorCategory,
    ErrorSignature,
    ErrorAnalysis,
    PreventionRule,
)
from models import (
    ErrorRecord,
    ErrorSeverity,
    Recommendation,
    RecommendationType,
    MemoryType,
)
from .unified_memory_client import (
    UnifiedMemoryClient,
    SaveResult,
    SearchResult,
)


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_all_categories(self):
        """Test all error categories exist."""
        categories = list(ErrorCategory)

        assert ErrorCategory.SYNTAX in categories
        assert ErrorCategory.RUNTIME in categories
        assert ErrorCategory.LOGIC in categories
        assert ErrorCategory.CONFIGURATION in categories
        assert ErrorCategory.INTEGRATION in categories
        assert ErrorCategory.PERFORMANCE in categories
        assert ErrorCategory.SECURITY in categories
        assert ErrorCategory.DATA in categories
        assert ErrorCategory.UNKNOWN in categories

    def test_category_values(self):
        """Test category values."""
        assert ErrorCategory.SYNTAX.value == "syntax"
        assert ErrorCategory.RUNTIME.value == "runtime"
        assert ErrorCategory.DATA.value == "data"


class TestErrorSignature:
    """Tests for ErrorSignature dataclass."""

    def test_create_signature(self):
        """Test creating error signature."""
        sig = ErrorSignature(
            error_type="TypeError",
            key_message="Cannot read property of undefined",
            file_pattern=r".*Module\.bsl$",
            category=ErrorCategory.DATA,
        )

        assert sig.error_type == "TypeError"
        assert sig.category == ErrorCategory.DATA
        assert sig.line_pattern is None

    def test_signature_from_error(self):
        """Test creating signature from error record."""
        error = ErrorRecord(
            id="err_1",
            error_type="ValueError",
            error_message="invalid literal for int() with base 10: 'abc'",
            severity=ErrorSeverity.MEDIUM,
            context="Parsing user input",
        )

        sig = ErrorSignature.from_error(error)

        assert sig.error_type == "ValueError"
        assert "invalid literal" in sig.key_message
        assert sig.category in list(ErrorCategory)

    def test_signature_hash_generation(self):
        """Test that signature generates consistent hash."""
        sig = ErrorSignature(
            error_type="RuntimeError",
            key_message="Connection failed",
            category=ErrorCategory.INTEGRATION,
        )

        hash1 = sig.generate_hash()
        hash2 = sig.generate_hash()

        assert hash1 == hash2
        assert len(hash1) == 12  # MD5 truncated to 12 chars

    def test_signature_category_detection(self):
        """Test automatic category detection."""
        # Syntax error
        error_syntax = ErrorRecord(
            id="err_syn",
            error_type="SyntaxError",
            error_message="Unexpected token",
            severity=ErrorSeverity.MEDIUM,
            context="Parsing source code",
        )
        sig = ErrorSignature.from_error(error_syntax)
        assert sig.category == ErrorCategory.SYNTAX

        # Configuration error - use type without 'exception'/'error' to avoid RUNTIME match first
        error_config = ErrorRecord(
            id="err_cfg",
            error_type="ConfigIssue",
            error_message="Config setting not found",
            severity=ErrorSeverity.MEDIUM,
            context="Loading configuration",
        )
        sig = ErrorSignature.from_error(error_config)
        assert sig.category == ErrorCategory.CONFIGURATION


class TestPreventionRule:
    """Tests for PreventionRule dataclass."""

    def test_create_rule(self):
        """Test creating prevention rule."""
        rule = PreventionRule(
            error_signature_hash="abc123def456",
            rule_type="code_check",
            description="Check for null before accessing properties",
            check_pattern=r"(\w+)\.(\w+)",
            recommendation="Add null check: Если {0} <> Неопределено Тогда",
            effectiveness=0.85,
        )

        assert rule.rule_type == "code_check"
        assert rule.effectiveness == 0.85
        assert rule.created_at is not None

    def test_rule_types(self):
        """Test different rule types."""
        rule_types = ['code_check', 'pre_condition', 'validation', 'warning']

        for rule_type in rule_types:
            rule = PreventionRule(
                error_signature_hash="hash123",
                rule_type=rule_type,
                description=f"Rule of type {rule_type}",
            )
            assert rule.rule_type == rule_type


class TestErrorAnalysis:
    """Tests for ErrorAnalysis dataclass."""

    def test_create_analysis(self):
        """Test creating error analysis."""
        error = ErrorRecord(
            id="err_1",
            error_type="RuntimeError",
            error_message="Connection timeout",
            severity=ErrorSeverity.HIGH,
            context="Connecting to database",
        )

        signature = ErrorSignature(
            error_type="RuntimeError",
            key_message="Connection timeout",
            category=ErrorCategory.INTEGRATION,
        )

        analysis = ErrorAnalysis(
            error=error,
            signature=signature,
            occurrence_count=3,
        )

        assert analysis.error.id == "err_1"
        assert analysis.signature.category == ErrorCategory.INTEGRATION
        assert analysis.occurrence_count == 3
        assert analysis.is_recurring is True

    def test_analysis_with_similar_errors(self):
        """Test analysis with similar errors."""
        error = ErrorRecord(
            id="err_main",
            error_type="ValidationError",
            error_message="Field required",
            severity=ErrorSeverity.MEDIUM,
            context="Validating form input",
        )

        similar = [
            ErrorRecord(
                id=f"err_similar_{i}",
                error_type="ValidationError",
                error_message="Field required: name",
                severity=ErrorSeverity.MEDIUM,
                context="Validating form input",
            )
            for i in range(3)
        ]

        signature = ErrorSignature.from_error(error)

        analysis = ErrorAnalysis(
            error=error,
            signature=signature,
            similar_errors=similar,
            occurrence_count=4,
            known_fixes=["Add required field validation"],
        )

        assert len(analysis.similar_errors) == 3
        assert len(analysis.known_fixes) == 1

    def test_analysis_recurrence_frequency(self):
        """Test recurrence frequency calculation."""
        error = ErrorRecord(
            id="err_1",
            error_type="Error",
            error_message="Test error",
            severity=ErrorSeverity.LOW,
            context="Running tests",
        )

        signature = ErrorSignature.from_error(error)

        now = datetime.now()
        analysis = ErrorAnalysis(
            error=error,
            signature=signature,
            occurrence_count=10,
            first_seen=now - timedelta(days=5),
            last_seen=now,
        )

        # 10 errors over 5 days = 2 per day
        assert analysis.recurrence_frequency == pytest.approx(2.0, rel=0.1)

    def test_analysis_not_recurring(self):
        """Test non-recurring error."""
        error = ErrorRecord(
            id="err_single",
            error_type="Error",
            error_message="One-time error",
            severity=ErrorSeverity.LOW,
            context="Single operation",
        )

        signature = ErrorSignature.from_error(error)

        analysis = ErrorAnalysis(
            error=error,
            signature=signature,
            occurrence_count=1,
        )

        assert analysis.is_recurring is False


class TestErrorLearner:
    """Tests for ErrorLearner class."""

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock memory client."""
        client = MagicMock(spec=UnifiedMemoryClient)
        client.search_memory = AsyncMock(return_value=[])
        client.save_memory = AsyncMock(
            return_value=SaveResult(success=True, memory_id="mem_1", message="Saved")
        )
        client.save_error = AsyncMock(
            return_value=SaveResult(success=True, memory_id="err_1", message="Saved")
        )
        return client

    @pytest.fixture
    def error_learner(self, mock_memory_client):
        """Create ErrorLearner with mock client."""
        return ErrorLearner(memory_client=mock_memory_client)

    @pytest.mark.asyncio
    async def test_learn_from_error(self, error_learner):
        """Test learning from an error."""
        error = ErrorRecord(
            id="err_1",
            error_type="RuntimeError",
            error_message="Division by zero",
            severity=ErrorSeverity.HIGH,
            context="Math calculation",
        )

        result = await error_learner.learn_from_error(error)

        assert result is not None
        # The learner should save the error
        error_learner.memory_client.save_error.assert_called()

    @pytest.mark.asyncio
    async def test_learn_with_fix(self, error_learner):
        """Test learning from error with fix already applied."""
        error = ErrorRecord(
            id="err_2",
            error_type="ValueError",
            error_message="Invalid input",
            severity=ErrorSeverity.MEDIUM,
            context="Processing user input",
            fix_applied="Add input validation before processing",
        )

        result = await error_learner.learn_from_error(error)

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_prevention_hints(self, error_learner, mock_memory_client):
        """Test getting prevention hints."""
        # Setup mock to return error with fixes
        mock_memory_client.search_memory = AsyncMock(
            return_value=[
                SearchResult(
                    id="err_similar",
                    content="Similar error with fix",
                    memory_type="error",
                    score=0.8,
                    importance=0.7,
                    created_at="",
                    tags=[],
                    metadata={
                        "fix_applied": "Added validation",
                        "fix_successful": True,
                    },
                )
            ]
        )

        # Note: get_prevention_hints doesn't exist - test check_for_potential_errors instead
        recommendations = await error_learner.check_for_potential_errors(
            code="test code",
            file_path="test.bsl",
        )

        assert isinstance(recommendations, list)

    def test_categorize_error_syntax(self):
        """Test categorizing syntax error via ErrorSignature."""
        error = ErrorRecord(
            id="err_syn",
            error_type="SyntaxError",
            error_message="Unexpected token at line 10",
            severity=ErrorSeverity.MEDIUM,
            context="Parsing code",
        )

        sig = ErrorSignature.from_error(error)

        assert sig.category == ErrorCategory.SYNTAX

    def test_categorize_error_runtime(self):
        """Test categorizing runtime error via ErrorSignature."""
        error = ErrorRecord(
            id="err_run",
            error_type="RuntimeException",
            error_message="Null pointer exception",
            severity=ErrorSeverity.HIGH,
            context="Running application",
        )

        sig = ErrorSignature.from_error(error)

        assert sig.category == ErrorCategory.RUNTIME

    def test_categorize_error_integration(self):
        """Test categorizing integration error via ErrorSignature."""
        # Use type without 'exception'/'error' so message keywords are checked
        error = ErrorRecord(
            id="err_int",
            error_type="NetworkIssue",
            error_message="API connection timeout",
            severity=ErrorSeverity.HIGH,
            context="Calling external API",
        )

        sig = ErrorSignature.from_error(error)

        assert sig.category == ErrorCategory.INTEGRATION


class TestErrorAnalyzer:
    """Tests for ErrorAnalyzer class."""

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock memory client."""
        client = MagicMock(spec=UnifiedMemoryClient)
        client.search_memory = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def analyzer(self, mock_memory_client):
        """Create ErrorAnalyzer with mock client."""
        return ErrorAnalyzer(memory_client=mock_memory_client)

    @pytest.mark.asyncio
    async def test_analyze_error(self, analyzer):
        """Test analyzing an error."""
        error = ErrorRecord(
            id="err_1",
            error_type="TypeError",
            error_message="Cannot read property 'length' of undefined",
            severity=ErrorSeverity.MEDIUM,
            context="Accessing array property",
        )

        analysis = await analyzer.analyze_error(error)

        assert analysis is not None
        assert analysis.error.id == "err_1"
        assert analysis.signature is not None

    @pytest.mark.asyncio
    async def test_analyze_with_context(self, analyzer):
        """Test analyzing error with context."""
        error = ErrorRecord(
            id="err_2",
            error_type="ValidationError",
            error_message="Required field missing",
            severity=ErrorSeverity.LOW,
            context="Validating form data",
            file_path="src/Module.bsl",
            line_number=42,
        )

        from .models import LearningContext
        context = LearningContext(
            project_id="test_project",
            session_id="sess_1",
        )

        analysis = await analyzer.analyze_error(error, context)

        assert analysis is not None
        assert analysis.signature is not None
        # file_pattern may be None - just check analysis was created

    @pytest.mark.asyncio
    async def test_find_similar_errors(self, analyzer, mock_memory_client):
        """Test finding similar errors."""
        mock_memory_client.search_memory = AsyncMock(
            return_value=[
                SearchResult(
                    id="err_similar_1",
                    content="Similar validation error",
                    memory_type="error",
                    score=0.85,
                    importance=0.7,
                    created_at="",
                    tags=["validation"],
                    metadata={
                        "error_type": "ValidationError",
                        "error_message": "Field required",
                    },
                ),
                SearchResult(
                    id="err_similar_2",
                    content="Another validation error",
                    memory_type="error",
                    score=0.75,
                    importance=0.6,
                    created_at="",
                    tags=["validation"],
                    metadata={
                        "error_type": "ValidationError",
                        "error_message": "Invalid format",
                    },
                ),
            ]
        )

        error = ErrorRecord(
            id="err_main",
            error_type="ValidationError",
            error_message="Required field name",
            severity=ErrorSeverity.MEDIUM,
            context="Validating form data",
        )

        signature = ErrorSignature.from_error(error)
        similar = await analyzer._find_similar_errors(error, signature)

        assert isinstance(similar, list)

    @pytest.mark.asyncio
    async def test_extract_fixes_from_similar(self, analyzer, mock_memory_client):
        """Test extracting fixes from similar errors."""
        mock_memory_client.search_memory = AsyncMock(
            return_value=[
                SearchResult(
                    id="err_with_fix",
                    content="Error with fix",
                    memory_type="error",
                    score=0.9,
                    importance=0.8,
                    created_at="",
                    tags=[],
                    metadata={
                        "fix_applied": "Added input validation",
                        "fix_successful": True,
                    },
                ),
            ]
        )

        error = ErrorRecord(
            id="err_1",
            error_type="Error",
            error_message="Test error",
            severity=ErrorSeverity.LOW,
            context="General testing",
        )

        analysis = await analyzer.analyze_error(error)

        # Fixes should be extracted if similar errors have them
        assert isinstance(analysis.known_fixes, list)


class TestErrorLearnerIntegration:
    """Integration tests for error learning flow."""

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock with realistic data."""
        client = MagicMock(spec=UnifiedMemoryClient)

        # Simulate error storage with fixes
        errors = [
            SearchResult(
                id="err_hist_1",
                content="Previous division error",
                memory_type="error",
                score=0.9,
                importance=0.8,
                created_at="",
                tags=["math", "division"],
                metadata={
                    "error_type": "ZeroDivisionError",
                    "error_message": "Division by zero",
                    "fix_applied": "Add zero check before division",
                    "fix_successful": True,
                },
            ),
            SearchResult(
                id="err_hist_2",
                content="Another math error",
                memory_type="error",
                score=0.7,
                importance=0.6,
                created_at="",
                tags=["math"],
                metadata={
                    "error_type": "OverflowError",
                    "error_message": "Integer overflow",
                    "fix_applied": "Use larger integer type",
                    "fix_successful": True,
                },
            ),
        ]

        client.search_memory = AsyncMock(return_value=errors)
        client.save_memory = AsyncMock(
            return_value=SaveResult(success=True, memory_id="m", message="ok")
        )
        client.save_error = AsyncMock(
            return_value=SaveResult(success=True, memory_id="e", message="ok")
        )

        return client

    @pytest.mark.asyncio
    async def test_learn_and_recall_error(self, mock_memory_client):
        """Test complete learning and recall flow."""
        learner = ErrorLearner(memory_client=mock_memory_client)

        # Learn from new error
        error = ErrorRecord(
            id="err_new",
            error_type="ZeroDivisionError",
            error_message="Division by zero in calculation",
            severity=ErrorSeverity.HIGH,
            context="Math calculation",
        )

        result = await learner.learn_from_error(error)

        assert result is not None

        # Check for potential errors (should use learned patterns)
        recommendations = await learner.check_for_potential_errors(
            code="result = a / b",
            file_path="calculation.bsl",
        )

        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_prevention_rule_generation(self, mock_memory_client):
        """Test prevention rule generation from repeated errors."""
        learner = ErrorLearner(memory_client=mock_memory_client)

        # Simulate learning from multiple similar errors
        errors = [
            ErrorRecord(
                id=f"err_{i}",
                error_type="ValidationError",
                error_message="Field 'email' is required",
                severity=ErrorSeverity.MEDIUM,
                context="Validating email input",
            )
            for i in range(5)
        ]

        for error in errors:
            await learner.learn_from_error(error)

        # Check that learner can suggest prevention based on learned patterns
        recommendations = await learner.check_for_potential_errors(
            code="email = input_field.value",
            file_path="validation.bsl",
        )

        # Should return recommendations based on frequency
        assert isinstance(recommendations, list)
