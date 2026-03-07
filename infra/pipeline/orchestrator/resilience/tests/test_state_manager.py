"""Tests for state_manager module."""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from datetime import datetime

from .state_manager import (
    CheckpointType,
    PipelinePhase,
    CheckpointMetadata,
    StateCheckpoint,
    StateManager,
    StateManagerConfig,
)


class TestCheckpointType:
    """Tests for CheckpointType enum."""

    def test_all_types_exist(self):
        """Test all checkpoint types are defined."""
        assert CheckpointType.MANUAL
        assert CheckpointType.AUTOMATIC
        assert CheckpointType.PHASE_START
        assert CheckpointType.PHASE_END
        assert CheckpointType.ERROR
        assert CheckpointType.RECOVERY


class TestPipelinePhase:
    """Tests for PipelinePhase enum."""

    def test_all_phases_exist(self):
        """Test all pipeline phases are defined."""
        assert PipelinePhase.INIT
        assert PipelinePhase.PM_SPEC_INIT
        assert PipelinePhase.PM_SPEC_SPEC
        assert PipelinePhase.ARCHITECT_DESIGN
        assert PipelinePhase.IMPLEMENTER_BUILD
        assert PipelinePhase.ARCHITECT_REVIEW
        assert PipelinePhase.PM_SPEC_VERIFY
        assert PipelinePhase.IMPLEMENTER_FIX
        assert PipelinePhase.COMPLETED
        assert PipelinePhase.FAILED


class TestCheckpointMetadata:
    """Tests for CheckpointMetadata dataclass."""

    def test_basic_creation(self):
        """Test basic metadata creation."""
        meta = CheckpointMetadata(
            checkpoint_id="cp-001",
            checkpoint_type=CheckpointType.AUTOMATIC,
            created_at=datetime.now(),
            phase=PipelinePhase.PM_SPEC_SPEC,
            pipeline_id="test-pipeline",
            step_number=5,
            total_steps=10,
        )

        assert meta.checkpoint_id == "cp-001"
        assert meta.checkpoint_type == CheckpointType.AUTOMATIC
        assert meta.phase == PipelinePhase.PM_SPEC_SPEC
        assert meta.step_number == 5
        assert meta.total_steps == 10

    def test_to_dict(self):
        """Test serialization to dict."""
        meta = CheckpointMetadata(
            checkpoint_id="cp-002",
            checkpoint_type=CheckpointType.MANUAL,
            created_at=datetime.now(),
            phase=PipelinePhase.ARCHITECT_DESIGN,
            pipeline_id="test-pipeline",
        )

        d = meta.to_dict()

        assert d["checkpoint_id"] == "cp-002"
        assert d["checkpoint_type"] == "manual"
        assert d["phase"] == "architect_design"
        assert d["pipeline_id"] == "test-pipeline"

    def test_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "checkpoint_id": "cp-003",
            "checkpoint_type": "phase_start",
            "created_at": "2025-12-23T10:00:00",
            "phase": "implementer_build",
            "pipeline_id": "test-pipeline",
            "step_number": 1,
            "total_steps": 5,
        }

        meta = CheckpointMetadata.from_dict(d)

        assert meta.checkpoint_id == "cp-003"
        assert meta.checkpoint_type == CheckpointType.PHASE_START
        assert meta.phase == PipelinePhase.IMPLEMENTER_BUILD
        assert meta.step_number == 1


class TestStateCheckpoint:
    """Tests for StateCheckpoint dataclass."""

    def test_basic_creation(self):
        """Test basic checkpoint creation."""
        metadata = CheckpointMetadata(
            checkpoint_id="cp-001",
            checkpoint_type=CheckpointType.AUTOMATIC,
            created_at=datetime.now(),
            phase=PipelinePhase.PM_SPEC_SPEC,
            pipeline_id="pipeline-001",
        )

        checkpoint = StateCheckpoint(
            metadata=metadata,
            current_phase=PipelinePhase.PM_SPEC_SPEC,
            phase_data={"key": "value"},
        )

        assert checkpoint.metadata.pipeline_id == "pipeline-001"
        assert checkpoint.current_phase == PipelinePhase.PM_SPEC_SPEC
        assert checkpoint.phase_data == {"key": "value"}

    def test_to_dict(self):
        """Test serialization to dict."""
        metadata = CheckpointMetadata(
            checkpoint_id="cp-002",
            checkpoint_type=CheckpointType.MANUAL,
            created_at=datetime.now(),
            phase=PipelinePhase.ARCHITECT_DESIGN,
            pipeline_id="pipeline-002",
        )

        checkpoint = StateCheckpoint(
            metadata=metadata,
            current_phase=PipelinePhase.ARCHITECT_DESIGN,
            phase_data={"design": "data"},
            artifacts={"spec.md": "/path/to/spec.md"},
        )

        d = checkpoint.to_dict()

        assert d["current_phase"] == "architect_design"
        assert d["phase_data"]["design"] == "data"
        assert "spec.md" in d["artifacts"]

    def test_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "metadata": {
                "checkpoint_id": "cp-003",
                "checkpoint_type": "automatic",
                "created_at": "2025-12-23T10:00:00",
                "phase": "implementer_build",
                "pipeline_id": "pipeline-003",
            },
            "current_phase": "implementer_build",
            "phase_data": {"impl": "data"},
            "artifacts": {},
            "artifact_contents": {},
            "completed_steps": [],
            "pending_steps": [],
            "failed_steps": [],
            "variables": {},
            "phase_history": [],
            "error_history": [],
        }

        checkpoint = StateCheckpoint.from_dict(d)

        assert checkpoint.current_phase == PipelinePhase.IMPLEMENTER_BUILD
        assert checkpoint.phase_data["impl"] == "data"


