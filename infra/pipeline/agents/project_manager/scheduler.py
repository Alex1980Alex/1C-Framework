"""
Scheduler for PROJECT-MANAGER Agent.

Handles task scheduling, prioritization, and resource allocation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum

from agents.project_manager.models import (
    Project,
    Task,
    TaskStatus,
    TaskPriority,
    ProjectStatus,
)
from agents.project_manager.dependency_tracker import DependencyTracker


class SchedulingStrategy(Enum):
    """Strategies for task scheduling."""

    PRIORITY_FIRST = "priority_first"      # High priority tasks first
    FIFO = "fifo"                          # First in, first out
    SHORTEST_FIRST = "shortest_first"      # Shortest estimated time first
    CRITICAL_PATH = "critical_path"        # Critical path method


@dataclass
class ScheduledTask:
    """A scheduled task with timing information."""

    task: Task
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None
    assigned_agent: Optional[str] = None
    parallel_group: int = 0  # Tasks in same group can run in parallel

    @property
    def estimated_duration(self) -> timedelta:
        """Get estimated duration."""
        hours = self.task.estimated_hours or 1.0
        return timedelta(hours=hours)


@dataclass
class Schedule:
    """Complete schedule for a project."""

    project_id: str
    scheduled_tasks: List[ScheduledTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY_FIRST

    @property
    def total_duration(self) -> timedelta:
        """Calculate total schedule duration."""
        if not self.scheduled_tasks:
            return timedelta()

        start = min(st.scheduled_start for st in self.scheduled_tasks)
        ends = [
            st.scheduled_end or (st.scheduled_start + st.estimated_duration)
            for st in self.scheduled_tasks
        ]
        end = max(ends)
        return end - start

    @property
    def parallel_groups_count(self) -> int:
        """Count parallel groups."""
        if not self.scheduled_tasks:
            return 0
        return max(st.parallel_group for st in self.scheduled_tasks) + 1

    def get_next_tasks(self, current_time: Optional[datetime] = None) -> List[ScheduledTask]:
        """Get tasks scheduled to start next."""
        current = current_time or datetime.now()
        return [
            st for st in self.scheduled_tasks
            if st.scheduled_start <= current and st.task.status == TaskStatus.PENDING
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "scheduled_tasks": [
                {
                    "task_id": st.task.task_id,
                    "title": st.task.title,
                    "scheduled_start": st.scheduled_start.isoformat(),
                    "scheduled_end": st.scheduled_end.isoformat() if st.scheduled_end else None,
                    "assigned_agent": st.assigned_agent,
                    "parallel_group": st.parallel_group,
                }
                for st in self.scheduled_tasks
            ],
            "created_at": self.created_at.isoformat(),
            "strategy": self.strategy.value,
            "total_duration_hours": self.total_duration.total_seconds() / 3600,
            "parallel_groups_count": self.parallel_groups_count,
        }


class TaskScheduler:
    """
    Task scheduler for project management.

    Provides:
    - Task prioritization
    - Scheduling based on dependencies
    - Resource allocation
    - Parallel execution planning
    """

    def __init__(self, dependency_tracker: Optional[DependencyTracker] = None) -> None:
        """Initialize scheduler."""
        self.dependency_tracker = dependency_tracker or DependencyTracker()

    def create_schedule(
        self,
        project: Project,
        strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY_FIRST,
        start_time: Optional[datetime] = None,
    ) -> Schedule:
        """
        Create schedule for project.

        Args:
            project: Project to schedule
            strategy: Scheduling strategy to use
            start_time: When to start schedule (default: now)

        Returns:
            Schedule for the project
        """
        start = start_time or datetime.now()
        schedule = Schedule(
            project_id=project.project_id,
            strategy=strategy,
        )

        # Get parallel groups
        parallel_groups = self.dependency_tracker.suggest_parallel_groups(project)

        if not parallel_groups:
            return schedule

        current_time = start
        for group_idx, group in enumerate(parallel_groups):
            # Sort group based on strategy
            sorted_group = self._sort_by_strategy(group, strategy)

            # Schedule each task in group
            for task in sorted_group:
                if task.status.is_terminal:
                    continue  # Skip completed/failed tasks

                scheduled = ScheduledTask(
                    task=task,
                    scheduled_start=current_time,
                    scheduled_end=current_time + timedelta(hours=task.estimated_hours or 1.0),
                    assigned_agent=task.assigned_agent,
                    parallel_group=group_idx,
                )
                schedule.scheduled_tasks.append(scheduled)

            # Move to next time slot after longest task in group
            if sorted_group:
                max_duration = max(
                    timedelta(hours=t.estimated_hours or 1.0)
                    for t in sorted_group
                )
                current_time += max_duration

        return schedule

    def _sort_by_strategy(
        self,
        tasks: List[Task],
        strategy: SchedulingStrategy,
    ) -> List[Task]:
        """Sort tasks based on scheduling strategy."""
        if strategy == SchedulingStrategy.PRIORITY_FIRST:
            return sorted(tasks, key=lambda t: t.priority.weight, reverse=True)
        elif strategy == SchedulingStrategy.FIFO:
            return sorted(tasks, key=lambda t: t.created_at)
        elif strategy == SchedulingStrategy.SHORTEST_FIRST:
            return sorted(tasks, key=lambda t: t.estimated_hours or float("inf"))
        elif strategy == SchedulingStrategy.CRITICAL_PATH:
            # Critical path: prioritize tasks with most dependents
            return sorted(
                tasks,
                key=lambda t: len(t.dependencies),
                reverse=True,
            )
        return tasks

    def get_next_task(self, project: Project) -> Optional[Task]:
        """
        Get the next task to execute.

        Args:
            project: Project to check

        Returns:
            Next task to execute, or None
        """
        ready = self.dependency_tracker.get_ready_tasks(project)
        if ready:
            return ready[0]  # Already sorted by priority
        return None

    def estimate_completion(
        self,
        project: Project,
        start_time: Optional[datetime] = None,
    ) -> datetime:
        """
        Estimate project completion time.

        Args:
            project: Project to estimate
            start_time: Start time (default: now)

        Returns:
            Estimated completion datetime
        """
        schedule = self.create_schedule(project, start_time=start_time)
        return (start_time or datetime.now()) + schedule.total_duration

    def get_critical_path(self, project: Project) -> List[Task]:
        """
        Get critical path through project.

        The critical path is the longest path through the dependency graph.

        Args:
            project: Project to analyze

        Returns:
            List of tasks on critical path
        """
        graph = self.dependency_tracker.build_graph(project)
        order = graph.topological_sort()

        if not order:
            return []

        task_map = {t.task_id: t for t in project.tasks}

        # Calculate longest path to each node
        distances: Dict[str, float] = {task_id: 0 for task_id in order}
        predecessors: Dict[str, Optional[str]] = {task_id: None for task_id in order}

        for task_id in order:
            task = task_map.get(task_id)
            if not task:
                continue

            duration = task.estimated_hours or 1.0

            for dep_id in task.dependencies:
                new_dist = distances.get(dep_id, 0) + duration
                if new_dist > distances.get(task_id, 0):
                    distances[task_id] = new_dist
                    predecessors[task_id] = dep_id

        # Find end of critical path
        if not distances:
            return []

        end_task = max(distances.keys(), key=lambda k: distances[k])

        # Trace back to get path
        path = []
        current = end_task
        while current:
            if current in task_map:
                path.append(task_map[current])
            current = predecessors.get(current)

        path.reverse()
        return path

    def allocate_to_agents(
        self,
        project: Project,
        available_agents: List[str],
    ) -> Dict[str, List[Task]]:
        """
        Allocate tasks to available agents.

        Args:
            project: Project with tasks
            available_agents: List of available agent names

        Returns:
            Dict mapping agent names to assigned tasks
        """
        if not available_agents:
            return {}

        allocation: Dict[str, List[Task]] = {agent: [] for agent in available_agents}

        # Get tasks in priority order
        ready = self.dependency_tracker.get_ready_tasks(project)

        for task in ready:
            # If task already assigned, keep assignment
            if task.assigned_agent and task.assigned_agent in available_agents:
                allocation[task.assigned_agent].append(task)
                continue

            # Find agent with least tasks
            min_agent = min(available_agents, key=lambda a: len(allocation[a]))
            allocation[min_agent].append(task)

        return allocation

    def rebalance_workload(
        self,
        project: Project,
        available_agents: List[str],
    ) -> List[Task]:
        """
        Rebalance workload and return tasks that need reassignment.

        Args:
            project: Project to rebalance
            available_agents: Available agents

        Returns:
            List of tasks that should be reassigned
        """
        if not available_agents:
            return []

        # Get current workload
        workload: Dict[str, float] = {agent: 0.0 for agent in available_agents}

        for task in project.tasks:
            if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent:
                if task.assigned_agent in workload:
                    workload[task.assigned_agent] += task.estimated_hours or 1.0

        # Find overloaded agents
        avg_workload = sum(workload.values()) / len(available_agents) if available_agents else 0
        overloaded_threshold = avg_workload * 1.5

        to_reassign = []
        for task in project.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            if task.assigned_agent and workload.get(task.assigned_agent, 0) > overloaded_threshold:
                to_reassign.append(task)

        return to_reassign
