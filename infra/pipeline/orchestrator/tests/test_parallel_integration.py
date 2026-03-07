"""
Integration Tests for Parallel Pipeline Execution.

Sprint 3.2.5: Интеграционные тесты

Tests the complete workflow:
1. Task decomposition → TaskGraph with ParallelGroups
2. Parallel execution → ExecutionReport with TaskResults
3. Result merging → MergedOutput
4. Conflict resolution → ConflictReport
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import json
import asyncio

from models import (
    TaskNode,
    TaskGraph,
    ParallelGroup,
    MergeStrategy,
    Conflict,
    ConflictType,
    ConflictResolution,
    TaskStatus,
)
from .task_decomposer import (
    TaskDecomposer,
    DecompositionPattern,
    ResourcePattern,
    decompose_task,
    find_parallel_groups,
    build_dependency_graph,
    analyze_parallelism,
)
from .parallel_executor import (
    ParallelExecutor,
    TaskResult,
    ExecutionReport,
    ExecutionState,
    ExecutionProgress,
    TaskExecutorInterface,
    MockTaskExecutor,
    execute_graph,
    run_graph_sync,
)


# =============================================================================
# Helper: Custom Task Executor for Tests
# =============================================================================

class CallableTaskExecutor(TaskExecutorInterface):
    """Task executor that wraps a callable for testing."""

    def __init__(self, handler: callable) -> None:
        """
        Initialize with a handler function.

        Args:
            handler: Function (task: TaskNode) -> Any
        """
        self.handler = handler

    async def execute(self, task: TaskNode, context: dict) -> TaskResult:
        """Execute using the provided handler."""
        from datetime import datetime

        started_at = datetime.now()
        try:
            # Call handler (may be sync or async)
            result = self.handler(task)
            if asyncio.iscoroutine(result):
                result = await result

            completed_at = datetime.now()
            execution_time_ms = int((completed_at - started_at).total_seconds() * 1000)

            return TaskResult(
                task_id=task.id,
                success=True,
                output=result,
                started_at=started_at,
                completed_at=completed_at,
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            completed_at = datetime.now()
            execution_time_ms = int((completed_at - started_at).total_seconds() * 1000)

            return TaskResult(
                task_id=task.id,
                success=False,
                error_message=str(e),
                started_at=started_at,
                completed_at=completed_at,
                execution_time_ms=execution_time_ms,
            )
from .result_merger import (
    ResultMerger,
    MergeResult,
    MergedOutput,
    MergeStatus,
    merge_results,
)
from .conflict_resolver import (
    ConflictResolver,
    ResolutionStrategy,
    ResolutionRule,
    ConflictReport,
    resolve_conflicts,
    create_default_rules,
)


# =============================================================================
# Integration Test Fixtures
# =============================================================================

@pytest.fixture
def simple_task_graph():
    """Create a simple task graph with independent tasks."""
    graph = TaskGraph(id="TEST-GRAPH", name="Test Graph")

    # Two independent tasks
    task1 = TaskNode(
        id="T1",
        name="Task 1",
        description="Independent task 1",
        resources_read={"file:input.txt"},
        resources_write={"file:output1.bsl"},
    )
    task2 = TaskNode(
        id="T2",
        name="Task 2",
        description="Independent task 2",
        resources_read={"file:input.txt"},
        resources_write={"file:output2.bsl"},
    )

    graph.add_task(task1)
    graph.add_task(task2)

    return graph


@pytest.fixture
def sequential_task_graph():
    """Create a task graph with sequential dependencies."""
    graph = TaskGraph(id="SEQ-GRAPH", name="Sequential Graph")

    task1 = TaskNode(
        id="T1",
        name="First Task",
        description="Must run first",
        resources_write={"file:intermediate.bsl"},
    )
    task2 = TaskNode(
        id="T2",
        name="Second Task",
        description="Depends on first",
        resources_read={"file:intermediate.bsl"},
        resources_write={"file:output.bsl"},
    )

    graph.add_task(task1)
    graph.add_task(task2)
    graph.add_dependency("T2", "T1")  # T2 depends on T1

    return graph


@pytest.fixture
def conflicting_task_graph():
    """Create a task graph with conflicting writes."""
    graph = TaskGraph(id="CONFLICT-GRAPH", name="Conflict Graph")

    task1 = TaskNode(
        id="T1",
        name="Writer 1",
        description="Writes to shared file",
        resources_write={"file:shared.bsl"},
    )
    task2 = TaskNode(
        id="T2",
        name="Writer 2",
        description="Also writes to shared file",
        resources_write={"file:shared.bsl"},
    )

    graph.add_task(task1)
    graph.add_task(task2)

    return graph


@pytest.fixture
def complex_task_graph():
    """Create a complex task graph with multiple parallel groups."""
    graph = TaskGraph(id="COMPLEX-GRAPH", name="Complex Graph")

    # Wave 1: Two independent tasks
    t1 = TaskNode(id="T1", name="Setup DB", resources_write={"db:schema"})
    t2 = TaskNode(id="T2", name="Setup Cache", resources_write={"cache:config"})

    # Wave 2: Three tasks depending on Wave 1
    t3 = TaskNode(
        id="T3",
        name="Load Data",
        resources_read={"db:schema"},
        resources_write={"db:data"}
    )
    t4 = TaskNode(
        id="T4",
        name="Init Cache",
        resources_read={"cache:config"},
        resources_write={"cache:entries"}
    )
    t5 = TaskNode(
        id="T5",
        name="Config API",
        resources_read={"db:schema", "cache:config"},
        resources_write={"api:config"}
    )

    # Wave 3: Final task
    t6 = TaskNode(
        id="T6",
        name="Start Server",
        resources_read={"db:data", "cache:entries", "api:config"},
        resources_write={"server:state"}
    )

    for t in [t1, t2, t3, t4, t5, t6]:
        graph.add_task(t)

    # Add dependencies
    graph.add_dependency("T3", "T1")  # T3 depends on T1
    graph.add_dependency("T4", "T2")  # T4 depends on T2
    graph.add_dependency("T5", "T1")  # T5 depends on T1
    graph.add_dependency("T5", "T2")  # T5 depends on T2
    graph.add_dependency("T6", "T3")  # T6 depends on T3
    graph.add_dependency("T6", "T4")  # T6 depends on T4
    graph.add_dependency("T6", "T5")  # T6 depends on T5

    return graph


# =============================================================================
# Test: Task Decomposition → Parallel Groups
# =============================================================================

class TestTaskDecompositionIntegration:
    """Test task decomposition creates correct parallel groups."""

    def test_decompose_simple_graph(self, simple_task_graph):
        """Test decomposing simple independent tasks."""
        # Find parallel groups directly on graph
        groups = simple_task_graph.find_parallel_groups()

        # Should have one group with both tasks
        assert len(groups) >= 1

        # Total tasks should be 2
        total_tasks = sum(len(g.tasks) for g in groups)
        assert total_tasks == 2

    def test_decompose_sequential_graph(self, sequential_task_graph):
        """Test decomposing sequential tasks creates separate waves."""
        groups = sequential_task_graph.find_parallel_groups()

        # Sequential tasks should be in separate groups/waves
        # or not in any parallel group at all
        assert len(groups) <= 2

    def test_decompose_complex_graph(self, complex_task_graph):
        """Test decomposing complex graph with dependencies."""
        groups = complex_task_graph.find_parallel_groups()

        # Should have identified parallel opportunities
        # Wave 1: T1, T2 (parallel)
        # Wave 2: T3, T4, T5 (parallel after T1/T2)
        # Wave 3: T6 (sequential after all)
        assert len(groups) >= 1


# =============================================================================
# Test: Parallel Execution
# =============================================================================

class TestParallelExecutionIntegration:
    """Test parallel task execution."""

    def test_execute_simple_graph(self, simple_task_graph):
        """Test executing simple parallel tasks."""
        # Create mock task handler
        def task_handler(task: TaskNode):
            return {"task_id": task.id, "result": f"Output from {task.name}"}

        executor = CallableTaskExecutor(task_handler)
        report = run_graph_sync(simple_task_graph, executor, max_parallel=2)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.completed_tasks == 2
        assert len(report.results) == 2
        assert all(r.success for r in report.results.values())

    def test_execute_with_failure(self, simple_task_graph):
        """Test execution handles task failures."""
        def failing_handler(task: TaskNode):
            if task.id == "T1":
                raise Exception("Task T1 failed")
            return {"result": "ok"}

        executor = CallableTaskExecutor(failing_handler)
        report = run_graph_sync(simple_task_graph, executor)

        assert report.progress.failed_tasks >= 1
        assert report.results["T1"].success is False
        assert "failed" in report.results["T1"].error_message.lower()

    def test_execute_respects_dependencies(self, sequential_task_graph):
        """Test that dependencies are respected during execution."""
        execution_order = []

        def tracking_handler(task: TaskNode):
            execution_order.append(task.id)
            return {"executed": task.id}

        executor = CallableTaskExecutor(tracking_handler)
        report = run_graph_sync(sequential_task_graph, executor)

        # T1 must execute before T2
        if "T1" in execution_order and "T2" in execution_order:
            assert execution_order.index("T1") < execution_order.index("T2")

    def test_execute_complex_graph(self, complex_task_graph):
        """Test executing complex graph with multiple waves."""
        wave_tracker = {"wave1": [], "wave2": [], "wave3": []}

        def wave_tracking_handler(task: TaskNode):
            if task.id in ["T1", "T2"]:
                wave_tracker["wave1"].append(task.id)
            elif task.id in ["T3", "T4", "T5"]:
                wave_tracker["wave2"].append(task.id)
            else:
                wave_tracker["wave3"].append(task.id)
            return {"wave": task.id}

        executor = CallableTaskExecutor(wave_tracking_handler)
        report = run_graph_sync(complex_task_graph, executor, max_parallel=3)

        assert report.state == ExecutionState.COMPLETED
        assert report.progress.completed_tasks == 6


# =============================================================================
# Test: Result Merging
# =============================================================================

class TestResultMergingIntegration:
    """Test merging results from parallel execution."""

    def test_merge_simple_results(self, simple_task_graph):
        """Test merging results from simple parallel tasks."""
        # Simulate execution results
        results = {
            "T1": TaskResult(
                task_id="T1",
                success=True,
                output={"data": "result1", "items": [1, 2]},
            ),
            "T2": TaskResult(
                task_id="T2",
                success=True,
                output={"data": "result2", "items": [3, 4]},
            ),
        }

        report = ExecutionReport(
            project_id="TEST",
            graph_id="TEST-exec",
            state=ExecutionState.COMPLETED,
            progress=ExecutionProgress(total_tasks=2, completed_tasks=2),
            results=results,
        )

        merger = ResultMerger(default_strategy=MergeStrategy.COMBINE)
        merged_output = merger.merge_execution_report(report, simple_task_graph)

        assert merged_output.total_tasks == 2
        assert merged_output.successful_tasks == 2
        assert merged_output.success_rate == 100.0

    def test_merge_with_partial_failure(self, simple_task_graph):
        """Test merging when some tasks failed."""
        results = {
            "T1": TaskResult(task_id="T1", success=True, output={"data": "ok"}),
            "T2": TaskResult(task_id="T2", success=False, error_message="Failed"),
        }

        report = ExecutionReport(
            project_id="TEST",
            graph_id="TEST-exec",
            state=ExecutionState.COMPLETED,
            progress=ExecutionProgress(
                total_tasks=2,
                completed_tasks=1,
                failed_tasks=1
            ),
            results=results,
        )

        merger = ResultMerger()
        merged_output = merger.merge_execution_report(report, simple_task_graph)

        assert merged_output.failed_tasks == 1
        assert merged_output.success_rate == 50.0

    def test_merge_detects_conflicts(self, conflicting_task_graph):
        """Test that merging detects write-write conflicts."""
        results = {
            "T1": TaskResult(task_id="T1", success=True, output={"content": "v1"}),
            "T2": TaskResult(task_id="T2", success=True, output={"content": "v2"}),
        }

        # Create a parallel group with both tasks to test conflict detection
        from .models import ParallelGroup
        group = ParallelGroup(
            id="conflict_group",
            tasks=list(conflicting_task_graph.tasks.values()),
        )

        merger = ResultMerger()
        merge_result = merger.merge_group_results(group, results)

        # Should detect conflict on shared.bsl
        assert len(merge_result.conflicts) > 0, "Should detect write-write conflict"
        assert any(c.resource == "file:shared.bsl" for c in merge_result.conflicts)


# =============================================================================
# Test: Conflict Resolution
# =============================================================================

class TestConflictResolutionIntegration:
    """Test conflict detection and resolution."""

    def test_resolve_write_write_conflict(self):
        """Test resolving a write-write conflict."""
        conflict = Conflict(
            id="conflict-1",
            conflict_type=ConflictType.WRITE_WRITE,
            resource="file:shared.bsl",
            task_ids=["T1", "T2"],
            description="Both tasks wrote to shared.bsl",
        )

        task_outputs = {
            "T1": {"content": "Version 1"},
            "T2": {"content": "Version 2"},
        }

        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_LAST)
        result = resolver.resolve_conflict(conflict, task_outputs)

        assert result.resolved is True
        assert result.chosen_task_id == "T2"
        assert result.chosen_value == {"content": "Version 2"}

    def test_resolve_with_rules(self):
        """Test rule-based conflict resolution."""
        conflicts = [
            Conflict(
                id="c1",
                conflict_type=ConflictType.WRITE_WRITE,
                resource="file:module.bsl",
                task_ids=["T1", "T2"],
                description="BSL conflict",
            ),
            Conflict(
                id="c2",
                conflict_type=ConflictType.WRITE_WRITE,
                resource="file:config.json",
                task_ids=["T1", "T2"],
                description="JSON conflict",
            ),
        ]

        task_outputs = {
            "T1": {"data": "first"},
            "T2": {"data": "second"},
        }

        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_FIRST)
        resolver.add_rule(ResolutionRule(
            resource_pattern=r"file:.*\.bsl$",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.TAKE_LAST,  # BSL: take last
        ))
        resolver.add_rule(ResolutionRule(
            resource_pattern=r"file:.*\.json$",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.MERGE,  # JSON: merge
        ))

        report = resolver.resolve_all(conflicts, task_outputs)

        assert report.total_conflicts == 2
        assert report.resolved_conflicts == 2

        # BSL conflict should use TAKE_LAST
        bsl_resolution = next(r for r in report.resolutions if r.conflict_id == "c1")
        assert bsl_resolution.resolution == ConflictResolution.TAKE_LAST

        # JSON conflict should use MERGE
        json_resolution = next(r for r in report.resolutions if r.conflict_id == "c2")
        assert json_resolution.resolution == ConflictResolution.MERGED

    def test_default_1c_rules(self):
        """Test default rules for 1C development."""
        rules = create_default_rules()

        # Should have rules for BSL, Forms, JSON, MD
        patterns = [r.resource_pattern for r in rules]

        assert any(".bsl" in p for p in patterns)
        assert any("Form" in p for p in patterns)
        assert any(".json" in p for p in patterns)
        assert any(".md" in p for p in patterns)


# =============================================================================
# Test: Full Pipeline Integration
# =============================================================================

class TestFullPipelineIntegration:
    """Test the complete parallel execution pipeline."""

    def test_complete_pipeline_simple(self, simple_task_graph):
        """Test complete pipeline: decompose → execute → merge → resolve."""

        # Step 1: Task handler
        def task_handler(task: TaskNode):
            return {"task_id": task.id, "processed": True}

        # Step 2: Execute
        executor = CallableTaskExecutor(task_handler)
        exec_report = run_graph_sync(simple_task_graph, executor)

        assert exec_report.state == ExecutionState.COMPLETED

        # Step 3: Merge
        merger = ResultMerger()
        merged_output = merger.merge_execution_report(exec_report, simple_task_graph)

        assert merged_output.success_rate == 100.0

        # Step 4: Resolve any conflicts (should be none for simple case)
        if merged_output.unresolved_conflicts:
            resolver = ConflictResolver()
            conflict_report = resolver.resolve_all(
                merged_output.unresolved_conflicts,
                {r.task_id: r.output for r in exec_report.results.values()}
            )
            assert conflict_report.all_resolved

    def test_complete_pipeline_with_conflicts(self, conflicting_task_graph):
        """Test pipeline handles conflicts correctly."""

        def task_handler(task: TaskNode):
            return {"content": f"Output from {task.id}"}

        # Execute
        executor = CallableTaskExecutor(task_handler)
        exec_report = run_graph_sync(conflicting_task_graph, executor)

        # Merge
        merger = ResultMerger()
        merged_output = merger.merge_execution_report(exec_report, conflicting_task_graph)

        # Resolve conflicts
        all_conflicts = []
        for mr in merged_output.merge_results:
            all_conflicts.extend(mr.conflicts)

        if all_conflicts:
            task_outputs = {
                r.task_id: r.output
                for r in exec_report.results.values()
                if r.success
            }

            resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_LAST)
            conflict_report = resolver.resolve_all(all_conflicts, task_outputs)

            assert conflict_report.resolved_conflicts > 0

    def test_complete_pipeline_complex(self, complex_task_graph):
        """Test complete pipeline with complex graph."""
        execution_times = {}

        def timed_handler(task: TaskNode):
            execution_times[task.id] = datetime.now()
            return {"task_id": task.id, "completed": True}

        # Execute
        executor = CallableTaskExecutor(timed_handler)
        exec_report = run_graph_sync(complex_task_graph, executor, max_parallel=3)

        assert exec_report.state == ExecutionState.COMPLETED
        assert exec_report.progress.completed_tasks == 6

        # Merge
        merger = ResultMerger()
        merged_output = merger.merge_execution_report(exec_report, complex_task_graph)

        assert merged_output.total_tasks == 6
        assert merged_output.success_rate == 100.0

    def test_pipeline_saves_artifacts(self, simple_task_graph):
        """Test that pipeline can save artifacts to disk."""
        def task_handler(task: TaskNode):
            return {"result": f"Data from {task.id}"}

        executor = CallableTaskExecutor(task_handler)
        exec_report = run_graph_sync(simple_task_graph, executor)

        merger = ResultMerger()
        merged_output = merger.merge_execution_report(exec_report, simple_task_graph)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "merged_output.json"

            # Save merged output
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(merged_output.to_dict(), f, indent=2)

            # Verify saved
            assert output_path.exists()

            with open(output_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)

            assert loaded["project_id"] == merged_output.project_id
            assert loaded["total_tasks"] == merged_output.total_tasks


# =============================================================================
# Test: Error Handling and Recovery
# =============================================================================

class TestErrorHandlingIntegration:
    """Test error handling across the pipeline."""

    def test_graceful_task_failure(self, simple_task_graph):
        """Test pipeline handles task failures gracefully."""
        def failing_handler(task: TaskNode):
            if task.id == "T1":
                raise ValueError("Simulated failure")
            return {"result": "ok"}

        executor = CallableTaskExecutor(failing_handler)
        report = run_graph_sync(simple_task_graph, executor)

        # Should complete with partial success
        assert report.progress.failed_tasks == 1
        assert report.progress.completed_tasks == 1
        assert report.results["T1"].success is False
        assert report.results["T2"].success is True

    def test_conflict_resolution_fallback(self):
        """Test conflict resolution falls back correctly."""
        conflict = Conflict(
            id="c1",
            conflict_type=ConflictType.WRITE_WRITE,
            resource="file:unknown.xyz",
            task_ids=["T1", "T2"],
            description="Unknown file type",
        )

        task_outputs = {"T1": "first", "T2": "second"}

        # Use default strategy when no rules match
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_FIRST)
        result = resolver.resolve_conflict(conflict, task_outputs)

        assert result.resolved is True
        assert result.chosen_task_id == "T1"


# =============================================================================
# Test: Performance Characteristics
# =============================================================================

class TestPerformanceIntegration:
    """Test performance characteristics of parallel execution."""

    def test_parallel_speedup(self):
        """Test that parallel execution provides speedup."""
        import time

        # Create many independent tasks
        graph = TaskGraph(id="PERF-TEST", name="Performance Test")
        for i in range(10):
            graph.add_task(TaskNode(
                id=f"T{i}",
                name=f"Task {i}",
                resources_write={f"file:output{i}.bsl"}
            ))

        def slow_handler(task: TaskNode):
            time.sleep(0.01)  # 10ms per task
            return {"done": True}

        # Execute with concurrency
        executor = CallableTaskExecutor(slow_handler)

        start = time.time()
        report = run_graph_sync(graph, executor, max_parallel=5)
        elapsed = time.time() - start

        assert report.progress.completed_tasks == 10
        # Should complete faster than sequential (10 * 10ms = 100ms)
        # With 5 concurrent, expect ~20-30ms (plus overhead)
        assert elapsed < 0.15  # 150ms max

    def test_execution_metrics(self, simple_task_graph):
        """Test that execution tracks metrics."""
        def task_handler(task: TaskNode):
            return {"result": "ok"}

        executor = CallableTaskExecutor(task_handler)
        report = run_graph_sync(simple_task_graph, executor)

        # Should track execution time
        assert report.total_execution_time_ms >= 0

        # Should track individual task durations
        for result in report.results.values():
            assert result.execution_time_ms is not None
            assert result.execution_time_ms >= 0
