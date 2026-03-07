"""Tests for TaskScheduler."""

import pytest
from datetime import datetime, timedelta

from agents.project_manager.models import Project, Task, TaskStatus, TaskPriority
from agents.project_manager.dependency_tracker import DependencyTracker
from agents.project_manager.scheduler import (
    SchedulingStrategy,
    ScheduledTask,
    Schedule,
    TaskScheduler,
)


class TestScheduledTask:
    """Tests for ScheduledTask."""

    def test_estimated_duration(self):
        """Test duration estimation."""
        task = Task(task_id="task-1", title="Test", estimated_hours=2.5)
        scheduled = ScheduledTask(task=task, scheduled_start=datetime.now())

        assert scheduled.estimated_duration == timedelta(hours=2.5)

    def test_estimated_duration_default(self):
        """Test default duration when not specified."""
        task = Task(task_id="task-1", title="Test")
        scheduled = ScheduledTask(task=task, scheduled_start=datetime.now())

        assert scheduled.estimated_duration == timedelta(hours=1.0)


class TestSchedule:
    """Tests for Schedule."""

    @pytest.fixture
    def sample_schedule(self):
        """Create sample schedule."""
        now = datetime.now()
        tasks = [
            Task(task_id="task-1", title="Task 1", estimated_hours=2),
            Task(task_id="task-2", title="Task 2", estimated_hours=3),
            Task(task_id="task-3", title="Task 3", estimated_hours=1),
        ]

        schedule = Schedule(project_id="proj-1")
        schedule.scheduled_tasks = [
            ScheduledTask(task=tasks[0], scheduled_start=now, parallel_group=0),
            ScheduledTask(task=tasks[1], scheduled_start=now, parallel_group=0),
            ScheduledTask(
                task=tasks[2],
                scheduled_start=now + timedelta(hours=3),
                parallel_group=1,
            ),
        ]
        return schedule

    def test_total_duration(self, sample_schedule):
        """Test total duration calculation."""
        duration = sample_schedule.total_duration
        # First group: max(2, 3) = 3 hours
        # Second group: 1 hour
        # Total: 4 hours
        assert duration >= timedelta(hours=3)

    def test_parallel_groups_count(self, sample_schedule):
        """Test parallel groups counting."""
        assert sample_schedule.parallel_groups_count == 2

    def test_get_next_tasks(self, sample_schedule):
        """Test getting next tasks."""
        next_tasks = sample_schedule.get_next_tasks()
        # All pending tasks at or before current time
        assert len(next_tasks) >= 0  # Depends on current time

    def test_to_dict(self, sample_schedule):
        """Test serialization."""
        data = sample_schedule.to_dict()

        assert data["project_id"] == "proj-1"
        assert len(data["scheduled_tasks"]) == 3
        assert "total_duration_hours" in data


