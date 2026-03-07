"""
Integration tests for Development Pipeline.

Tests the interaction between pipeline components:
- PROJECT-MANAGER → Agents orchestration
- Artifact flow between phases
- Checkpoint system
- Verification loop
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from agents.project_manager import (
    Project,
    Task,
    TaskStatus,
    TaskPriority,
    ProjectStatus,
    ProjectManagerConfig,
    ProjectManagerAgent,
    DependencyTracker,
    TaskScheduler,
    SchedulingStrategy,
)
from models import (
    Artifact,
    ArtifactType,
    ArtifactMetadata,
)
from constants import PipelinePhase, AgentRole
from artifact_store import ArtifactStore


class TestProjectManagerIntegration:
    """Integration tests for PROJECT-MANAGER with other components."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def agent(self, temp_dir):
        """Create PROJECT-MANAGER agent."""
        config = ProjectManagerConfig(
            max_concurrent_projects=5,
            max_tasks_per_project=100,
            projects_dir=temp_dir,
        )
        return ProjectManagerAgent(config=config)

    @pytest.fixture
    def artifact_store(self, temp_dir):
        """Create artifact store."""
        return ArtifactStore(base_path=temp_dir / "artifacts")  # base_path, not storage_dir

    def test_full_project_lifecycle(self, agent):
        """Test complete project lifecycle."""
        # 1. Create project
        tasks = [
            {
                "task_id": "analyze",
                "title": "Analyze requirements",
                "priority": "critical",
                "estimated_hours": 4,
            },
            {
                "task_id": "design",
                "title": "Design solution",
                "priority": "high",
                "estimated_hours": 8,
                "dependencies": ["analyze"],
            },
            {
                "task_id": "implement",
                "title": "Implement solution",
                "priority": "high",
                "estimated_hours": 16,
                "dependencies": ["design"],
            },
            {
                "task_id": "test",
                "title": "Test implementation",
                "priority": "medium",
                "estimated_hours": 8,
                "dependencies": ["implement"],
            },
            {
                "task_id": "deploy",
                "title": "Deploy to production",
                "priority": "medium",
                "estimated_hours": 2,
                "dependencies": ["test"],
            },
        ]

        create_result = agent.create_project(
            project_id="lifecycle-test",
            name="Lifecycle Test Project",
            tasks=tasks,
        )
        assert create_result.success is True

        # 2. Start project
        start_result = agent.start_project("lifecycle-test")
        assert start_result.success is True

        status = agent.get_project_status("lifecycle-test")
        # After start_project, status is INITIALIZING; becomes IN_PROGRESS when first task starts
        assert status["status"] in [ProjectStatus.INITIALIZING.value, ProjectStatus.IN_PROGRESS.value]

        # 3. Process tasks in order
        task_order = ["analyze", "design", "implement", "test", "deploy"]
        for task_id in task_order:
            # Get next task
            next_task = agent.get_next_task("lifecycle-test")
            assert next_task is not None
            assert next_task.task_id == task_id  # Task object, not dict

            # Start and complete
            agent.start_task("lifecycle-test", task_id)
            result = agent.complete_task("lifecycle-test", task_id)
            assert result.success is True

        # 4. Verify project completion
        final_status = agent.get_project_status("lifecycle-test")
        assert final_status["progress_percent"] == 100.0  # progress_percent, not progress

    def test_parallel_tasks_execution(self, agent):
        """Test parallel task execution."""
        tasks = [
            {"task_id": "setup", "title": "Setup", "estimated_hours": 1},
            {
                "task_id": "module-a",
                "title": "Module A",
                "dependencies": ["setup"],
                "estimated_hours": 4,
            },
            {
                "task_id": "module-b",
                "title": "Module B",
                "dependencies": ["setup"],
                "estimated_hours": 4,
            },
            {
                "task_id": "module-c",
                "title": "Module C",
                "dependencies": ["setup"],
                "estimated_hours": 4,
            },
            {
                "task_id": "integration",
                "title": "Integration",
                "dependencies": ["module-a", "module-b", "module-c"],
                "estimated_hours": 2,
            },
        ]

        agent.create_project(
            project_id="parallel-test",
            name="Parallel Tasks Test",
            tasks=tasks,
        )
        agent.start_project("parallel-test")

        # Complete setup
        agent.complete_task("parallel-test", "setup")

        # All three modules should be ready now
        ready = agent.get_ready_tasks("parallel-test")
        ready_ids = {t.task_id for t in ready}  # Task objects, not dicts
        assert "module-a" in ready_ids
        assert "module-b" in ready_ids
        assert "module-c" in ready_ids

        # Integration should not be ready
        assert "integration" not in ready_ids

    def test_dependency_tracker_integration(self, agent):
        """Test DependencyTracker with PROJECT-MANAGER."""
        tasks = [
            {"task_id": "t1", "title": "Task 1", "estimated_hours": 1},
            {"task_id": "t2", "title": "Task 2", "dependencies": ["t1"], "estimated_hours": 1},
            {"task_id": "t3", "title": "Task 3", "dependencies": ["t1"], "estimated_hours": 1},
            {"task_id": "t4", "title": "Task 4", "dependencies": ["t2", "t3"], "estimated_hours": 1},
        ]

        agent.create_project(
            project_id="dep-test",
            name="Dependency Test",
            tasks=tasks,
        )
        agent.start_project("dep-test")

        # Create schedule - this validates dependencies internally
        schedule = agent.create_schedule("dep-test")
        assert schedule is not None

        # Schedule should contain all tasks
        assert len(schedule.scheduled_tasks) == 4

        # First task should be t1 (no dependencies)
        first_ready = agent.get_ready_tasks("dep-test")
        assert len(first_ready) == 1
        assert first_ready[0].task_id == "t1"

    def test_scheduling_strategies(self, agent):
        """Test different scheduling strategies."""
        tasks = [
            {
                "task_id": "low-long",
                "title": "Low Priority Long",
                "priority": "low",
                "estimated_hours": 10,
            },
            {
                "task_id": "high-short",
                "title": "High Priority Short",
                "priority": "critical",
                "estimated_hours": 1,
            },
            {
                "task_id": "medium-medium",
                "title": "Medium Priority Medium",
                "priority": "medium",
                "estimated_hours": 5,
            },
        ]

        agent.create_project(
            project_id="schedule-test",
            name="Scheduling Test",
            tasks=tasks,
        )
        agent.start_project("schedule-test")

        # Create schedule with priority-first strategy
        schedule = agent.create_schedule("schedule-test", strategy="priority_first")
        assert schedule is not None
        scheduled_tasks = schedule.scheduled_tasks

        # Critical priority should come first
        assert scheduled_tasks[0].task.task_id == "high-short"  # ScheduledTask.task.task_id


