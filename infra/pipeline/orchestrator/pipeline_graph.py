"""
Pipeline Graph for Parallel Multi-Module Execution.

P3 Enhancement: Execute multiple modules in parallel using DAG-based orchestration.

This module provides:
- PipelineTask: Represents a single pipeline task (PM-SPEC, ARCHITECT, IMPLEMENTER)
- PipelineGraph: DAG of tasks with dependencies
- ParallelPipelineOrchestrator: Orchestrates parallel execution across modules

Author: Development Pipeline
Date: 2026-01-08
Version: 2.0.0 (P3 Enhancement)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable
import uuid
import json

from constants import (
    AgentRole,
    AgentMode,
    PipelinePhase,
)


class PipelineTaskType(str, Enum):
    """Types of pipeline tasks."""

    PM_SPEC = "pm_spec"
    ARCHITECT = "architect"
    IMPLEMENTER = "implementer"
    VERIFICATION = "verification"
    BSL_DEBUGGER = "bsl_debugger"


@dataclass
class PipelineTask:
    """
    A single pipeline task with dependencies.

    Attributes:
        task_id: Unique task identifier
        task_type: Type of pipeline task
        module_name: Name of the module this task belongs to
        dependencies: List of task IDs that must complete before this task
        phase: Pipeline phase this task represents
        config: Task-specific configuration
        status: Current task status
        result: Task execution result (when completed)
    """

    task_id: str
    task_type: PipelineTaskType
    module_name: str
    dependencies: List[str] = field(default_factory=list)
    phase: PipelinePhase = PipelinePhase.INITIALIZATION
    config: Dict[str, Any] = field(default_factory=dict)
    status: PipelinePhase = PipelinePhase.INITIALIZATION
    result: Optional[Any] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "module_name": self.module_name,
            "dependencies": self.dependencies,
            "phase": self.phase.value,
            "config": self.config,
            "status": self.status.value,
            "result": str(self.result) if self.result else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @property
    def is_ready(self) -> bool:
        """Check if task is ready to execute (all dependencies met)."""
        return self.status == PipelinePhase.INITIALIZATION

    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status in [
            PipelinePhase.COMPLETED,
            PipelinePhase.VERIFICATION,  # Verification phase considered complete
        ]

    @property
    def duration_seconds(self) -> float:
        """Get task execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


@dataclass
class PipelineGraph:
    """
    Directed Acyclic Graph (DAG) of pipeline tasks.

    Manages dependencies and execution order for multiple modules.
    """

    project_id: str
    tasks: Dict[str, PipelineTask] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)  # task_id -> [dependent_task_ids]

    def add_task(self, task: PipelineTask) -> None:
        """Add a task to the graph."""
        self.tasks[task.task_id] = task

        # Initialize edges list if not exists
        if task.task_id not in self.edges:
            self.edges[task.task_id] = []

        # Register dependencies
        for dep_id in task.dependencies:
            if dep_id not in self.edges:
                self.edges[dep_id] = []
            self.edges[dep_id].append(task.task_id)

    def get_ready_tasks(self) -> List[PipelineTask]:
        """
        Get tasks that are ready to execute.

        A task is ready if:
        - It hasn't started yet
        - All its dependencies are completed

        Returns:
            List of ready tasks
        """
        ready_tasks = []

        for task in self.tasks.values():
            if not task.is_ready:
                continue

            # Check if all dependencies are completed
            dependencies_completed = all(
                dep_id in self.tasks and self.tasks[dep_id].is_completed
                for dep_id in task.dependencies
            )

            if dependencies_completed:
                ready_tasks.append(task)

        return ready_tasks

    def get_dependent_tasks(self, task_id: str) -> List[PipelineTask]:
        """
        Get tasks that depend on the specified task.

        Args:
            task_id: Task to get dependents for

        Returns:
            List of dependent tasks
        """
        dependent_ids = self.edges.get(task_id, [])
        return [self.tasks[dep_id] for dep_id in dependent_ids if dep_id in self.tasks]

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate the DAG structure.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check for circular dependencies using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(task_id: str, path: List[str]) -> bool:
            """Check if there's a cycle starting from task_id."""
            visited.add(task_id)
            rec_stack.add(task_id)

            for dep_id in self.tasks.get(task_id, PipelineTask(task_id="", task_type=PipelineTaskType.PM_SPEC, module_name="")).dependencies:
                if dep_id not in self.tasks:
                    errors.append(f"Dependency not found: {dep_id}")
                    continue

                if dep_id not in visited:
                    if has_cycle(dep_id, path + [task_id]):
                        return True
                elif dep_id in rec_stack:
                    cycle_path = " -> ".join(path + [task_id, dep_id])
                    errors.append(f"Circular dependency detected: {cycle_path}")
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if has_cycle(task_id, []):
                    return False, errors

        # Check for self-dependencies
        for task_id, task in self.tasks.items():
            if task_id in task.dependencies:
                errors.append(f"Task {task_id} depends on itself")

        return len(errors) == 0, errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
            "edges": self.edges,
        }

    def save(self, filepath: Path) -> None:
        """Save graph to file."""
        filepath.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, filepath: Path) -> "PipelineGraph":
        """Load graph from file."""
        data = json.loads(filepath.read_text(encoding="utf-8"))

        graph = cls(project_id=data["project_id"])
        graph.edges = data["edges"]

        for task_id, task_data in data["tasks"].items():
            task = PipelineTask(
                task_id=task_data["task_id"],
                task_type=PipelineTaskType(task_data["task_type"]),
                module_name=task_data["module_name"],
                dependencies=task_data["dependencies"],
                phase=PipelinePhase(task_data["phase"]),
                config=task_data["config"],
                status=PipelinePhase(task_data["status"]),
            )
            graph.tasks[task_id] = task

        return graph


