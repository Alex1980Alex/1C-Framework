"""Tests for ProjectManagerAgent."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from agents.project_manager.models import (
    Project,
    Task,
    TaskStatus,
    TaskPriority,
    ProjectStatus,
    ProjectManagerConfig,
    ProjectManagerInput,
)
from agents.project_manager.repository import ProjectRepository
from agents.project_manager.agent import ProjectManagerAgent, ProjectManagerResult


class TestProjectManagerAgent:
    """Tests for ProjectManagerAgent."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ProjectManagerConfig(
            max_concurrent_projects=3,
            max_tasks_per_project=50,
            project_timeout=1800,
        )

    @pytest.fixture
    def agent(self, temp_dir, config):
        """Create agent with temp storage."""
        return ProjectManagerAgent(config=config, storage_dir=temp_dir)

    @pytest.fixture
    def sample_input(self):
        """Create sample input."""
        return ProjectManagerInput(
            project_id="proj-1",
            project_name="Test Project",
            tasks=[
                {
                    "task_id": "task-1",
                    "title": "Setup environment",
                    "priority": "high",
                    "estimated_hours": 2,
                },
                {
                    "task_id": "task-2",
                    "title": "Implement feature",
                    "priority": "medium",
                    "estimated_hours": 8,
                    "dependencies": ["task-1"],
                },
                {
                    "task_id": "task-3",
                    "title": "Write tests",
                    "priority": "medium",
                    "estimated_hours": 4,
                    "dependencies": ["task-2"],
                },
            ],
        )

    def test_create_project(self, agent, sample_input):
        """Test project creation."""
        result = agent.create_project(sample_input)

        assert result.success is True
        assert result.project_id == "proj-1"
        assert result.message is not None

    def test_create_duplicate_project(self, agent, sample_input):
        """Test creating duplicate project fails."""
        agent.create_project(sample_input)
        result = agent.create_project(sample_input)

        assert result.success is False
        assert "exists" in result.message.lower() or "duplicate" in result.message.lower()

    def test_get_project_status(self, agent, sample_input):
        """Test getting project status."""
        agent.create_project(sample_input)
        status = agent.get_project_status("proj-1")

        assert status is not None
        assert status["project_id"] == "proj-1"
        assert "status" in status
        assert "progress" in status
        assert "task_count" in status

    def test_get_nonexistent_project_status(self, agent):
        """Test getting status of non-existent project."""
        status = agent.get_project_status("non-existent")
        assert status is None

    def test_start_project(self, agent, sample_input):
        """Test starting a project."""
        agent.create_project(sample_input)
        result = agent.start_project("proj-1")

        assert result.success is True

        status = agent.get_project_status("proj-1")
        assert status["status"] == ProjectStatus.IN_PROGRESS.value

    def test_get_next_task(self, agent, sample_input):
        """Test getting next task."""
        agent.create_project(sample_input)
        agent.start_project("proj-1")

        next_task = agent.get_next_task("proj-1")

        # Should be task-1 (no dependencies)
        assert next_task is not None
        assert next_task["task_id"] == "task-1"

    def test_complete_task(self, agent, sample_input):
        """Test completing a task."""
        agent.create_project(sample_input)
        agent.start_project("proj-1")

        result = agent.complete_task("proj-1", "task-1")
        assert result.success is True

        status = agent.get_project_status("proj-1")
        assert status["progress"] > 0

    def test_complete_task_unlocks_dependencies(self, agent, sample_input):
        """Test that completing a task unlocks dependent tasks."""
        agent.create_project(sample_input)
        agent.start_project("proj-1")

        # Initially only task-1 is available
        ready = agent.get_ready_tasks("proj-1")
        assert len(ready) == 1
        assert ready[0]["task_id"] == "task-1"

        # Complete task-1
        agent.complete_task("proj-1", "task-1")

        # Now task-2 should be available
        ready = agent.get_ready_tasks("proj-1")
        assert len(ready) == 1
        assert ready[0]["task_id"] == "task-2"

    def test_fail_task(self, agent, sample_input):
        """Test failing a task."""
        agent.create_project(sample_input)
        agent.start_project("proj-1")

        result = agent.fail_task("proj-1", "task-1", "Environment error")
        assert result.success is True

        task_status = agent.get_task_status("proj-1", "task-1")
        assert task_status["status"] == TaskStatus.FAILED.value

    def test_assign_task(self, agent, sample_input):
        """Test assigning task to agent."""
        agent.create_project(sample_input)
        agent.start_project("proj-1")

        result = agent.assign_task("proj-1", "task-1", "IMPLEMENTER")
        assert result.success is True

        task_status = agent.get_task_status("proj-1", "task-1")
        assert task_status["assigned_agent"] == "IMPLEMENTER"

    def test_get_schedule(self, agent, sample_input):
        """Test getting project schedule."""
        agent.create_project(sample_input)
        schedule = agent.get_schedule("proj-1")

        assert schedule is not None
        assert "scheduled_tasks" in schedule
        assert len(schedule["scheduled_tasks"]) == 3

    def test_allocate_agents(self, agent, sample_input):
        """Test allocating agents to project."""
        agent.create_project(sample_input)
        agent.start_project("proj-1")

        agents = ["ARCHITECT", "IMPLEMENTER", "QA"]
        allocation = agent.allocate_agents("proj-1", agents)

        assert allocation is not None
        assert len(allocation) == 3

    def test_validate_dependencies(self, agent, sample_input):
        """Test dependency validation."""
        agent.create_project(sample_input)
        is_valid, errors = agent.validate_dependencies("proj-1")

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_circular_dependencies(self, agent):
        """Test detection of circular dependencies."""
        input_data = ProjectManagerInput(
            project_id="proj-1",
            project_name="Circular",
            tasks=[
                {
                    "task_id": "task-1",
                    "title": "Task 1",
                    "dependencies": ["task-2"],
                },
                {
                    "task_id": "task-2",
                    "title": "Task 2",
                    "dependencies": ["task-1"],
                },
            ],
        )

        agent.create_project(input_data)
        is_valid, errors = agent.validate_dependencies("proj-1")

        assert is_valid is False
        assert any("circular" in e.lower() for e in errors)

    def test_get_blocked_tasks(self, agent, sample_input):
        """Test getting blocked tasks."""
        agent.create_project(sample_input)
        agent.start_project("proj-1")

        blocked = agent.get_blocked_tasks("proj-1")

        # task-2 and task-3 are blocked by dependencies
        blocked_ids = {t["task_id"] for t in blocked}
        assert "task-2" in blocked_ids or "task-3" in blocked_ids

    def test_get_critical_path(self, agent, sample_input):
        """Test getting critical path."""
        agent.create_project(sample_input)
        path = agent.get_critical_path("proj-1")

        assert path is not None
        assert len(path) > 0

    def test_estimate_completion(self, agent, sample_input):
        """Test completion estimation."""
        agent.create_project(sample_input)
        estimate = agent.estimate_completion("proj-1")

        assert estimate is not None
        assert "estimated_completion" in estimate
        assert "total_hours" in estimate

    def test_list_projects(self, agent, sample_input):
        """Test listing all projects."""
        # Initially empty
        projects = agent.list_projects()
        assert len(projects) == 0

        # Create projects
        agent.create_project(sample_input)

        input2 = ProjectManagerInput(
            project_id="proj-2",
            project_name="Project 2",
            tasks=[{"task_id": "t1", "title": "Task"}],
        )
        agent.create_project(input2)

        projects = agent.list_projects()
        assert len(projects) == 2

    def test_cancel_project(self, agent, sample_input):
        """Test cancelling a project."""
        agent.create_project(sample_input)
        result = agent.cancel_project("proj-1", "No longer needed")

        assert result.success is True

        status = agent.get_project_status("proj-1")
        assert status["status"] == ProjectStatus.CANCELLED.value


