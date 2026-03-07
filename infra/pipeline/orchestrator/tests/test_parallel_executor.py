"""
Tests for Parallel Executor module.

Sprint 3.2.2: Параллельный запуск агентов
"""

import asyncio
import pytest
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from models import (
    TaskNode,
    TaskGraph,
    TaskStatus,
    ExecutionPriority,
)
from .parallel_executor import (
    ExecutionState,
    TaskResult,
    ExecutionProgress,
    ExecutionReport,
    TaskExecutorInterface,
    MockTaskExecutor,
    ParallelExecutor,
    execute_graph,
    execute_tasks,
    run_graph_sync,
)
from constants import AgentRole, AgentMode


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_task() -> TaskNode:
    """Create a sample task node."""
    return TaskNode(
        id="task-1",
        name="Test Task",
        description="A test task",
        agent_role=AgentRole.IMPLEMENTER.value,
        agent_mode=AgentMode.BUILD.value,
        priority=ExecutionPriority.NORMAL,
    )


@pytest.fixture
def sample_graph() -> TaskGraph:
    """Create a sample task graph with independent tasks."""
    task1 = TaskNode(
        id="task-1",
        name="Task 1",
        description="First task",
        agent_role=AgentRole.PM_SPEC.value,
        agent_mode=AgentMode.INIT.value,
        priority=ExecutionPriority.HIGH,
    )
    task2 = TaskNode(
        id="task-2",
        name="Task 2",
        description="Second task",
        agent_role=AgentRole.IMPLEMENTER.value,
        agent_mode=AgentMode.BUILD.value,
        priority=ExecutionPriority.NORMAL,
    )
    task3 = TaskNode(
        id="task-3",
        name="Task 3",
        description="Third task",
        agent_role=AgentRole.PM_SPEC.value,
        agent_mode=AgentMode.VERIFY.value,
        priority=ExecutionPriority.LOW,
    )

    graph = TaskGraph(id="test-project", name="Test Project")
    graph.add_task(task1)
    graph.add_task(task2)
    graph.add_task(task3)

    return graph


@pytest.fixture
def dependent_graph() -> TaskGraph:
    """Create a task graph with dependencies."""
    task1 = TaskNode(
        id="task-1",
        name="Task 1",
        description="First task",
        agent_role=AgentRole.PM_SPEC.value,
        agent_mode=AgentMode.INIT.value,
    )
    task2 = TaskNode(
        id="task-2",
        name="Task 2",
        description="Second task - depends on task 1",
        agent_role=AgentRole.IMPLEMENTER.value,
        agent_mode=AgentMode.BUILD.value,
    )
    task3 = TaskNode(
        id="task-3",
        name="Task 3",
        description="Third task - depends on task 1",
        agent_role=AgentRole.IMPLEMENTER.value,
        agent_mode=AgentMode.BUILD.value,
    )
    task4 = TaskNode(
        id="task-4",
        name="Task 4",
        description="Fourth task - depends on tasks 2 and 3",
        agent_role=AgentRole.PM_SPEC.value,
        agent_mode=AgentMode.VERIFY.value,
    )

    graph = TaskGraph(id="test-project", name="Test Project")
    graph.add_task(task1)
    graph.add_task(task2)
    graph.add_task(task3)
    graph.add_task(task4)

    # Dependencies: task1 -> task2, task3 -> task4
    graph.add_dependency("task-1", "task-2")
    graph.add_dependency("task-1", "task-3")
    graph.add_dependency("task-2", "task-4")
    graph.add_dependency("task-3", "task-4")

    return graph


# =============================================================================
# Test TaskResult
# =============================================================================

