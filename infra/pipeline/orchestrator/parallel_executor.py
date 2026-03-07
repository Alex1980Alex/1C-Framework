"""
Parallel Executor for Pipeline Tasks.

Sprint 3.2.2: Параллельный запуск агентов

This module provides functionality to:
- Execute multiple tasks in parallel
- Manage agent pool for concurrent execution
- Handle task lifecycle (start, monitor, complete)
- Track execution progress and results
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Any, Coroutine
from pathlib import Path
import logging

from .models import (
    TaskNode,
    TaskGraph,
    ParallelGroup,
    TaskStatus,
    ExecutionPriority,
    MergeStrategy,
    Conflict,
    ConflictType,
)
from .task_decomposer import TaskDecomposer
from constants import AgentRole

logger = logging.getLogger(__name__)


# =============================================================================
# Execution Result Models
# =============================================================================

class ExecutionState(Enum):
    """Overall execution state."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of a single task execution."""

    task_id: str
    success: bool
    output: Any = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0
    artifacts_produced: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        return self.execution_time_ms / 1000.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "output": self.output,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "artifacts_produced": self.artifacts_produced,
            "metrics": self.metrics,
        }


@dataclass
class ExecutionProgress:
    """Progress tracking for execution."""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    running_tasks: int = 0
    pending_tasks: int = 0
    current_wave: int = 0
    total_waves: int = 0
    elapsed_time_ms: int = 0
    estimated_remaining_ms: int = 0

    @property
    def completion_percentage(self) -> float:
        """Get completion percentage."""
        if self.total_tasks == 0:
            return 100.0
        return (self.completed_tasks / self.total_tasks) * 100.0

    @property
    def success_rate(self) -> float:
        """Get success rate."""
        completed = self.completed_tasks + self.failed_tasks
        if completed == 0:
            return 100.0
        return (self.completed_tasks / completed) * 100.0


@dataclass
class ExecutionReport:
    """Complete execution report."""

    project_id: str
    graph_id: str
    state: ExecutionState
    progress: ExecutionProgress
    results: dict[str, TaskResult] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_execution_time_ms: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "state": self.state.value,
            "progress": {
                "total_tasks": self.progress.total_tasks,
                "completed_tasks": self.progress.completed_tasks,
                "failed_tasks": self.progress.failed_tasks,
                "running_tasks": self.progress.running_tasks,
                "completion_percentage": self.progress.completion_percentage,
                "success_rate": self.progress.success_rate,
                "current_wave": self.progress.current_wave,
                "total_waves": self.progress.total_waves,
            },
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "conflicts": [c.to_dict() for c in self.conflicts],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_execution_time_ms": self.total_execution_time_ms,
        }


# =============================================================================
# Task Executor Interface
# =============================================================================

class TaskExecutorInterface:
    """Interface for task execution."""

    async def execute(self, task: TaskNode, context: dict) -> TaskResult:
        """
        Execute a single task.

        Args:
            task: Task to execute
            context: Execution context (artifacts from previous tasks, etc.)

        Returns:
            TaskResult with execution outcome
        """
        raise NotImplementedError


class MockTaskExecutor(TaskExecutorInterface):
    """Mock executor for testing."""

    def __init__(
        self,
        execution_time_range: tuple[float, float] = (0.1, 0.5),
        failure_rate: float = 0.0,
    ):
        """
        Initialize mock executor.

        Args:
            execution_time_range: (min, max) execution time in seconds
            failure_rate: Probability of task failure (0.0 to 1.0)
        """
        self.execution_time_range = execution_time_range
        self.failure_rate = failure_rate

    async def execute(self, task: TaskNode, context: dict) -> TaskResult:
        """Execute mock task."""
        import random

        started_at = datetime.now()

        # Simulate execution time
        exec_time = random.uniform(*self.execution_time_range)
        await asyncio.sleep(exec_time)

        # Determine success
        success = random.random() > self.failure_rate

        completed_at = datetime.now()
        execution_time_ms = int((completed_at - started_at).total_seconds() * 1000)

        return TaskResult(
            task_id=task.id,
            success=success,
            output={"mock": True, "task_name": task.name} if success else None,
            error_message=None if success else "Mock failure",
            started_at=started_at,
            completed_at=completed_at,
            execution_time_ms=execution_time_ms,
            artifacts_produced=[f"artifact_{task.id}"] if success else [],
            metrics={"mock_exec_time": exec_time},
        )


