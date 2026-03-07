"""
Conflict Resolver for Parallel Pipeline Execution.

Sprint 3.2.4: Разрешение конфликтов

This module provides functionality to:
- Detect conflicts between parallel task outputs
- Apply resolution strategies (take_first, take_last, merge, manual)
- Handle resource conflicts (write-write, read-write)
- Generate conflict reports for user review
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
    Conflict,
    ConflictType,
    ConflictResolution,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Resolution Strategies
# =============================================================================

class ResolutionStrategy(Enum):
    """Strategy for automatic conflict resolution."""
    TAKE_FIRST = "take_first"       # Take first task's result
    TAKE_LAST = "take_last"         # Take last task's result
    TAKE_PRIORITY = "take_priority" # Take highest priority task's result
    MERGE = "merge"                 # Attempt to merge conflicting values
    MANUAL = "manual"               # Require manual intervention
    SKIP = "skip"                   # Skip conflicting changes


@dataclass
class ResolutionRule:
    """Rule for automatic conflict resolution."""

    resource_pattern: str  # Regex pattern for resource matching
    conflict_type: ConflictType
    strategy: ResolutionStrategy
    priority_order: Optional[list[str]] = None  # Task ID priority for TAKE_PRIORITY

    def matches(self, resource: str, conflict_type: ConflictType) -> bool:
        """Check if this rule matches the conflict."""
        import re
        return (
            conflict_type == self.conflict_type and
            re.match(self.resource_pattern, resource) is not None
        )


@dataclass
class ResolutionResult:
    """Result of conflict resolution."""

    conflict_id: str
    resolved: bool
    resolution: ConflictResolution
    chosen_value: Any = None
    chosen_task_id: Optional[str] = None
    reason: str = ""
    requires_manual_review: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "resolved": self.resolved,
            "resolution": self.resolution.value,
            "chosen_task_id": self.chosen_task_id,
            "reason": self.reason,
            "requires_manual_review": self.requires_manual_review,
        }


@dataclass
class ConflictReport:
    """Report of all conflicts and their resolutions."""

    total_conflicts: int = 0
    resolved_conflicts: int = 0
    unresolved_conflicts: int = 0
    manual_review_required: int = 0
    resolutions: list[ResolutionResult] = field(default_factory=list)
    generated_at: Optional[datetime] = None

    @property
    def all_resolved(self) -> bool:
        """Check if all conflicts are resolved."""
        return self.unresolved_conflicts == 0 and self.manual_review_required == 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_conflicts": self.total_conflicts,
            "resolved_conflicts": self.resolved_conflicts,
            "unresolved_conflicts": self.unresolved_conflicts,
            "manual_review_required": self.manual_review_required,
            "all_resolved": self.all_resolved,
            "resolutions": [r.to_dict() for r in self.resolutions],
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }


# =============================================================================
# Conflict Resolver
# =============================================================================

class ConflictResolver:
    """
    Resolves conflicts between parallel task outputs.

    Features:
    - Multiple resolution strategies
    - Rule-based automatic resolution
    - Priority-based resolution
    - Manual review support
    """

    def __init__(
        self,
        default_strategy: ResolutionStrategy = ResolutionStrategy.TAKE_LAST,
        rules: Optional[list[ResolutionRule]] = None,
        manual_handler: Optional[Callable[[Conflict, dict[str, Any]], ResolutionResult]] = None,
    ):
        """
        Initialize conflict resolver.

        Args:
            default_strategy: Default resolution strategy
            rules: List of resolution rules to apply
            manual_handler: Optional handler for manual resolution
        """
        self.default_strategy = default_strategy
        self.rules = rules or []
        self.manual_handler = manual_handler

    def add_rule(self, rule: ResolutionRule) -> None:
        """Add a resolution rule."""
        self.rules.append(rule)

    def resolve_conflict(
        self,
        conflict: Conflict,
        task_outputs: dict[str, Any],
    ) -> ResolutionResult:
        """
        Resolve a single conflict.

        Args:
            conflict: Conflict to resolve
            task_outputs: Dict of task_id -> output value

        Returns:
            ResolutionResult
        """
        # Find matching rule
        strategy = self.default_strategy
        priority_order = None

        for rule in self.rules:
            if rule.matches(conflict.resource, conflict.conflict_type):
                strategy = rule.strategy
                priority_order = rule.priority_order
                break

        # Apply strategy
        if strategy == ResolutionStrategy.TAKE_FIRST:
            return self._resolve_take_first(conflict, task_outputs)

        elif strategy == ResolutionStrategy.TAKE_LAST:
            return self._resolve_take_last(conflict, task_outputs)

        elif strategy == ResolutionStrategy.TAKE_PRIORITY:
            return self._resolve_take_priority(conflict, task_outputs, priority_order)

        elif strategy == ResolutionStrategy.MERGE:
            return self._resolve_merge(conflict, task_outputs)

        elif strategy == ResolutionStrategy.MANUAL:
            return self._resolve_manual(conflict, task_outputs)

        elif strategy == ResolutionStrategy.SKIP:
            return self._resolve_skip(conflict)

        else:
            return ResolutionResult(
                conflict_id=conflict.id,
                resolved=False,
                resolution=ConflictResolution.UNRESOLVED,
                reason=f"Unknown strategy: {strategy}",
            )

    def resolve_all(
        self,
        conflicts: list[Conflict],
        task_outputs: dict[str, Any],
    ) -> ConflictReport:
        """
        Resolve all conflicts.

        Args:
            conflicts: List of conflicts to resolve
            task_outputs: Dict of task_id -> output value

        Returns:
            ConflictReport with all resolutions
        """
        report = ConflictReport(
            total_conflicts=len(conflicts),
            generated_at=datetime.now(),
        )

        for conflict in conflicts:
            result = self.resolve_conflict(conflict, task_outputs)
            report.resolutions.append(result)

            if result.resolved:
                report.resolved_conflicts += 1
                conflict.resolution = result.resolution
            else:
                report.unresolved_conflicts += 1

            if result.requires_manual_review:
                report.manual_review_required += 1

        return report

    def _resolve_take_first(
        self,
        conflict: Conflict,
        task_outputs: dict[str, Any],
    ) -> ResolutionResult:
        """Take the first task's output."""
        if not conflict.task_ids:
            return ResolutionResult(
                conflict_id=conflict.id,
                resolved=False,
                resolution=ConflictResolution.UNRESOLVED,
                reason="No task IDs in conflict",
            )

        first_task_id = conflict.task_ids[0]
        value = task_outputs.get(first_task_id)

        return ResolutionResult(
            conflict_id=conflict.id,
            resolved=True,
            resolution=ConflictResolution.TAKE_FIRST,
            chosen_value=value,
            chosen_task_id=first_task_id,
            reason=f"Took first task's output: {first_task_id}",
        )

    def _resolve_take_last(
        self,
        conflict: Conflict,
        task_outputs: dict[str, Any],
    ) -> ResolutionResult:
        """Take the last task's output."""
        if not conflict.task_ids:
            return ResolutionResult(
                conflict_id=conflict.id,
                resolved=False,
                resolution=ConflictResolution.UNRESOLVED,
                reason="No task IDs in conflict",
            )

        last_task_id = conflict.task_ids[-1]
        value = task_outputs.get(last_task_id)

        return ResolutionResult(
            conflict_id=conflict.id,
            resolved=True,
            resolution=ConflictResolution.TAKE_LAST,
            chosen_value=value,
            chosen_task_id=last_task_id,
            reason=f"Took last task's output: {last_task_id}",
        )

    def _resolve_take_priority(
        self,
        conflict: Conflict,
        task_outputs: dict[str, Any],
        priority_order: Optional[list[str]],
    ) -> ResolutionResult:
        """Take the highest priority task's output."""
        if not priority_order:
            # Fall back to take_first if no priority defined
            return self._resolve_take_first(conflict, task_outputs)

        # Find highest priority task in conflict
        for task_id in priority_order:
            if task_id in conflict.task_ids:
                value = task_outputs.get(task_id)
                return ResolutionResult(
                    conflict_id=conflict.id,
                    resolved=True,
                    resolution=ConflictResolution.TAKE_FIRST,  # Using TAKE_FIRST as closest
                    chosen_value=value,
                    chosen_task_id=task_id,
                    reason=f"Took highest priority task's output: {task_id}",
                )

        # No prioritized task found, fall back to take_first
        return self._resolve_take_first(conflict, task_outputs)

    def _resolve_merge(
        self,
        conflict: Conflict,
        task_outputs: dict[str, Any],
    ) -> ResolutionResult:
        """Attempt to merge conflicting values."""
        if not conflict.task_ids:
            return ResolutionResult(
                conflict_id=conflict.id,
                resolved=False,
                resolution=ConflictResolution.UNRESOLVED,
                reason="No task IDs in conflict",
            )

        # Collect all values
        values = [task_outputs.get(tid) for tid in conflict.task_ids]
        values = [v for v in values if v is not None]

        if not values:
            return ResolutionResult(
                conflict_id=conflict.id,
                resolved=False,
                resolution=ConflictResolution.UNRESOLVED,
                reason="No values to merge",
            )

        # Try to merge based on type
        try:
            merged = self._merge_values(values)
            return ResolutionResult(
                conflict_id=conflict.id,
                resolved=True,
                resolution=ConflictResolution.MERGED,
                chosen_value=merged,
                reason=f"Merged {len(values)} values",
            )
        except Exception as e:
            return ResolutionResult(
                conflict_id=conflict.id,
                resolved=False,
                resolution=ConflictResolution.UNRESOLVED,
                reason=f"Merge failed: {e}",
                requires_manual_review=True,
            )

    def _merge_values(self, values: list[Any]) -> Any:
        """Merge a list of values."""
        if all(isinstance(v, dict) for v in values):
            # Merge dictionaries
            result = {}
            for v in values:
                result.update(v)
            return result

        if all(isinstance(v, list) for v in values):
            # Concatenate lists, removing duplicates
            result = []
            seen = set()
            for v in values:
                for item in v:
                    key = str(item)
                    if key not in seen:
                        seen.add(key)
                        result.append(item)
            return result

        if all(isinstance(v, str) for v in values):
            # Join strings
            return "\n".join(values)

        # Cannot merge other types
        raise ValueError(f"Cannot merge values of mixed types: {[type(v).__name__ for v in values]}")

    def _resolve_manual(
        self,
        conflict: Conflict,
        task_outputs: dict[str, Any],
    ) -> ResolutionResult:
        """Request manual resolution."""
        if self.manual_handler:
            try:
                return self.manual_handler(conflict, task_outputs)
            except Exception as e:
                logger.warning(f"Manual handler failed: {e}")

        return ResolutionResult(
            conflict_id=conflict.id,
            resolved=False,
            resolution=ConflictResolution.UNRESOLVED,
            reason="Manual resolution required",
            requires_manual_review=True,
        )

    def _resolve_skip(
        self,
        conflict: Conflict,
    ) -> ResolutionResult:
        """Skip the conflicting changes."""
        return ResolutionResult(
            conflict_id=conflict.id,
            resolved=True,
            resolution=ConflictResolution.SKIPPED,
            reason="Conflict skipped by strategy",
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def resolve_conflicts(
    conflicts: list[Conflict],
    task_outputs: dict[str, Any],
    strategy: ResolutionStrategy = ResolutionStrategy.TAKE_LAST,
) -> ConflictReport:
    """
    Resolve conflicts with default settings.

    Args:
        conflicts: List of conflicts to resolve
        task_outputs: Dict of task_id -> output value
        strategy: Default resolution strategy

    Returns:
        ConflictReport
    """
    resolver = ConflictResolver(default_strategy=strategy)
    return resolver.resolve_all(conflicts, task_outputs)


def create_default_rules() -> list[ResolutionRule]:
    """
    Create default resolution rules for 1C development.

    Returns:
        List of ResolutionRule
    """
    return [
        # BSL module files - take last (most recent)
        ResolutionRule(
            resource_pattern=r"file:.*\.bsl$",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.TAKE_LAST,
        ),
        # Form files - require manual review
        ResolutionRule(
            resource_pattern=r"file:.*Form\.xml$",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.MANUAL,
        ),
        # Configuration files - merge when possible
        ResolutionRule(
            resource_pattern=r"file:.*\.json$",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.MERGE,
        ),
        # Documentation - concatenate
        ResolutionRule(
            resource_pattern=r"file:.*\.md$",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.MERGE,
        ),
    ]


def save_conflict_report(
    report: ConflictReport,
    output_path: Path,
) -> None:
    """
    Save conflict report to a JSON file.

    Args:
        report: ConflictReport to save
        output_path: Path to output file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info(f"Saved conflict report to {output_path}")


def load_conflict_report(input_path: Path) -> dict:
    """
    Load conflict report from a JSON file.

    Args:
        input_path: Path to input file

    Returns:
        Dict representation of ConflictReport
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        return json.load(f)
