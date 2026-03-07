"""
Models for Parallel Pipeline Orchestration.

Sprint 3.2: Data structures for task decomposition, parallel execution,
and result merging.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import hashlib
import json


class DependencyType(str, Enum):
    """Types of dependencies between tasks."""

    # Hard dependencies - must complete before dependent can start
    PRODUCES = "produces"       # Task A produces artifact needed by B
    REQUIRES = "requires"       # Task A requires completion of B
    MODIFIES = "modifies"       # Task A modifies resource used by B

    # Soft dependencies - preferred but not required
    PREFERS = "prefers"         # Better if A runs before B
    SUGGESTS = "suggests"       # Hint for optimization

    @property
    def is_hard(self) -> bool:
        """Check if this is a hard (blocking) dependency."""
        return self in (
            DependencyType.PRODUCES,
            DependencyType.REQUIRES,
            DependencyType.MODIFIES,
        )


class ExecutionPriority(str, Enum):
    """Priority levels for task execution."""

    CRITICAL = "critical"       # Must run first, blocking
    HIGH = "high"               # Prefer to run early
    NORMAL = "normal"           # Standard priority
    LOW = "low"                 # Can be deferred
    BACKGROUND = "background"   # Run when resources available


class TaskStatus(str, Enum):
    """Status of a task in execution."""

    PENDING = "pending"         # Not yet started
    WAITING = "waiting"         # Waiting for dependencies
    READY = "ready"             # All dependencies satisfied, ready to run
    RUNNING = "running"         # Currently executing
    COMPLETED = "completed"     # Successfully completed
    FAILED = "failed"           # Failed with error
    CANCELLED = "cancelled"     # Cancelled by user or system
    SKIPPED = "skipped"         # Skipped due to conditions


class MergeStrategy(str, Enum):
    """Strategies for merging parallel results."""

    COMBINE = "combine"             # Merge dicts, concatenate lists/strings
    OVERRIDE = "override"           # Last value wins
    CONCATENATE = "concatenate"     # Append results sequentially
    AGGREGATE = "aggregate"         # Combine into structured format
    BEST_WINS = "best_wins"         # Take result with best quality score
    UNION = "union"                 # Merge unique items from all results
    INTERSECTION = "intersection"   # Keep only common items
    WEIGHTED = "weighted"           # Weighted combination based on priority


class ConflictType(str, Enum):
    """Types of conflicts between parallel tasks."""

    WRITE_WRITE = "write_write"             # Multiple tasks write to same resource
    WRITE_READ = "write_read"               # Write conflicts with read dependency
    FILE_COLLISION = "file_collision"       # Multiple tasks modify same file
    RESOURCE_LOCK = "resource_lock"         # Competing for same resource
    DATA_INCONSISTENCY = "data_inconsistency"  # Conflicting data changes
    ARTIFACT_OVERLAP = "artifact_overlap"   # Overlapping artifact contents
    SEQUENCE_VIOLATION = "sequence_violation"  # Order dependency violated


class ConflictResolution(str, Enum):
    """Resolution strategies for conflicts."""

    UNRESOLVED = "unresolved"           # Not yet resolved
    TAKE_FIRST = "take_first"           # Take first task's result
    TAKE_LAST = "take_last"             # Take last task's result
    PRIORITY_WINS = "priority_wins"     # Higher priority task wins
    LATEST_WINS = "latest_wins"         # Latest completion wins
    MERGE_MANUAL = "merge_manual"       # Require manual merge
    MERGE_AUTO = "merge_auto"           # Automatic merge attempt
    ABORT = "abort"                     # Abort conflicting tasks
    RETRY = "retry"                     # Retry with serialization
    MERGED = "merged"                   # Successfully merged results
    SKIPPED = "skipped"                 # Conflict skipped


@dataclass
class TaskDependency:
    """Represents a dependency between two tasks."""

    source_id: str              # Task that depends on target
    target_id: str              # Task that must complete first
    dependency_type: DependencyType
    artifact_name: Optional[str] = None  # Specific artifact if applicable
    condition: Optional[str] = None       # Conditional expression

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "dependency_type": self.dependency_type.value,
            "artifact_name": self.artifact_name,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskDependency":
        """Create from dictionary."""
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            dependency_type=DependencyType(data["dependency_type"]),
            artifact_name=data.get("artifact_name"),
            condition=data.get("condition"),
        )


@dataclass
class TaskNode:
    """Represents a single task in the execution graph."""

    id: str
    name: str = ""
    description: str = ""
    agent_role: str = "IMPLEMENTER"  # AgentRole value as string
    agent_mode: str = "BUILD"  # AgentMode value as string

    # Execution metadata
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING

    # Artifacts
    input_artifacts: List[str] = field(default_factory=list)
    output_artifacts: List[str] = field(default_factory=list)

    # Resources (files, modules, etc.)
    resources_read: Set[str] = field(default_factory=set)
    resources_write: Set[str] = field(default_factory=set)

    # Timing
    estimated_duration_seconds: int = 60
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # Metadata
    tags: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_parallelizable(self) -> bool:
        """Check if this task can potentially run in parallel with others."""
        # Tasks with write resources may conflict
        return len(self.resources_write) == 0 or self.priority != ExecutionPriority.CRITICAL

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get actual execution duration if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def conflicts_with(self, other: "TaskNode") -> bool:
        """Check if this task conflicts with another."""
        # Write-Write conflict
        if self.resources_write & other.resources_write:
            return True
        # Write-Read conflict
        if self.resources_write & other.resources_read:
            return True
        if self.resources_read & other.resources_write:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_role": self.agent_role,
            "agent_mode": self.agent_mode,
            "priority": self.priority.value,
            "status": self.status.value,
            "input_artifacts": self.input_artifacts,
            "output_artifacts": self.output_artifacts,
            "resources_read": list(self.resources_read),
            "resources_write": list(self.resources_write),
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error_message": self.error_message,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskNode":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            agent_role=data["agent_role"],
            agent_mode=data["agent_mode"],
            priority=ExecutionPriority(data.get("priority", "normal")),
            status=TaskStatus(data.get("status", "pending")),
            input_artifacts=data.get("input_artifacts", []),
            output_artifacts=data.get("output_artifacts", []),
            resources_read=set(data.get("resources_read", [])),
            resources_write=set(data.get("resources_write", [])),
            estimated_duration_seconds=data.get("estimated_duration_seconds", 60),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            result=data.get("result"),
            error_message=data.get("error_message"),
            tags=data.get("tags", {}),
        )


@dataclass
class ParallelGroup:
    """A group of tasks that can execute in parallel."""

    id: str
    tasks: List[TaskNode] = field(default_factory=list)
    merge_strategy: MergeStrategy = MergeStrategy.CONCATENATE

    # Execution constraints
    max_parallel: int = 4           # Maximum concurrent tasks
    timeout_seconds: int = 600      # Group timeout
    fail_fast: bool = False         # Stop on first failure

    # Results
    results: List[Dict[str, Any]] = field(default_factory=list)
    merged_result: Optional[Dict[str, Any]] = None

    @property
    def task_count(self) -> int:
        """Get number of tasks in group."""
        return len(self.tasks)

    @property
    def all_completed(self) -> bool:
        """Check if all tasks are completed."""
        return all(t.status == TaskStatus.COMPLETED for t in self.tasks)

    @property
    def any_failed(self) -> bool:
        """Check if any task failed."""
        return any(t.status == TaskStatus.FAILED for t in self.tasks)

    def add_task(self, task: TaskNode) -> None:
        """Add a task to the group."""
        self.tasks.append(task)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "tasks": [t.to_dict() for t in self.tasks],
            "merge_strategy": self.merge_strategy.value,
            "max_parallel": self.max_parallel,
            "timeout_seconds": self.timeout_seconds,
            "fail_fast": self.fail_fast,
            "results": self.results,
            "merged_result": self.merged_result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParallelGroup":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            tasks=[TaskNode.from_dict(t) for t in data.get("tasks", [])],
            merge_strategy=MergeStrategy(data.get("merge_strategy", "concatenate")),
            max_parallel=data.get("max_parallel", 4),
            timeout_seconds=data.get("timeout_seconds", 600),
            fail_fast=data.get("fail_fast", False),
            results=data.get("results", []),
            merged_result=data.get("merged_result"),
        )


@dataclass
class TaskGraph:
    """Directed acyclic graph of tasks with dependencies."""

    id: str
    name: str = ""
    nodes: Dict[str, TaskNode] = field(default_factory=dict)
    dependencies: List[TaskDependency] = field(default_factory=list)
    parallel_groups: List[ParallelGroup] = field(default_factory=list)

    # Graph metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Alias properties for compatibility
    @property
    def project_id(self) -> str:
        """Alias for id - used by ParallelExecutor."""
        return self.id

    @property
    def tasks(self) -> Dict[str, "TaskNode"]:
        """Alias for nodes - used by ParallelExecutor."""
        return self.nodes

    def add_task(self, task: "TaskNode") -> None:
        """Alias for add_node - used by ParallelExecutor."""
        self.add_node(task)

    def add_dependency(self, source_id, target_id: str = None, dep_type: "DependencyType" = None) -> None:
        """
        Add a dependency between tasks.

        Args:
            source_id: Task that depends on another (or TaskDependency object for backward compatibility)
            target_id: Task that must complete first (ignored if source_id is TaskDependency)
            dep_type: Type of dependency (optional)
        """
        # Support both old and new API
        if isinstance(source_id, TaskDependency):
            dependency = source_id
        elif target_id is None:
            raise ValueError("target_id is required when source_id is a string")
        else:
            from .models import DependencyType
            dependency = TaskDependency(
                source_id=source_id,
                target_id=target_id,
                dependency_type=dep_type or DependencyType.REQUIRES,
            )

        if dependency.source_id not in self.nodes:
            raise ValueError(f"Source node {dependency.source_id} not found")
        if dependency.target_id not in self.nodes:
            raise ValueError(f"Target node {dependency.target_id} not found")
        self.dependencies.append(dependency)
        self.updated_at = datetime.now()

    def add_node(self, node: TaskNode) -> None:
        """Add a task node to the graph."""
        self.nodes[node.id] = node
        self.updated_at = datetime.now()

    def get_dependencies(self, task_id: str) -> List[TaskDependency]:
        """Get all dependencies where task_id is the source (depends on others)."""
        return [d for d in self.dependencies if d.source_id == task_id]

    def get_dependents(self, task_id: str) -> List[TaskDependency]:
        """Get all dependencies where task_id is the target (others depend on it)."""
        return [d for d in self.dependencies if d.target_id == task_id]

    def get_ready_tasks(self) -> List[TaskNode]:
        """Get all tasks that are ready to execute (all dependencies satisfied)."""
        ready = []
        for node in self.nodes.values():
            if node.status != TaskStatus.PENDING:
                continue

            # Check all dependencies
            deps = self.get_dependencies(node.id)
            all_satisfied = True
            for dep in deps:
                if dep.dependency_type.is_hard:
                    target = self.nodes.get(dep.target_id)
                    if target and target.status != TaskStatus.COMPLETED:
                        all_satisfied = False
                        break

            if all_satisfied:
                ready.append(node)

        return ready

    def find_parallel_groups(self, max_group_size: int = None) -> List[ParallelGroup]:
        """
        Identify groups of tasks that can run in parallel.

        This method analyzes ALL tasks in the graph (not just ready ones)
        and groups them based on resource conflicts AND graph dependencies.

        Args:
            max_group_size: Maximum number of tasks per group (None = unlimited)
        """
        groups = []
        all_tasks = list(self.nodes.values())

        if not all_tasks:
            return groups

        # Build dependency set for quick lookup (task_id -> set of tasks it depends on)
        depends_on: Dict[str, Set[str]] = {task.id: set() for task in all_tasks}
        for dep in self.dependencies:
            if dep.dependency_type.is_hard:
                depends_on[dep.source_id].add(dep.target_id)

        # Group by non-conflicting tasks (no resource conflicts AND no dependencies)
        current_group = ParallelGroup(id=f"group_{len(self.parallel_groups)}")
        tasks_in_groups: Set[str] = set()

        for task in all_tasks:
            # Check if task conflicts with any in current group
            conflicts = False

            for existing in current_group.tasks:
                # Check resource conflicts
                if task.conflicts_with(existing):
                    conflicts = True
                    break
                # Check if there's a dependency between them
                if existing.id in depends_on[task.id] or task.id in depends_on[existing.id]:
                    conflicts = True
                    break

            # Also check max_group_size limit
            if max_group_size and len(current_group.tasks) >= max_group_size:
                conflicts = True

            if not conflicts:
                current_group.add_task(task)
                tasks_in_groups.add(task.id)
            else:
                # Start new group for conflicting task
                if current_group.tasks:
                    groups.append(current_group)
                current_group = ParallelGroup(id=f"group_{len(self.parallel_groups) + len(groups)}")
                current_group.add_task(task)
                tasks_in_groups.add(task.id)

        if current_group.tasks:
            groups.append(current_group)

        return groups

    def topological_sort(self) -> List[TaskNode]:
        """Return tasks in topological order (respecting dependencies)."""
        # Kahn's algorithm
        in_degree = {node_id: 0 for node_id in self.nodes}

        for dep in self.dependencies:
            if dep.dependency_type.is_hard:
                in_degree[dep.source_id] += 1

        # Start with nodes that have no dependencies
        queue = [
            self.nodes[node_id]
            for node_id, degree in in_degree.items()
            if degree == 0
        ]

        # Sort by priority
        queue.sort(key=lambda n: list(ExecutionPriority).index(n.priority))

        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)

            # Reduce in-degree of dependents
            for dep in self.get_dependents(node.id):
                if dep.dependency_type.is_hard:
                    in_degree[dep.source_id] -= 1
                    if in_degree[dep.source_id] == 0:
                        queue.append(self.nodes[dep.source_id])
                        queue.sort(key=lambda n: list(ExecutionPriority).index(n.priority))

        if len(result) != len(self.nodes):
            raise ValueError("Cycle detected in task graph")

        return result

    def validate(self) -> List[str]:
        """Validate the task graph. Returns list of errors."""
        errors = []

        # Check for cycles
        try:
            self.topological_sort()
        except ValueError as e:
            errors.append(str(e))

        # Check for missing dependencies
        for dep in self.dependencies:
            if dep.source_id not in self.nodes:
                errors.append(f"Missing source node: {dep.source_id}")
            if dep.target_id not in self.nodes:
                errors.append(f"Missing target node: {dep.target_id}")

        # Check for orphan nodes with no input/output
        for node in self.nodes.values():
            deps = self.get_dependencies(node.id)
            dependents = self.get_dependents(node.id)
            if not deps and not dependents and len(self.nodes) > 1:
                errors.append(f"Isolated node: {node.id}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "dependencies": [d.to_dict() for d in self.dependencies],
            "parallel_groups": [g.to_dict() for g in self.parallel_groups],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskGraph":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            nodes={k: TaskNode.from_dict(v) for k, v in data.get("nodes", {}).items()},
            dependencies=[TaskDependency.from_dict(d) for d in data.get("dependencies", [])],
            parallel_groups=[ParallelGroup.from_dict(g) for g in data.get("parallel_groups", [])],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
        )

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram of the task graph."""
        lines = ["graph TD"]

        # Add nodes
        for node in self.nodes.values():
            status_icon = {
                TaskStatus.PENDING: "⬜",
                TaskStatus.WAITING: "⏳",
                TaskStatus.READY: "🟢",
                TaskStatus.RUNNING: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.CANCELLED: "🚫",
                TaskStatus.SKIPPED: "⏭️",
            }.get(node.status, "")

            label = f"{status_icon} {node.name}"
            lines.append(f'    {node.id}["{label}"]')

        # Add dependencies
        for dep in self.dependencies:
            arrow = "-->" if dep.dependency_type.is_hard else "-.->"
            lines.append(f"    {dep.target_id} {arrow} {dep.source_id}")

        return "\n".join(lines)


@dataclass
class Conflict:
    """Represents a conflict between parallel tasks."""

    id: str
    conflict_type: ConflictType
    task_ids: List[str]
    resource: str  # The resource that caused the conflict
    description: str
    detected_at: datetime = field(default_factory=datetime.now)
    resolution: Optional[ConflictResolution] = None
    resolved_at: Optional[datetime] = None
    resolution_details: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        """Check if conflict is resolved."""
        return self.resolution is not None

    def resolve(self, resolution: ConflictResolution, details: str = "") -> None:
        """Mark conflict as resolved."""
        self.resolution = resolution
        self.resolved_at = datetime.now()
        self.resolution_details = details

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "conflict_type": self.conflict_type.value,
            "task_ids": self.task_ids,
            "resource": self.resource,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "resolution": self.resolution.value if self.resolution else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_details": self.resolution_details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conflict":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            conflict_type=ConflictType(data["conflict_type"]),
            task_ids=data["task_ids"],
            resource=data["resource"],
            description=data["description"],
            detected_at=datetime.fromisoformat(data["detected_at"]) if data.get("detected_at") else datetime.now(),
            resolution=ConflictResolution(data["resolution"]) if data.get("resolution") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            resolution_details=data.get("resolution_details"),
        )