def build_multi_module_graph(modules: List[str], enable_parallel: bool = True) -> PipelineGraph:
    """
    Build a pipeline graph for multiple modules.

    Creates a DAG where:
    - Module 2 can start ARCHITECT while Module 1 is in IMPLEMENTER
    - Module 3 can start PM-SPEC while Module 1 is in ARCHITECT

    Args:
        modules: List of module names
        enable_parallel: Whether to enable parallel execution across modules

    Returns:
        PipelineGraph with tasks for all modules
    """
    graph = PipelineGraph(project_id=f"multi-module-{str(uuid.uuid4())[:8]}")

    if not enable_parallel:
        # Sequential execution: each module depends on previous module's completion
        prev_implementer_id = None

        for i, module in enumerate(modules):
            # PM-SPEC task
            pm_task_id = f"{module}_pm_spec"
            pm_task = PipelineTask(
                task_id=pm_task_id,
                task_type=PipelineTaskType.PM_SPEC,
                module_name=module,
                dependencies=[prev_implementer_id] if prev_implementer_id else [],
                phase=PipelinePhase.SPECIFICATION,
                config={"module_index": i},
            )
            graph.add_task(pm_task)

            # ARCHITECT task
            arch_task_id = f"{module}_architect"
            arch_task = PipelineTask(
                task_id=arch_task_id,
                task_type=PipelineTaskType.ARCHITECT,
                module_name=module,
                dependencies=[pm_task_id],
                phase=PipelinePhase.DESIGN,
                config={"module_index": i},
            )
            graph.add_task(arch_task)

            # IMPLEMENTER task
            impl_task_id = f"{module}_implementer"
            impl_task = PipelineTask(
                task_id=impl_task_id,
                task_type=PipelineTaskType.IMPLEMENTER,
                module_name=module,
                dependencies=[arch_task_id],
                phase=PipelinePhase.IMPLEMENTATION,
                config={"module_index": i},
            )
            graph.add_task(impl_task)

            # VERIFICATION task
            verify_task_id = f"{module}_verification"
            verify_task = PipelineTask(
                task_id=verify_task_id,
                task_type=PipelineTaskType.VERIFICATION,
                module_name=module,
                dependencies=[impl_task_id],
                phase=PipelinePhase.VERIFICATION,
                config={"module_index": i},
            )
            graph.add_task(verify_task)

            prev_implementer_id = impl_task_id

    else:
        # Parallel execution with smart dependencies
        # Module N+1 can start while Module N is running
        for i, module in enumerate(modules):
            # PM-SPEC task (can start immediately if i == 0, else wait for previous module's PM-SPEC)
            pm_task_id = f"{module}_pm_spec"
            pm_dependencies = []
            if i > 0:
                # Start after previous module's PM-SPEC completes
                pm_dependencies.append(f"{modules[i-1]}_pm_spec")

            pm_task = PipelineTask(
                task_id=pm_task_id,
                task_type=PipelineTaskType.PM_SPEC,
                module_name=module,
                dependencies=pm_dependencies,
                phase=PipelinePhase.SPECIFICATION,
                config={"module_index": i},
            )
            graph.add_task(pm_task)

            # ARCHITECT task (depends on this module's PM-SPEC)
            arch_task_id = f"{module}_architect"
            arch_task = PipelineTask(
                task_id=arch_task_id,
                task_type=PipelineTaskType.ARCHITECT,
                module_name=module,
                dependencies=[pm_task_id],
                phase=PipelinePhase.DESIGN,
                config={"module_index": i},
            )
            graph.add_task(arch_task)

            # IMPLEMENTER task (depends on this module's ARCHITECT)
            impl_task_id = f"{module}_implementer"
            impl_task = PipelineTask(
                task_id=impl_task_id,
                task_type=PipelineTaskType.IMPLEMENTER,
                module_name=module,
                dependencies=[arch_task_id],
                phase=PipelinePhase.IMPLEMENTATION,
                config={"module_index": i},
            )
            graph.add_task(impl_task)

            # VERIFICATION task (can start when implementation is 50% done)
            verify_task_id = f"{module}_verification"
            verify_task = PipelineTask(
                task_id=verify_task_id,
                task_type=PipelineTaskType.VERIFICATION,
                module_name=module,
                dependencies=[impl_task_id],
                phase=PipelinePhase.VERIFICATION,
                config={"module_index": i},
            )
            graph.add_task(verify_task)

    return graph


