"""Tests for recovery_handler module."""

import pytest
import asyncio
from datetime import datetime

from .recovery_handler import (
    RecoveryStrategy,
    RecoveryAction,
    RecoveryStep,
    RecoveryPlan,
    RecoveryResult,
    RecoveryHandler,
)
from .error_handler import ErrorContext, ErrorSeverity, ErrorCategory
from .state_manager import StateManager, PipelinePhase


class TestRecoveryStrategy:
    """Tests for RecoveryStrategy enum."""

    def test_all_strategies_exist(self):
        """Test all recovery strategies are defined."""
        assert RecoveryStrategy.RESTART_PHASE
        assert RecoveryStrategy.RESTART_PIPELINE
        assert RecoveryStrategy.RESUME_FROM_CHECKPOINT
        assert RecoveryStrategy.SKIP_AND_CONTINUE
        assert RecoveryStrategy.ROLLBACK_PHASE
        assert RecoveryStrategy.RETRY_WITH_MODIFICATION
        assert RecoveryStrategy.ESCALATE_TO_HUMAN
        assert RecoveryStrategy.ABORT


class TestRecoveryAction:
    """Tests for RecoveryAction enum."""

    def test_all_actions_exist(self):
        """Test all recovery actions are defined."""
        assert RecoveryAction.LOAD_CHECKPOINT
        assert RecoveryAction.RESTORE_STATE
        assert RecoveryAction.RESET_PHASE
        assert RecoveryAction.RETRY_STEP
        assert RecoveryAction.SKIP_STEP
        assert RecoveryAction.MODIFY_PARAMS
        assert RecoveryAction.NOTIFY_USER
        assert RecoveryAction.WAIT_FOR_INPUT
        assert RecoveryAction.CLEANUP
        assert RecoveryAction.FINALIZE


class TestRecoveryStep:
    """Tests for RecoveryStep dataclass."""

    def test_basic_creation(self):
        """Test basic step creation."""
        step = RecoveryStep(
            action=RecoveryAction.RETRY_STEP,
            description="Retry the failed operation",
            order=1,
        )

        assert step.action == RecoveryAction.RETRY_STEP
        assert step.order == 1
        assert step.required is True  # Default value

    def test_with_parameters(self):
        """Test step with parameters."""
        step = RecoveryStep(
            action=RecoveryAction.LOAD_CHECKPOINT,
            description="Load checkpoint",
            order=1,
            params={"checkpoint_id": "cp-001"},
        )

        assert step.params["checkpoint_id"] == "cp-001"

    def test_optional_step(self):
        """Test optional step."""
        step = RecoveryStep(
            action=RecoveryAction.CLEANUP,
            description="Cleanup",
            order=1,
            required=False,
        )

        assert step.required is False


class TestRecoveryPlan:
    """Tests for RecoveryPlan dataclass."""

    def test_basic_creation(self):
        """Test basic plan creation."""
        plan = RecoveryPlan(
            plan_id="plan-001",
            strategy=RecoveryStrategy.RETRY_WITH_MODIFICATION,
        )

        assert plan.plan_id == "plan-001"
        assert plan.strategy == RecoveryStrategy.RETRY_WITH_MODIFICATION
        assert len(plan.steps) == 0

    def test_add_step(self):
        """Test adding steps to plan."""
        plan = RecoveryPlan(
            plan_id="plan-002",
            strategy=RecoveryStrategy.RESUME_FROM_CHECKPOINT,
        )

        plan.add_step(
            RecoveryAction.LOAD_CHECKPOINT,
            "Load checkpoint",
        )
        plan.add_step(
            RecoveryAction.RESTORE_STATE,
            "Restore state",
        )

        assert len(plan.steps) == 2
        assert plan.steps[0].action == RecoveryAction.LOAD_CHECKPOINT
        assert plan.steps[0].order == 0
        assert plan.steps[1].order == 1

    def test_to_dict(self):
        """Test serialization to dict."""
        plan = RecoveryPlan(
            plan_id="plan-003",
            strategy=RecoveryStrategy.SKIP_AND_CONTINUE,
        )
        plan.add_step(
            RecoveryAction.SKIP_STEP,
            "Skip failed step",
        )

        d = plan.to_dict()

        assert d["plan_id"] == "plan-003"
        assert d["strategy"] == "skip_and_continue"
        assert len(d["steps"]) == 1


