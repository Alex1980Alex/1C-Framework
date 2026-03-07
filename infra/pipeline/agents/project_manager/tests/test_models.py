"""Tests for PROJECT-MANAGER models."""

import pytest
from datetime import datetime

from agents.project_manager.models import (
    ProjectStatus,
    TaskStatus,
    TaskPriority,
    DependencyType,
    Task,
    TaskDependency,
    Project,
    ProjectManagerConfig,
)


class TestProjectStatus:
    """Tests for ProjectStatus enum."""

    def test_is_active(self):
        """Test is_active property."""
        assert ProjectStatus.INITIALIZING.is_active is True
        assert ProjectStatus.IN_PROGRESS.is_active is True
        assert ProjectStatus.NOT_STARTED.is_active is False
        assert ProjectStatus.COMPLETED.is_active is False

    def test_is_terminal(self):
        """Test is_terminal property."""
        assert ProjectStatus.COMPLETED.is_terminal is True
        assert ProjectStatus.FAILED.is_terminal is True
        assert ProjectStatus.CANCELLED.is_terminal is True
        assert ProjectStatus.IN_PROGRESS.is_terminal is False

    def test_ru_name(self):
        """Test Russian names."""
        assert ProjectStatus.NOT_STARTED.ru_name == "Не начат"
        assert ProjectStatus.COMPLETED.ru_name == "Завершён"


class TestTaskPriority:
    """Tests for TaskPriority enum."""

    def test_weight(self):
        """Test priority weights."""
        assert TaskPriority.CRITICAL.weight == 100
        assert TaskPriority.HIGH.weight == 75
        assert TaskPriority.MEDIUM.weight == 50
        assert TaskPriority.LOW.weight == 25

    def test_ordering(self):
        """Test priority ordering."""
        priorities = [TaskPriority.LOW, TaskPriority.CRITICAL, TaskPriority.MEDIUM]
        sorted_priorities = sorted(priorities, key=lambda p: p.weight, reverse=True)
        assert sorted_priorities[0] == TaskPriority.CRITICAL
        assert sorted_priorities[-1] == TaskPriority.LOW


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_is_terminal(self):
        """Test is_terminal property."""
        assert TaskStatus.COMPLETED.is_terminal is True
        assert TaskStatus.FAILED.is_terminal is True
        assert TaskStatus.SKIPPED.is_terminal is True
        assert TaskStatus.PENDING.is_terminal is False
        assert TaskStatus.IN_PROGRESS.is_terminal is False


class TestTaskDependency:
    """Tests for TaskDependency."""

    def test_finish_to_start_satisfied(self):
        """Test finish-to-start dependency."""
        dep = TaskDependency(
            source_task_id="task-1",
            target_task_id="task-2",
            dependency_type=DependencyType.FINISH_TO_START,
        )
        assert dep.is_satisfied(TaskStatus.COMPLETED) is True
        assert dep.is_satisfied(TaskStatus.IN_PROGRESS) is False

    def test_start_to_start_satisfied(self):
        """Test start-to-start dependency."""
        dep = TaskDependency(
            source_task_id="task-1",
            target_task_id="task-2",
            dependency_type=DependencyType.START_TO_START,
        )
        assert dep.is_satisfied(TaskStatus.IN_PROGRESS) is True
        assert dep.is_satisfied(TaskStatus.PENDING) is False


class TestTask:
    """Tests for Task dataclass."""

    def test_create_task(self):
        """Test task creation."""
        task = Task(
            task_id="task-1",
            title="Test Task",
            description="A test task",
        )
        assert task.task_id == "task-1"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM

    def test_duration_hours(self):
        """Test duration calculation."""
        task = Task(
            task_id="task-1",
            title="Test",
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            completed_at=datetime(2025, 1, 1, 12, 30, 0),
        )
        assert task.duration_hours == 2.5

    def test_duration_hours_incomplete(self):
        """Test duration when not completed."""
        task = Task(
            task_id="task-1",
            title="Test",
            started_at=datetime(2025, 1, 1, 10, 0, 0),
        )
        assert task.duration_hours is None

    def test_is_blocked(self):
        """Test is_blocked property."""
        task = Task(task_id="task-1", title="Test")
        task.status = TaskStatus.WAITING_DEPENDENCY
        assert task.is_blocked is True

        task.status = TaskStatus.PENDING
        assert task.is_blocked is False

    def test_to_dict(self):
        """Test serialization."""
        task = Task(
            task_id="task-1",
            title="Test Task",
            priority=TaskPriority.HIGH,
        )
        data = task.to_dict()
        assert data["task_id"] == "task-1"
        assert data["priority"] == "high"


class TestProject:
    """Tests for Project dataclass."""

    def test_create_project(self):
        """Test project creation."""
        project = Project(
            project_id="proj-1",
            name="Test Project",
        )
        assert project.project_id == "proj-1"
        assert project.status == ProjectStatus.NOT_STARTED
        assert project.task_count == 0

    def test_add_task(self):
        """Test adding tasks."""
        project = Project(project_id="proj-1", name="Test")
        task = Task(task_id="task-1", title="Task 1")
        project.add_task(task)

        assert project.task_count == 1
        assert project.get_task("task-1") == task

    def test_progress_percent(self):
        """Test progress calculation."""
        project = Project(project_id="proj-1", name="Test")

        # Empty project
        assert project.progress_percent == 0.0

        # Add tasks
        task1 = Task(task_id="task-1", title="Task 1", status=TaskStatus.COMPLETED)
        task2 = Task(task_id="task-2", title="Task 2", status=TaskStatus.PENDING)
        project.add_task(task1)
        project.add_task(task2)

        assert project.progress_percent == 50.0

    def test_blocked_tasks(self):
        """Test blocked tasks property."""
        project = Project(project_id="proj-1", name="Test")
        task1 = Task(task_id="task-1", title="Task 1", status=TaskStatus.WAITING_DEPENDENCY)
        task2 = Task(task_id="task-2", title="Task 2", status=TaskStatus.PENDING)
        project.add_task(task1)
        project.add_task(task2)

        blocked = project.blocked_tasks
        assert len(blocked) == 1
        assert blocked[0].task_id == "task-1"

    def test_next_tasks(self):
        """Test next_tasks property."""
        project = Project(project_id="proj-1", name="Test")
        task1 = Task(task_id="task-1", title="Task 1", dependencies=["task-2"])
        task2 = Task(task_id="task-2", title="Task 2")  # No dependencies
        project.add_task(task1)
        project.add_task(task2)

        next_tasks = project.next_tasks
        assert len(next_tasks) == 1
        assert next_tasks[0].task_id == "task-2"

    def test_to_dict(self):
        """Test serialization."""
        project = Project(project_id="proj-1", name="Test Project")
        task = Task(task_id="task-1", title="Task 1")
        project.add_task(task)

        data = project.to_dict()
        assert data["project_id"] == "proj-1"
        assert data["name"] == "Test Project"
        assert len(data["tasks"]) == 1


class TestProjectManagerConfig:
    """Tests for ProjectManagerConfig."""

    def test_defaults(self):
        """Test default values."""
        config = ProjectManagerConfig()
        assert config.max_concurrent_projects == 5
        assert config.max_tasks_per_project == 100
        assert config.project_timeout == 3600
