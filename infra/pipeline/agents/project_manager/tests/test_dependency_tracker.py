"""Tests for DependencyTracker."""

import pytest

from agents.project_manager.models import Project, Task, TaskStatus, TaskPriority
from agents.project_manager.dependency_tracker import DependencyGraph, DependencyTracker


class TestDependencyGraph:
    """Tests for DependencyGraph."""

    def test_add_node(self):
        """Test adding nodes."""
        graph = DependencyGraph()
        graph.add_node("task-1")
        graph.add_node("task-2")

        assert "task-1" in graph.nodes
        assert "task-2" in graph.nodes

    def test_add_edge(self):
        """Test adding edges."""
        graph = DependencyGraph()
        graph.add_edge("task-1", "task-2")

        assert "task-1" in graph.nodes
        assert "task-2" in graph.nodes
        assert "task-2" in graph.edges["task-1"]
        assert "task-1" in graph.reverse_edges["task-2"]

    def test_get_dependents(self):
        """Test getting dependents."""
        graph = DependencyGraph()
        graph.add_edge("task-1", "task-2")
        graph.add_edge("task-1", "task-3")

        dependents = graph.get_dependents("task-1")
        assert len(dependents) == 2
        assert "task-2" in dependents
        assert "task-3" in dependents

    def test_get_dependencies(self):
        """Test getting dependencies."""
        graph = DependencyGraph()
        graph.add_edge("task-1", "task-3")
        graph.add_edge("task-2", "task-3")

        deps = graph.get_dependencies("task-3")
        assert len(deps) == 2
        assert "task-1" in deps
        assert "task-2" in deps

    def test_has_cycle_no_cycle(self):
        """Test cycle detection without cycle."""
        graph = DependencyGraph()
        graph.add_edge("task-1", "task-2")
        graph.add_edge("task-2", "task-3")

        assert graph.has_cycle() is False

    def test_has_cycle_with_cycle(self):
        """Test cycle detection with cycle."""
        graph = DependencyGraph()
        graph.add_edge("task-1", "task-2")
        graph.add_edge("task-2", "task-3")
        graph.add_edge("task-3", "task-1")  # Creates cycle

        assert graph.has_cycle() is True

    def test_topological_sort(self):
        """Test topological sorting."""
        graph = DependencyGraph()
        graph.add_edge("task-1", "task-2")
        graph.add_edge("task-1", "task-3")
        graph.add_edge("task-2", "task-4")
        graph.add_edge("task-3", "task-4")

        order = graph.topological_sort()
        assert order is not None
        assert order.index("task-1") < order.index("task-2")
        assert order.index("task-1") < order.index("task-3")
        assert order.index("task-2") < order.index("task-4")
        assert order.index("task-3") < order.index("task-4")

    def test_topological_sort_with_cycle(self):
        """Test topological sort with cycle returns None."""
        graph = DependencyGraph()
        graph.add_edge("task-1", "task-2")
        graph.add_edge("task-2", "task-1")

        order = graph.topological_sort()
        assert order is None