class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_task_result_creation(self):
        """Test basic TaskResult creation."""
        result = TaskResult(
            task_id="task-1",
            success=True,
            output={"data": "value"},
        )
        assert result.task_id == "task-1"
        assert result.success is True
        assert result.output == {"data": "value"}
        assert result.error_message is None

    def test_task_result_failure(self):
        """Test TaskResult for failed task."""
        result = TaskResult(
            task_id="task-1",
            success=False,
            error_message="Something went wrong",
        )
        assert result.success is False
        assert result.error_message == "Something went wrong"

    def test_task_result_duration(self):
        """Test duration property."""
        result = TaskResult(
            task_id="task-1",
            success=True,
            execution_time_ms=1500,
        )
        assert result.duration == 1.5

    def test_task_result_to_dict(self):
        """Test conversion to dictionary."""
        started = datetime(2025, 1, 1, 12, 0, 0)
        completed = datetime(2025, 1, 1, 12, 0, 1)

        result = TaskResult(
            task_id="task-1",
            success=True,
            output={"key": "value"},
            started_at=started,
            completed_at=completed,
            execution_time_ms=1000,
            artifacts_produced=["artifact-1"],
            metrics={"cpu": 50},
        )

        d = result.to_dict()
        assert d["task_id"] == "task-1"
        assert d["success"] is True
        assert d["output"] == {"key": "value"}
        assert d["started_at"] == "2025-01-01T12:00:00"
        assert d["completed_at"] == "2025-01-01T12:00:01"
        assert d["execution_time_ms"] == 1000
        assert d["artifacts_produced"] == ["artifact-1"]
        assert d["metrics"] == {"cpu": 50}


# =============================================================================
# Test ExecutionProgress
# =============================================================================

class TestExecutionProgress:
    """Tests for ExecutionProgress dataclass."""

    def test_completion_percentage_empty(self):
        """Test completion percentage with no tasks."""
        progress = ExecutionProgress(total_tasks=0)
        assert progress.completion_percentage == 100.0

    def test_completion_percentage_partial(self):
        """Test completion percentage with some completed."""
        progress = ExecutionProgress(
            total_tasks=10,
            completed_tasks=5,
        )
        assert progress.completion_percentage == 50.0

    def test_completion_percentage_full(self):
        """Test completion percentage when all done."""
        progress = ExecutionProgress(
            total_tasks=10,
            completed_tasks=10,
        )
        assert progress.completion_percentage == 100.0

    def test_success_rate_empty(self):
        """Test success rate with no completed tasks."""
        progress = ExecutionProgress()
        assert progress.success_rate == 100.0

    def test_success_rate_all_success(self):
        """Test success rate with all successful."""
        progress = ExecutionProgress(
            completed_tasks=10,
            failed_tasks=0,
        )
        assert progress.success_rate == 100.0

    def test_success_rate_partial_failure(self):
        """Test success rate with some failures."""
        progress = ExecutionProgress(
            completed_tasks=7,
            failed_tasks=3,
        )
        assert progress.success_rate == 70.0


# =============================================================================
# Test ExecutionReport
# =============================================================================

class TestExecutionReport:
    """Tests for ExecutionReport dataclass."""

    def test_execution_report_creation(self):
        """Test basic report creation."""
        report = ExecutionReport(
            project_id="project-1",
            graph_id="graph-1",
            state=ExecutionState.COMPLETED,
            progress=ExecutionProgress(total_tasks=5, completed_tasks=5),
        )
        assert report.project_id == "project-1"
        assert report.state == ExecutionState.COMPLETED

    def test_execution_report_to_dict(self):
        """Test conversion to dictionary."""
        report = ExecutionReport(
            project_id="project-1",
            graph_id="graph-1",
            state=ExecutionState.RUNNING,
            progress=ExecutionProgress(
                total_tasks=10,
                completed_tasks=3,
                failed_tasks=1,
                running_tasks=2,
                current_wave=2,
                total_waves=5,
            ),
        )

        d = report.to_dict()
        assert d["project_id"] == "project-1"
        assert d["state"] == "running"
        assert d["progress"]["total_tasks"] == 10
        assert d["progress"]["completed_tasks"] == 3
        assert d["progress"]["completion_percentage"] == 30.0