class TestArtifactFlowIntegration:
    """Integration tests for artifact flow between phases."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def artifact_store(self, temp_dir):
        """Create artifact store."""
        return ArtifactStore(base_path=temp_dir)  # base_path, not storage_dir

    def test_artifact_chain(self, artifact_store):
        """Test artifact chain through pipeline phases."""
        project_id = "artifact-chain"
        task_id = "TASK-001"

        # 1. PM-SPEC creates spec.md
        spec_artifact = artifact_store.store(
            artifact_type=ArtifactType.SPEC,
            content="# Спецификация\n\n## Требования\n- Feature A\n- Feature B\n\n## Критерии приёмки\n- Test 1",
            producer=AgentRole.PM_SPEC,
            tags={"project_id": project_id, "task_id": task_id},
        )

        # 2. ARCHITECT creates design.md (depends on spec)
        design_artifact = artifact_store.store(
            artifact_type=ArtifactType.DESIGN,
            content="# Техническое решение\n\n## Архитектурные решения\n- Component A\n\n## План изменений\n- Step 1",
            producer=AgentRole.ARCHITECT,
            dependencies=[ArtifactType.SPEC],
            tags={"project_id": project_id, "task_id": task_id},
        )

        # 3. IMPLEMENTER creates result.md (depends on design)
        result_artifact = artifact_store.store(
            artifact_type=ArtifactType.RESULT,
            content="# Результат реализации\n\n## Выполненные шаги\n- Step 1\n\n## Созданные файлы\n- File A",
            producer=AgentRole.IMPLEMENTER,
            dependencies=[ArtifactType.DESIGN],
            tags={"project_id": project_id, "task_id": task_id},
        )

        # Verify artifact chain
        loaded_result = artifact_store.get(ArtifactType.RESULT)
        assert loaded_result is not None
        assert ArtifactType.DESIGN.value in loaded_result.metadata.dependencies

        # Verify all artifacts stored
        all_artifacts = artifact_store.get_all()
        assert len(all_artifacts) == 3
        assert ArtifactType.SPEC in all_artifacts
        assert ArtifactType.DESIGN in all_artifacts
        assert ArtifactType.RESULT in all_artifacts

    def test_artifact_versioning(self, artifact_store):
        """Test artifact versioning through revisions."""
        project_id = "versioning-test"

        # Version 1
        artifact_v1 = artifact_store.store(
            artifact_type=ArtifactType.SPEC,
            content="# Спецификация\n\n## Требования\n- v1\n\n## Критерии приёмки\n- Test",
            producer=AgentRole.PM_SPEC,
            tags={"project_id": project_id},
        )
        assert artifact_v1.metadata.version == 1

        # Version 2 (update same artifact type - should auto-version)
        artifact_v2 = artifact_store.store(
            artifact_type=ArtifactType.SPEC,
            content="# Спецификация\n\n## Требования\n- v2 Updated\n\n## Критерии приёмки\n- Test",
            producer=AgentRole.PM_SPEC,
            tags={"project_id": project_id},
        )
        assert artifact_v2.metadata.version == 2

        # History should contain v1
        history = artifact_store.get_history(ArtifactType.SPEC)
        assert len(history) == 1
        assert history[0].metadata.version == 1

        # Current artifact should be v2
        current = artifact_store.get(ArtifactType.SPEC)
        assert current.metadata.version == 2


class TestCheckpointIntegration:
    """Integration tests for checkpoint system."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_checkpoint_creation_on_phase_complete(self, temp_dir):
        """Test checkpoint creation when phase completes."""
        from orchestrator.resilience.state_manager import (
            StateManager,
            StateManagerConfig,
            CheckpointType,
            PipelinePhase as SMPipelinePhase,
        )

        checkpoint_dir = temp_dir / "checkpoints"
        config = StateManagerConfig(checkpoint_dir=str(checkpoint_dir))
        manager = StateManager(pipeline_id="checkpoint-test", config=config)

        task_id = "TASK-001"

        # Set phase to specification
        manager.set_phase(SMPipelinePhase.PM_SPEC_SPEC, data={"status": "in_progress"})

        # Create checkpoint after PM-SPEC phase
        checkpoint = await manager.create_checkpoint(
            checkpoint_type=CheckpointType.PHASE_END,
            task_id=task_id,
            custom_data={"status": "completed", "reviewer_approved": True},
        )

        assert checkpoint is not None
        assert checkpoint.current_phase == SMPipelinePhase.PM_SPEC_SPEC

        # Load checkpoint
        loaded = await manager.load_checkpoint(checkpoint.metadata.checkpoint_id)
        assert loaded is not None
        assert loaded.metadata.custom_data["status"] == "completed"

        # Cleanup
        await manager.cleanup(remove_files=True)


