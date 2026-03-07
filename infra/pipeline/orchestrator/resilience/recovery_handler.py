"""Recovery Handler for Pipeline Restoration.

Implements recovery strategies, recovery plans, and
checkpoint-based restoration for pipeline failures.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, Dict, List, Callable, Awaitable, Union
import asyncio
import logging

from .state_manager import (
    StateManager,
    StateCheckpoint,
    CheckpointMetadata,
    PipelinePhase,
    CheckpointType,
)
from .error_handler import ErrorContext, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Recovery strategy types."""

    RESTART_PHASE = "restart_phase"       # Restart current phase
    RESTART_PIPELINE = "restart_pipeline" # Restart entire pipeline
    RESUME_FROM_CHECKPOINT = "resume_from_checkpoint"  # Resume from last checkpoint
    SKIP_AND_CONTINUE = "skip_and_continue"  # Skip failed step, continue
    ROLLBACK_PHASE = "rollback_phase"     # Rollback to previous phase
    RETRY_WITH_MODIFICATION = "retry_with_modification"  # Retry with changed params
    ESCALATE_TO_HUMAN = "escalate_to_human"  # Require human intervention
    ABORT = "abort"                       # Abort pipeline execution


class RecoveryAction(Enum):
    """Specific recovery actions."""

    LOAD_CHECKPOINT = "load_checkpoint"
    RESTORE_STATE = "restore_state"
    RESET_PHASE = "reset_phase"
    RETRY_STEP = "retry_step"
    SKIP_STEP = "skip_step"
    MODIFY_PARAMS = "modify_params"
    NOTIFY_USER = "notify_user"
    WAIT_FOR_INPUT = "wait_for_input"
    CLEANUP = "cleanup"
    FINALIZE = "finalize"


@dataclass
class RecoveryStep:
    """Single step in a recovery plan."""

    action: RecoveryAction
    description: str
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: Optional[float] = None
    required: bool = True  # If False, can skip on failure
    order: int = 0


@dataclass
class RecoveryPlan:
    """Complete recovery plan."""

    plan_id: str
    strategy: RecoveryStrategy
    created_at: datetime = field(default_factory=datetime.now)

    # Target
    target_phase: Optional[PipelinePhase] = None
    target_checkpoint_id: Optional[str] = None

    # Steps
    steps: List[RecoveryStep] = field(default_factory=list)

    # Context
    error_context: Optional[ErrorContext] = None
    reason: str = ""

    # Constraints
    max_retries: int = 3
    timeout_seconds: float = 300.0  # 5 minutes total

    # Options
    notify_on_start: bool = True
    notify_on_complete: bool = True
    require_confirmation: bool = False

    def add_step(
        self,
        action: RecoveryAction,
        description: str,
        **kwargs
    ) -> "RecoveryPlan":
        """Add a step to the plan.

        Args:
            action: Recovery action
            description: Step description
            **kwargs: Additional step parameters

        Returns:
            Self for chaining
        """
        order = len(self.steps)
        step = RecoveryStep(
            action=action,
            description=description,
            order=order,
            **kwargs
        )
        self.steps.append(step)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "strategy": self.strategy.value,
            "created_at": self.created_at.isoformat(),
            "target_phase": self.target_phase.value if self.target_phase else None,
            "target_checkpoint_id": self.target_checkpoint_id,
            "steps": [
                {
                    "action": s.action.value,
                    "description": s.description,
                    "params": s.params,
                    "timeout_seconds": s.timeout_seconds,
                    "required": s.required,
                    "order": s.order,
                }
                for s in self.steps
            ],
            "reason": self.reason,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class RecoveryResult:
    """Result of recovery execution."""

    success: bool
    plan: RecoveryPlan
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # Execution details
    steps_completed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0

    # State
    restored_phase: Optional[PipelinePhase] = None
    restored_checkpoint_id: Optional[str] = None

    # Errors
    errors: List[str] = field(default_factory=list)
    final_error: Optional[str] = None

    # Output
    message: str = ""
    requires_human_action: bool = False
    human_action_description: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "plan_id": self.plan.plan_id,
            "strategy": self.plan.strategy.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "steps_skipped": self.steps_skipped,
            "restored_phase": self.restored_phase.value if self.restored_phase else None,
            "restored_checkpoint_id": self.restored_checkpoint_id,
            "errors": self.errors,
            "final_error": self.final_error,
            "message": self.message,
            "requires_human_action": self.requires_human_action,
            "human_action_description": self.human_action_description,
        }