@dataclass
class ParallelPipelineConfig:
    """Configuration for parallel pipeline execution."""

    project_id: str
    project_path: Path
    task_description: str
    modules: List[str]
    enable_parallel: bool = True
    max_parallel_tasks: int = 10
    enable_checkpoints: bool = True
    enable_bsl_debugger: bool = True
    max_revision_attempts: int = 3
    timeout_seconds: int = 3600
    artifact_dir: Path = field(default_factory=lambda: Path("artifacts"))
    verbose: bool = True


@dataclass
class ParallelPipelineResult:
    """Result of parallel pipeline execution."""

    success: bool
    project_id: str
    run_id: str
    module_results: Dict[str, Any] = field(default_factory=dict)
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    execution_time_seconds: float = 0.0
    error_message: Optional[str] = None
    graph: Optional[PipelineGraph] = None


class ParallelPipelineOrchestrator:
    """
    Orchestrates parallel execution of pipelines across multiple modules.

    Uses DAG-based execution to maximize parallelism while respecting dependencies.
    """

    def __init__(
        self,
        config: ParallelPipelineConfig,
        progress_callback: Optional[Callable[[str, PipelinePhase], None]] = None,
    ):
        """
        Initialize parallel pipeline orchestrator.

        Args:
            config: Configuration for parallel execution
            progress_callback: Optional callback for progress updates
        """
        self.config = config
        self.progress_callback = progress_callback
        self.run_id = str(uuid.uuid4())[:8]

        # Build execution graph
        self.graph = build_multi_module_graph(
            modules=config.modules,
            enable_parallel=config.enable_parallel,
        )

        # Execution tracking
        self._completed_tasks: Set[str] = set()
        self._failed_tasks: Set[str] = set()
        self._running_tasks: Set[str] = set()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    async def execute(self) -> ParallelPipelineResult:
        """
        Execute all tasks in the graph.

        Returns:
            ParallelPipelineResult with execution outcome
        """
        self.started_at = datetime.now()

        if self.config.verbose:
            print(f"[{self.run_id}] Starting parallel pipeline execution")
            print(f"[{self.run_id}] Modules: {', '.join(self.config.modules)}")
            print(f"[{self.run_id}] Total tasks: {len(self.graph.tasks)}")
            print(f"[{self.run_id}] Max parallel tasks: {self.config.max_parallel_tasks}")

        # Validate graph
        is_valid, errors = self.graph.validate()
        if not is_valid:
            return ParallelPipelineResult(
                success=False,
                project_id=self.config.project_id,
                run_id=self.run_id,
                error_message=f"Invalid graph: {'; '.join(errors)}",
                graph=self.graph,
            )

        # Execute tasks in waves
        while True:
            # Get ready tasks
            ready_tasks = self.graph.get_ready_tasks()

            if not ready_tasks:
                # No more ready tasks - check if all completed
                if len(self._completed_tasks) + len(self._failed_tasks) == len(self.graph.tasks):
                    break
                else:
                    # Deadlock or waiting
                    await asyncio.sleep(0.1)
                    continue

            # Limit parallel tasks
            available_slots = self.config.max_parallel_tasks - len(self._running_tasks)
            tasks_to_run = ready_tasks[:available_slots]

            if not tasks_to_run:
                # Wait for running tasks to complete
                await asyncio.sleep(0.1)
                continue

            # Execute tasks in parallel
            await self._execute_tasks_parallel(tasks_to_run)

        self.completed_at = datetime.now()
        execution_time = (self.completed_at - self.started_at).total_seconds()

        success = len(self._failed_tasks) == 0

        return ParallelPipelineResult(
            success=success,
            project_id=self.config.project_id,
            run_id=self.run_id,
            module_results=self._collect_module_results(),
            total_tasks=len(self.graph.tasks),
            completed_tasks=len(self._completed_tasks),
            failed_tasks=len(self._failed_tasks),
            execution_time_seconds=execution_time,
            graph=self.graph,
        )

    async def _execute_tasks_parallel(self, tasks: List[PipelineTask]) -> None:
        """
        Execute multiple tasks in parallel.

        Args:
            tasks: List of tasks to execute
        """
        async def execute_single_task(task: PipelineTask) -> None:
            """Execute a single task."""
            self._running_tasks.add(task.task_id)
            task.started_at = datetime.now()

            if self.progress_callback:
                self.progress_callback(task.module_name, task.phase)

            if self.config.verbose:
                print(f"[{self.run_id}] Executing: {task.task_id} ({task.task_type.value})")

            try:
                # Simulate task execution (replace with actual agent calls)
                await self._execute_task_impl(task)

                task.status = PipelinePhase.COMPLETED
                task.completed_at = datetime.now()
                self._completed_tasks.add(task.task_id)

                if self.config.verbose:
                    duration = task.duration_seconds
                    print(f"[{self.run_id}] Completed: {task.task_id} ({duration:.2f}s)")

            except Exception as e:
                task.status = PipelinePhase.FAILED
                task.completed_at = datetime.now()
                self._failed_tasks.add(task.task_id)

                if self.config.verbose:
                    print(f"[{self.run_id}] Failed: {task.task_id} - {e}")

            finally:
                self._running_tasks.discard(task.task_id)

        # Execute all tasks concurrently
        await asyncio.gather(*[execute_single_task(task) for task in tasks])

    async def _execute_task_impl(self, task: PipelineTask) -> None:
        """
        Implement actual task execution.

        This is a placeholder - in real implementation, this would call the appropriate agents.

        Args:
            task: Task to execute
        """
        # Simulate work based on task type
        work_times = {
            PipelineTaskType.PM_SPEC: 0.5,
            PipelineTaskType.ARCHITECT: 0.3,  # P2: Faster due to parallel subtasks
            PipelineTaskType.IMPLEMENTER: 0.7,
            PipelineTaskType.VERIFICATION: 0.2,
            PipelineTaskType.BSL_DEBUGGER: 0.4,
        }

        work_time = work_times.get(task.task_type, 0.5)
        await asyncio.sleep(work_time)

        # Store mock result
        task.result = f"Completed {task.task_type.value} for {task.module_name}"

    def _collect_module_results(self) -> Dict[str, Any]:
        """Collect results per module."""
        module_results: Dict[str, Any] = {}

        for module in self.config.modules:
            module_tasks = [
                task for task in self.graph.tasks.values()
                if task.module_name == module
            ]

            module_results[module] = {
                "tasks": [task.task_id for task in module_tasks],
                "completed": sum(1 for task in module_tasks if task.is_completed),
                "failed": sum(1 for task in module_tasks if task.status == PipelinePhase.FAILED),
                "total_duration": sum(task.duration_seconds for task in module_tasks),
            }

        return module_results


# Convenience function

async def run_parallel_pipeline(
    project_id: str,
    project_path: Path,
    task_description: str,
    modules: List[str],
    **kwargs,
) -> ParallelPipelineResult:
    """
    Run parallel pipeline for multiple modules.

    Args:
        project_id: Project identifier
        project_path: Path to project directory
        task_description: Task description
        modules: List of module names
        **kwargs: Additional configuration options

    Returns:
        ParallelPipelineResult
    """
    config = ParallelPipelineConfig(
        project_id=project_id,
        project_path=project_path,
        task_description=task_description,
        modules=modules,
        **kwargs,
    )

    orchestrator = ParallelPipelineOrchestrator(config)
    return await orchestrator.execute()