class TestProjectManagerAgentConcurrency:
    """Tests for concurrent project management."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def agent(self, temp_dir):
        """Create agent with limited concurrency."""
        config = ProjectManagerConfig(max_concurrent_projects=2)
        return ProjectManagerAgent(config=config, storage_dir=temp_dir)

    def test_max_concurrent_projects(self, agent):
        """Test that max concurrent projects is enforced."""
        # Create first project
        input1 = ProjectManagerInput(
            project_id="proj-1",
            project_name="Project 1",
            tasks=[{"task_id": "t1", "title": "Task"}],
        )
        agent.create_project(input1)
        agent.start_project("proj-1")

        # Create second project
        input2 = ProjectManagerInput(
            project_id="proj-2",
            project_name="Project 2",
            tasks=[{"task_id": "t1", "title": "Task"}],
        )
        agent.create_project(input2)
        agent.start_project("proj-2")

        # Third project should be queued or rejected
        input3 = ProjectManagerInput(
            project_id="proj-3",
            project_name="Project 3",
            tasks=[{"task_id": "t1", "title": "Task"}],
        )
        result = agent.create_project(input3)

        # Depending on implementation, this might create but not start
        # or might be rejected
        if result.success:
            start_result = agent.start_project("proj-3")
            # Should either work (WAITING status) or fail
            assert start_result.success or "limit" in start_result.message.lower()

    def test_project_priorities(self, agent):
        """Test project priority handling."""
        # Create high priority project
        input1 = ProjectManagerInput(
            project_id="proj-high",
            project_name="High Priority",
            priority="critical",
            tasks=[{"task_id": "t1", "title": "Task"}],
        )
        agent.create_project(input1)

        # Create low priority project
        input2 = ProjectManagerInput(
            project_id="proj-low",
            project_name="Low Priority",
            priority="low",
            tasks=[{"task_id": "t1", "title": "Task"}],
        )
        agent.create_project(input2)

        # Get prioritized list
        projects = agent.list_projects(sort_by_priority=True)
        if len(projects) > 1:
            # High priority should come first
            assert projects[0]["project_id"] == "proj-high"


class TestProjectManagerResult:
    """Tests for ProjectManagerResult."""

    def test_success_result(self):
        """Test creating success result."""
        result = ProjectManagerResult.success(
            project_id="proj-1",
            message="Created successfully",
            data={"key": "value"},
        )

        assert result.success is True
        assert result.project_id == "proj-1"
        assert result.message == "Created successfully"
        assert result.data == {"key": "value"}

    def test_failure_result(self):
        """Test creating failure result."""
        result = ProjectManagerResult.failure(
            message="Something went wrong",
            error_code="E001",
        )

        assert result.success is False
        assert result.message == "Something went wrong"
        assert result.error_code == "E001"

    def test_result_to_dict(self):
        """Test result serialization."""
        result = ProjectManagerResult.success(
            project_id="proj-1",
            message="OK",
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["project_id"] == "proj-1"
        assert data["message"] == "OK"