@dataclass
class RecoveryConfig:
    """Configuration for RecoveryHandler."""

    # Strategy selection
    default_strategy: RecoveryStrategy = RecoveryStrategy.RESUME_FROM_CHECKPOINT
    max_auto_retries: int = 3
    escalation_threshold: int = 2  # Escalate after N failed recoveries

    # Timeouts
    step_timeout_seconds: float = 60.0
    total_timeout_seconds: float = 300.0

    # Notifications
    notify_on_recovery_start: bool = True
    notify_on_recovery_complete: bool = True
    notify_on_escalation: bool = True

    # Cleanup
    cleanup_on_success: bool = False
    preserve_error_checkpoints: bool = True


class RecoveryHandler:
    """Handler for pipeline recovery operations."""

    def __init__(
        self,
        state_manager: StateManager,
        config: Optional[RecoveryConfig] = None,
    ):
        self._state_manager = state_manager
        self._config = config or RecoveryConfig()

        # Recovery history
        self._recovery_attempts: int = 0
        self._recovery_history: List[RecoveryResult] = []
        self._current_plan: Optional[RecoveryPlan] = None

        # Action handlers
        self._action_handlers: Dict[
            RecoveryAction,
            Callable[..., Awaitable[bool]]
        ] = {
            RecoveryAction.LOAD_CHECKPOINT: self._action_load_checkpoint,
            RecoveryAction.RESTORE_STATE: self._action_restore_state,
            RecoveryAction.RESET_PHASE: self._action_reset_phase,
            RecoveryAction.RETRY_STEP: self._action_retry_step,
            RecoveryAction.SKIP_STEP: self._action_skip_step,
            RecoveryAction.MODIFY_PARAMS: self._action_modify_params,
            RecoveryAction.NOTIFY_USER: self._action_notify_user,
            RecoveryAction.WAIT_FOR_INPUT: self._action_wait_for_input,
            RecoveryAction.CLEANUP: self._action_cleanup,
            RecoveryAction.FINALIZE: self._action_finalize,
        }

        # Callbacks
        self._on_recovery_start: Optional[Callable[[RecoveryPlan], None]] = None
        self._on_recovery_complete: Optional[Callable[[RecoveryResult], None]] = None
        self._on_escalation: Optional[Callable[[RecoveryResult], None]] = None

    @property
    def recovery_attempts(self) -> int:
        """Get number of recovery attempts."""
        return self._recovery_attempts

    @property
    def current_plan(self) -> Optional[RecoveryPlan]:
        """Get current recovery plan."""
        return self._current_plan

    @property
    def last_result(self) -> Optional[RecoveryResult]:
        """Get last recovery result."""
        return self._recovery_history[-1] if self._recovery_history else None

    # Strategy selection

    def select_strategy(
        self,
        error: ErrorContext,
        phase: PipelinePhase,
    ) -> RecoveryStrategy:
        """Select appropriate recovery strategy based on error.

        Args:
            error: Error context
            phase: Current phase

        Returns:
            Recommended recovery strategy
        """
        # Critical errors: abort or escalate
        if error.severity == ErrorSeverity.CRITICAL:
            if self._recovery_attempts >= self._config.escalation_threshold:
                return RecoveryStrategy.ESCALATE_TO_HUMAN
            return RecoveryStrategy.ABORT

        # High severity: restart phase or pipeline
        if error.severity == ErrorSeverity.HIGH:
            if phase in [PipelinePhase.INIT, PipelinePhase.PM_SPEC_INIT]:
                return RecoveryStrategy.RESTART_PIPELINE
            return RecoveryStrategy.RESTART_PHASE

        # Network/timeout: retry with modification
        if error.category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT]:
            return RecoveryStrategy.RETRY_WITH_MODIFICATION

        # Validation errors: skip and continue
        if error.category == ErrorCategory.VALIDATION:
            return RecoveryStrategy.SKIP_AND_CONTINUE

        # Default: resume from checkpoint
        return self._config.default_strategy

    # Plan creation

    def create_plan(
        self,
        strategy: RecoveryStrategy,
        error: Optional[ErrorContext] = None,
        target_phase: Optional[PipelinePhase] = None,
        target_checkpoint_id: Optional[str] = None,
    ) -> RecoveryPlan:
        """Create a recovery plan.

        Args:
            strategy: Recovery strategy
            error: Optional error context
            target_phase: Optional target phase
            target_checkpoint_id: Optional checkpoint to restore

        Returns:
            Recovery plan
        """
        import uuid

        plan = RecoveryPlan(
            plan_id=str(uuid.uuid4())[:8],
            strategy=strategy,
            target_phase=target_phase,
            target_checkpoint_id=target_checkpoint_id,
            error_context=error,
            reason=error.message if error else "Manual recovery",
        )

        # Build steps based on strategy
        if strategy == RecoveryStrategy.RESUME_FROM_CHECKPOINT:
            plan.add_step(
                RecoveryAction.LOAD_CHECKPOINT,
                "Загрузка последнего checkpoint",
                params={"checkpoint_id": target_checkpoint_id},
            )
            plan.add_step(
                RecoveryAction.RESTORE_STATE,
                "Восстановление состояния из checkpoint",
            )
            plan.add_step(
                RecoveryAction.FINALIZE,
                "Финализация восстановления",
            )

        elif strategy == RecoveryStrategy.RESTART_PHASE:
            plan.add_step(
                RecoveryAction.RESET_PHASE,
                "Сброс текущей фазы",
                params={"phase": target_phase or self._state_manager.current_phase},
            )
            plan.add_step(
                RecoveryAction.CLEANUP,
                "Очистка временных данных фазы",
            )
            plan.add_step(
                RecoveryAction.FINALIZE,
                "Готовность к повторному выполнению фазы",
            )

        elif strategy == RecoveryStrategy.RESTART_PIPELINE:
            plan.add_step(
                RecoveryAction.CLEANUP,
                "Очистка всех данных pipeline",
            )
            plan.add_step(
                RecoveryAction.RESET_PHASE,
                "Сброс к начальной фазе",
                params={"phase": PipelinePhase.INIT},
            )
            plan.add_step(
                RecoveryAction.FINALIZE,
                "Готовность к перезапуску pipeline",
            )

        elif strategy == RecoveryStrategy.SKIP_AND_CONTINUE:
            plan.add_step(
                RecoveryAction.SKIP_STEP,
                "Пропуск неудавшегося шага",
            )
            plan.add_step(
                RecoveryAction.FINALIZE,
                "Продолжение выполнения",
            )

        elif strategy == RecoveryStrategy.ROLLBACK_PHASE:
            # Find previous phase
            prev_phase = self._get_previous_phase(
                target_phase or self._state_manager.current_phase
            )
            plan.add_step(
                RecoveryAction.RESET_PHASE,
                f"Откат к фазе {prev_phase.value}",
                params={"phase": prev_phase},
            )
            plan.add_step(
                RecoveryAction.FINALIZE,
                "Готовность к повторному выполнению",
            )

        elif strategy == RecoveryStrategy.RETRY_WITH_MODIFICATION:
            plan.add_step(
                RecoveryAction.MODIFY_PARAMS,
                "Модификация параметров для повторной попытки",
                params={"increase_timeout": True, "reduce_batch_size": True},
            )
            plan.add_step(
                RecoveryAction.RETRY_STEP,
                "Повторная попытка с изменёнными параметрами",
            )
            plan.add_step(
                RecoveryAction.FINALIZE,
                "Проверка результата",
            )

        elif strategy == RecoveryStrategy.ESCALATE_TO_HUMAN:
            plan.add_step(
                RecoveryAction.NOTIFY_USER,
                "Уведомление пользователя о проблеме",
            )
            plan.add_step(
                RecoveryAction.WAIT_FOR_INPUT,
                "Ожидание решения пользователя",
                timeout_seconds=None,  # No timeout for human input
            )
            plan.add_step(
                RecoveryAction.FINALIZE,
                "Применение решения пользователя",
            )

        elif strategy == RecoveryStrategy.ABORT:
            plan.add_step(
                RecoveryAction.CLEANUP,
                "Очистка и финализация",
            )
            plan.add_step(
                RecoveryAction.NOTIFY_USER,
                "Уведомление об остановке pipeline",
            )

        return plan

    def _get_previous_phase(self, phase: PipelinePhase) -> PipelinePhase:
        """Get previous phase in sequence.

        Args:
            phase: Current phase

        Returns:
            Previous phase
        """
        phase_order = [
            PipelinePhase.INIT,
            PipelinePhase.PM_SPEC_INIT,
            PipelinePhase.PM_SPEC_SPEC,
            PipelinePhase.ARCHITECT_DESIGN,
            PipelinePhase.IMPLEMENTER_BUILD,
            PipelinePhase.ARCHITECT_REVIEW,
            PipelinePhase.PM_SPEC_VERIFY,
        ]

        try:
            idx = phase_order.index(phase)
            if idx > 0:
                return phase_order[idx - 1]
        except ValueError:
            pass

        return PipelinePhase.INIT

    # Plan execution

    async def execute_plan(
        self,
        plan: RecoveryPlan,
    ) -> RecoveryResult:
        """Execute a recovery plan.

        Args:
            plan: Recovery plan to execute

        Returns:
            Recovery result
        """
        self._current_plan = plan
        self._recovery_attempts += 1

        result = RecoveryResult(
            success=False,
            plan=plan,
        )

        # Notify start
        if self._config.notify_on_recovery_start and self._on_recovery_start:
            try:
                self._on_recovery_start(plan)
            except Exception as e:
                logger.error(f"Error in recovery start callback: {e}")

        logger.info(
            f"Starting recovery plan: {plan.plan_id} "
            f"(strategy={plan.strategy.value})"
        )

        try:
            # Execute steps with timeout
            await asyncio.wait_for(
                self._execute_steps(plan, result),
                timeout=plan.timeout_seconds,
            )

        except asyncio.TimeoutError:
            result.final_error = f"Recovery timed out after {plan.timeout_seconds}s"
            result.errors.append(result.final_error)
            logger.error(result.final_error)

        except Exception as e:
            result.final_error = str(e)
            result.errors.append(str(e))
            logger.error(f"Recovery failed: {e}")

        result.completed_at = datetime.now()
        self._recovery_history.append(result)
        self._current_plan = None

        # Check for escalation
        if not result.success:
            if self._recovery_attempts >= self._config.escalation_threshold:
                result.requires_human_action = True
                result.human_action_description = (
                    f"Автоматическое восстановление не удалось после "
                    f"{self._recovery_attempts} попыток. Требуется ручное вмешательство."
                )
                if self._config.notify_on_escalation and self._on_escalation:
                    try:
                        self._on_escalation(result)
                    except Exception as e:
                        logger.error(f"Error in escalation callback: {e}")

        # Notify complete
        if self._config.notify_on_recovery_complete and self._on_recovery_complete:
            try:
                self._on_recovery_complete(result)
            except Exception as e:
                logger.error(f"Error in recovery complete callback: {e}")

        logger.info(
            f"Recovery plan {plan.plan_id} completed: "
            f"success={result.success}, "
            f"steps={result.steps_completed}/{len(plan.steps)}"
        )

        return result

    async def _execute_steps(
        self,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> None:
        """Execute plan steps.

        Args:
            plan: Recovery plan
            result: Result to update
        """
        for step in plan.steps:
            try:
                # Get handler
                handler = self._action_handlers.get(step.action)
                if not handler:
                    raise ValueError(f"No handler for action: {step.action}")

                # Execute with timeout
                timeout = step.timeout_seconds or self._config.step_timeout_seconds
                success = await asyncio.wait_for(
                    handler(step, plan, result),
                    timeout=timeout,
                )

                if success:
                    result.steps_completed += 1
                    logger.debug(f"Step completed: {step.description}")
                else:
                    if step.required:
                        result.steps_failed += 1
                        result.errors.append(f"Step failed: {step.description}")
                        return  # Stop on required step failure
                    else:
                        result.steps_skipped += 1
                        logger.warning(f"Optional step skipped: {step.description}")

            except asyncio.TimeoutError:
                result.steps_failed += 1
                result.errors.append(f"Step timed out: {step.description}")
                if step.required:
                    return

            except Exception as e:
                result.steps_failed += 1
                result.errors.append(f"Step error: {step.description} - {e}")
                if step.required:
                    return

        # All steps completed
        result.success = True
        result.message = "Recovery completed successfully"

    # Action handlers

    async def _action_load_checkpoint(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Load checkpoint action."""
        checkpoint_id = step.params.get("checkpoint_id") or plan.target_checkpoint_id

        if checkpoint_id:
            checkpoint = await self._state_manager.load_checkpoint(checkpoint_id)
        else:
            checkpoint = await self._state_manager.load_latest_checkpoint()

        if checkpoint is None:
            logger.warning("No checkpoint found to load")
            return False

        result.restored_checkpoint_id = checkpoint.metadata.checkpoint_id
        # Store for next step
        self._loaded_checkpoint = checkpoint
        return True

    async def _action_restore_state(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Restore state from loaded checkpoint."""
        if not hasattr(self, "_loaded_checkpoint") or self._loaded_checkpoint is None:
            logger.error("No checkpoint loaded to restore from")
            return False

        await self._state_manager.restore_from_checkpoint(self._loaded_checkpoint)
        result.restored_phase = self._loaded_checkpoint.current_phase
        self._loaded_checkpoint = None
        return True

    async def _action_reset_phase(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Reset to specified phase."""
        phase = step.params.get("phase", PipelinePhase.INIT)
        if isinstance(phase, str):
            phase = PipelinePhase(phase)

        self._state_manager.set_phase(phase)
        result.restored_phase = phase
        return True

    async def _action_retry_step(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Retry failed step."""
        # This is a placeholder - actual retry logic depends on pipeline implementation
        logger.info("Retry step action triggered")
        return True

    async def _action_skip_step(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Skip failed step and continue."""
        failed_steps = self._state_manager._failed_steps.copy()
        for failed_step in failed_steps:
            self._state_manager._failed_steps.remove(failed_step)
            logger.info(f"Skipped failed step: {failed_step}")
        return True

    async def _action_modify_params(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Modify parameters for retry."""
        params = step.params

        # Increase timeout
        if params.get("increase_timeout"):
            current_timeout = self._state_manager.get_variable("timeout", 30.0)
            self._state_manager.set_variable("timeout", current_timeout * 2)
            logger.info(f"Timeout increased to {current_timeout * 2}s")

        # Reduce batch size
        if params.get("reduce_batch_size"):
            current_batch = self._state_manager.get_variable("batch_size", 10)
            self._state_manager.set_variable("batch_size", max(1, current_batch // 2))
            logger.info(f"Batch size reduced to {max(1, current_batch // 2)}")

        return True

    async def _action_notify_user(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Notify user about recovery status."""
        message = step.params.get(
            "message",
            f"Pipeline recovery: {plan.strategy.value}"
        )
        logger.info(f"User notification: {message}")
        # In real implementation, this would send notification
        return True

    async def _action_wait_for_input(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Wait for user input."""
        result.requires_human_action = True
        result.human_action_description = (
            "Требуется подтверждение пользователя для продолжения восстановления"
        )
        # In real implementation, this would wait for input
        logger.info("Waiting for user input...")
        return True

    async def _action_cleanup(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Cleanup temporary data."""
        # Reset failed steps
        self._state_manager._failed_steps.clear()
        logger.info("Cleanup completed")
        return True

    async def _action_finalize(
        self,
        step: RecoveryStep,
        plan: RecoveryPlan,
        result: RecoveryResult,
    ) -> bool:
        """Finalize recovery."""
        # Create recovery checkpoint
        await self._state_manager.create_checkpoint(
            checkpoint_type=CheckpointType.RECOVERY,
            tags=["recovery", plan.strategy.value],
            custom_data={
                "plan_id": plan.plan_id,
                "recovery_attempt": self._recovery_attempts,
            },
        )
        return True

    # Convenience methods

    async def recover_from_error(
        self,
        error: ErrorContext,
    ) -> RecoveryResult:
        """Attempt recovery from an error.

        Args:
            error: Error context

        Returns:
            Recovery result
        """
        strategy = self.select_strategy(error, self._state_manager.current_phase)
        plan = self.create_plan(strategy, error=error)
        return await self.execute_plan(plan)

    async def recover_from_checkpoint(
        self,
        checkpoint_id: Optional[str] = None,
    ) -> RecoveryResult:
        """Recover from a specific checkpoint.

        Args:
            checkpoint_id: Optional checkpoint ID (latest if None)

        Returns:
            Recovery result
        """
        plan = self.create_plan(
            RecoveryStrategy.RESUME_FROM_CHECKPOINT,
            target_checkpoint_id=checkpoint_id,
        )
        return await self.execute_plan(plan)

    def reset_attempts(self) -> None:
        """Reset recovery attempt counter."""
        self._recovery_attempts = 0

    def get_history(self) -> List[RecoveryResult]:
        """Get recovery history.

        Returns:
            List of recovery results
        """
        return self._recovery_history.copy()

    # Callbacks

    def set_on_recovery_start(
        self,
        callback: Callable[[RecoveryPlan], None],
    ) -> None:
        """Set callback for recovery start."""
        self._on_recovery_start = callback

    def set_on_recovery_complete(
        self,
        callback: Callable[[RecoveryResult], None],
    ) -> None:
        """Set callback for recovery complete."""
        self._on_recovery_complete = callback

    def set_on_escalation(
        self,
        callback: Callable[[RecoveryResult], None],
    ) -> None:
        """Set callback for escalation."""
        self._on_escalation = callback