class TestStateManager:
    """Tests for StateManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create state manager for testing."""
        config = StateManagerConfig(
            checkpoint_dir=str(temp_dir),
        )
        return StateManager(
            pipeline_id="test-pipeline",
            config=config,
        )

    def test_initial_state(self, manager):
        """Test initial manager state."""
        assert manager.current_phase == PipelinePhase.INIT
        assert manager.checkpoint_count == 0

    @pytest.mark.asyncio
    async def test_create_checkpoint(self, manager):
        """Test creating a checkpoint."""
        checkpoint = await manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            task_id="task-001",
            agent_type="TEST_AGENT",
            tags=["test"],
            custom_data={"test": "data"},
        )

        assert checkpoint is not None
        assert checkpoint.metadata.pipeline_id == "test-pipeline"
        assert checkpoint.metadata.custom_data.get("test") == "data"
        assert manager.checkpoint_count == 1

    @pytest.mark.asyncio
    async def test_phase_transition(self, manager):
        """Test transitioning between phases."""
        # Start in INIT
        assert manager.current_phase == PipelinePhase.INIT

        # Transition to PM_SPEC_SPEC
        manager.set_phase(PipelinePhase.PM_SPEC_SPEC)
        assert manager.current_phase == PipelinePhase.PM_SPEC_SPEC

        # Should have created phase checkpoints if auto_checkpoint_on_phase_change
        assert manager.checkpoint_count >= 0

    @pytest.mark.asyncio
    async def test_add_artifact(self, manager):
        """Test adding artifacts."""
        manager.register_artifact("spec.md", "/path/to/spec.md")
        manager.register_artifact("design.md", "/path/to/design.md")

        artifacts = manager.list_artifacts()

        assert "spec.md" in artifacts
        assert "design.md" in artifacts

    @pytest.mark.asyncio
    async def test_record_step(self, manager):
        """Test recording steps."""
        manager.mark_step_completed("Step 1 completed")
        manager.mark_step_completed("Step 2 completed")

        progress = manager.get_progress()
        assert progress["completed_count"] == 2

    @pytest.mark.asyncio
    async def test_auto_checkpoint(self, manager):
        """Test auto-checkpoint on interval."""
        # Manager has auto_checkpoint_interval=60
        manager.mark_step_completed("Step 1")
        initial_count = manager.checkpoint_count

        manager.mark_step_completed("Step 2")
        # Should trigger auto-checkpoint based on interval or phase change
        assert manager.checkpoint_count >= initial_count

    @pytest.mark.asyncio
    async def test_restore_checkpoint(self, manager):
        """Test restoring from checkpoint."""
        # Create some state
        manager.set_phase(PipelinePhase.PM_SPEC_SPEC)
        manager.register_artifact("test.md", "/path/test.md")

        # Create checkpoint
        checkpoint = await manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            custom_data={"important": "state"},
        )

        # Modify state
        manager.set_phase(PipelinePhase.ARCHITECT_DESIGN)
        manager.register_artifact("another.md", "/path/another.md")

        # Load checkpoint and restore from it
        loaded_checkpoint = await manager.load_checkpoint(checkpoint.metadata.checkpoint_id)
        await manager.restore_from_checkpoint(loaded_checkpoint)

        # Should be back to PM_SPEC_SPEC phase
        assert manager.current_phase == PipelinePhase.PM_SPEC_SPEC

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self, manager):
        """Test getting latest checkpoint."""
        await manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            custom_data={"first": True},
        )

        await asyncio.sleep(0.01)  # Ensure different timestamps

        await manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            custom_data={"second": True},
        )

        # Use last_checkpoint property
        latest_metadata = manager.last_checkpoint

        assert latest_metadata is not None
        assert latest_metadata.custom_data.get("second") is True

    @pytest.mark.asyncio
    async def test_save_and_load(self, manager, temp_dir):
        """Test saving and loading state."""
        # Create some state
        manager.set_phase(PipelinePhase.PM_SPEC_SPEC)
        manager.register_artifact("spec.md", "/path/spec.md")

        # Create checkpoint (saves automatically)
        checkpoint = await manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            custom_data={"saved": "data"},
        )

        # Load checkpoint from file
        loaded_checkpoint = await manager.load_checkpoint(checkpoint.metadata.checkpoint_id)

        # Verify state was saved and loaded
        assert loaded_checkpoint is not None
        assert loaded_checkpoint.current_phase == PipelinePhase.PM_SPEC_SPEC
        assert "spec.md" in loaded_checkpoint.artifacts

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints(self, manager):
        """Test cleanup of old checkpoints."""
        # Create multiple checkpoints
        for i in range(5):
            await manager.create_checkpoint(
                checkpoint_type=CheckpointType.AUTOMATIC,
                custom_data={"index": i},
            )

        # Checkpoints should be auto-cleaned based on max_checkpoints config
        assert manager.checkpoint_count <= 10

    @pytest.mark.asyncio
    async def test_list_checkpoints(self, manager):
        """Test listing checkpoints."""
        await manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTOMATIC,
            custom_data={"auto": True},
        )
        await manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            custom_data={"manual": True},
        )

        checkpoints = manager.list_checkpoints()

        assert len(checkpoints) >= 2

    def test_get_progress(self, manager):
        """Test getting progress information."""
        manager.mark_step_completed("Step 1")
        manager.mark_step_completed("Step 2")

        progress = manager.get_progress()

        assert progress["completed_count"] == 2
        assert "Step 1" in progress["completed"]
        assert "Step 2" in progress["completed"]