# =============================================================================
# Test MockTaskExecutor
# =============================================================================

class TestMockTaskExecutor:
    """Tests for MockTaskExecutor."""

    @pytest.mark.asyncio
    async def test_mock_executor_success(self, sample_task):
        """Test successful mock execution."""
        executor = MockTaskExecutor(
            execution_time_range=(0.01, 0.02),
            failure_rate=0.0,
        )

        result = await executor.execute(sample_task, {})

        assert result.success is True
        assert result.task_id == sample_task.id
        assert result.output is not None
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_mock_executor_always_fails(self, sample_task):
        """Test always-failing mock execution."""
        executor = MockTaskExecutor(
            execution_time_range=(0.01, 0.02),
            failure_rate=1.0,
        )

        result = await executor.execute(sample_task, {})

        assert result.success is False
        assert result.error_message == "Mock failure"

    @pytest.mark.asyncio
    async def test_mock_executor_context_passed(self, sample_task):
        """Test that context is accessible."""
        executor = MockTaskExecutor(
            execution_time_range=(0.01, 0.02),
            failure_rate=0.0,
        )

        context = {"previous_result": "data"}
        result = await executor.execute(sample_task, context)

        assert result.success is True


# =============================================================================
# Test ParallelExecutor
# =============================================================================

class TestParallelExecutor:
    """Tests for ParallelExecutor."""

    @pytest.mark.asyncio
    async def test_execute_empty_graph(self):
        """Test execution of empty graph."""
        executor = MockTaskExecutor(execution_time_range=(0.01, 0.02))
        parallel = ParallelExecutor(executor=executor, max_parallel=4)

        graph = TaskGraph(id="empty-project", name="Empty Project")
        report = await parallel.execute(graph)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.total_tasks == 0
        assert len(report.results) == 0

    @pytest.mark.asyncio
    async def test_execute_single_task(self, sample_task):
        """Test execution of single task."""
        executor = MockTaskExecutor(execution_time_range=(0.01, 0.02))
        parallel = ParallelExecutor(executor=executor, max_parallel=4)

        graph = TaskGraph(id="single-task", name="Single Task")
        graph.add_task(sample_task)

        report = await parallel.execute(graph)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.total_tasks == 1
        assert report.progress.completed_tasks == 1
        assert sample_task.id in report.results

    @pytest.mark.asyncio
    async def test_execute_independent_tasks(self, sample_graph):
        """Test parallel execution of independent tasks."""
        executor = MockTaskExecutor(execution_time_range=(0.01, 0.02))
        parallel = ParallelExecutor(executor=executor, max_parallel=4)

        report = await parallel.execute(sample_graph)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.total_tasks == 3
        assert report.progress.completed_tasks == 3
        assert len(report.results) == 3

    @pytest.mark.asyncio
    async def test_execute_dependent_tasks(self, dependent_graph):
        """Test execution respects dependencies."""
        executor = MockTaskExecutor(execution_time_range=(0.01, 0.02))
        parallel = ParallelExecutor(executor=executor, max_parallel=4)

        report = await parallel.execute(dependent_graph)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.total_tasks == 4
        assert report.progress.completed_tasks == 4

        # Verify all tasks completed
        for task_id in ["task-1", "task-2", "task-3", "task-4"]:
            assert task_id in report.results
            assert report.results[task_id].success is True

    @pytest.mark.asyncio
    async def test_execute_with_failure(self, sample_graph):
        """Test execution handles task failure."""
        executor = MockTaskExecutor(
            execution_time_range=(0.01, 0.02),
            failure_rate=1.0,
        )
        parallel = ParallelExecutor(
            executor=executor,
            max_parallel=4,
            retry_count=0,
        )

        report = await parallel.execute(sample_graph)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.failed_tasks == 3
        assert report.progress.completed_tasks == 0

    @pytest.mark.asyncio
    async def test_execute_with_retry(self, sample_task):
        """Test retry logic on failure."""
        # Create executor that fails first attempt
        call_count = {"count": 0}

        class FailOnceExecutor(TaskExecutorInterface):
            async def execute(self, task: TaskNode, context: dict) -> TaskResult:
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return TaskResult(
                        task_id=task.id,
                        success=False,
                        error_message="First attempt failed",
                    )
                return TaskResult(
                    task_id=task.id,
                    success=True,
                    output={"retried": True},
                )

        parallel = ParallelExecutor(
            executor=FailOnceExecutor(),
            max_parallel=4,
            retry_count=1,
            retry_delay_seconds=0.01,
        )

        graph = TaskGraph(id="retry-test", name="Retry Test")
        graph.add_task(sample_task)

        report = await parallel.execute(graph)

        assert report.state == ExecutionState.COMPLETED
        assert call_count["count"] == 2  # Initial + 1 retry
        assert sample_task.id in report.results
        assert report.results[sample_task.id].success is True

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """Test max_parallel is respected."""
        max_concurrent = {"value": 0}
        current_concurrent = {"value": 0}

        class ConcurrencyTracker(TaskExecutorInterface):
            async def execute(self, task: TaskNode, context: dict) -> TaskResult:
                current_concurrent["value"] += 1
                max_concurrent["value"] = max(
                    max_concurrent["value"],
                    current_concurrent["value"],
                )
                await asyncio.sleep(0.05)
                current_concurrent["value"] -= 1
                return TaskResult(task_id=task.id, success=True)

        # Create 10 independent tasks
        graph = TaskGraph(id="concurrency-test", name="Concurrency Test")
        for i in range(10):
            graph.add_task(TaskNode(
                id=f"task-{i}",
                name=f"Task {i}",
                description=f"Task {i}",
                agent_role=AgentRole.IMPLEMENTER.value,
                agent_mode=AgentMode.BUILD.value,
            ))

        parallel = ParallelExecutor(
            executor=ConcurrencyTracker(),
            max_parallel=3,
        )

        await parallel.execute(graph)

        assert max_concurrent["value"] <= 3

    @pytest.mark.asyncio
    async def test_cancel_execution(self, sample_graph):
        """Test cancellation of execution."""
        class SlowExecutor(TaskExecutorInterface):
            async def execute(self, task: TaskNode, context: dict) -> TaskResult:
                await asyncio.sleep(1.0)  # Long execution
                return TaskResult(task_id=task.id, success=True)

        parallel = ParallelExecutor(
            executor=SlowExecutor(),
            max_parallel=1,
        )

        # Start execution
        task = asyncio.create_task(parallel.execute(sample_graph))

        # Cancel after short delay
        await asyncio.sleep(0.1)
        parallel.cancel()

        report = await task

        assert report.state == ExecutionState.CANCELLED

    @pytest.mark.asyncio
    async def test_pause_resume_execution(self, sample_graph):
        """Test pause and resume functionality."""
        execution_times = []

        class TimingExecutor(TaskExecutorInterface):
            async def execute(self, task: TaskNode, context: dict) -> TaskResult:
                execution_times.append(datetime.now())
                await asyncio.sleep(0.05)
                return TaskResult(task_id=task.id, success=True)

        parallel = ParallelExecutor(
            executor=TimingExecutor(),
            max_parallel=1,  # Sequential for predictable timing
        )

        async def run_with_pause():
            task = asyncio.create_task(parallel.execute(sample_graph))
            await asyncio.sleep(0.1)
            parallel.pause()
            await asyncio.sleep(0.2)
            parallel.resume()
            return await task

        report = await run_with_pause()

        assert report.state == ExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_progress_callback(self, sample_graph):
        """Test progress callback is called."""
        progress_updates = []

        def on_progress(progress: ExecutionProgress):
            progress_updates.append(progress.completion_percentage)

        executor = MockTaskExecutor(execution_time_range=(0.01, 0.02))
        parallel = ParallelExecutor(
            executor=executor,
            max_parallel=4,
            progress_callback=on_progress,
        )

        await parallel.execute(sample_graph)

        assert len(progress_updates) > 0

    @pytest.mark.asyncio
    async def test_context_propagation(self, dependent_graph):
        """Test that context is propagated between waves."""
        class ContextAwareExecutor(TaskExecutorInterface):
            async def execute(self, task: TaskNode, context: dict) -> TaskResult:
                # Task 4 depends on task 2 and 3
                if task.id == "task-4":
                    assert "task-2" in context or "task-3" in context

                return TaskResult(
                    task_id=task.id,
                    success=True,
                    output={f"result_from_{task.id}": True},
                )

        parallel = ParallelExecutor(
            executor=ContextAwareExecutor(),
            max_parallel=4,
        )

        report = await parallel.execute(dependent_graph)

        assert report.state == ExecutionState.COMPLETED

    def test_state_property(self):
        """Test state property reflects current state."""
        executor = MockTaskExecutor()
        parallel = ParallelExecutor(executor=executor)

        assert parallel.state == ExecutionState.IDLE

        parallel.cancel()
        assert parallel.state == ExecutionState.CANCELLED


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_execute_graph_default_executor(self, sample_graph):
        """Test execute_graph with default executor."""
        report = await execute_graph(sample_graph)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.total_tasks == 3

    @pytest.mark.asyncio
    async def test_execute_graph_custom_executor(self, sample_graph):
        """Test execute_graph with custom executor."""
        executor = MockTaskExecutor(
            execution_time_range=(0.01, 0.02),
            failure_rate=0.0,
        )

        report = await execute_graph(
            sample_graph,
            executor=executor,
            max_parallel=2,
        )

        assert report.state == ExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_graph_with_context(self, sample_graph):
        """Test execute_graph with initial context."""
        context = {"initial_data": "value"}

        report = await execute_graph(
            sample_graph,
            context=context,
        )

        assert report.state == ExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_tasks_list(self):
        """Test execute_tasks with task list."""
        tasks = [
            TaskNode(
                id=f"task-{i}",
                name=f"Task {i}",
                description=f"Task {i}",
                agent_role=AgentRole.IMPLEMENTER.value,
                agent_mode=AgentMode.BUILD.value,
            )
            for i in range(3)
        ]

        report = await execute_tasks(tasks)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.total_tasks == 3

    def test_run_graph_sync(self, sample_graph):
        """Test synchronous execution wrapper."""
        report = run_graph_sync(sample_graph)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.total_tasks == 3