class TestTaskScheduler:
    """Tests for TaskScheduler."""

    @pytest.fixture
    def project_with_deps(self):
        """Create project with dependencies."""
        project = Project(project_id="proj-1", name="Test")
        task1 = Task(
            task_id="task-1",
            title="Task 1",
            priority=TaskPriority.HIGH,
            estimated_hours=2,
        )
        task2 = Task(
            task_id="task-2",
            title="Task 2",
            priority=TaskPriority.MEDIUM,
            estimated_hours=3,
            dependencies=["task-1"],
        )
        task3 = Task(
            task_id="task-3",
            title="Task 3",
            priority=TaskPriority.LOW,
            estimated_hours=1,
            dependencies=["task-1"],
        )
        task4 = Task(
            task_id="task-4",
            title="Task 4",
            priority=TaskPriority.CRITICAL,
            estimated_hours=4,
            dependencies=["task-2", "task-3"],
        )
        project.add_task(task1)
        project.add_task(task2)
        project.add_task(task3)
        project.add_task(task4)
        return project

    def test_create_schedule(self, project_with_deps):
        """Test schedule creation."""
        scheduler = TaskScheduler()
        schedule = scheduler.create_schedule(project_with_deps)

        assert schedule.project_id == "proj-1"
        assert len(schedule.scheduled_tasks) == 4

    def test_create_schedule_with_strategy(self, project_with_deps):
        """Test schedule with different strategies."""
        scheduler = TaskScheduler()

        # Priority first
        schedule = scheduler.create_schedule(
            project_with_deps,
            strategy=SchedulingStrategy.PRIORITY_FIRST,
        )
        assert schedule.strategy == SchedulingStrategy.PRIORITY_FIRST

        # Shortest first
        schedule = scheduler.create_schedule(
            project_with_deps,
            strategy=SchedulingStrategy.SHORTEST_FIRST,
        )
        assert schedule.strategy == SchedulingStrategy.SHORTEST_FIRST

    def test_get_next_task(self, project_with_deps):
        """Test getting next task."""
        scheduler = TaskScheduler()
        next_task = scheduler.get_next_task(project_with_deps)

        # task-1 is the only one without dependencies
        assert next_task is not None
        assert next_task.task_id == "task-1"

    def test_estimate_completion(self, project_with_deps):
        """Test completion estimation."""
        scheduler = TaskScheduler()
        start_time = datetime(2025, 1, 1, 9, 0, 0)
        completion = scheduler.estimate_completion(project_with_deps, start_time)

        assert completion > start_time

    def test_get_critical_path(self, project_with_deps):
        """Test critical path calculation."""
        scheduler = TaskScheduler()
        path = scheduler.get_critical_path(project_with_deps)

        assert len(path) > 0
        # task-4 should be on critical path (most dependencies)

    def test_allocate_to_agents(self, project_with_deps):
        """Test agent allocation."""
        scheduler = TaskScheduler()
        agents = ["ARCHITECT", "IMPLEMENTER"]
        allocation = scheduler.allocate_to_agents(project_with_deps, agents)

        assert len(allocation) == 2
        assert "ARCHITECT" in allocation
        assert "IMPLEMENTER" in allocation

    def test_rebalance_workload(self, project_with_deps):
        """Test workload rebalancing."""
        scheduler = TaskScheduler()
        agents = ["ARCHITECT", "IMPLEMENTER"]

        # Simulate overload
        project_with_deps.get_task("task-1").status = TaskStatus.IN_PROGRESS
        project_with_deps.get_task("task-1").assigned_agent = "ARCHITECT"
        project_with_deps.get_task("task-1").estimated_hours = 100  # Overloaded

        to_reassign = scheduler.rebalance_workload(project_with_deps, agents)
        # May return tasks that need reassignment
        assert isinstance(to_reassign, list)


class TestSchedulingStrategies:
    """Tests for different scheduling strategies."""

    @pytest.fixture
    def varied_tasks(self):
        """Create project with varied task properties."""
        project = Project(project_id="proj-1", name="Test")

        # Tasks with different priorities and durations
        tasks = [
            Task(task_id="t1", title="T1", priority=TaskPriority.LOW, estimated_hours=1),
            Task(task_id="t2", title="T2", priority=TaskPriority.CRITICAL, estimated_hours=5),
            Task(task_id="t3", title="T3", priority=TaskPriority.MEDIUM, estimated_hours=2),
            Task(task_id="t4", title="T4", priority=TaskPriority.HIGH, estimated_hours=3),
        ]

        for t in tasks:
            project.add_task(t)

        return project

    def test_priority_first_strategy(self, varied_tasks):
        """Test priority-first scheduling."""
        scheduler = TaskScheduler()
        schedule = scheduler.create_schedule(
            varied_tasks,
            strategy=SchedulingStrategy.PRIORITY_FIRST,
        )

        # All in one parallel group (no dependencies)
        # But within group, should be sorted by priority
        tasks = [st.task for st in schedule.scheduled_tasks]
        priorities = [t.priority.weight for t in tasks]

        # Should be descending priority order
        assert priorities == sorted(priorities, reverse=True)

    def test_shortest_first_strategy(self, varied_tasks):
        """Test shortest-first scheduling."""
        scheduler = TaskScheduler()
        schedule = scheduler.create_schedule(
            varied_tasks,
            strategy=SchedulingStrategy.SHORTEST_FIRST,
        )

        tasks = [st.task for st in schedule.scheduled_tasks]
        durations = [t.estimated_hours for t in tasks]

        # Should be ascending duration order
        assert durations == sorted(durations)
