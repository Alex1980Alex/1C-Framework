"""
Task Decomposer for Parallel Pipeline Execution.

Sprint 3.2.1: Определение независимых задач

This module provides functionality to:
- Decompose complex tasks into subtasks
- Build dependency graphs
- Find parallel execution groups
- Analyze task dependencies based on resources
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path

from .models import (
    TaskNode,
    TaskGraph,
    TaskDependency,
    DependencyType,
    ExecutionPriority,
    ParallelGroup,
    MergeStrategy,
    TaskStatus,
)
from constants import AgentRole, ArtifactType


# =============================================================================
# Task Decomposition Patterns
# =============================================================================

@dataclass
class DecompositionPattern:
    """Pattern for decomposing tasks based on keywords."""

    name: str
    keywords: list[str]
    subtask_generator: Callable[[str, str], list[TaskNode]]
    priority: ExecutionPriority = ExecutionPriority.NORMAL


@dataclass
class ResourcePattern:
    """Pattern for extracting resources from task descriptions."""

    pattern: str
    resource_type: str  # 'file', 'module', 'object', 'register'
    is_write: bool = False


# =============================================================================
# Task Decomposer
# =============================================================================

class TaskDecomposer:
    """
    Decomposes complex tasks into subtasks and builds dependency graphs.

    Responsibilities:
    - Parse task descriptions to identify subtasks
    - Extract resource dependencies (read/write)
    - Build TaskGraph with proper dependencies
    - Identify parallel execution groups
    """

    # 1C-specific resource patterns
    RESOURCE_PATTERNS: list[ResourcePattern] = [
        # Modules
        ResourcePattern(r"(?:модуль|module)\s+([А-Яа-яёЁ\w]+)", "module", False),
        ResourcePattern(r"(?:создать|create)\s+(?:модуль|module)\s+([А-Яа-яёЁ\w]+)", "module", True),
        ResourcePattern(r"(?:изменить|modify|update)\s+(?:модуль|module)\s+([А-Яа-яёЁ\w]+)", "module", True),

        # Documents
        ResourcePattern(r"(?:документ|document)\s+([А-Яа-яёЁ\w]+)", "document", False),
        ResourcePattern(r"(?:создать|добавить|изменить|create|add|modify)\s+(?:документ|document)\s+([А-Яа-яёЁ\w]+)", "document", True),

        # Catalogs
        ResourcePattern(r"(?:справочник|catalog)\s+([А-Яа-яёЁ\w]+)", "catalog", False),
        ResourcePattern(r"(?:создать|добавить|create|add)\s+(?:справочник|catalog)\s+([А-Яа-яёЁ\w]+)", "catalog", True),

        # Registers
        ResourcePattern(r"(?:регистр|register)\s+([А-Яа-яёЁ\w]+)", "register", False),
        ResourcePattern(r"(?:изменить|modify)\s+(?:регистр|register)\s+([А-Яа-яёЁ\w]+)", "register", True),

        # Reports
        ResourcePattern(r"(?:отчёт|отчет|report)\s+([А-Яа-яёЁ\w]+)", "report", False),
        ResourcePattern(r"(?:создать|добавить|create|add)\s+(?:отчёт|отчет|report)\s+([А-Яа-яёЁ\w]+)", "report", True),

        # Data Processors
        ResourcePattern(r"(?:обработка|dataprocessor|processing)\s+([А-Яа-яёЁ\w]+)", "dataprocessor", False),
        ResourcePattern(r"(?:изменить|modify)\s+(?:обработка|dataprocessor)\s+([А-Яа-яёЁ\w]+)", "dataprocessor", True),

        # Files
        ResourcePattern(r"(?:файл|file)\s+([^\s,]+\.bsl)", "file", False),
        ResourcePattern(r"(?:редактировать|edit|изменить|modify)\s+(?:файл|file)\s+([^\s,]+\.bsl)", "file", True),
    ]

    # Task type patterns
    TASK_PATTERNS: dict[str, list[str]] = {
        "analysis": ["анализ", "analyze", "исследовать", "изучить", "проверить"],
        "implementation": ["реализовать", "implement", "создать", "добавить", "написать"],
        "refactoring": ["рефакторинг", "refactor", "оптимизировать", "улучшить"],
        "testing": ["тест", "test", "проверить", "протестировать"],
        "documentation": ["документ", "document", "описать", "задокументировать"],
        "bugfix": ["исправить", "fix", "баг", "bug", "ошибка", "error"],
    }

    def __init__(
        self,
        project_id: str,
        project_path: Optional[str] = None,
        max_parallel_tasks: int = 4,
    ):
        """
        Initialize task decomposer.

        Args:
            project_id: Project identifier
            project_path: Path to project root
            max_parallel_tasks: Maximum tasks to run in parallel
        """
        self.project_id = project_id
        self.project_path = Path(project_path) if project_path else None
        self.max_parallel_tasks = max_parallel_tasks
        self._task_counter = 0

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        self._task_counter += 1
        return f"{self.project_id}-T{self._task_counter:03d}"

    def decompose(
        self,
        task_description: str,
        agent_role: AgentRole = AgentRole.IMPLEMENTER,
    ) -> TaskGraph:
        """
        Decompose a complex task into subtasks.

        Args:
            task_description: Natural language task description
            agent_role: Default agent role for subtasks

        Returns:
            TaskGraph with decomposed tasks and dependencies
        """
        graph = TaskGraph(id=self.project_id, name=f"Project {self.project_id}")

        # Detect task type
        task_type = self._detect_task_type(task_description)

        # Extract resources
        reads, writes = self._extract_resources(task_description)

        # Split into subtasks based on patterns
        subtasks = self._split_into_subtasks(task_description, task_type, agent_role)

        if not subtasks:
            # Single task, no decomposition needed
            main_task = TaskNode(
                id=self._generate_task_id(),
                name=f"Task: {task_description[:50]}...",
                description=task_description,
                agent_role=agent_role.value if hasattr(agent_role, 'value') else str(agent_role),
                agent_mode="BUILD",  # Default mode for implementation
                resources_read=reads,
                resources_write=writes,
                priority=self._determine_priority(task_type),
            )
            graph.add_task(main_task)
        else:
            # Add subtasks to graph
            for subtask in subtasks:
                graph.add_task(subtask)

            # Build dependencies between subtasks
            self._build_subtask_dependencies(graph, subtasks)

        return graph

    def _detect_task_type(self, description: str) -> str:
        """Detect task type from description."""
        description_lower = description.lower()

        for task_type, keywords in self.TASK_PATTERNS.items():
            for keyword in keywords:
                if keyword in description_lower:
                    return task_type

        return "implementation"  # default

    def _extract_resources(self, description: str) -> tuple[set[str], set[str]]:
        """
        Extract read and write resources from description.

        Returns:
            Tuple of (resources_read, resources_write)
        """
        reads: set[str] = set()
        writes: set[str] = set()

        for pattern in self.RESOURCE_PATTERNS:
            matches = re.findall(pattern.pattern, description, re.IGNORECASE)
            for match in matches:
                resource_id = f"{pattern.resource_type}:{match}"
                if pattern.is_write:
                    writes.add(resource_id)
                else:
                    reads.add(resource_id)

        return reads, writes

    def _split_into_subtasks(
        self,
        description: str,
        task_type: str,
        agent_role: AgentRole,
    ) -> list[TaskNode]:
        """Split task into subtasks based on structure."""
        subtasks: list[TaskNode] = []

        # Check for numbered list
        numbered_pattern = r"(?:^|\n)\s*(\d+)[.)]\s*(.+?)(?=\n\s*\d+[.)]|\n\n|$)"
        numbered_matches = re.findall(numbered_pattern, description, re.DOTALL)

        if len(numbered_matches) >= 2:
            for num, subtask_desc in numbered_matches:
                reads, writes = self._extract_resources(subtask_desc)
                subtask = TaskNode(
                    id=self._generate_task_id(),
                    name=f"Шаг {num}: {subtask_desc[:40]}...",
                    description=subtask_desc.strip(),
                    agent_role=agent_role.value if hasattr(agent_role, 'value') else str(agent_role),
                    agent_mode="BUILD",
                    resources_read=reads,
                    resources_write=writes,
                    priority=self._determine_priority(task_type),
                )
                subtasks.append(subtask)
            return subtasks

        # Check for bullet list
        bullet_pattern = r"(?:^|\n)\s*[-•*]\s*(.+?)(?=\n\s*[-•*]|\n\n|$)"
        bullet_matches = re.findall(bullet_pattern, description, re.DOTALL)

        if len(bullet_matches) >= 2:
            for i, subtask_desc in enumerate(bullet_matches, 1):
                reads, writes = self._extract_resources(subtask_desc)
                subtask = TaskNode(
                    id=self._generate_task_id(),
                    name=f"Подзадача {i}: {subtask_desc[:40]}...",
                    description=subtask_desc.strip(),
                    agent_role=agent_role.value if hasattr(agent_role, 'value') else str(agent_role),
                    agent_mode="BUILD",
                    resources_read=reads,
                    resources_write=writes,
                    priority=self._determine_priority(task_type),
                )
                subtasks.append(subtask)
            return subtasks

        # Check for "и" / "and" conjunctions with multiple actions
        conjunction_pattern = r"([^,]+(?:,\s*[^,]+)*)\s+и\s+([^,]+(?:,\s*[^,]+)*)"
        conjunction_match = re.search(conjunction_pattern, description, re.IGNORECASE)

        if conjunction_match:
            parts = [conjunction_match.group(1).strip(), conjunction_match.group(2).strip()]
            for i, part in enumerate(parts, 1):
                reads, writes = self._extract_resources(part)
                subtask = TaskNode(
                    id=self._generate_task_id(),
                    name=f"Часть {i}: {part[:40]}...",
                    description=part,
                    agent_role=agent_role.value if hasattr(agent_role, 'value') else str(agent_role),
                    agent_mode="BUILD",
                    resources_read=reads,
                    resources_write=writes,
                    priority=self._determine_priority(task_type),
                )
                subtasks.append(subtask)
            return subtasks

        return []  # No decomposition possible

    def _determine_priority(self, task_type: str) -> ExecutionPriority:
        """Determine task priority based on type."""
        priority_map = {
            "bugfix": ExecutionPriority.CRITICAL,
            "testing": ExecutionPriority.HIGH,
            "implementation": ExecutionPriority.NORMAL,
            "refactoring": ExecutionPriority.NORMAL,
            "analysis": ExecutionPriority.LOW,
            "documentation": ExecutionPriority.BACKGROUND,
        }
        return priority_map.get(task_type, ExecutionPriority.NORMAL)

    def _build_subtask_dependencies(
        self,
        graph: TaskGraph,
        subtasks: list[TaskNode],
    ) -> None:
        """Build dependencies between subtasks based on resources."""
        for i, task in enumerate(subtasks):
            for j, other_task in enumerate(subtasks):
                if i >= j:
                    continue

                # Check if task writes something that other_task reads
                # other_task depends on task (source=other, target=task)
                write_read_conflict = task.resources_write & other_task.resources_read
                if write_read_conflict:
                    graph.add_dependency(TaskDependency(
                        source_id=other_task.id,
                        target_id=task.id,
                        dependency_type=DependencyType.PRODUCES,
                    ))

                # Check if both write to the same resource
                write_write_conflict = task.resources_write & other_task.resources_write
                if write_write_conflict:
                    # other_task depends on task (task must complete first)
                    graph.add_dependency(TaskDependency(
                        source_id=other_task.id,
                        target_id=task.id,
                        dependency_type=DependencyType.MODIFIES,
                    ))

    def find_parallel_groups(self, graph: TaskGraph) -> list[ParallelGroup]:
        """
        Find groups of tasks that can be executed in parallel.

        Args:
            graph: TaskGraph to analyze

        Returns:
            List of ParallelGroup instances
        """
        return graph.find_parallel_groups(max_group_size=self.max_parallel_tasks)

    def build_execution_plan(
        self,
        graph: TaskGraph,
    ) -> list[list[TaskNode]]:
        """
        Build execution plan as waves of parallel tasks.

        Args:
            graph: TaskGraph to plan

        Returns:
            List of waves, each wave is a list of tasks to run in parallel
        """
        plan: list[list[TaskNode]] = []
        remaining = set(graph.tasks.keys())
        completed: set[str] = set()

        while remaining:
            # Find tasks with all dependencies satisfied
            ready: list[TaskNode] = []
            for task_id in remaining:
                task = graph.tasks[task_id]
                deps = graph.get_dependencies(task_id)

                # Check if all dependencies are completed
                # deps contains TaskDependency where source_id == task_id
                # target_id is the task that must complete first
                if all(d.target_id in completed for d in deps):
                    ready.append(task)

            if not ready:
                # Circular dependency or error
                break

            # Limit parallel tasks
            wave = ready[:self.max_parallel_tasks]
            plan.append(wave)

            # Mark as completed
            for task in wave:
                remaining.remove(task.id)
                completed.add(task.id)

        return plan


# =============================================================================
# Convenience Functions
# =============================================================================

def decompose_task(
    task_description: str,
    project_id: str,
    agent_role: AgentRole = AgentRole.IMPLEMENTER,
) -> TaskGraph:
    """
    Decompose a task into subtasks.

    Args:
        task_description: Natural language task description
        project_id: Project identifier
        agent_role: Default agent role

    Returns:
        TaskGraph with decomposed tasks
    """
    decomposer = TaskDecomposer(project_id=project_id)
    return decomposer.decompose(task_description, agent_role)


def find_parallel_groups(
    graph: TaskGraph,
    max_group_size: int = 4,
) -> list[ParallelGroup]:
    """
    Find parallel execution groups in a task graph.

    Args:
        graph: TaskGraph to analyze
        max_group_size: Maximum tasks per group

    Returns:
        List of ParallelGroup instances
    """
    return graph.find_parallel_groups(max_group_size=max_group_size)


def build_dependency_graph(
    tasks: list[TaskNode],
    auto_detect_dependencies: bool = True,
) -> TaskGraph:
    """
    Build a TaskGraph from a list of tasks.

    Args:
        tasks: List of TaskNode instances
        auto_detect_dependencies: Whether to auto-detect resource dependencies

    Returns:
        TaskGraph with tasks and dependencies
    """
    if not tasks:
        return TaskGraph(id="default", name="Default Graph")

    # Extract project_id from first task
    project_id = tasks[0].id.split("-")[0] if "-" in tasks[0].id else "default"
    graph = TaskGraph(id=project_id, name=f"Graph {project_id}")

    # Add tasks
    for task in tasks:
        graph.add_task(task)

    if auto_detect_dependencies:
        # Build dependencies based on resources
        for i, task in enumerate(tasks):
            for j, other_task in enumerate(tasks):
                if i >= j:
                    continue

                # Write-Read dependency
                # other_task depends on task (task writes, other reads)
                if task.resources_write & other_task.resources_read:
                    graph.add_dependency(TaskDependency(
                        source_id=other_task.id,
                        target_id=task.id,
                        dependency_type=DependencyType.PRODUCES,
                    ))

                # Write-Write conflict (sequential)
                # other_task depends on task (task must complete first)
                if task.resources_write & other_task.resources_write:
                    graph.add_dependency(TaskDependency(
                        source_id=other_task.id,
                        target_id=task.id,
                        dependency_type=DependencyType.MODIFIES,
                    ))

    return graph


def analyze_parallelism(graph: TaskGraph) -> dict:
    """
    Analyze parallelism potential in a task graph.

    Args:
        graph: TaskGraph to analyze

    Returns:
        Analysis results dictionary
    """
    total_tasks = len(graph.tasks)
    if total_tasks == 0:
        return {
            "total_tasks": 0,
            "parallel_groups": 0,
            "max_parallelism": 0,
            "parallelism_ratio": 0.0,
            "critical_path_length": 0,
        }

    # Find parallel groups
    groups = graph.find_parallel_groups()
    max_parallelism = max(len(g.tasks) for g in groups) if groups else 1

    # Calculate critical path (longest path in DAG)
    # Using topological order to find longest path
    topo_order = graph.topological_sort()
    distances: dict[str, int] = {task_id: 0 for task_id in graph.tasks}

    for task_id in topo_order:
        for dep in graph.get_dependencies(task_id):
            # dep.target_id is the task that must complete first
            if dep.target_id in distances:
                distances[task_id] = max(
                    distances[task_id],
                    distances[dep.target_id] + 1
                )

    critical_path_length = max(distances.values()) + 1 if distances else 1

    # Parallelism ratio: ideal parallel execution time / sequential time
    # Higher is better (more parallelism possible)
    parallelism_ratio = total_tasks / critical_path_length if critical_path_length > 0 else 1.0

    return {
        "total_tasks": total_tasks,
        "parallel_groups": len(groups),
        "max_parallelism": max_parallelism,
        "parallelism_ratio": round(parallelism_ratio, 2),
        "critical_path_length": critical_path_length,
        "groups_detail": [
            {
                "group_id": g.id,
                "size": len(g.tasks),
                "merge_strategy": g.merge_strategy.value,
            }
            for g in groups
        ],
    }