# =============================================================================
# Test Exception Handling
# =============================================================================

class TestExceptionHandling:
    """Tests for exception handling."""

    @pytest.mark.asyncio
    async def test_executor_exception_caught(self, sample_task):
        """Test that executor exceptions are caught."""
        class ExceptionExecutor(TaskExecutorInterface):
            async def execute(self, task: TaskNode, context: dict) -> TaskResult:
                raise RuntimeError("Executor crashed")

        parallel = ParallelExecutor(
            executor=ExceptionExecutor(),
            max_parallel=4,
            retry_count=0,
        )

        graph = TaskGraph(id="exception-test", name="Exception Test")
        graph.add_task(sample_task)

        report = await parallel.execute(graph)

        # Should complete but with failure
        assert sample_task.id in report.results
        assert report.results[sample_task.id].success is False
        assert "Executor crashed" in report.results[sample_task.id].error_message

    @pytest.mark.asyncio
    async def test_progress_callback_exception_ignored(self, sample_graph):
        """Test that progress callback exceptions don't stop execution."""
        def bad_callback(progress: ExecutionProgress):
            raise ValueError("Callback error")

        executor = MockTaskExecutor(execution_time_range=(0.01, 0.02))
        parallel = ParallelExecutor(
            executor=executor,
            max_parallel=4,
            progress_callback=bad_callback,
        )

        # Should complete despite callback errors
        report = await parallel.execute(sample_graph)

        assert report.state == ExecutionState.COMPLETED