class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def pipeline_context(self, temp_dir):
        """Create complete pipeline context."""
        return {
            "project_dir": temp_dir / "projects",
            "artifact_dir": temp_dir / "artifacts",
            "checkpoint_dir": temp_dir / "checkpoints",
        }

    def test_simple_1c_task_workflow(self, pipeline_context):
        """Test simple 1C development task workflow."""
        # Setup PROJECT-MANAGER
        config = ProjectManagerConfig(
            projects_dir=pipeline_context["project_dir"],
        )
        agent = ProjectManagerAgent(config=config)

        # Create 1C development task
        tasks = [
            {
                "task_id": "spec",
                "title": "Specify catalog structure",
                "priority": "high",
                "estimated_hours": 2,
                "agent": "PM-SPEC",
            },
            {
                "task_id": "design",
                "title": "Design catalog metadata",
                "priority": "high",
                "estimated_hours": 4,
                "dependencies": ["spec"],
                "agent": "ARCHITECT",
            },
            {
                "task_id": "implement",
                "title": "Implement catalog in BSL",
                "priority": "high",
                "estimated_hours": 8,
                "dependencies": ["design"],
                "agent": "IMPLEMENTER",
            },
            {
                "task_id": "test",
                "title": "Test catalog functionality",
                "priority": "medium",
                "estimated_hours": 4,
                "dependencies": ["implement"],
                "agent": "QA",
            },
        ]

        # Execute workflow
        agent.create_project(
            project_id="1c-feature",
            name="Add new catalog",
            description="Create new catalog for storing product categories",
            tasks=tasks,
        )
        agent.start_project("1c-feature")

        # Validate schedule
        schedule = agent.create_schedule("1c-feature")
        assert schedule is not None
        assert len(schedule.scheduled_tasks) == 4

        # Validate critical path
        critical_path = agent.get_critical_path("1c-feature")
        assert len(critical_path) == 4  # All tasks on critical path (sequential chain)

        # Verify project status
        status = agent.get_project_status("1c-feature")
        assert status is not None
        assert status["task_count"] == 4  # task_count, not total_tasks

    def test_multi_project_coordination(self, pipeline_context):
        """Test coordination of multiple projects."""
        config = ProjectManagerConfig(
            max_concurrent_projects=3,
            projects_dir=pipeline_context["project_dir"],
        )
        agent = ProjectManagerAgent(config=config)

        # Create multiple projects
        project_ids = []
        for i in range(3):
            project_id = f"project-{i}"
            project_ids.append(project_id)
            agent.create_project(
                project_id=project_id,
                name=f"Project {i}",
                tasks=[
                    {"task_id": "t1", "title": "Task 1", "estimated_hours": 4},
                    {"task_id": "t2", "title": "Task 2", "dependencies": ["t1"], "estimated_hours": 4},
                ],
            )
            agent.start_project(project_id)

        # Verify all projects created and started
        all_projects = agent.list_projects()
        assert len(all_projects) == 3

        # Check project statuses (should be INITIALIZING or IN_PROGRESS)
        for project in all_projects:
            assert project.status in [ProjectStatus.INITIALIZING, ProjectStatus.IN_PROGRESS]

        # Verify each project has tasks
        for project_id in project_ids:
            status = agent.get_project_status(project_id)
            assert status["task_count"] == 2  # task_count, not total_tasks
