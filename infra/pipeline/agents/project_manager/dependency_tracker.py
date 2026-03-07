"""
Dependency Tracker for PROJECT-MANAGER Agent.

Manages task dependencies and determines execution order.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict

from agents.project_manager.models import (
    Project,
    Task,
    TaskStatus,
    TaskDependency,
    DependencyType,
)


@dataclass
class DependencyGraph:
    """Graph representation of task dependencies."""

    nodes: Set[str] = field(default_factory=set)  # task_ids
    edges: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))  # task_id -> [dependent_task_ids]
    reverse_edges: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))  # task_id -> [dependency_task_ids]

    def add_node(self, task_id: str) -> None:
        """Add node to graph."""
        self.nodes.add(task_id)

    def add_edge(self, from_task: str, to_task: str) -> None:
        """
        Add dependency edge.

        Args:
            from_task: Task that must complete first
            to_task: Task that depends on from_task
        """
        self.nodes.add(from_task)
        self.nodes.add(to_task)
        self.edges[from_task].append(to_task)
        self.reverse_edges[to_task].append(from_task)

    def get_dependents(self, task_id: str) -> List[str]:
        """Get tasks that depend on this task."""
        return self.edges.get(task_id, [])

    def get_dependencies(self, task_id: str) -> List[str]:
        """Get tasks this task depends on."""
        return self.reverse_edges.get(task_id, [])

    def has_cycle(self) -> bool:
        """Check if graph has cycles."""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.edges.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in self.nodes:
            if node not in visited:
                if dfs(node):
                    return True

        return False

    def topological_sort(self) -> Optional[List[str]]:
        """
        Get topological ordering of tasks.

        Returns:
            List of task_ids in execution order, or None if cycle exists
        """
        if self.has_cycle():
            return None

        in_degree = {node: 0 for node in self.nodes}
        for deps in self.edges.values():
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0) + 1

        queue = [node for node in self.nodes if in_degree.get(node, 0) == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for dependent in self.edges.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self.nodes):
            return None  # Cycle detected

        return result


class DependencyTracker:
    """
    Tracks and manages task dependencies.

    Provides:
    - Dependency graph construction
    - Cycle detection
    - Execution order calculation
    - Blocked task identification
    """

    def __init__(self) -> None:
        """Initialize tracker."""
        self._graphs: Dict[str, DependencyGraph] = {}

    def build_graph(self, project: Project) -> DependencyGraph:
        """
        Build dependency graph for project.

        Args:
            project: Project to analyze

        Returns:
            DependencyGraph for the project
        """
        graph = DependencyGraph()

        # Add all tasks as nodes
        for task in project.tasks:
            graph.add_node(task.task_id)

        # Add dependency edges
        for task in project.tasks:
            for dep_id in task.dependencies:
                graph.add_edge(dep_id, task.task_id)

        self._graphs[project.project_id] = graph
        return graph

    def get_graph(self, project_id: str) -> Optional[DependencyGraph]:
        """Get cached graph for project."""
        return self._graphs.get(project_id)

    def validate_dependencies(self, project: Project) -> Tuple[bool, List[str]]:
        """
        Validate project dependencies.

        Args:
            project: Project to validate

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        task_ids = {t.task_id for t in project.tasks}

        # Check for missing dependencies
        for task in project.tasks:
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    errors.append(
                        f"Task '{task.task_id}' depends on non-existent task '{dep_id}'"
                    )

        # Check for cycles
        graph = self.build_graph(project)
        if graph.has_cycle():
            errors.append("Circular dependency detected in project")

        return len(errors) == 0, errors

    def get_execution_order(self, project: Project) -> Optional[List[Task]]:
        """
        Get tasks in execution order.

        Args:
            project: Project to analyze

        Returns:
            List of tasks in execution order, or None if invalid
        """
        graph = self.build_graph(project)
        order = graph.topological_sort()

        if order is None:
            return None

        # Map IDs to tasks
        task_map = {t.task_id: t for t in project.tasks}
        return [task_map[task_id] for task_id in order if task_id in task_map]

    def get_ready_tasks(self, project: Project) -> List[Task]:
        """
        Get tasks ready for execution.

        A task is ready if:
        - Status is PENDING
        - All dependencies are COMPLETED

        Args:
            project: Project to check

        Returns:
            List of ready tasks sorted by priority
        """
        completed_ids = {
            t.task_id for t in project.tasks
            if t.status == TaskStatus.COMPLETED
        }

        ready = []
        for task in project.tasks:
            if task.status != TaskStatus.PENDING:
                continue

            deps_met = all(dep in completed_ids for dep in task.dependencies)
            if deps_met:
                ready.append(task)

        # Sort by priority (highest first)
        ready.sort(key=lambda t: t.priority.weight, reverse=True)
        return ready

    def get_blocked_tasks(self, project: Project) -> List[Tuple[Task, List[str]]]:
        """
        Get blocked tasks with their unmet dependencies.

        Args:
            project: Project to check

        Returns:
            List of (task, unmet_dependency_ids) tuples
        """
        completed_ids = {
            t.task_id for t in project.tasks
            if t.status == TaskStatus.COMPLETED
        }

        blocked = []
        for task in project.tasks:
            if task.status not in (TaskStatus.PENDING, TaskStatus.WAITING_DEPENDENCY):
                continue

            unmet = [dep for dep in task.dependencies if dep not in completed_ids]
            if unmet:
                blocked.append((task, unmet))

        return blocked

    def can_start(self, project: Project, task_id: str) -> Tuple[bool, List[str]]:
        """
        Check if task can start.

        Args:
            project: Project containing task
            task_id: Task to check

        Returns:
            Tuple of (can_start, list of unmet dependency IDs)
        """
        task = project.get_task(task_id)
        if not task:
            return False, [f"Task '{task_id}' not found"]

        if task.status != TaskStatus.PENDING:
            return False, [f"Task status is '{task.status.value}', not pending"]

        completed_ids = {
            t.task_id for t in project.tasks
            if t.status == TaskStatus.COMPLETED
        }

        unmet = [dep for dep in task.dependencies if dep not in completed_ids]
        return len(unmet) == 0, unmet

    def get_impact_of_failure(self, project: Project, task_id: str) -> List[Task]:
        """
        Get tasks that would be blocked if a task fails.

        Args:
            project: Project to analyze
            task_id: Failed task ID

        Returns:
            List of tasks that would be blocked
        """
        graph = self.build_graph(project)

        # Find all tasks reachable from failed task
        blocked_ids = set()
        queue = graph.get_dependents(task_id)

        while queue:
            current = queue.pop(0)
            if current not in blocked_ids:
                blocked_ids.add(current)
                queue.extend(graph.get_dependents(current))

        # Map to tasks
        task_map = {t.task_id: t for t in project.tasks}
        return [task_map[tid] for tid in blocked_ids if tid in task_map]

    def suggest_parallel_groups(self, project: Project) -> List[List[Task]]:
        """
        Suggest groups of tasks that can run in parallel.

        Args:
            project: Project to analyze

        Returns:
            List of task groups that can run in parallel
        """
        graph = self.build_graph(project)
        order = graph.topological_sort()

        if order is None:
            return []

        # Group by level (tasks at same level can run in parallel)
        levels: Dict[str, int] = {}

        for task_id in order:
            deps = graph.get_dependencies(task_id)
            if not deps:
                levels[task_id] = 0
            else:
                levels[task_id] = max(levels.get(d, 0) for d in deps) + 1

        # Group tasks by level
        groups: Dict[int, List[str]] = defaultdict(list)
        for task_id, level in levels.items():
            groups[level].append(task_id)

        # Map to tasks
        task_map = {t.task_id: t for t in project.tasks}
        result = []
        for level in sorted(groups.keys()):
            group = [task_map[tid] for tid in groups[level] if tid in task_map]
            if group:
                result.append(group)

        return result
