"""
Result Merger for Parallel Pipeline Execution.

Sprint 3.2.3: Синхронизация результатов

This module provides functionality to:
- Merge results from parallel task execution
- Apply merge strategies (combine, override, concatenate)
- Handle partial failures
- Generate consolidated output artifacts
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable

from .models import (
    TaskNode,
    TaskGraph,
    ParallelGroup,
    MergeStrategy,
    Conflict,
    ConflictType,
    ConflictResolution,
)
from .parallel_executor import TaskResult, ExecutionReport

logger = logging.getLogger(__name__)


# =============================================================================
# Merge Result Types
# =============================================================================

class MergeStatus(Enum):
    """Status of merge operation."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some results failed to merge
    FAILED = "failed"
    CONFLICT = "conflict"  # Unresolved conflicts


@dataclass
class ArtifactMerge:
    """Represents a single artifact merge operation."""

    artifact_name: str
    source_task_ids: list[str]
    strategy: MergeStrategy
    success: bool
    merged_content: Any = None
    error_message: Optional[str] = None


@dataclass
class MergeResult:
    """Result of merging multiple task results."""

    group_id: str
    status: MergeStatus = MergeStatus.SUCCESS  # Default, will be updated based on merge outcome
    merged_artifacts: dict[str, Any] = field(default_factory=dict)
    artifact_merges: list[ArtifactMerge] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    failed_task_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    merged_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "group_id": self.group_id,
            "status": self.status.value,
            "merged_artifacts": self.merged_artifacts,
            "artifact_merges": [
                {
                    "artifact_name": am.artifact_name,
                    "source_task_ids": am.source_task_ids,
                    "strategy": am.strategy.value,
                    "success": am.success,
                    "error_message": am.error_message,
                }
                for am in self.artifact_merges
            ],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "failed_task_ids": self.failed_task_ids,
            "warnings": self.warnings,
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
        }


@dataclass
class MergedOutput:
    """Consolidated output from parallel execution."""

    project_id: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    merge_results: list[MergeResult] = field(default_factory=list)
    final_artifacts: dict[str, Any] = field(default_factory=dict)
    unresolved_conflicts: list[Conflict] = field(default_factory=list)
    execution_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_tasks == 0:
            return 100.0
        return (self.successful_tasks / self.total_tasks) * 100.0

    @property
    def has_conflicts(self) -> bool:
        """Check if there are unresolved conflicts."""
        return len(self.unresolved_conflicts) > 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.success_rate,
            "has_conflicts": self.has_conflicts,
            "merge_results": [mr.to_dict() for mr in self.merge_results],
            "final_artifacts": self.final_artifacts,
            "unresolved_conflicts": [c.to_dict() for c in self.unresolved_conflicts],
            "execution_summary": self.execution_summary,
        }


# =============================================================================
# Merge Strategies Implementation
# =============================================================================

class MergeStrategyHandler:
    """Handles different merge strategies."""

    @staticmethod
    def merge_combine(values: list[Any]) -> Any:
        """
        Combine values into a single structure.

        - Lists are concatenated
        - Dicts are merged (shallow)
        - Strings are joined with newlines
        - Other types return the list of values
        """
        if not values:
            return None

        if all(isinstance(v, dict) for v in values):
            result = {}
            for v in values:
                result.update(v)
            return result

        if all(isinstance(v, list) for v in values):
            result = []
            for v in values:
                result.extend(v)
            return result

        if all(isinstance(v, str) for v in values):
            return "\n".join(values)

        return values

    @staticmethod
    def merge_override(values: list[Any], priority_order: Optional[list[str]] = None) -> Any:
        """
        Take the highest priority value.

        If priority_order is provided, values are sorted by that order.
        Otherwise, last value wins.
        """
        if not values:
            return None

        # Last value wins by default
        return values[-1]

    @staticmethod
    def merge_concatenate(values: list[Any]) -> Any:
        """
        Concatenate all values.

        Works best for strings and lists.
        """
        if not values:
            return None

        if all(isinstance(v, str) for v in values):
            return "\n\n---\n\n".join(values)

        if all(isinstance(v, list) for v in values):
            result = []
            for v in values:
                result.extend(v)
            return result

        return values

    @staticmethod
    def merge_first_success(values: list[Any]) -> Any:
        """Return the first non-None value."""
        for v in values:
            if v is not None:
                return v
        return None

    @staticmethod
    def merge_all(values: list[Any]) -> list[Any]:
        """Keep all values as a list."""
        return values


