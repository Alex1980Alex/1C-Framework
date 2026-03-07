"""
Tests for Conflict Resolver.

Sprint 3.2.4: Разрешение конфликтов
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import json

from models import (
    Conflict,
    ConflictType,
    ConflictResolution,
)
from .conflict_resolver import (
    ResolutionStrategy,
    ResolutionRule,
    ResolutionResult,
    ConflictReport,
    ConflictResolver,
    resolve_conflicts,
    create_default_rules,
    save_conflict_report,
    load_conflict_report,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def simple_conflict():
    """Create a simple write-write conflict."""
    return Conflict(
        id="conflict-1",
        conflict_type=ConflictType.WRITE_WRITE,
        resource="file:output.bsl",
        task_ids=["T1", "T2"],
        description="Multiple tasks wrote to output.bsl",
    )


@pytest.fixture
def multi_task_conflict():
    """Create a conflict involving multiple tasks."""
    return Conflict(
        id="conflict-2",
        conflict_type=ConflictType.WRITE_WRITE,
        resource="file:shared.bsl",
        task_ids=["T1", "T2", "T3"],
        description="Three tasks wrote to shared.bsl",
    )


@pytest.fixture
def task_outputs():
    """Create sample task outputs."""
    return {
        "T1": {"data": "value1", "count": 10},
        "T2": {"data": "value2", "count": 20},
        "T3": {"data": "value3", "count": 30},
    }


@pytest.fixture
def string_outputs():
    """Create string task outputs."""
    return {
        "T1": "Line 1 from T1",
        "T2": "Line 2 from T2",
    }


@pytest.fixture
def list_outputs():
    """Create list task outputs."""
    return {
        "T1": [1, 2, 3],
        "T2": [3, 4, 5],
    }


# =============================================================================
# Test ResolutionResult
# =============================================================================

class TestResolutionResult:
    """Test ResolutionResult dataclass."""

    def test_resolution_result_creation(self):
        """Test creating ResolutionResult."""
        result = ResolutionResult(
            conflict_id="c1",
            resolved=True,
            resolution=ConflictResolution.TAKE_FIRST,
            chosen_task_id="T1",
            reason="Test reason",
        )
        assert result.conflict_id == "c1"
        assert result.resolved is True
        assert result.resolution == ConflictResolution.TAKE_FIRST

    def test_resolution_result_to_dict(self):
        """Test ResolutionResult serialization."""
        result = ResolutionResult(
            conflict_id="c1",
            resolved=True,
            resolution=ConflictResolution.TAKE_LAST,
            chosen_task_id="T2",
            reason="Took last",
        )
        d = result.to_dict()
        assert d["conflict_id"] == "c1"
        assert d["resolved"] is True
        assert d["resolution"] == "take_last"
        assert d["chosen_task_id"] == "T2"


# =============================================================================
# Test ConflictReport
# =============================================================================

class TestConflictReport:
    """Test ConflictReport dataclass."""

    def test_conflict_report_creation(self):
        """Test creating ConflictReport."""
        report = ConflictReport(
            total_conflicts=5,
            resolved_conflicts=3,
            unresolved_conflicts=2,
        )
        assert report.total_conflicts == 5
        assert report.all_resolved is False

    def test_conflict_report_all_resolved(self):
        """Test all_resolved property."""
        report = ConflictReport(
            total_conflicts=5,
            resolved_conflicts=5,
            unresolved_conflicts=0,
            manual_review_required=0,
        )
        assert report.all_resolved is True

    def test_conflict_report_to_dict(self):
        """Test ConflictReport serialization."""
        report = ConflictReport(
            total_conflicts=3,
            resolved_conflicts=2,
            unresolved_conflicts=1,
            generated_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        d = report.to_dict()
        assert d["total_conflicts"] == 3
        assert d["all_resolved"] is False


# =============================================================================
# Test ResolutionRule
# =============================================================================

class TestResolutionRule:
    """Test ResolutionRule matching."""

    def test_rule_matches_bsl(self):
        """Test rule matching BSL files."""
        rule = ResolutionRule(
            resource_pattern=r"file:.*\.bsl$",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.TAKE_LAST,
        )
        assert rule.matches("file:module.bsl", ConflictType.WRITE_WRITE) is True
        assert rule.matches("file:module.xml", ConflictType.WRITE_WRITE) is False

    def test_rule_matches_conflict_type(self):
        """Test rule matching conflict type."""
        rule = ResolutionRule(
            resource_pattern=r"file:.*",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.TAKE_FIRST,
        )
        assert rule.matches("file:test", ConflictType.WRITE_WRITE) is True
        assert rule.matches("file:test", ConflictType.WRITE_READ) is False


# =============================================================================
# Test ConflictResolver - Basic Strategies
# =============================================================================

class TestConflictResolverTakeFirst:
    """Test TAKE_FIRST resolution strategy."""

    def test_take_first(self, simple_conflict, task_outputs):
        """Test taking first task's output."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_FIRST)
        result = resolver.resolve_conflict(simple_conflict, task_outputs)

        assert result.resolved is True
        assert result.resolution == ConflictResolution.TAKE_FIRST
        assert result.chosen_task_id == "T1"
        assert result.chosen_value == {"data": "value1", "count": 10}

    def test_take_first_empty_conflict(self, task_outputs):
        """Test take_first with no task IDs."""
        conflict = Conflict(
            id="c1",
            conflict_type=ConflictType.WRITE_WRITE,
            resource="file:test.bsl",
            task_ids=[],
            description="Empty conflict",
        )
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_FIRST)
        result = resolver.resolve_conflict(conflict, task_outputs)

        assert result.resolved is False


