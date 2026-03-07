"""State Manager for Pipeline Persistence.

Implements state checkpointing, persistence, and recovery
for pipeline execution state.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List, Callable, TypeVar
import asyncio
import json
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CheckpointType(Enum):
    """Types of checkpoints."""

    MANUAL = "manual"           # Manually created
    AUTOMATIC = "automatic"     # Auto-created on progress
    PHASE_START = "phase_start" # At phase start
    PHASE_END = "phase_end"     # At phase end
    ERROR = "error"             # Created on error
    RECOVERY = "recovery"       # Created during recovery


class PipelinePhase(Enum):
    """Pipeline execution phases."""

    INIT = "init"
    PM_SPEC_INIT = "pm_spec_init"
    PM_SPEC_SPEC = "pm_spec_spec"
    ARCHITECT_DESIGN = "architect_design"
    IMPLEMENTER_BUILD = "implementer_build"
    ARCHITECT_REVIEW = "architect_review"
    PM_SPEC_VERIFY = "pm_spec_verify"
    IMPLEMENTER_FIX = "implementer_fix"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CheckpointMetadata:
    """Metadata about a checkpoint."""

    checkpoint_id: str
    checkpoint_type: CheckpointType
    created_at: datetime
    phase: PipelinePhase

    # Context
    pipeline_id: str
    task_id: Optional[str] = None
    agent_type: Optional[str] = None

    # Progress info
    step_number: int = 0
    total_steps: int = 0
    progress_percent: float = 0.0

    # Error info (if checkpoint_type == ERROR)
    error_message: Optional[str] = None
    error_type: Optional[str] = None

    # Storage info
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    checksum: Optional[str] = None

    # Additional metadata
    tags: List[str] = field(default_factory=list)
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_type": self.checkpoint_type.value,
            "created_at": self.created_at.isoformat(),
            "phase": self.phase.value,
            "pipeline_id": self.pipeline_id,
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "step_number": self.step_number,
            "total_steps": self.total_steps,
            "progress_percent": self.progress_percent,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "checksum": self.checksum,
            "tags": self.tags,
            "custom_data": self.custom_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointMetadata":
        """Create from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            checkpoint_type=CheckpointType(data["checkpoint_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            phase=PipelinePhase(data["phase"]),
            pipeline_id=data["pipeline_id"],
            task_id=data.get("task_id"),
            agent_type=data.get("agent_type"),
            step_number=data.get("step_number", 0),
            total_steps=data.get("total_steps", 0),
            progress_percent=data.get("progress_percent", 0.0),
            error_message=data.get("error_message"),
            error_type=data.get("error_type"),
            file_path=data.get("file_path"),
            file_size_bytes=data.get("file_size_bytes", 0),
            checksum=data.get("checksum"),
            tags=data.get("tags", []),
            custom_data=data.get("custom_data", {}),
        )


@dataclass
class StateCheckpoint:
    """Complete state checkpoint."""

    metadata: CheckpointMetadata

    # Pipeline state
    current_phase: PipelinePhase
    phase_data: Dict[str, Any] = field(default_factory=dict)

    # Artifacts
    artifacts: Dict[str, str] = field(default_factory=dict)  # name -> path
    artifact_contents: Dict[str, str] = field(default_factory=dict)  # name -> content

    # Execution state
    completed_steps: List[str] = field(default_factory=list)
    pending_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)

    # Variables/context
    variables: Dict[str, Any] = field(default_factory=dict)

    # History
    phase_history: List[Dict[str, Any]] = field(default_factory=list)
    error_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "current_phase": self.current_phase.value,
            "phase_data": self.phase_data,
            "artifacts": self.artifacts,
            "artifact_contents": self.artifact_contents,
            "completed_steps": self.completed_steps,
            "pending_steps": self.pending_steps,
            "failed_steps": self.failed_steps,
            "variables": self.variables,
            "phase_history": self.phase_history,
            "error_history": self.error_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateCheckpoint":
        """Create from dictionary."""
        return cls(
            metadata=CheckpointMetadata.from_dict(data["metadata"]),
            current_phase=PipelinePhase(data["current_phase"]),
            phase_data=data.get("phase_data", {}),
            artifacts=data.get("artifacts", {}),
            artifact_contents=data.get("artifact_contents", {}),
            completed_steps=data.get("completed_steps", []),
            pending_steps=data.get("pending_steps", []),
            failed_steps=data.get("failed_steps", []),
            variables=data.get("variables", {}),
            phase_history=data.get("phase_history", []),
            error_history=data.get("error_history", []),
        )

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "StateCheckpoint":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class StateManagerConfig:
    """Configuration for StateManager."""

    # Storage
    checkpoint_dir: str = "checkpoints"
    max_checkpoints: int = 10

    # Auto-checkpoint
    auto_checkpoint_enabled: bool = True
    auto_checkpoint_interval_seconds: float = 60.0
    auto_checkpoint_on_phase_change: bool = True
    auto_checkpoint_on_error: bool = True

    # Cleanup
    auto_cleanup_enabled: bool = True
    cleanup_after_success: bool = False

    # Compression (future)
    compress_checkpoints: bool = False


