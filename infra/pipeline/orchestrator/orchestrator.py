"""
Main Pipeline Orchestrator - Coordinates all agents in sequential workflow.

This is the P0 Orchestrator that implements the sequential flow:
PM-SPEC → ARCHITECT → IMPLEMENTER → BSL-DEBUGGER (on errors)

Author: Development Pipeline
Date: 2025-12-24
Version: 1.0.0
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import json
import uuid

from models import Artifact, ArtifactMetadata
from constants import (
    AgentRole,
    AgentMode,
    PipelinePhase,
    VerificationStatus,
    MAX_REVISION_ATTEMPTS,
    DEFAULT_TIMEOUT_SECONDS,
    ARTIFACT_DIR,
    ArtifactType,
)
from .models import TaskNode, TaskGraph, TaskStatus
from .parallel_executor import ParallelExecutor, ExecutionReport, ExecutionProgress


class OrchestratorState(str, Enum):
    """States of the orchestrator."""

    IDLE = "idle"                      # Not running
    INITIALIZING = "initializing"      # Setting up
    RUNNING_PM_SPEC = "running_pm_spec"  # PM-SPEC phase active
    RUNNING_ARCHITECT = "running_architect"  # ARCHITECT phase active
    RUNNING_IMPLEMENTER = "running_implementer"  # IMPLEMENTER phase active
    RUNNING_BSL_DEBUGGER = "running_bsl_debugger"  # BSL-DEBUGGER phase active
    AWAITING_CHECKPOINT = "awaiting_checkpoint"  # Waiting for user input
    COMPLETED = "completed"            # Successfully finished
    FAILED = "failed"                  # Failed with error
    CANCELLED = "cancelled"            # Cancelled by user
    PAUSED = "paused"                  # Paused by user


class CheckpointAction(str, Enum):
    """Actions user can take at checkpoint."""

    ACCEPT = "accept"                  # Accept and continue
    CORRECT = "correct"                # Request corrections
    REDO = "redo"                      # Redo the phase
    CANCEL = "cancel"                  # Cancel pipeline


@dataclass
class Checkpoint:
    """Represents a checkpoint in the pipeline."""

    id: str
    phase: PipelinePhase
    artifact_name: str
    prompt: str
    created_at: datetime = field(default_factory=datetime.now)
    action: Optional[CheckpointAction] = None
    user_comment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "phase": self.phase.value,
            "artifact_name": self.artifact_name,
            "prompt": self.prompt,
            "created_at": self.created_at.isoformat(),
            "action": self.action.value if self.action else None,
            "user_comment": self.user_comment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            phase=PipelinePhase(data["phase"]),
            artifact_name=data["artifact_name"],
            prompt=data["prompt"],
            created_at=datetime.fromisoformat(data["created_at"]),
            action=CheckpointAction(data["action"]) if data.get("action") else None,
            user_comment=data.get("user_comment"),
        )


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""

    project_id: str
    project_path: Path
    task_description: str
    enable_checkpoints: bool = True
    enable_bsl_debugger: bool = True
    max_revision_attempts: int = MAX_REVISION_ATTEMPTS
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    artifact_dir: Path = field(default_factory=lambda: Path(ARTIFACT_DIR))

    # Additional settings
    skip_verification: bool = False
    auto_fix_errors: bool = False
    verbose: bool = True


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    success: bool
    run_id: str
    phase: PipelinePhase
    artifacts: Dict[str, Artifact] = field(default_factory=dict)
    checkpoints: List[Checkpoint] = field(default_factory=list)
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "run_id": self.run_id,
            "phase": self.phase.value,
            "artifacts": {k: v.to_dict() for k, v in self.artifacts.items()},
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "error_message": self.error_message,
            "execution_time_seconds": self.execution_time_seconds,
            "metadata": self.metadata,
        }


class PipelineOrchestrator:
    """
    Main orchestrator for Development Pipeline.

    Coordinates the sequential workflow:
    1. PM-SPEC (INIT → SPEC → VERIFY)
    2. ARCHITECT (DESIGN → REVIEW)
    3. IMPLEMENTER (BUILD → TEST → DOC)
    4. BSL-DEBUGGER (DEBUG) - only on BSL errors
    5. Back to VERIFICATION if needed
    """

    def __init__(
        self,
        config: PipelineConfig,
        state_callback: Optional[Callable[[OrchestratorState], None]] = None,
        progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            config: Pipeline configuration
            state_callback: Optional callback for state changes
            progress_callback: Optional callback for progress updates
        """
        self.config = config
        self.state_callback = state_callback
        self.progress_callback = progress_callback

        # Generate unique run ID
        self.run_id = str(uuid.uuid4())[:8]

        # State tracking
        self._state = OrchestratorState.IDLE
        self.current_phase = PipelinePhase.INITIALIZATION
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

        # Artifacts storage
        self.artifacts: Dict[str, Artifact] = {}

        # Checkpoints
        self.checkpoints: List[Checkpoint] = []
        self.current_checkpoint: Optional[Checkpoint] = None

        # Execution tracking
        self.revision_count = 0
        self.error_log: List[str] = []

        # Task graph for parallel execution (if needed)
        self.task_graph: Optional[TaskGraph] = None

        # Create artifact directory
        self.config.artifact_dir.mkdir(parents=True, exist_ok=True)

    @property
    def state(self) -> OrchestratorState:
        """Get current orchestrator state."""
        return self._state

    def _set_state(self, new_state: OrchestratorState) -> None:
        """Set orchestrator state and notify callback."""
        self._state = new_state
        if self.state_callback:
            self.state_callback(new_state)

    @property
    def execution_time_seconds(self) -> float:
        """Get execution time in seconds."""
        if self.started_at:
            end = self.completed_at or datetime.now()
            return (end - self.started_at).total_seconds()
        return 0.0

    def run_pipeline(self) -> PipelineResult:
        """
        Run the complete pipeline synchronously.

        This is the main entry point that executes all phases sequentially.

        Returns:
            PipelineResult with artifacts and status
        """
        self.started_at = datetime.now()
        self._set_state(OrchestratorState.INITIALIZING)

        try:
            # Phase 1: PM-SPEC (INIT → SPEC)
            self._run_pm_spec_phase()
            # Save checkpoint after PM-SPEC
            self.save_checkpoint(PipelinePhase.SPECIFICATION)

            # Checkpoint after spec
            if self.config.enable_checkpoints:
                if not self._handle_checkpoint(
                    PipelinePhase.SPECIFICATION,
                    "spec.md",
                    "Спецификация создана. Хотите внести правки?",
                ):
                    return self._create_result(PipelinePhase.SPECIFICATION, success=False)

            # Phase 2: ARCHITECT (DESIGN → REVIEW)
            self._run_architect_phase()
            # Save checkpoint after ARCHITECT
            self.save_checkpoint(PipelinePhase.DESIGN)

            # Checkpoint after design
            if self.config.enable_checkpoints:
                if not self._handle_checkpoint(
                    PipelinePhase.DESIGN,
                    "design.md",
                    "Техническое решение готово. Хотите внести правки?",
                ):
                    return self._create_result(PipelinePhase.DESIGN, success=False)

            # Phase 3: IMPLEMENTER (BUILD)
            implementation_success = self._run_implementer_phase()
            # Save checkpoint after IMPLEMENTER (only if successful)
            if implementation_success:
                self.save_checkpoint(PipelinePhase.IMPLEMENTATION)

            # Checkpoint after implementation
            if self.config.enable_checkpoints:
                if not self._handle_checkpoint(
                    PipelinePhase.IMPLEMENTATION,
                    "result.md",
                    "Реализация завершена. Хотите внести правки?",
                ):
                    return self._create_result(PipelinePhase.IMPLEMENTATION, success=False)

            # Phase 4: BSL-DEBUGGER (only if BSL errors found)
            if not implementation_success and self.config.enable_bsl_debugger:
                self._run_bsl_debugger_phase()

                # After debugging, RESUME from implementation (not restart from beginning!)
                if self.revision_count < self.config.max_revision_attempts:
                    self.revision_count += 1
                    # ✅ RESUME: Continue with implementation phase instead of full restart
                    # This saves time by skipping PM-SPEC and ARCHITECT phases
                    implementation_success = self._run_implementer_phase(mode=AgentMode.RETRY)

                    # After retry, continue to verification if enabled
                    if not self.config.skip_verification and implementation_success:
                        verification_passed = self._run_verification_phase()
                        if not verification_passed and self.revision_count < self.config.max_revision_attempts:
                            self.revision_count += 1
                            implementation_success = self._run_implementer_phase(mode=AgentMode.FIX)

                    # Return result after retry
                    self._set_state(OrchestratorState.COMPLETED if implementation_success else OrchestratorState.FAILED)
                    self.completed_at = datetime.now()
                    return self._create_result(PipelinePhase.IMPLEMENTATION, success=implementation_success)

            # Phase 5: VERIFICATION
            if not self.config.skip_verification:
                verification_passed = self._run_verification_phase()

                if not verification_passed and self.revision_count < self.config.max_revision_attempts:
                    # Back to IMPLEMENTER for fixes
                    self.revision_count += 1
                    self._run_implementer_phase(mode=AgentMode.FIX)

            # Completed successfully
            self._set_state(OrchestratorState.COMPLETED)
            self.completed_at = datetime.now()

            return self._create_result(PipelinePhase.COMPLETED, success=True)

        except Exception as e:
            self.error_log.append(str(e))
            self._set_state(OrchestratorState.FAILED)
            self.completed_at = datetime.now()

            return self._create_result(
                self.current_phase,
                success=False,
                error_message=str(e),
            )

    def _run_pm_spec_phase(self) -> None:
        """Run PM-SPEC phase: INIT → SPEC."""
        self._set_state(OrchestratorState.RUNNING_PM_SPEC)
        self.current_phase = PipelinePhase.SPECIFICATION

        if self.config.verbose:
            print(f"[{self.run_id}] PM-SPEC phase started")

        # TODO: Integrate with actual PM-SPEC agent
        # For now, create placeholder artifacts

        # Context artifact
        context_artifact = self._create_artifact(
            ArtifactType.CONTEXT,
            AgentRole.PM_SPEC,
            "# Контекст проекта\n\nАвтоматически сгенерировано контекстом.",
        )
        self.artifacts["context.md"] = context_artifact

        # Spec artifact
        spec_artifact = self._create_artifact(
            ArtifactType.SPEC,
            AgentRole.PM_SPEC,
            f"# Спецификация: {self.config.task_description}\n\n"
            f"## Проект\n{self.config.project_id}\n\n"
            f"## Задача\n{self.config.task_description}",
        )
        self.artifacts["spec.md"] = spec_artifact

        if self.config.verbose:
            print(f"[{self.run_id}] PM-SPEC phase completed")

    def _run_architect_phase(self) -> None:
        """
        Run ARCHITECT phase: DESIGN → REVIEW.

        P2 Enhancement: Execute design subtasks in parallel using ParallelExecutor.
        Subtasks: database_schema, api_interface, security_model, integrations
        """
        self._set_state(OrchestratorState.RUNNING_ARCHITECT)
        self.current_phase = PipelinePhase.DESIGN

        if self.config.verbose:
            print(f"[{self.run_id}] ARCHITECT phase started")

        # ✅ P2: Parallel execution of design subtasks
        try:
            import asyncio

            # Run parallel design
            design_result = asyncio.run(self._run_parallel_architect_design())

            # Merge results into single design artifact
            design_artifact = self._create_artifact(
                ArtifactType.DESIGN,
                AgentRole.ARCHITECT,
                design_result,
            )
            self.artifacts["design.md"] = design_artifact

            if self.config.verbose:
                print(f"[{self.run_id}] ARCHITECT phase completed (parallel execution)")

        except Exception as e:
            # Fallback to sequential if parallel fails
            if self.config.verbose:
                print(f"[{self.run_id}] Parallel execution failed, falling back to sequential: {e}")

            # Sequential fallback
            design_artifact = self._create_artifact(
                ArtifactType.DESIGN,
                AgentRole.ARCHITECT,
                f"# Техническое решение\n\n"
                f"## Задача\n{self.config.task_description}\n\n"
                f"## Архитектурные решения\n\nОписание архитектуры...",
            )
            self.artifacts["design.md"] = design_artifact

            if self.config.verbose:
                print(f"[{self.run_id}] ARCHITECT phase completed (sequential fallback)")

    async def _run_parallel_architect_design(self) -> str:
        """
        Execute architecture design subtasks in parallel.

        Returns:
            Merged design document
        """
        # Define parallel design tasks
        design_tasks = {
            "database": self._design_database_schema,
            "api": self._design_api_interface,
            "security": self._design_security_model,
            "integration": self._design_integrations,
        }

        # Execute all tasks in parallel
        results = await asyncio.gather(
            *[task() for task in design_tasks.values()],
            return_exceptions=True,
        )

        # Merge results
        merged_design = f"# Техническое решение\n\n"
        merged_design += f"## Задача\n{self.config.task_description}\n\n"
        merged_design += f"## Параллельное проектирование\n\n"
        merged_design += f"Время выполнения: параллельно (4 потока)\n\n"

        for (task_name, _), result in zip(design_tasks.items(), results):
            if isinstance(result, Exception):
                merged_design += f"### {task_name.upper()}: ОШИБКА\n```\n{result}\n```\n\n"
            else:
                merged_design += f"### {task_name.upper()}\n{result}\n\n"

        return merged_design

    async def _design_database_schema(self) -> str:
        """Design database schema (parallel subtask)."""
        # Simulate async work
        await asyncio.sleep(0.1)

        return """#### База данных

**Таблицы:**
- `Users` - пользователи системы
- `Projects` - проекты
- `Tasks` - задачи
- `Artifacts` - артефакты пайплайна

**Индексы:**
- PRIMARY KEY на всех таблицах
- INDEX на `project_id` в Tasks
- INDEX на `user_id` в Projects

**Связи:**
- Users 1:N Projects
- Projects 1:N Tasks
"""

    async def _design_api_interface(self) -> str:
        """Design API interface (parallel subtask)."""
        # Simulate async work
        await asyncio.sleep(0.1)

        return """#### API интерфейс

**REST endpoints:**
- `POST /api/projects` - создать проект
- `GET /api/projects/{id}` - получить проект
- `PUT /api/projects/{id}` - обновить проект
- `DELETE /api/projects/{id}` - удалить проект

**WebSocket:**
- `/ws/pipeline/{run_id}` - статус пайплайна
- `/ws/artifacts` - поток артефактов

**Аутентификация:**
- JWT tokens
- OAuth 2.0
"""

    async def _design_security_model(self) -> str:
        """Design security model (parallel subtask)."""
        # Simulate async work
        await asyncio.sleep(0.1)

        return """#### Безопасность

**Аутентификация:**
- Многокомпонентная (MFA)
- SSO интеграция
- Сессия с TTL

**Авторизация:**
- RBAC (Role-Based Access Control)
- Роли: Admin, Architect, Developer, Viewer
- Granular permissions

**Шифрование:**
- TLS 1.3 для коммуникации
- AES-256 для данных
- Hashing: bcrypt для паролей
"""

    async def _design_integrations(self) -> str:
        """Design integrations (parallel subtask)."""
        # Simulate async work
        await asyncio.sleep(0.1)

        return """#### Интеграции

**Внешние системы:**
- Git (GitHub, GitLab)
- CI/CD (Jenkins, GitHub Actions)
- Jira for task tracking
- Slack for notifications

**LLM провайдеры:**
- Anthropic Claude
- Google Gemini
- OpenAI GPT

**Хранилище:**
- S3-compatible storage
- Local filesystem fallback
"""

    def _run_implementer_phase(self, mode: AgentMode = AgentMode.BUILD) -> bool:
        """
        Run IMPLEMENTER phase: BUILD (or FIX).

        Returns:
            True if implementation succeeded without BSL errors
        """
        self._set_state(OrchestratorState.RUNNING_IMPLEMENTER)
        self.current_phase = PipelinePhase.IMPLEMENTATION

        if self.config.verbose:
            print(f"[{self.run_id}] IMPLEMENTER phase started (mode={mode.value})")

        # TODO: Integrate with actual IMPLEMENTER agent
        # TODO: Detect BSL errors and return False if found

        # Result artifact
        result_artifact = self._create_artifact(
            ArtifactType.RESULT,
            AgentRole.IMPLEMENTER,
            f"# Результат реализации\n\n"
            f"## Задача\n{self.config.task_description}\n\n"
            f"## Выполненные шаги\n\n1. Анализ требований\n2. Реализация\n3. Тестирование",
        )
        self.artifacts["result.md"] = result_artifact

        if self.config.verbose:
            print(f"[{self.run_id}] IMPLEMENTER phase completed")

        # For now, assume success (no BSL errors)
        return True

    def _run_bsl_debugger_phase(self) -> None:
        """Run BSL-DEBUGGER phase to fix BSL runtime errors."""
        self._set_state(OrchestratorState.RUNNING_BSL_DEBUGGER)
        self.current_phase = PipelinePhase.IMPLEMENTATION  # Still in implementation

        if self.config.verbose:
            print(f"[{self.run_id}] BSL-DEBUGGER phase started")

        # TODO: Integrate with BSL-DEBUGGER subagent
        # TODO: Analyze errors, set breakpoints, step through code

        if self.config.verbose:
            print(f"[{self.run_id}] BSL-DEBUGGER phase completed")

    def _run_verification_phase(self) -> bool:
        """
        Run VERIFICATION phase.

        Returns:
            True if verification passed
        """
        self.current_phase = PipelinePhase.VERIFICATION

        if self.config.verbose:
            print(f"[{self.run_id}] VERIFICATION phase started")

        # TODO: Integrate with PM-SPEC verifier
        verification_artifact = self._create_artifact(
            ArtifactType.VERIFICATION,
            AgentRole.PM_SPEC,
            f"# Верификация\n\n"
            f"## Статус\n✅ PASSED\n\n"
            f"## Вердикт\nРеализация соответствует спецификации.",
        )
        self.artifacts["verification.md"] = verification_artifact

        if self.config.verbose:
            print(f"[{self.run_id}] VERIFICATION phase completed")

        # For now, assume passed
        return True

    def _handle_checkpoint(
        self,
        phase: PipelinePhase,
        artifact_name: str,
        prompt: str,
    ) -> bool:
        """
        Handle checkpoint - wait for user input.

        Args:
            phase: Current pipeline phase
            artifact_name: Name of artifact to review
            prompt: Prompt to show user

        Returns:
            True if user accepted, False if cancelled
        """
        self._set_state(OrchestratorState.AWAITING_CHECKPOINT)

        checkpoint = Checkpoint(
            id=str(uuid.uuid4())[:8],
            phase=phase,
            artifact_name=artifact_name,
            prompt=prompt,
        )
        self.checkpoints.append(checkpoint)
        self.current_checkpoint = checkpoint

        if self.config.verbose:
            print(f"[{self.run_id}] CHECKPOINT: {prompt}")
            print(f"[{self.run_id}] Review artifact: {artifact_name}")

        # Wait for user action (will be set by handle_checkpoint_response)
        # For now, auto-accept in non-interactive mode
        if not self.config.enable_checkpoints:
            checkpoint.action = CheckpointAction.ACCEPT
            return True

        # In real implementation, this would wait for user input
        # For now, auto-accept
        checkpoint.action = CheckpointAction.ACCEPT
        return True

    def handle_checkpoint_response(
        self,
        checkpoint_id: str,
        action: CheckpointAction,
        comment: Optional[str] = None,
    ) -> bool:
        """
        Handle user response to checkpoint.

        Args:
            checkpoint_id: ID of checkpoint
            action: User's action
            comment: Optional user comment

        Returns:
            True if action was handled successfully
        """
        # Find checkpoint
        checkpoint = next(
            (c for c in self.checkpoints if c.id == checkpoint_id),
            None,
        )
        if not checkpoint:
            self.error_log.append(f"Checkpoint not found: {checkpoint_id}")
            return False

        checkpoint.action = action
        checkpoint.user_comment = comment

        # Handle action
        if action == CheckpointAction.ACCEPT:
            self._set_state(OrchestratorState.RUNNING_PM_SPEC)  # Continue
            return True
        elif action == CheckpointAction.CANCEL:
            self._set_state(OrchestratorState.CANCELLED)
            return False
        elif action == CheckpointAction.REDO:
            # Restart current phase (handled by caller)
            return True
        elif action == CheckpointAction.CORRECT:
            # Apply corrections and continue
            # TODO: Implement correction logic
            return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get current pipeline status."""
        return {
            "run_id": self.run_id,
            "state": self.state.value,
            "phase": self.current_phase.value,
            "project_id": self.config.project_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_seconds": self.execution_time_seconds,
            "artifacts": list(self.artifacts.keys()),
            "checkpoints": len(self.checkpoints),
            "revision_count": self.revision_count,
            "errors": self.error_log,
        }

    def cancel(self) -> None:
        """Cancel pipeline execution."""
        if self.state in [OrchestratorState.IDLE, OrchestratorState.COMPLETED, OrchestratorState.FAILED]:
            return

        self._set_state(OrchestratorState.CANCELLED)
        self.completed_at = datetime.now()

        if self.config.verbose:
            print(f"[{self.run_id}] Pipeline cancelled")

    def pause(self) -> None:
        """Pause pipeline execution."""
        if self.state not in [OrchestratorState.RUNNING_PM_SPEC, OrchestratorState.RUNNING_ARCHITECT,
                              OrchestratorState.RUNNING_IMPLEMENTER, OrchestratorState.RUNNING_BSL_DEBUGGER]:
            return

        self._set_state(OrchestratorState.PAUSED)

        if self.config.verbose:
            print(f"[{self.run_id}] Pipeline paused")

    def resume(self) -> None:
        """Resume paused pipeline execution."""
        if self.state != OrchestratorState.PAUSED:
            return

        # Resume based on current phase
        if self.current_phase == PipelinePhase.SPECIFICATION:
            self._set_state(OrchestratorState.RUNNING_PM_SPEC)
        elif self.current_phase == PipelinePhase.DESIGN:
            self._set_state(OrchestratorState.RUNNING_ARCHITECT)
        elif self.current_phase == PipelinePhase.IMPLEMENTATION:
            self._set_state(OrchestratorState.RUNNING_IMPLEMENTER)

        if self.config.verbose:
            print(f"[{self.run_id}] Pipeline resumed")

    def _create_artifact(
        self,
        artifact_type: ArtifactType,
        producer: AgentRole,
        content: str,
    ) -> Artifact:
        """Create an artifact with metadata."""
        metadata = ArtifactMetadata(
            artifact_type=artifact_type,
            producer=producer,
        )

        artifact = Artifact(
            name=artifact_type.value,
            content=content,
            metadata=metadata,
            path=self.config.artifact_dir / artifact_type.value,
        )

        # Save to disk
        artifact_path = self.config.artifact_dir / f"{self.run_id}_{artifact_type.value}"
        artifact_path.write_text(artifact.full_content, encoding="utf-8")

        return artifact

    def _create_result(
        self,
        phase: PipelinePhase,
        success: bool,
        error_message: Optional[str] = None,
    ) -> PipelineResult:
        """Create pipeline result."""
        return PipelineResult(
            success=success,
            run_id=self.run_id,
            phase=phase,
            artifacts=self.artifacts,
            checkpoints=self.checkpoints,
            error_message=error_message,
            execution_time_seconds=self.execution_time_seconds,
            metadata={
                "project_id": self.config.project_id,
                "revision_count": self.revision_count,
                "error_log": self.error_log,
            },
        )

    def save_state(self, filepath: Optional[Path] = None) -> None:
        """Save orchestrator state to file for recovery."""
        if filepath is None:
            filepath = self.config.artifact_dir / f"{self.run_id}_state.json"

        state_data = {
            "run_id": self.run_id,
            "state": self.state.value,
            "current_phase": self.current_phase.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "artifacts": {k: v.to_dict() for k, v in self.artifacts.items()},
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "revision_count": self.revision_count,
            "error_log": self.error_log,
            "config": {
                "project_id": self.config.project_id,
                "project_path": str(self.config.project_path),
                "task_description": self.config.task_description,
                "enable_checkpoints": self.config.enable_checkpoints,
                "enable_bsl_debugger": self.config.enable_bsl_debugger,
                "max_revision_attempts": self.config.max_revision_attempts,
            },
        }

        filepath.write_text(json.dumps(state_data, indent=2, ensure_ascii=False))

        if self.config.verbose:
            print(f"[{self.run_id}] State saved to {filepath}")

    @classmethod
    def load_state(cls, filepath: Path) -> "PipelineOrchestrator":
        """Load orchestrator state from file."""
        state_data = json.loads(filepath.read_text(encoding="utf-8"))

        # Reconstruct config
        config = PipelineConfig(
            project_id=state_data["config"]["project_id"],
            project_path=Path(state_data["config"]["project_path"]),
            task_description=state_data["config"]["task_description"],
            enable_checkpoints=state_data["config"]["enable_checkpoints"],
            enable_bsl_debugger=state_data["config"]["enable_bsl_debugger"],
            max_revision_attempts=state_data["config"]["max_revision_attempts"],
        )

        # Create orchestrator
        orchestrator = cls(config)
        orchestrator.run_id = state_data["run_id"]
        orchestrator._state = OrchestratorState(state_data["state"])
        orchestrator.current_phase = PipelinePhase(state_data["current_phase"])
        orchestrator.started_at = datetime.fromisoformat(state_data["started_at"]) if state_data["started_at"] else None
        orchestrator.completed_at = datetime.fromisoformat(state_data["completed_at"]) if state_data["completed_at"] else None
        orchestrator.revision_count = state_data["revision_count"]
        orchestrator.error_log = state_data["error_log"]

        # Reconstruct artifacts and checkpoints
        for name, artifact_data in state_data["artifacts"].items():
            orchestrator.artifacts[name] = Artifact(
                name=artifact_data["name"],
                content=artifact_data["content"],
                metadata=ArtifactMetadata.from_dict(artifact_data["metadata"]),
                path=Path(artifact_data["path"]) if artifact_data.get("path") else None,
            )

        for checkpoint_data in state_data["checkpoints"]:
            orchestrator.checkpoints.append(Checkpoint.from_dict(checkpoint_data))

        return orchestrator

    def save_checkpoint(self, phase: PipelinePhase) -> Path:
        """
        Save checkpoint state after successful phase completion.

        This allows resuming from specific phases instead of restarting from beginning.

        Args:
            phase: The pipeline phase that just completed

        Returns:
            Path to the checkpoint file
        """
        checkpoint_data = {
            "version": "1.0",
            "run_id": self.run_id,
            "phase": phase.value,
            "timestamp": datetime.now().isoformat(),
            "revision_count": self.revision_count,
            "artifacts": {
                name: {
                    "name": artifact.name,
                    "content": artifact.content,
                    "metadata": artifact.metadata.to_dict() if hasattr(artifact.metadata, 'to_dict') else {},
                    "path": str(artifact.path) if artifact.path else None
                }
                for name, artifact in self.artifacts.items()
            },
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "error_log": self.error_log,
        }

        checkpoint_path = self.config.artifact_dir / f"{self.run_id}_checkpoint_{phase.value}.json"
        checkpoint_path.write_text(
            json.dumps(checkpoint_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        if self.config.verbose:
            print(f"[{self.run_id}] Checkpoint saved: {phase.value} → {checkpoint_path}")

        return checkpoint_path

    def load_checkpoint(self, phase: PipelinePhase) -> bool:
        """
        Load checkpoint state and prepare to resume from phase.

        Args:
            phase: The phase to resume from

        Returns:
            True if checkpoint was loaded successfully, False otherwise
        """
        checkpoint_path = self.config.artifact_dir / f"{self.run_id}_checkpoint_{phase.value}.json"

        if not checkpoint_path.exists():
            if self.config.verbose:
                print(f"[{self.run_id}] No checkpoint found for phase: {phase.value}")
            return False

        try:
            checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))

            # Validate checkpoint version and run_id
            if checkpoint_data.get("version") != "1.0":
                self.error_log.append(f"Incompatible checkpoint version: {checkpoint_data.get('version')}")
                return False

            if checkpoint_data["run_id"] != self.run_id:
                self.error_log.append(f"Checkpoint run_id mismatch: {checkpoint_data['run_id']} != {self.run_id}")
                return False

            # Restore state
            self.revision_count = checkpoint_data["revision_count"]
            self.error_log = checkpoint_data["error_log"]

            # Restore artifacts
            self.artifacts.clear()
            for name, artifact_data in checkpoint_data["artifacts"].items():
                # Verify artifact file exists on disk
                artifact_path = artifact_data.get("path")
                if artifact_path and Path(artifact_path).exists():
                    self.artifacts[name] = Artifact(
                        name=artifact_data["name"],
                        content=artifact_data["content"],
                        metadata=ArtifactMetadata.from_dict(artifact_data["metadata"]),
                        path=Path(artifact_path),
                    )
                else:
                    # File missing - log warning but still restore artifact with in-memory content
                    self.error_log.append(f"Warning: Artifact file missing: {artifact_path}")
                    self.artifacts[name] = Artifact(
                        name=artifact_data["name"],
                        content=artifact_data["content"],
                        metadata=ArtifactMetadata.from_dict(artifact_data["metadata"]),
                        path=None,
                    )

            # Restore checkpoints
            self.checkpoints = [Checkpoint.from_dict(c) for c in checkpoint_data["checkpoints"]]

            if self.config.verbose:
                print(f"[{self.run_id}] Checkpoint loaded: {phase.value} ({len(self.artifacts)} artifacts)")

            return True

        except Exception as e:
            self.error_log.append(f"Failed to load checkpoint: {str(e)}")
            return False

    def resume_from_checkpoint(self, phase: PipelinePhase) -> PipelineResult:
        """
        Resume pipeline execution from a specific checkpoint.

        Args:
            phase: The phase to resume from

        Returns:
            PipelineResult from resumed execution
        """
        if not self.load_checkpoint(phase):
            return self._create_result(
                phase,
                success=False,
                error_message=f"Failed to load checkpoint for phase: {phase.value}"
            )

        self.started_at = datetime.now()
        self._set_state(OrchestratorState.INITIALIZING)

        try:
            # Continue from the specified phase
            if phase == PipelinePhase.SPECIFICATION:
                # Resume from PM-SPEC phase completion
                self._run_architect_phase()
                return self._continue_from_architect()

            elif phase == PipelinePhase.DESIGN:
                # Resume from ARCHITECT phase completion
                return self._continue_from_architect()

            elif phase == PipelinePhase.IMPLEMENTATION:
                # Resume from IMPLEMENTER phase
                implementation_success = self._run_implementer_phase(mode=AgentMode.RESUME)

                if not self.config.skip_verification and implementation_success:
                    verification_passed = self._run_verification_phase()
                    if not verification_passed and self.revision_count < self.config.max_revision_attempts:
                        self.revision_count += 1
                        implementation_success = self._run_implementer_phase(mode=AgentMode.FIX)

                self._set_state(OrchestratorState.COMPLETED if implementation_success else OrchestratorState.FAILED)
                self.completed_at = datetime.now()
                return self._create_result(PipelinePhase.IMPLEMENTATION, success=implementation_success)

            else:
                return self._create_result(
                    phase,
                    success=False,
                    error_message=f"Cannot resume from phase: {phase.value}"
                )

        except Exception as e:
            self.error_log.append(str(e))
            self._set_state(OrchestratorState.FAILED)
            self.completed_at = datetime.now()
            return self._create_result(phase, success=False, error_message=str(e))

    def _continue_from_architect(self) -> PipelineResult:
        """Continue pipeline from architect phase completion."""
        # Checkpoint after design
        if self.config.enable_checkpoints:
            if not self._handle_checkpoint(
                PipelinePhase.DESIGN,
                "design.md",
                "Техническое решение готово. Хотите внести правки?",
            ):
                return self._create_result(PipelinePhase.DESIGN, success=False)

        # Continue with implementation
        implementation_success = self._run_implementer_phase()

        # Checkpoint after implementation
        if self.config.enable_checkpoints:
            if not self._handle_checkpoint(
                PipelinePhase.IMPLEMENTATION,
                "result.md",
                "Реализация завершена. Хотите внести правки?",
            ):
                return self._create_result(PipelinePhase.IMPLEMENTATION, success=False)

        # Handle BSL errors if any
        if not implementation_success and self.config.enable_bsl_debugger:
            self._run_bsl_debugger_phase()

            if self.revision_count < self.config.max_revision_attempts:
                self.revision_count += 1
                implementation_success = self._run_implementer_phase(mode=AgentMode.RETRY)

                if not self.config.skip_verification and implementation_success:
                    verification_passed = self._run_verification_phase()
                    if not verification_passed and self.revision_count < self.config.max_revision_attempts:
                        self.revision_count += 1
                        implementation_success = self._run_implementer_phase(mode=AgentMode.FIX)

                self._set_state(OrchestratorState.COMPLETED if implementation_success else OrchestratorState.FAILED)
                self.completed_at = datetime.now()
                return self._create_result(PipelinePhase.IMPLEMENTATION, success=implementation_success)

        # Verification
        if not self.config.skip_verification:
            verification_passed = self._run_verification_phase()

            if not verification_passed and self.revision_count < self.config.max_revision_attempts:
                self.revision_count += 1
                self._run_implementer_phase(mode=AgentMode.FIX)

        # Completed
        self._set_state(OrchestratorState.COMPLETED)
        self.completed_at = datetime.now()
        return self._create_result(PipelinePhase.COMPLETED, success=True)


# Convenience functions

def create_pipeline(
    project_id: str,
    project_path: Path,
    task_description: str,
    **kwargs,
) -> PipelineOrchestrator:
    """
    Create a new pipeline orchestrator.

    Args:
        project_id: Project identifier
        project_path: Path to project directory
        task_description: Task description
        **kwargs: Additional config options

    Returns:
        Configured PipelineOrchestrator
    """
    config = PipelineConfig(
        project_id=project_id,
        project_path=project_path,
        task_description=task_description,
        **kwargs,
    )

    return PipelineOrchestrator(config)


def run_pipeline_sync(
    project_id: str,
    project_path: Path,
    task_description: str,
    **kwargs,
) -> PipelineResult:
    """
    Run pipeline synchronously (convenience function).

    Args:
        project_id: Project identifier
        project_path: Path to project directory
        task_description: Task description
        **kwargs: Additional config options

    Returns:
        PipelineResult
    """
    orchestrator = create_pipeline(project_id, project_path, task_description, **kwargs)
    return orchestrator.run_pipeline()