class TestConflictResolverTakeLast:
    """Test TAKE_LAST resolution strategy."""

    def test_take_last(self, simple_conflict, task_outputs):
        """Test taking last task's output."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_LAST)
        result = resolver.resolve_conflict(simple_conflict, task_outputs)

        assert result.resolved is True
        assert result.resolution == ConflictResolution.TAKE_LAST
        assert result.chosen_task_id == "T2"
        assert result.chosen_value == {"data": "value2", "count": 20}

    def test_take_last_multi_task(self, multi_task_conflict, task_outputs):
        """Test taking last with multiple tasks."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_LAST)
        result = resolver.resolve_conflict(multi_task_conflict, task_outputs)

        assert result.chosen_task_id == "T3"
        assert result.chosen_value == {"data": "value3", "count": 30}


class TestConflictResolverTakePriority:
    """Test TAKE_PRIORITY resolution strategy."""

    def test_take_priority(self, multi_task_conflict, task_outputs):
        """Test priority-based resolution."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_PRIORITY)
        resolver.add_rule(ResolutionRule(
            resource_pattern=r"file:.*",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.TAKE_PRIORITY,
            priority_order=["T2", "T1", "T3"],  # T2 is highest priority
        ))

        result = resolver.resolve_conflict(multi_task_conflict, task_outputs)

        assert result.resolved is True
        assert result.chosen_task_id == "T2"

    def test_take_priority_no_order(self, simple_conflict, task_outputs):
        """Test priority falls back to take_first when no order."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_PRIORITY)
        result = resolver.resolve_conflict(simple_conflict, task_outputs)

        # Should fall back to take_first
        assert result.resolved is True
        assert result.chosen_task_id == "T1"


# =============================================================================
# Test ConflictResolver - Merge Strategy
# =============================================================================

class TestConflictResolverMerge:
    """Test MERGE resolution strategy."""

    def test_merge_dicts(self, simple_conflict, task_outputs):
        """Test merging dictionaries."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.MERGE)
        result = resolver.resolve_conflict(simple_conflict, task_outputs)

        assert result.resolved is True
        assert result.resolution == ConflictResolution.MERGED
        # Merged dict should have both values (last wins for same keys)
        assert "data" in result.chosen_value
        assert result.chosen_value["count"] == 20  # From T2 (last)

    def test_merge_strings(self, simple_conflict, string_outputs):
        """Test merging strings."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.MERGE)
        result = resolver.resolve_conflict(simple_conflict, string_outputs)

        assert result.resolved is True
        assert "T1" in result.chosen_value
        assert "T2" in result.chosen_value

    def test_merge_lists(self, simple_conflict, list_outputs):
        """Test merging lists."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.MERGE)
        result = resolver.resolve_conflict(simple_conflict, list_outputs)

        assert result.resolved is True
        # Should have unique values
        assert 1 in result.chosen_value
        assert 5 in result.chosen_value

    def test_merge_empty_values(self, simple_conflict):
        """Test merge with no values."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.MERGE)
        result = resolver.resolve_conflict(simple_conflict, {})

        assert result.resolved is False


# =============================================================================
# Test ConflictResolver - Manual and Skip
# =============================================================================