# =============================================================================
# Parallel Executor
# =============================================================================

class ParallelExecutor:
    """
    Executes tasks in parallel based on dependency graph.

    Features:
    - Wave-based execution (groups of parallel tasks)
    - Configurable concurrency limits
    - Progress tracking and callbacks
    - Cancellation support
    - Retry logic for failed tasks
    """

    def __init__(
        self,
        executor: TaskExecutorInterface,
        max_parallel: int = 4,
        retry_count: int = 1,
        retry_delay_seconds: float = 1.0,
        progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
    ):
        """
        Initialize parallel executor.

        Args:
            executor: Task executor implementation
            max_parallel: Maximum concurrent tasks
            retry_count: Number of retries for failed tasks
            retry_delay_seconds: Delay between retries
            progress_callback: Optional callback for progress updates
        """
        self.executor = executor
        self.max_parallel = max_parallel
        self.retry_count = retry_count
        self.retry_delay_seconds = retry_delay_seconds
        self.progress_callback = progress_callback

        self._state = ExecutionState.IDLE
        self._cancelled = False
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

    @property
    def state(self) -> ExecutionState:
        """Get current execution state."""
        return self._state

    async def execute(
        self,
        graph: TaskGraph,
        context: Optional[dict] = None,
    ) -> ExecutionReport:
        """
        Execute all tasks in the graph.

        Args:
            graph: TaskGraph with tasks and dependencies
            context: Initial execution context

        Returns:
            ExecutionReport with all results
        """
        context = context or {}
        self._state = ExecutionState.RUNNING
        self._cancelled = False

        # Build execution plan
        decomposer = TaskDecomposer(
            project_id=graph.project_id,
            max_parallel_tasks=self.max_parallel,
        )
        waves = decomposer.build_execution_plan(graph)

        # Initialize report
        report = ExecutionReport(
            project_id=graph.project_id,
            graph_id=f"{graph.project_id}-exec-{int(time.time())}",
            state=ExecutionState.RUNNING,
            progress=ExecutionProgress(
                total_tasks=len(graph.tasks),
                pending_tasks=len(graph.tasks),
                total_waves=len(waves),
            ),
            started_at=datetime.now(),
        )

        start_time = time.time()

        try:
            # Execute waves sequentially
            for wave_index, wave in enumerate(waves):
                if self._cancelled:
                    report.state = ExecutionState.CANCELLED
                    break

                # Wait if paused
                await self._pause_event.wait()

                report.progress.current_wave = wave_index + 1

                # Execute wave (all tasks in parallel)
                wave_results = await self._execute_wave(wave, context, report)

                # Update context with new artifacts
                for result in wave_results:
                    if result.success and result.output:
                        context[result.task_id] = result.output

                    report.results[result.task_id] = result

                # Update progress
                report.progress.running_tasks = 0
                self._notify_progress(report.progress)

            # Finalize
            if not self._cancelled:
                report.state = ExecutionState.COMPLETED

        except Exception as e:
            logger.exception(f"Execution failed: {e}")
            report.state = ExecutionState.FAILED

        finally:
            report.completed_at = datetime.now()
            report.total_execution_time_ms = int((time.time() - start_time) * 1000)
            report.progress.elapsed_time_ms = report.total_execution_time_ms
            self._state = report.state

        return report

    async def _execute_wave(
        self,
        wave: list[TaskNode],
        context: dict,
        report: ExecutionReport,
    ) -> list[TaskResult]:
        """Execute a wave of parallel tasks."""
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def execute_with_semaphore(task: TaskNode) -> TaskResult:
            async with semaphore:
                return await self._execute_single_task(task, context, report)

        # Update running count
        report.progress.running_tasks = min(len(wave), self.max_parallel)
        report.progress.pending_tasks -= len(wave)
        self._notify_progress(report.progress)

        # Execute all tasks in wave concurrently
        tasks = [execute_with_semaphore(task) for task in wave]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results: list[TaskResult] = []
        for task, result in zip(wave, results):
            if isinstance(result, Exception):
                processed_results.append(TaskResult(
                    task_id=task.id,
                    success=False,
                    error_message=str(result),
                ))
                report.progress.failed_tasks += 1
            else:
                processed_results.append(result)
                if result.success:
                    report.progress.completed_tasks += 1
                else:
                    report.progress.failed_tasks += 1

        return processed_results

    async def _execute_single_task(
        self,
        task: TaskNode,
        context: dict,
        report: ExecutionReport,
    ) -> TaskResult:
        """Execute single task with retry logic."""
        last_result: Optional[TaskResult] = None

        for attempt in range(self.retry_count + 1):
            if self._cancelled:
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    error_message="Execution cancelled",
                )

            try:
                result = await self.executor.execute(task, context)

                if result.success:
                    return result

                last_result = result

                # Retry delay
                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay_seconds)

            except Exception as e:
                logger.exception(f"Task {task.id} failed: {e}")
                last_result = TaskResult(
                    task_id=task.id,
                    success=False,
                    error_message=str(e),
                )

                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay_seconds)

        return last_result or TaskResult(
            task_id=task.id,
            success=False,
            error_message="Unknown error",
        )

    def cancel(self) -> None:
        """Cancel execution."""
        self._cancelled = True
        self._state = ExecutionState.CANCELLED
        logger.info("Execution cancelled")

    def pause(self) -> None:
        """Pause execution."""
        if self._state == ExecutionState.RUNNING:
            self._paused = True
            self._pause_event.clear()
            self._state = ExecutionState.PAUSED
            logger.info("Execution paused")

    def resume(self) -> None:
        """Resume paused execution."""
        if self._state == ExecutionState.PAUSED:
            self._paused = False
            self._pause_event.set()
            self._state = ExecutionState.RUNNING
            logger.info("Execution resumed")

    def _notify_progress(self, progress: ExecutionProgress) -> None:
        """Notify progress callback if set."""
        if self.progress_callback:
            try:
                self.progress_callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")