class TestDependencyTracker:
    """Tests for DependencyTracker."""

    @pytest.fixture
    def simple_project(self):
        """Create simple project with dependencies."""
        project = Project(project_id="proj-1", name="Test")
        task1 = Task(task_id="task-1", title="Task 1")
        task2 = Task(task_id="task-2", title="Task 2", dependencies=["task-1"])
        task3 = Task(task_id="task-3", title="Task 3", dependencies=["task-1"])
        task4 = Task(task_id="task-4", title="Task 4", dependencies=["task-2", "task-3"])
        project.add_task(task1)
        project.add_task(task2)
        project.add_task(task3)
        project.add_task(task4)
        return project

    def test_build_graph(self, simple_project):
        """Test building dependency graph."""
        tracker = DependencyTracker()
        graph = tracker.build_graph(simple_project)

        assert len(graph.nodes) == 4
        assert "task-2" in graph.edges["task-1"]
        assert "task-3" in graph.edges["task-1"]

    def test_validate_dependencies_valid(self, simple_project):
        """Test validation of valid dependencies."""
        tracker = DependencyTracker()
        is_valid, errors = tracker.validate_dependencies(simple_project)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_dependencies_missing(self):
        """Test validation with missing dependency."""
        project = Project(project_id="proj-1", name="Test")
        task = Task(task_id="task-1", title="Task 1", dependencies=["non-existent"])
        project.add_task(task)

        tracker = DependencyTracker()
        is_valid, errors = tracker.validate_dependencies(project)

        assert is_valid is False
        assert len(errors) == 1
        assert "non-existent" in errors[0]

    def test_validate_dependencies_cycle(self):
        """Test validation with circular dependency."""
        project = Project(project_id="proj-1", name="Test")
        task1 = Task(task_id="task-1", title="Task 1", dependencies=["task-2"])
        task2 = Task(task_id="task-2", title="Task 2", dependencies=["task-1"])
        project.add_task(task1)
        project.add_task(task2)

        tracker = DependencyTracker()
        is_valid, errors = tracker.validate_dependencies(project)

        assert is_valid is False
        assert any("Circular" in e for e in errors)

    def test_get_execution_order(self, simple_project):
        """Test getting execution order."""
        tracker = DependencyTracker()
        order = tracker.get_execution_order(simple_project)

        assert order is not None
        assert len(order) == 4

        # task-1 must come before task-2 and task-3
        ids = [t.task_id for t in order]
        assert ids.index("task-1") < ids.index("task-2")
        assert ids.index("task-1") < ids.index("task-3")
        # task-2 and task-3 must come before task-4
        assert ids.index("task-2") < ids.index("task-4")
        assert ids.index("task-3") < ids.index("task-4")

    def test_get_ready_tasks(self, simple_project):
        """Test getting ready tasks."""
        tracker = DependencyTracker()
        ready = tracker.get_ready_tasks(simple_project)

        # Only task-1 has no dependencies
        assert len(ready) == 1
        assert ready[0].task_id == "task-1"

    def test_get_ready_tasks_after_completion(self, simple_project):
        """Test ready tasks after some completion."""
        # Complete task-1
        simple_project.get_task("task-1").status = TaskStatus.COMPLETED

        tracker = DependencyTracker()
        ready = tracker.get_ready_tasks(simple_project)

        # task-2 and task-3 should be ready now
        assert len(ready) == 2
        ready_ids = {t.task_id for t in ready}
        assert "task-2" in ready_ids
        assert "task-3" in ready_ids

    def test_get_blocked_tasks(self, simple_project):
        """Test getting blocked tasks."""
        # Set task-2 as waiting
        simple_project.get_task("task-2").status = TaskStatus.WAITING_DEPENDENCY

        tracker = DependencyTracker()
        blocked = tracker.get_blocked_tasks(simple_project)

        # task-2, task-3, task-4 are waiting on dependencies
        assert len(blocked) >= 1
        task_ids = {t.task_id for t, _ in blocked}
        assert "task-2" in task_ids

    def test_can_start(self, simple_project):
        """Test can_start check."""
        tracker = DependencyTracker()

        # task-1 can start (no dependencies)
        can_start, unmet = tracker.can_start(simple_project, "task-1")
        assert can_start is True
        assert len(unmet) == 0

        # task-2 cannot start (depends on task-1)
        can_start, unmet = tracker.can_start(simple_project, "task-2")
        assert can_start is False
        assert "task-1" in unmet

    def test_get_impact_of_failure(self, simple_project):
        """Test impact analysis of task failure."""
        tracker = DependencyTracker()
        impacted = tracker.get_impact_of_failure(simple_project, "task-1")

        # All other tasks depend on task-1
        impacted_ids = {t.task_id for t in impacted}
        assert "task-2" in impacted_ids
        assert "task-3" in impacted_ids
        assert "task-4" in impacted_ids

    def test_suggest_parallel_groups(self, simple_project):
        """Test parallel group suggestion."""
        tracker = DependencyTracker()
        groups = tracker.suggest_parallel_groups(simple_project)

        assert len(groups) == 3  # 3 levels

        # Level 0: task-1
        level0_ids = {t.task_id for t in groups[0]}
        assert "task-1" in level0_ids

        # Level 1: task-2, task-3
        level1_ids = {t.task_id for t in groups[1]}
        assert "task-2" in level1_ids
        assert "task-3" in level1_ids

        # Level 2: task-4
        level2_ids = {t.task_id for t in groups[2]}
        assert "task-4" in level2_ids