class StateManager:
    """Manager for pipeline state persistence and recovery."""

    def __init__(
        self,
        pipeline_id: str,
        config: Optional[StateManagerConfig] = None,
    ):
        self._pipeline_id = pipeline_id
        self._config = config or StateManagerConfig()

        # Current state
        self._current_phase = PipelinePhase.INIT
        self._phase_data: Dict[str, Any] = {}
        self._artifacts: Dict[str, str] = {}
        self._artifact_contents: Dict[str, str] = {}
        self._completed_steps: List[str] = []
        self._pending_steps: List[str] = []
        self._failed_steps: List[str] = []
        self._variables: Dict[str, Any] = {}

        # History
        self._phase_history: List[Dict[str, Any]] = []
        self._error_history: List[Dict[str, Any]] = []
        self._checkpoints: List[CheckpointMetadata] = []

        # Auto-checkpoint
        self._auto_checkpoint_task: Optional[asyncio.Task] = None
        self._last_checkpoint_time: Optional[datetime] = None

        # Listeners
        self._phase_listeners: List[Callable[[PipelinePhase, PipelinePhase], None]] = []
        self._checkpoint_listeners: List[Callable[[StateCheckpoint], None]] = []

        # Ensure checkpoint directory exists
        self._checkpoint_path = Path(self._config.checkpoint_dir) / pipeline_id
        self._checkpoint_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"StateManager initialized for pipeline: {pipeline_id}")

    @property
    def pipeline_id(self) -> str:
        """Get pipeline ID."""
        return self._pipeline_id

    @property
    def current_phase(self) -> PipelinePhase:
        """Get current phase."""
        return self._current_phase

    @property
    def checkpoint_count(self) -> int:
        """Get number of checkpoints."""
        return len(self._checkpoints)

    @property
    def last_checkpoint(self) -> Optional[CheckpointMetadata]:
        """Get last checkpoint metadata."""
        return self._checkpoints[-1] if self._checkpoints else None

    # Phase management

    def set_phase(
        self,
        phase: PipelinePhase,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Set current pipeline phase.

        Args:
            phase: New phase
            data: Optional phase-specific data
        """
        old_phase = self._current_phase
        self._current_phase = phase

        if data:
            self._phase_data = data
        else:
            self._phase_data = {}

        # Record in history
        self._phase_history.append({
            "from_phase": old_phase.value,
            "to_phase": phase.value,
            "timestamp": datetime.now().isoformat(),
            "data": self._phase_data,
        })

        logger.info(f"Phase changed: {old_phase.value} -> {phase.value}")

        # Notify listeners
        for listener in self._phase_listeners:
            try:
                listener(old_phase, phase)
            except Exception as e:
                logger.error(f"Error in phase listener: {e}")

        # Auto-checkpoint on phase change
        if self._config.auto_checkpoint_on_phase_change:
            asyncio.create_task(self._create_auto_checkpoint(CheckpointType.PHASE_START))

    def get_phase_data(self) -> Dict[str, Any]:
        """Get current phase data."""
        return self._phase_data.copy()

    def update_phase_data(self, data: Dict[str, Any]) -> None:
        """Update phase data.

        Args:
            data: Data to merge into phase data
        """
        self._phase_data.update(data)

    # Variable management

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable.

        Args:
            name: Variable name
            value: Variable value
        """
        self._variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable.

        Args:
            name: Variable name
            default: Default value if not found

        Returns:
            Variable value or default
        """
        return self._variables.get(name, default)

    def get_all_variables(self) -> Dict[str, Any]:
        """Get all variables."""
        return self._variables.copy()

    # Artifact management

    def register_artifact(
        self,
        name: str,
        path: str,
        content: Optional[str] = None,
    ) -> None:
        """Register an artifact.

        Args:
            name: Artifact name (e.g., "spec.md")
            path: Path to artifact file
            content: Optional content to store inline
        """
        self._artifacts[name] = path
        if content is not None:
            self._artifact_contents[name] = content

    def get_artifact_path(self, name: str) -> Optional[str]:
        """Get artifact path.

        Args:
            name: Artifact name

        Returns:
            Path or None
        """
        return self._artifacts.get(name)

    def get_artifact_content(self, name: str) -> Optional[str]:
        """Get artifact content.

        Args:
            name: Artifact name

        Returns:
            Content or None
        """
        return self._artifact_contents.get(name)

    def list_artifacts(self) -> List[str]:
        """List all artifact names."""
        return list(self._artifacts.keys())

    # Step tracking

    def mark_step_completed(self, step: str) -> None:
        """Mark a step as completed.

        Args:
            step: Step identifier
        """
        if step in self._pending_steps:
            self._pending_steps.remove(step)
        if step in self._failed_steps:
            self._failed_steps.remove(step)
        if step not in self._completed_steps:
            self._completed_steps.append(step)

    def mark_step_failed(self, step: str, error: Optional[str] = None) -> None:
        """Mark a step as failed.

        Args:
            step: Step identifier
            error: Optional error message
        """
        if step in self._pending_steps:
            self._pending_steps.remove(step)
        if step not in self._failed_steps:
            self._failed_steps.append(step)

        self._error_history.append({
            "step": step,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })

        # Auto-checkpoint on error
        if self._config.auto_checkpoint_on_error:
            asyncio.create_task(self._create_auto_checkpoint(CheckpointType.ERROR))

    def add_pending_step(self, step: str) -> None:
        """Add a pending step.

        Args:
            step: Step identifier
        """
        if step not in self._pending_steps:
            self._pending_steps.append(step)

    def set_pending_steps(self, steps: List[str]) -> None:
        """Set all pending steps.

        Args:
            steps: List of step identifiers
        """
        self._pending_steps = steps.copy()

    def get_progress(self) -> Dict[str, Any]:
        """Get progress information.

        Returns:
            Progress dictionary
        """
        total = len(self._completed_steps) + len(self._pending_steps) + len(self._failed_steps)
        completed = len(self._completed_steps)

        return {
            "completed": self._completed_steps.copy(),
            "pending": self._pending_steps.copy(),
            "failed": self._failed_steps.copy(),
            "total": total,
            "completed_count": completed,
            "pending_count": len(self._pending_steps),
            "failed_count": len(self._failed_steps),
            "percent": (completed / total * 100) if total > 0 else 0,
        }

    # Checkpoint operations

    async def create_checkpoint(
        self,
        checkpoint_type: CheckpointType = CheckpointType.MANUAL,
        task_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> StateCheckpoint:
        """Create a state checkpoint.

        Args:
            checkpoint_type: Type of checkpoint
            task_id: Optional task ID
            agent_type: Optional agent type
            tags: Optional tags
            custom_data: Optional custom data

        Returns:
            Created StateCheckpoint
        """
        import uuid

        checkpoint_id = str(uuid.uuid4())[:8]
        progress = self.get_progress()

        metadata = CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            checkpoint_type=checkpoint_type,
            created_at=datetime.now(),
            phase=self._current_phase,
            pipeline_id=self._pipeline_id,
            task_id=task_id,
            agent_type=agent_type,
            step_number=progress["completed_count"],
            total_steps=progress["total"],
            progress_percent=progress["percent"],
            tags=tags or [],
            custom_data=custom_data or {},
        )

        checkpoint = StateCheckpoint(
            metadata=metadata,
            current_phase=self._current_phase,
            phase_data=self._phase_data.copy(),
            artifacts=self._artifacts.copy(),
            artifact_contents=self._artifact_contents.copy(),
            completed_steps=self._completed_steps.copy(),
            pending_steps=self._pending_steps.copy(),
            failed_steps=self._failed_steps.copy(),
            variables=self._variables.copy(),
            phase_history=self._phase_history.copy(),
            error_history=self._error_history.copy(),
        )

        # Save to file
        await self._save_checkpoint(checkpoint)

        self._checkpoints.append(metadata)
        self._last_checkpoint_time = datetime.now()

        # Cleanup old checkpoints
        if self._config.auto_cleanup_enabled:
            await self._cleanup_old_checkpoints()

        # Notify listeners
        for listener in self._checkpoint_listeners:
            try:
                listener(checkpoint)
            except Exception as e:
                logger.error(f"Error in checkpoint listener: {e}")

        logger.info(
            f"Checkpoint created: {checkpoint_id} "
            f"(type={checkpoint_type.value}, phase={self._current_phase.value})"
        )

        return checkpoint

    async def _create_auto_checkpoint(self, checkpoint_type: CheckpointType) -> None:
        """Create automatic checkpoint."""
        try:
            await self.create_checkpoint(checkpoint_type=checkpoint_type)
        except Exception as e:
            logger.error(f"Failed to create auto-checkpoint: {e}")

    async def _save_checkpoint(self, checkpoint: StateCheckpoint) -> None:
        """Save checkpoint to file.

        Args:
            checkpoint: Checkpoint to save
        """
        filename = f"checkpoint_{checkpoint.metadata.checkpoint_id}.json"
        filepath = self._checkpoint_path / filename

        json_content = checkpoint.to_json()

        # Calculate checksum
        checksum = hashlib.md5(json_content.encode()).hexdigest()
        checkpoint.metadata.checksum = checksum
        checkpoint.metadata.file_path = str(filepath)
        checkpoint.metadata.file_size_bytes = len(json_content.encode())

        # Write file
        await asyncio.to_thread(self._write_file, filepath, json_content)

    def _write_file(self, filepath: Path, content: str) -> None:
        """Write content to file (sync)."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[StateCheckpoint]:
        """Load checkpoint from file.

        Args:
            checkpoint_id: Checkpoint ID to load

        Returns:
            StateCheckpoint or None
        """
        filename = f"checkpoint_{checkpoint_id}.json"
        filepath = self._checkpoint_path / filename

        if not filepath.exists():
            logger.warning(f"Checkpoint file not found: {filepath}")
            return None

        try:
            content = await asyncio.to_thread(self._read_file, filepath)
            return StateCheckpoint.from_json(content)
        except Exception as e:
            logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def _read_file(self, filepath: Path) -> str:
        """Read file content (sync)."""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    async def load_latest_checkpoint(self) -> Optional[StateCheckpoint]:
        """Load the most recent checkpoint.

        Returns:
            Latest StateCheckpoint or None
        """
        if not self._checkpoints:
            # Try to discover checkpoints from disk
            await self._discover_checkpoints()

        if not self._checkpoints:
            return None

        latest = self._checkpoints[-1]
        return await self.load_checkpoint(latest.checkpoint_id)

    async def _discover_checkpoints(self) -> None:
        """Discover checkpoints from disk."""
        if not self._checkpoint_path.exists():
            return

        for filepath in sorted(self._checkpoint_path.glob("checkpoint_*.json")):
            try:
                content = await asyncio.to_thread(self._read_file, filepath)
                checkpoint = StateCheckpoint.from_json(content)
                self._checkpoints.append(checkpoint.metadata)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint from {filepath}: {e}")

    async def restore_from_checkpoint(
        self,
        checkpoint: StateCheckpoint,
    ) -> None:
        """Restore state from checkpoint.

        Args:
            checkpoint: Checkpoint to restore from
        """
        self._current_phase = checkpoint.current_phase
        self._phase_data = checkpoint.phase_data.copy()
        self._artifacts = checkpoint.artifacts.copy()
        self._artifact_contents = checkpoint.artifact_contents.copy()
        self._completed_steps = checkpoint.completed_steps.copy()
        self._pending_steps = checkpoint.pending_steps.copy()
        self._failed_steps = checkpoint.failed_steps.copy()
        self._variables = checkpoint.variables.copy()
        self._phase_history = checkpoint.phase_history.copy()
        self._error_history = checkpoint.error_history.copy()

        logger.info(
            f"State restored from checkpoint: {checkpoint.metadata.checkpoint_id} "
            f"(phase={checkpoint.current_phase.value})"
        )

    async def _cleanup_old_checkpoints(self) -> None:
        """Remove old checkpoints exceeding max limit."""
        if len(self._checkpoints) <= self._config.max_checkpoints:
            return

        # Remove oldest checkpoints
        to_remove = len(self._checkpoints) - self._config.max_checkpoints

        for _ in range(to_remove):
            old = self._checkpoints.pop(0)
            if old.file_path:
                try:
                    await asyncio.to_thread(os.remove, old.file_path)
                    logger.debug(f"Removed old checkpoint: {old.checkpoint_id}")
                except Exception as e:
                    logger.warning(f"Failed to remove checkpoint file: {e}")

    def list_checkpoints(self) -> List[CheckpointMetadata]:
        """List all checkpoints.

        Returns:
            List of checkpoint metadata
        """
        return self._checkpoints.copy()

    # Listeners

    def add_phase_listener(
        self,
        listener: Callable[[PipelinePhase, PipelinePhase], None],
    ) -> None:
        """Add phase change listener.

        Args:
            listener: Callback(old_phase, new_phase)
        """
        self._phase_listeners.append(listener)

    def add_checkpoint_listener(
        self,
        listener: Callable[[StateCheckpoint], None],
    ) -> None:
        """Add checkpoint creation listener.

        Args:
            listener: Callback(checkpoint)
        """
        self._checkpoint_listeners.append(listener)

    # Auto-checkpoint task

    async def start_auto_checkpoint(self) -> None:
        """Start automatic checkpoint task."""
        if not self._config.auto_checkpoint_enabled:
            return

        if self._auto_checkpoint_task is not None:
            return

        async def auto_checkpoint_loop():
            while True:
                await asyncio.sleep(self._config.auto_checkpoint_interval_seconds)
                await self._create_auto_checkpoint(CheckpointType.AUTOMATIC)

        self._auto_checkpoint_task = asyncio.create_task(auto_checkpoint_loop())
        logger.info("Auto-checkpoint started")

    async def stop_auto_checkpoint(self) -> None:
        """Stop automatic checkpoint task."""
        if self._auto_checkpoint_task is not None:
            self._auto_checkpoint_task.cancel()
            try:
                await self._auto_checkpoint_task
            except asyncio.CancelledError:
                pass
            self._auto_checkpoint_task = None
            logger.info("Auto-checkpoint stopped")

    # Cleanup

    async def cleanup(self, remove_files: bool = False) -> None:
        """Cleanup state manager.

        Args:
            remove_files: Whether to remove checkpoint files
        """
        await self.stop_auto_checkpoint()

        if remove_files:
            for metadata in self._checkpoints:
                if metadata.file_path:
                    try:
                        await asyncio.to_thread(os.remove, metadata.file_path)
                    except Exception:
                        pass

            try:
                await asyncio.to_thread(os.rmdir, self._checkpoint_path)
            except Exception:
                pass

        self._checkpoints.clear()
        logger.info("StateManager cleanup completed")

    def reset(self) -> None:
        """Reset state to initial."""
        self._current_phase = PipelinePhase.INIT
        self._phase_data = {}
        self._artifacts = {}
        self._artifact_contents = {}
        self._completed_steps = []
        self._pending_steps = []
        self._failed_steps = []
        self._variables = {}
        self._phase_history = []
        self._error_history = []
        logger.info("StateManager reset to initial state")