# =============================================================================
# Convenience Functions
# =============================================================================

async def execute_graph(
    graph: TaskGraph,
    executor: Optional[TaskExecutorInterface] = None,
    max_parallel: int = 4,
    context: Optional[dict] = None,
) -> ExecutionReport:
    """
    Execute a task graph.

    Args:
        graph: TaskGraph to execute
        executor: Task executor (defaults to MockTaskExecutor)
        max_parallel: Maximum parallel tasks
        context: Initial context

    Returns:
        ExecutionReport
    """
    if executor is None:
        executor = MockTaskExecutor()

    parallel_executor = ParallelExecutor(
        executor=executor,
        max_parallel=max_parallel,
    )

    return await parallel_executor.execute(graph, context)


async def execute_tasks(
    tasks: list[TaskNode],
    executor: Optional[TaskExecutorInterface] = None,
    max_parallel: int = 4,
    auto_detect_dependencies: bool = True,
) -> ExecutionReport:
    """
    Execute a list of tasks.

    Args:
        tasks: List of tasks to execute
        executor: Task executor
        max_parallel: Maximum parallel tasks
        auto_detect_dependencies: Auto-detect resource dependencies

    Returns:
        ExecutionReport
    """
    from .task_decomposer import build_dependency_graph

    graph = build_dependency_graph(tasks, auto_detect_dependencies)
    return await execute_graph(graph, executor, max_parallel)


def run_graph_sync(
    graph: TaskGraph,
    executor: Optional[TaskExecutorInterface] = None,
    max_parallel: int = 4,
    context: Optional[dict] = None,
) -> ExecutionReport:
    """
    Synchronous wrapper for execute_graph.

    Args:
        graph: TaskGraph to execute
        executor: Task executor
        max_parallel: Maximum parallel tasks
        context: Initial context

    Returns:
        ExecutionReport
    """
    return asyncio.run(execute_graph(graph, executor, max_parallel, context))