class TestConflictResolverManual:
    """Test MANUAL resolution strategy."""

    def test_manual_no_handler(self, simple_conflict, task_outputs):
        """Test manual resolution without handler."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.MANUAL)
        result = resolver.resolve_conflict(simple_conflict, task_outputs)

        assert result.resolved is False
        assert result.requires_manual_review is True

    def test_manual_with_handler(self, simple_conflict, task_outputs):
        """Test manual resolution with custom handler."""
        def custom_handler(conflict, outputs):
            return ResolutionResult(
                conflict_id=conflict.id,
                resolved=True,
                resolution=ConflictResolution.TAKE_FIRST,
                chosen_task_id="T1",
                reason="Manual selection",
            )

        resolver = ConflictResolver(
            default_strategy=ResolutionStrategy.MANUAL,
            manual_handler=custom_handler,
        )
        result = resolver.resolve_conflict(simple_conflict, task_outputs)

        assert result.resolved is True
        assert result.chosen_task_id == "T1"


class TestConflictResolverSkip:
    """Test SKIP resolution strategy."""

    def test_skip(self, simple_conflict, task_outputs):
        """Test skipping conflict."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.SKIP)
        result = resolver.resolve_conflict(simple_conflict, task_outputs)

        assert result.resolved is True
        assert result.resolution == ConflictResolution.SKIPPED


# =============================================================================
# Test ConflictResolver - Rule Matching
# =============================================================================

class TestConflictResolverRules:
    """Test rule-based conflict resolution."""

    def test_rule_matching(self, task_outputs):
        """Test that rules are matched correctly."""
        bsl_conflict = Conflict(
            id="c1",
            conflict_type=ConflictType.WRITE_WRITE,
            resource="file:module.bsl",
            task_ids=["T1", "T2"],
            description="BSL conflict",
        )

        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_LAST)
        resolver.add_rule(ResolutionRule(
            resource_pattern=r"file:.*\.bsl$",
            conflict_type=ConflictType.WRITE_WRITE,
            strategy=ResolutionStrategy.TAKE_FIRST,
        ))

        result = resolver.resolve_conflict(bsl_conflict, task_outputs)

        # Should use rule (TAKE_FIRST) not default (TAKE_LAST)
        assert result.resolution == ConflictResolution.TAKE_FIRST
        assert result.chosen_task_id == "T1"

    def test_default_rules(self):
        """Test creating default rules."""
        rules = create_default_rules()
        assert len(rules) > 0

        # Check that BSL rule exists
        bsl_rules = [r for r in rules if ".bsl" in r.resource_pattern]
        assert len(bsl_rules) > 0


# =============================================================================
# Test ConflictResolver - Resolve All
# =============================================================================

class TestConflictResolverResolveAll:
    """Test resolving multiple conflicts."""

    def test_resolve_all(self, task_outputs):
        """Test resolving all conflicts at once."""
        conflicts = [
            Conflict(
                id="c1",
                conflict_type=ConflictType.WRITE_WRITE,
                resource="file:a.bsl",
                task_ids=["T1", "T2"],
                description="Conflict 1",
            ),
            Conflict(
                id="c2",
                conflict_type=ConflictType.WRITE_WRITE,
                resource="file:b.bsl",
                task_ids=["T2", "T3"],
                description="Conflict 2",
            ),
        ]

        resolver = ConflictResolver(default_strategy=ResolutionStrategy.TAKE_LAST)
        report = resolver.resolve_all(conflicts, task_outputs)

        assert report.total_conflicts == 2
        assert report.resolved_conflicts == 2
        assert report.unresolved_conflicts == 0
        assert report.all_resolved is True
        assert len(report.resolutions) == 2


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_resolve_conflicts_function(self, simple_conflict, task_outputs):
        """Test resolve_conflicts convenience function."""
        report = resolve_conflicts(
            [simple_conflict],
            task_outputs,
            strategy=ResolutionStrategy.TAKE_FIRST,
        )

        assert report.total_conflicts == 1
        assert report.resolved_conflicts == 1

    def test_save_and_load_report(self):
        """Test saving and loading conflict report."""
        report = ConflictReport(
            total_conflicts=3,
            resolved_conflicts=2,
            unresolved_conflicts=1,
            generated_at=datetime.now(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_conflict_report(report, path)

            assert path.exists()

            loaded = load_conflict_report(path)
            assert loaded["total_conflicts"] == 3
            assert loaded["resolved_conflicts"] == 2


# =============================================================================
# Test ResolutionStrategy
# =============================================================================

class TestResolutionStrategy:
    """Test ResolutionStrategy enum."""

    def test_strategy_values(self):
        """Test all strategy values."""
        assert ResolutionStrategy.TAKE_FIRST.value == "take_first"
        assert ResolutionStrategy.TAKE_LAST.value == "take_last"
        assert ResolutionStrategy.TAKE_PRIORITY.value == "take_priority"
        assert ResolutionStrategy.MERGE.value == "merge"
        assert ResolutionStrategy.MANUAL.value == "manual"
        assert ResolutionStrategy.SKIP.value == "skip"