# =============================================================================
# Test ExecutionState
# =============================================================================

class TestExecutionState:
    """Tests for ExecutionState enum."""

    def test_execution_state_values(self):
        """Test all execution states exist."""
        assert ExecutionState.IDLE.value == "idle"
        assert ExecutionState.RUNNING.value == "running"
        assert ExecutionState.PAUSED.value == "paused"
        assert ExecutionState.COMPLETED.value == "completed"
        assert ExecutionState.FAILED.value == "failed"
        assert ExecutionState.CANCELLED.value == "cancelled"


# =============================================================================
# Test Integration
# =============================================================================

class TestIntegration:
    """Integration tests for parallel execution."""

    @pytest.mark.asyncio
    async def test_full_pipeline_execution(self):
        """Test complete pipeline with multiple waves."""
        # Create a complex graph
        graph = TaskGraph(id="integration-test", name="Integration Test")

        # Wave 1: 3 parallel tasks
        for i in range(3):
            graph.add_task(TaskNode(
                id=f"wave1-task-{i}",
                name=f"Wave 1 Task {i}",
                description=f"Wave 1 Task {i}",
                agent_role=AgentRole.PM_SPEC.value,
                agent_mode=AgentMode.INIT.value,
            ))

        # Wave 2: 2 tasks depending on wave 1
        for i in range(2):
            task = TaskNode(
                id=f"wave2-task-{i}",
                name=f"Wave 2 Task {i}",
                description=f"Wave 2 Task {i}",
                agent_role=AgentRole.IMPLEMENTER.value,
                agent_mode=AgentMode.BUILD.value,
            )
            graph.add_task(task)
            # Depend on all wave 1 tasks
            for j in range(3):
                graph.add_dependency(f"wave1-task-{j}", f"wave2-task-{i}")

        # Wave 3: 1 final task
        final = TaskNode(
            id="final-task",
            name="Final Task",
            description="Final Task",
            agent_role=AgentRole.PM_SPEC.value,
            agent_mode=AgentMode.VERIFY.value,
        )
        graph.add_task(final)
        for i in range(2):
            graph.add_dependency(f"wave2-task-{i}", "final-task")

        executor = MockTaskExecutor(execution_time_range=(0.01, 0.02))
        parallel = ParallelExecutor(
            executor=executor,
            max_parallel=4,
        )

        report = await parallel.execute(graph)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.total_tasks == 6
        assert report.progress.completed_tasks == 6
        assert len(report.results) == 6

    @pytest.mark.asyncio
    async def test_execution_timing(self):
        """Test that parallel execution is actually parallel."""
        # Create 4 tasks that each take 100ms
        graph = TaskGraph(id="timing-test", name="Timing Test")
        for i in range(4):
            graph.add_task(TaskNode(
                id=f"task-{i}",
                name=f"Task {i}",
                description=f"Task {i}",
                agent_role=AgentRole.IMPLEMENTER.value,
                agent_mode=AgentMode.BUILD.value,
            ))

        class TimedExecutor(TaskExecutorInterface):
            async def execute(self, task: TaskNode, context: dict) -> TaskResult:
                await asyncio.sleep(0.1)
                return TaskResult(task_id=task.id, success=True)

        parallel = ParallelExecutor(
            executor=TimedExecutor(),
            max_parallel=4,
        )

        start = datetime.now()
        report = await parallel.execute(graph)
        duration = (datetime.now() - start).total_seconds()

        assert report.state == ExecutionState.COMPLETED

        # Should complete in ~100ms (parallel) rather than ~400ms (sequential)
        # Allow some overhead
        assert duration < 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
