"""
Tests for Result Merger.

Sprint 3.2.3: Синхронизация результатов
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import json

from models import (
    TaskNode,
    TaskGraph,
    ParallelGroup,
    MergeStrategy,
    Conflict,
    ConflictType,
    ConflictResolution,
)
from .parallel_executor import TaskResult, ExecutionReport, ExecutionState, ExecutionProgress
from .result_merger import (
    MergeStatus,
    ArtifactMerge,
    MergeResult,
    MergedOutput,
    MergeStrategyHandler,
    ResultMerger,
    merge_results,
    save_merged_output,
    load_merged_output,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def simple_tasks():
    """Create simple tasks for testing."""
    task1 = TaskNode(
        id="T1",
        name="Task 1",
        description="First task",
        resources_read=set(),
        resources_write={"file:output1.bsl"},
    )
    task2 = TaskNode(
        id="T2",
        name="Task 2",
        description="Second task",
        resources_read=set(),
        resources_write={"file:output2.bsl"},
    )
    return [task1, task2]


@pytest.fixture
def conflicting_tasks():
    """Create tasks that write to the same resource."""
    task1 = TaskNode(
        id="T1",
        name="Task 1",
        description="First task",
        resources_read=set(),
        resources_write={"file:shared.bsl"},
    )
    task2 = TaskNode(
        id="T2",
        name="Task 2",
        description="Second task",
        resources_read=set(),
        resources_write={"file:shared.bsl"},
    )
    return [task1, task2]


@pytest.fixture
def simple_results():
    """Create simple task results."""
    return {
        "T1": TaskResult(
            task_id="T1",
            success=True,
            output={"data": "result1", "count": 10},
        ),
        "T2": TaskResult(
            task_id="T2",
            success=True,
            output={"data": "result2", "count": 20},
        ),
    }


@pytest.fixture
def partial_failure_results():
    """Create results with one failure."""
    return {
        "T1": TaskResult(
            task_id="T1",
            success=True,
            output={"data": "result1"},
        ),
        "T2": TaskResult(
            task_id="T2",
            success=False,
            error_message="Task failed",
        ),
    }


# =============================================================================
# Test MergeStrategyHandler
# =============================================================================

class TestMergeStrategyCombine:
    """Test COMBINE merge strategy."""

    def test_combine_dicts(self):
        """Test combining dictionaries."""
        values = [{"a": 1}, {"b": 2}, {"c": 3}]
        result = MergeStrategyHandler.merge_combine(values)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_combine_dicts_override(self):
        """Test that later dicts override earlier for same keys."""
        values = [{"a": 1}, {"a": 2}]
        result = MergeStrategyHandler.merge_combine(values)
        assert result == {"a": 2}

    def test_combine_lists(self):
        """Test combining lists."""
        values = [[1, 2], [3, 4], [5]]
        result = MergeStrategyHandler.merge_combine(values)
        assert result == [1, 2, 3, 4, 5]

    def test_combine_strings(self):
        """Test combining strings."""
        values = ["line1", "line2", "line3"]
        result = MergeStrategyHandler.merge_combine(values)
        assert result == "line1\nline2\nline3"

    def test_combine_mixed_types(self):
        """Test combining mixed types returns list."""
        values = [1, "two", {"three": 3}]
        result = MergeStrategyHandler.merge_combine(values)
        assert result == [1, "two", {"three": 3}]

    def test_combine_empty(self):
        """Test combining empty list."""
        result = MergeStrategyHandler.merge_combine([])
        assert result is None


class TestMergeStrategyOverride:
    """Test OVERRIDE merge strategy."""

    def test_override_takes_last(self):
        """Test that override takes last value."""
        values = ["first", "second", "third"]
        result = MergeStrategyHandler.merge_override(values)
        assert result == "third"

    def test_override_empty(self):
        """Test override with empty list."""
        result = MergeStrategyHandler.merge_override([])
        assert result is None

    def test_override_single(self):
        """Test override with single value."""
        result = MergeStrategyHandler.merge_override(["only"])
        assert result == "only"


class TestMergeStrategyConcatenate:
    """Test CONCATENATE merge strategy."""

    def test_concatenate_strings(self):
        """Test concatenating strings."""
        values = ["part1", "part2"]
        result = MergeStrategyHandler.merge_concatenate(values)
        assert "part1" in result
        assert "part2" in result
        assert "---" in result  # Separator

    def test_concatenate_lists(self):
        """Test concatenating lists."""
        values = [[1, 2], [3, 4]]
        result = MergeStrategyHandler.merge_concatenate(values)
        assert result == [1, 2, 3, 4]

    def test_concatenate_empty(self):
        """Test concatenating empty list."""
        result = MergeStrategyHandler.merge_concatenate([])
        assert result is None


class TestMergeStrategyHelpers:
    """Test helper merge strategies."""

    def test_first_success(self):
        """Test first_success returns first non-None."""
        values = [None, None, "value", "ignored"]
        result = MergeStrategyHandler.merge_first_success(values)
        assert result == "value"

    def test_first_success_all_none(self):
        """Test first_success with all None."""
        values = [None, None, None]
        result = MergeStrategyHandler.merge_first_success(values)
        assert result is None

    def test_merge_all(self):
        """Test merge_all keeps all values."""
        values = [1, 2, 3]
        result = MergeStrategyHandler.merge_all(values)
        assert result == [1, 2, 3]


# =============================================================================
# Test MergeResult
# =============================================================================

class TestMergeResult:
    """Test MergeResult dataclass."""

    def test_merge_result_creation(self):
        """Test creating MergeResult."""
        result = MergeResult(
            group_id="group-1",
            status=MergeStatus.SUCCESS,
        )
        assert result.group_id == "group-1"
        assert result.status == MergeStatus.SUCCESS

    def test_merge_result_to_dict(self):
        """Test MergeResult serialization."""
        result = MergeResult(
            group_id="group-1",
            status=MergeStatus.SUCCESS,
            merged_artifacts={"output": "merged"},
            merged_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        d = result.to_dict()
        assert d["group_id"] == "group-1"
        assert d["status"] == "success"
        assert d["merged_artifacts"] == {"output": "merged"}


# =============================================================================
# Test MergedOutput
# =============================================================================

class TestMergedOutput:
    """Test MergedOutput dataclass."""

    def test_merged_output_creation(self):
        """Test creating MergedOutput."""
        output = MergedOutput(
            project_id="TEST",
            total_tasks=10,
            successful_tasks=8,
            failed_tasks=2,
        )
        assert output.project_id == "TEST"
        assert output.success_rate == 80.0

    def test_merged_output_empty(self):
        """Test MergedOutput with zero tasks."""
        output = MergedOutput(
            project_id="TEST",
            total_tasks=0,
            successful_tasks=0,
            failed_tasks=0,
        )
        assert output.success_rate == 100.0

    def test_merged_output_has_conflicts(self):
        """Test has_conflicts property."""
        output = MergedOutput(
            project_id="TEST",
            total_tasks=2,
            successful_tasks=2,
            failed_tasks=0,
        )
        assert output.has_conflicts is False

        output.unresolved_conflicts.append(
            Conflict(
                id="c1",
                conflict_type=ConflictType.WRITE_WRITE,
                resource="file:test.bsl",
                task_ids=["T1", "T2"],
                description="Test conflict",
            )
        )
        assert output.has_conflicts is True

    def test_merged_output_to_dict(self):
        """Test MergedOutput serialization."""
        output = MergedOutput(
            project_id="TEST",
            total_tasks=5,
            successful_tasks=4,
            failed_tasks=1,
        )
        d = output.to_dict()
        assert d["project_id"] == "TEST"
        assert d["success_rate"] == 80.0
        assert d["has_conflicts"] is False


# =============================================================================
# Test ResultMerger
# =============================================================================

class TestResultMerger:
    """Test ResultMerger class."""

    def test_merge_group_results_success(self, simple_tasks, simple_results):
        """Test merging successful group results."""
        group = ParallelGroup(id="group-1", tasks=simple_tasks)
        merger = ResultMerger()

        result = merger.merge_group_results(group, simple_results)

        assert result.status == MergeStatus.SUCCESS
        assert len(result.failed_task_ids) == 0
        assert "output" in result.merged_artifacts

    def test_merge_group_results_with_strategy(self, simple_tasks, simple_results):
        """Test merging with specific strategy."""
        group = ParallelGroup(
            id="group-1",
            tasks=simple_tasks,
            merge_strategy=MergeStrategy.OVERRIDE,
        )
        merger = ResultMerger()

        result = merger.merge_group_results(group, simple_results)

        assert result.status == MergeStatus.SUCCESS
        # Override takes last value
        assert result.merged_artifacts["output"] == simple_results["T2"].output

    def test_merge_group_results_partial_failure(self, simple_tasks, partial_failure_results):
        """Test merging with partial failure."""
        group = ParallelGroup(id="group-1", tasks=simple_tasks)
        merger = ResultMerger()

        result = merger.merge_group_results(group, partial_failure_results)

        assert result.status == MergeStatus.PARTIAL
        assert "T2" in result.failed_task_ids
        assert "output" in result.merged_artifacts

    def test_merge_group_results_all_failed(self, simple_tasks):
        """Test merging when all tasks failed."""
        group = ParallelGroup(id="group-1", tasks=simple_tasks)
        all_failed = {
            "T1": TaskResult(task_id="T1", success=False, error_message="Failed"),
            "T2": TaskResult(task_id="T2", success=False, error_message="Failed"),
        }
        merger = ResultMerger()

        result = merger.merge_group_results(group, all_failed)

        assert result.status == MergeStatus.FAILED

    def test_merge_detects_conflicts(self, conflicting_tasks, simple_results):
        """Test that conflicts are detected."""
        group = ParallelGroup(id="group-1", tasks=conflicting_tasks)
        merger = ResultMerger()

        result = merger.merge_group_results(group, simple_results)

        assert len(result.conflicts) > 0
        assert result.conflicts[0].conflict_type == ConflictType.WRITE_WRITE

    def test_merge_with_conflict_handler(self, conflicting_tasks, simple_results):
        """Test custom conflict handler."""
        def resolve_to_first(conflict: Conflict) -> ConflictResolution:
            return ConflictResolution.TAKE_FIRST

        group = ParallelGroup(id="group-1", tasks=conflicting_tasks)
        merger = ResultMerger(conflict_handler=resolve_to_first)

        result = merger.merge_group_results(group, simple_results)

        assert result.conflicts[0].resolution == ConflictResolution.TAKE_FIRST

    def test_merge_fail_on_conflict(self, conflicting_tasks, simple_results):
        """Test fail_on_conflict option."""
        group = ParallelGroup(id="group-1", tasks=conflicting_tasks)
        merger = ResultMerger(fail_on_conflict=True)

        result = merger.merge_group_results(group, simple_results)

        assert result.status == MergeStatus.CONFLICT


class TestResultMergerExecutionReport:
    """Test merging ExecutionReport."""

    def test_merge_execution_report(self, simple_tasks, simple_results):
        """Test merging full execution report."""
        # Build graph
        graph = TaskGraph(id="TEST", name="Test Graph")
        for task in simple_tasks:
            graph.add_task(task)

        # Build report
        report = ExecutionReport(
            project_id="TEST",
            graph_id="TEST-exec-1",
            state=ExecutionState.COMPLETED,
            progress=ExecutionProgress(
                total_tasks=2,
                completed_tasks=2,
                failed_tasks=0,
            ),
            results=simple_results,
        )

        merger = ResultMerger()
        output = merger.merge_execution_report(report, graph)

        assert output.project_id == "TEST"
        assert output.total_tasks == 2
        assert output.successful_tasks == 2
        assert output.success_rate == 100.0

    def test_merge_execution_report_with_failures(self, simple_tasks, partial_failure_results):
        """Test merging report with failures."""
        graph = TaskGraph(id="TEST", name="Test Graph")
        for task in simple_tasks:
            graph.add_task(task)

        report = ExecutionReport(
            project_id="TEST",
            graph_id="TEST-exec-1",
            state=ExecutionState.COMPLETED,
            progress=ExecutionProgress(
                total_tasks=2,
                completed_tasks=1,
                failed_tasks=1,
            ),
            results=partial_failure_results,
        )

        merger = ResultMerger()
        output = merger.merge_execution_report(report, graph)

        assert output.successful_tasks == 1
        assert output.failed_tasks == 1
        assert output.success_rate == 50.0


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_merge_results_function(self, simple_tasks, simple_results):
        """Test merge_results convenience function."""
        graph = TaskGraph(id="TEST", name="Test Graph")
        for task in simple_tasks:
            graph.add_task(task)

        report = ExecutionReport(
            project_id="TEST",
            graph_id="TEST-exec-1",
            state=ExecutionState.COMPLETED,
            progress=ExecutionProgress(
                total_tasks=2,
                completed_tasks=2,
            ),
            results=simple_results,
        )

        output = merge_results(report, graph)

        assert output.project_id == "TEST"
        assert output.total_tasks == 2

    def test_save_and_load_merged_output(self, simple_tasks):
        """Test saving and loading merged output."""
        output = MergedOutput(
            project_id="TEST",
            total_tasks=2,
            successful_tasks=2,
            failed_tasks=0,
            final_artifacts={"test": "value"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            save_merged_output(output, path)

            assert path.exists()

            loaded = load_merged_output(path)
            assert loaded["project_id"] == "TEST"
            assert loaded["final_artifacts"] == {"test": "value"}


# =============================================================================
# Test ArtifactMerge
# =============================================================================

class TestArtifactMerge:
    """Test ArtifactMerge dataclass."""

    def test_artifact_merge_success(self):
        """Test successful artifact merge."""
        merge = ArtifactMerge(
            artifact_name="output.bsl",
            source_task_ids=["T1", "T2"],
            strategy=MergeStrategy.COMBINE,
            success=True,
            merged_content={"combined": True},
        )
        assert merge.success is True
        assert merge.error_message is None

    def test_artifact_merge_failure(self):
        """Test failed artifact merge."""
        merge = ArtifactMerge(
            artifact_name="output.bsl",
            source_task_ids=["T1", "T2"],
            strategy=MergeStrategy.COMBINE,
            success=False,
            error_message="Merge failed",
        )
        assert merge.success is False
        assert merge.error_message == "Merge failed"


# =============================================================================
# Test MergeStatus
# =============================================================================

class TestMergeStatus:
    """Test MergeStatus enum."""

    def test_merge_status_values(self):
        """Test all MergeStatus values."""
        assert MergeStatus.SUCCESS.value == "success"
        assert MergeStatus.PARTIAL.value == "partial"
        assert MergeStatus.FAILED.value == "failed"
        assert MergeStatus.CONFLICT.value == "conflict"