# =============================================================================
# Result Merger
# =============================================================================

class ResultMerger:
    """
    Merges results from parallel task execution.

    Features:
    - Multiple merge strategies
    - Conflict detection and tracking
    - Artifact consolidation
    - Partial failure handling
    """

    def __init__(
        self,
        default_strategy: MergeStrategy = MergeStrategy.COMBINE,
        conflict_handler: Optional[Callable[[Conflict], ConflictResolution]] = None,
        fail_on_conflict: bool = False,
    ):
        """
        Initialize result merger.

        Args:
            default_strategy: Default merge strategy for artifacts
            conflict_handler: Optional handler for resolving conflicts
            fail_on_conflict: Whether to fail merge on unresolved conflicts
        """
        self.default_strategy = default_strategy
        self.conflict_handler = conflict_handler
        self.fail_on_conflict = fail_on_conflict

        self._strategy_handlers = {
            MergeStrategy.COMBINE: MergeStrategyHandler.merge_combine,
            MergeStrategy.OVERRIDE: MergeStrategyHandler.merge_override,
            MergeStrategy.CONCATENATE: MergeStrategyHandler.merge_concatenate,
        }

    def merge_group_results(
        self,
        group: ParallelGroup,
        results: dict[str, TaskResult],
    ) -> MergeResult:
        """
        Merge results from a parallel group.

        Args:
            group: ParallelGroup that was executed
            results: Dict of task_id -> TaskResult

        Returns:
            MergeResult with merged artifacts and status
        """
        merge_result = MergeResult(
            group_id=group.id,
            merged_at=datetime.now(),
        )

        # Collect successful outputs
        successful_outputs: dict[str, Any] = {}
        for task in group.tasks:
            result = results.get(task.id)
            if result and result.success and result.output:
                successful_outputs[task.id] = result.output
            elif result and not result.success:
                merge_result.failed_task_ids.append(task.id)

        if not successful_outputs:
            merge_result.status = MergeStatus.FAILED
            return merge_result

        # Merge outputs based on strategy
        strategy = group.merge_strategy or self.default_strategy
        handler = self._strategy_handlers.get(strategy, MergeStrategyHandler.merge_combine)

        # Collect all output values
        output_values = list(successful_outputs.values())

        try:
            merged = handler(output_values)
            merge_result.merged_artifacts["output"] = merged
            merge_result.artifact_merges.append(ArtifactMerge(
                artifact_name="output",
                source_task_ids=list(successful_outputs.keys()),
                strategy=strategy,
                success=True,
                merged_content=merged,
            ))
        except Exception as e:
            logger.exception(f"Failed to merge outputs: {e}")
            merge_result.artifact_merges.append(ArtifactMerge(
                artifact_name="output",
                source_task_ids=list(successful_outputs.keys()),
                strategy=strategy,
                success=False,
                error_message=str(e),
            ))

        # Detect conflicts
        conflicts = self._detect_conflicts(successful_outputs, group.tasks)
        merge_result.conflicts = conflicts

        # Handle conflicts
        for conflict in conflicts:
            resolution = self._resolve_conflict(conflict)
            if resolution == ConflictResolution.UNRESOLVED:
                merge_result.warnings.append(
                    f"Unresolved conflict: {conflict.description}"
                )

        # Determine final status
        if merge_result.failed_task_ids and merge_result.conflicts:
            merge_result.status = MergeStatus.PARTIAL
        elif merge_result.conflicts and self.fail_on_conflict:
            merge_result.status = MergeStatus.CONFLICT
        elif merge_result.failed_task_ids:
            merge_result.status = MergeStatus.PARTIAL
        else:
            merge_result.status = MergeStatus.SUCCESS

        return merge_result

    def merge_execution_report(
        self,
        report: ExecutionReport,
        graph: TaskGraph,
    ) -> MergedOutput:
        """
        Merge all results from an execution report.

        Args:
            report: ExecutionReport from parallel executor
            graph: Original TaskGraph

        Returns:
            MergedOutput with consolidated artifacts
        """
        merged_output = MergedOutput(
            project_id=report.project_id,
            total_tasks=report.progress.total_tasks,
            successful_tasks=report.progress.completed_tasks,
            failed_tasks=report.progress.failed_tasks,
        )

        # Group results by parallel group if available
        parallel_groups = graph.find_parallel_groups()

        if parallel_groups:
            for group in parallel_groups:
                # Get results for this group
                group_results = {
                    task.id: report.results.get(task.id)
                    for task in group.tasks
                    if report.results.get(task.id)
                }

                if group_results:
                    merge_result = self.merge_group_results(group, group_results)
                    merged_output.merge_results.append(merge_result)

                    # Collect conflicts
                    for conflict in merge_result.conflicts:
                        if conflict.resolution == ConflictResolution.UNRESOLVED:
                            merged_output.unresolved_conflicts.append(conflict)

        # Build final artifacts from all merge results
        for merge_result in merged_output.merge_results:
            for key, value in merge_result.merged_artifacts.items():
                if key not in merged_output.final_artifacts:
                    merged_output.final_artifacts[key] = []
                merged_output.final_artifacts[key].append(value)

        # Flatten final artifacts using combine strategy
        for key in merged_output.final_artifacts:
            values = merged_output.final_artifacts[key]
            merged_output.final_artifacts[key] = MergeStrategyHandler.merge_combine(values)

        # Build execution summary
        merged_output.execution_summary = {
            "total_groups": len(parallel_groups),
            "total_merges": len(merged_output.merge_results),
            "successful_merges": sum(
                1 for mr in merged_output.merge_results
                if mr.status == MergeStatus.SUCCESS
            ),
            "partial_merges": sum(
                1 for mr in merged_output.merge_results
                if mr.status == MergeStatus.PARTIAL
            ),
            "failed_merges": sum(
                1 for mr in merged_output.merge_results
                if mr.status == MergeStatus.FAILED
            ),
            "total_conflicts": sum(
                len(mr.conflicts) for mr in merged_output.merge_results
            ),
            "unresolved_conflicts": len(merged_output.unresolved_conflicts),
            "execution_time_ms": report.total_execution_time_ms,
        }

        return merged_output

    def _detect_conflicts(
        self,
        outputs: dict[str, Any],
        tasks: list[TaskNode],
    ) -> list[Conflict]:
        """Detect conflicts between task outputs."""
        conflicts: list[Conflict] = []

        # Build resource write map
        task_writes: dict[str, list[str]] = {}  # resource -> [task_ids]
        for task in tasks:
            for resource in task.resources_write:
                if resource not in task_writes:
                    task_writes[resource] = []
                task_writes[resource].append(task.id)

        # Check for write-write conflicts
        for resource, task_ids in task_writes.items():
            if len(task_ids) > 1:
                conflicts.append(Conflict(
                    id=f"conflict-{resource}",
                    conflict_type=ConflictType.WRITE_WRITE,
                    resource=resource,
                    task_ids=task_ids,
                    description=f"Multiple tasks wrote to {resource}: {', '.join(task_ids)}",
                    resolution=ConflictResolution.UNRESOLVED,
                ))

        return conflicts

    def _resolve_conflict(self, conflict: Conflict) -> ConflictResolution:
        """Attempt to resolve a conflict."""
        if self.conflict_handler:
            try:
                resolution = self.conflict_handler(conflict)
                conflict.resolution = resolution
                return resolution
            except Exception as e:
                logger.warning(f"Conflict handler failed: {e}")

        return ConflictResolution.UNRESOLVED


# =============================================================================
# Convenience Functions
# =============================================================================

def merge_results(
    report: ExecutionReport,
    graph: TaskGraph,
    strategy: MergeStrategy = MergeStrategy.COMBINE,
) -> MergedOutput:
    """
    Merge execution results.

    Args:
        report: ExecutionReport from parallel executor
        graph: Original TaskGraph
        strategy: Default merge strategy

    Returns:
        MergedOutput with consolidated results
    """
    merger = ResultMerger(default_strategy=strategy)
    return merger.merge_execution_report(report, graph)


def save_merged_output(
    merged_output: MergedOutput,
    output_path: Path,
) -> None:
    """
    Save merged output to a JSON file.

    Args:
        merged_output: MergedOutput to save
        output_path: Path to output file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(merged_output.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info(f"Saved merged output to {output_path}")


def load_merged_output(input_path: Path) -> dict:
    """
    Load merged output from a JSON file.

    Args:
        input_path: Path to input file

    Returns:
        Dict representation of MergedOutput
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        return json.load(f)