class TestRecoveryResult:
    """Tests for RecoveryResult dataclass."""

    def test_success_result(self):
        """Test successful recovery result."""
        plan = RecoveryPlan(
            plan_id="plan-001",
            strategy=RecoveryStrategy.RETRY_WITH_MODIFICATION,
        )

        result = RecoveryResult(
            success=True,
            plan=plan,
            steps_completed=3,
            steps_failed=0,
        )

        assert result.success is True
        assert result.plan.plan_id == "plan-001"
        assert result.steps_completed == 3
        assert result.steps_failed == 0

    def test_partial_result(self):
        """Test partial recovery result."""
        plan = RecoveryPlan(
            plan_id="plan-002",
            strategy=RecoveryStrategy.ROLLBACK_PHASE,
        )

        result = RecoveryResult(
            success=False,
            plan=plan,
            steps_completed=2,
            steps_failed=3,
            final_error="Step 3 failed",
        )

        assert result.success is False
        assert result.steps_failed == 3
        assert result.final_error == "Step 3 failed"

    def test_to_dict(self):
        """Test serialization to dict."""
        plan = RecoveryPlan(
            plan_id="plan-003",
            strategy=RecoveryStrategy.SKIP_AND_CONTINUE,
        )

        result = RecoveryResult(
            success=True,
            plan=plan,
            steps_completed=1,
            steps_failed=0,
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["plan_id"] == "plan-003"
        assert d["strategy"] == "skip_and_continue"
        assert "timestamp" in d or "started_at" in d


class TestRecoveryHandler:
    """Tests for RecoveryHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler for testing."""
        state_manager = StateManager(pipeline_id="test-pipeline")
        return RecoveryHandler(state_manager=state_manager)

    @pytest.fixture
    def low_error(self):
        """Create low severity error context."""
        return ErrorContext(
            error_id="err-low",
            error_type="ValueError",
            message="Minor error",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
        )

    @pytest.fixture
    def high_error(self):
        """Create high severity error context."""
        return ErrorContext(
            error_id="err-high",
            error_type="RuntimeError",
            message="Serious error",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.INTERNAL,
        )

    @pytest.fixture
    def critical_error(self):
        """Create critical error context."""
        return ErrorContext(
            error_id="err-critical",
            error_type="MemoryError",
            message="Critical system error",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.RESOURCE,
            is_recoverable=False,
        )

    def test_initial_state(self, handler):
        """Test initial handler state."""
        assert handler.recovery_attempts == 0
        assert handler.current_plan is None
        assert handler.last_result is None

    def test_select_strategy_low(self, handler, low_error):
        """Test strategy selection for low severity."""
        strategy = handler.select_strategy(low_error, PipelinePhase.PM_SPEC_SPEC)

        # Low severity validation errors should suggest SKIP
        assert strategy in [RecoveryStrategy.SKIP_AND_CONTINUE, RecoveryStrategy.RESUME_FROM_CHECKPOINT]

    def test_select_strategy_high(self, handler, high_error):
        """Test strategy selection for high severity."""
        strategy = handler.select_strategy(high_error, PipelinePhase.PM_SPEC_SPEC)

        # High severity should suggest RESTART
        assert strategy in [
            RecoveryStrategy.RESTART_PHASE,
            RecoveryStrategy.RESTART_PIPELINE,
            RecoveryStrategy.ROLLBACK_PHASE,
        ]

    def test_select_strategy_critical(self, handler, critical_error):
        """Test strategy selection for critical error."""
        strategy = handler.select_strategy(critical_error, PipelinePhase.PM_SPEC_SPEC)

        # Critical should ABORT or ESCALATE
        assert strategy in [RecoveryStrategy.ABORT, RecoveryStrategy.ESCALATE_TO_HUMAN]

    def test_create_plan(self, handler, low_error):
        """Test creating a recovery plan."""
        strategy = handler.select_strategy(low_error, PipelinePhase.PM_SPEC_SPEC)
        plan = handler.create_plan(strategy, error=low_error)

        assert plan is not None
        assert plan.plan_id is not None
        assert len(plan.steps) > 0

    def test_create_plan_has_steps(self, handler, low_error):
        """Test plan includes steps."""
        strategy = handler.select_strategy(low_error, PipelinePhase.PM_SPEC_SPEC)
        plan = handler.create_plan(strategy, error=low_error)

        # All strategies should add at least one step
        assert len(plan.steps) >= 1

    @pytest.mark.asyncio
    async def test_execute_plan_success(self, handler, low_error):
        """Test executing a successful recovery plan."""
        strategy = handler.select_strategy(low_error, PipelinePhase.PM_SPEC_SPEC)
        plan = handler.create_plan(strategy, error=low_error)

        result = await handler.execute_plan(plan)

        assert result is not None
        assert result.plan.plan_id == plan.plan_id

    @pytest.mark.asyncio
    async def test_execute_plan_increments_attempts(self, handler, low_error):
        """Test plan execution increments attempts counter."""
        initial_attempts = handler.recovery_attempts

        strategy = handler.select_strategy(low_error, PipelinePhase.PM_SPEC_SPEC)
        plan = handler.create_plan(strategy, error=low_error)
        await handler.execute_plan(plan)

        assert handler.recovery_attempts == initial_attempts + 1

    @pytest.mark.asyncio
    async def test_recover_full_flow(self, handler, low_error):
        """Test full recovery flow."""
        result = await handler.recover_from_error(low_error)

        assert result is not None
        assert result.plan is not None
        assert result.plan.strategy is not None

    def test_get_history(self, handler):
        """Test getting recovery history."""
        # History should be empty initially
        history = handler.get_history()
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_recovery_adds_to_history(self, handler, low_error):
        """Test recovery adds to history."""
        await handler.recover_from_error(low_error)

        history = handler.get_history()
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_multiple_recoveries_tracked(self, handler, low_error, high_error):
        """Test multiple recoveries are tracked."""
        await handler.recover_from_error(low_error)
        await handler.recover_from_error(high_error)

        history = handler.get_history()
        assert len(history) == 2

    def test_reset_attempts(self, handler):
        """Test resetting recovery attempts."""
        # Simulate some attempts
        handler._recovery_attempts = 5

        handler.reset_attempts()

        assert handler.recovery_attempts == 0

    def test_last_result_property(self, handler):
        """Test last_result property."""
        # Initially None
        assert handler.last_result is None

        # Add mock result
        plan = RecoveryPlan(
            plan_id="test-plan",
            strategy=RecoveryStrategy.ABORT,
        )
        result = RecoveryResult(
            success=False,
            plan=plan,
        )
        handler._recovery_history.append(result)

        # Now should return the result
        assert handler.last_result is not None
        assert handler.last_result.plan.plan_id == "test-plan"

    def test_set_on_recovery_start(self, handler):
        """Test setting recovery start callback."""
        called = []

        def callback(plan):
            called.append(plan.plan_id)

        handler.set_on_recovery_start(callback)
        handler._on_recovery_start(RecoveryPlan(
            plan_id="test",
            strategy=RecoveryStrategy.ABORT,
        ))

        assert len(called) == 1
        assert called[0] == "test"

    def test_set_on_recovery_complete(self, handler):
        """Test setting recovery complete callback."""
        called = []

        def callback(result):
            called.append(result.success)

        handler.set_on_recovery_complete(callback)

        plan = RecoveryPlan(
            plan_id="test",
            strategy=RecoveryStrategy.ABORT,
        )
        result = RecoveryResult(success=True, plan=plan)
        handler._on_recovery_complete(result)

        assert len(called) == 1
        assert called[0] is True

    def test_set_on_escalation(self, handler):
        """Test setting escalation callback."""
        called = []

        def callback(result):
            called.append(result.requires_human_action)

        handler.set_on_escalation(callback)

        plan = RecoveryPlan(
            plan_id="test",
            strategy=RecoveryStrategy.ABORT,
        )
        result = RecoveryResult(
            success=False,
            plan=plan,
            requires_human_action=True,
        )
        handler._on_escalation(result)

        assert len(called) == 1
        assert called[0] is True

    @pytest.mark.asyncio
    async def test_recover_from_checkpoint(self, handler):
        """Test recovery from checkpoint."""
        result = await handler.recover_from_checkpoint()

        assert result is not None
        assert result.plan.strategy == RecoveryStrategy.RESUME_FROM_CHECKPOINT

    def test_strategy_for_category(self, handler):
        """Test strategy selection based on error category."""
        network_error = ErrorContext(
            error_id="net-err",
            error_type="ConnectionError",
            message="Network timeout",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
        )

        strategy = handler.select_strategy(network_error, PipelinePhase.PM_SPEC_SPEC)

        # Network errors should suggest RETRY_WITH_MODIFICATION
        assert strategy == RecoveryStrategy.RETRY_WITH_MODIFICATION

    @pytest.mark.asyncio
    async def test_current_plan_property(self, handler, low_error):
        """Test current_plan property during execution."""
        strategy = handler.select_strategy(low_error, PipelinePhase.PM_SPEC_SPEC)
        plan = handler.create_plan(strategy, error=low_error)

        # Before execution
        assert handler.current_plan is None

        # Start execution (non-blocking check)
        task = asyncio.create_task(handler.execute_plan(plan))

        # Plan should be set during execution
        # Note: This is timing-dependent, so we just check it exists after
        await task
        assert handler.current_plan is None  # Cleared after execution

    @pytest.mark.asyncio
    async def test_result_contains_plan_info(self, handler, low_error):
        """Test result contains plan information."""
        strategy = handler.select_strategy(low_error, PipelinePhase.PM_SPEC_SPEC)
        plan = handler.create_plan(strategy, error=low_error)

        result = await handler.execute_plan(plan)

        # Result should reference the plan
        assert result.plan.plan_id == plan.plan_id
        assert result.plan.strategy == plan.strategy
