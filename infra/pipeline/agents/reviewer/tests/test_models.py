"""
Tests for REVIEWER models.
"""

import pytest
from datetime import datetime

from agents.reviewer.models import (
    IssueSeverity,
    IssueCategory,
    ReviewVerdict,
    DiffHunk,
    FileChange,
    ReviewIssue,
    StyleViolation,
    ArchIssue,
    StandardCheck,
    ReviewReport,
)


class TestIssueSeverity:
    """Tests for IssueSeverity enum."""

    def test_values(self):
        """Test enum values."""
        assert IssueSeverity.CRITICAL.value == "critical"
        assert IssueSeverity.WARNING.value == "warning"
        assert IssueSeverity.RECOMMENDATION.value == "recommendation"
        assert IssueSeverity.INFO.value == "info"

    def test_all_values_exist(self):
        """Test all expected values exist."""
        values = [e.value for e in IssueSeverity]
        assert "critical" in values
        assert "warning" in values
        assert "recommendation" in values
        assert "info" in values


class TestIssueCategory:
    """Tests for IssueCategory enum."""

    def test_critical_categories(self):
        """Test critical category values."""
        assert IssueCategory.SECURITY.value == "security"
        assert IssueCategory.DATA_INTEGRITY.value == "data_integrity"
        assert IssueCategory.LOGIC_ERROR.value == "logic_error"

    def test_warning_categories(self):
        """Test warning category values."""
        assert IssueCategory.STYLE.value == "style"
        assert IssueCategory.NAMING.value == "naming"
        assert IssueCategory.COMPLEXITY.value == "complexity"


class TestReviewVerdict:
    """Tests for ReviewVerdict enum."""

    def test_values(self):
        """Test verdict values."""
        assert ReviewVerdict.APPROVED.value == "approved"
        assert ReviewVerdict.CHANGES_REQUESTED.value == "changes_requested"
        assert ReviewVerdict.BLOCKED.value == "blocked"


class TestDiffHunk:
    """Tests for DiffHunk dataclass."""

    def test_creation(self):
        """Test hunk creation."""
        hunk = DiffHunk(
            old_start=1,
            old_count=5,
            new_start=1,
            new_count=7,
            content="test content"
        )
        assert hunk.old_start == 1
        assert hunk.new_count == 7

    def test_has_changes_with_additions(self):
        """Test has_changes with additions."""
        hunk = DiffHunk(
            old_start=1, old_count=1, new_start=1, new_count=2,
            content="",
            added_lines=["new line"]
        )
        assert hunk.has_changes is True

    def test_has_changes_with_removals(self):
        """Test has_changes with removals."""
        hunk = DiffHunk(
            old_start=1, old_count=2, new_start=1, new_count=1,
            content="",
            removed_lines=["old line"]
        )
        assert hunk.has_changes is True

    def test_has_changes_empty(self):
        """Test has_changes when empty."""
        hunk = DiffHunk(
            old_start=1, old_count=1, new_start=1, new_count=1,
            content=""
        )
        assert hunk.has_changes is False

    def test_to_dict(self):
        """Test serialization."""
        hunk = DiffHunk(
            old_start=10, old_count=5, new_start=10, new_count=8,
            content="",
            added_lines=["a", "b", "c"],
            removed_lines=["x"]
        )
        d = hunk.to_dict()
        assert d["old_start"] == 10
        assert d["added_lines"] == 3
        assert d["removed_lines"] == 1


class TestFileChange:
    """Tests for FileChange dataclass."""

    def test_creation(self):
        """Test file change creation."""
        fc = FileChange(
            file_path="src/Module.bsl",
            change_type="modified"
        )
        assert fc.file_path == "src/Module.bsl"
        assert fc.is_bsl is True

    def test_is_bsl_detection(self):
        """Test BSL file detection."""
        bsl_file = FileChange(file_path="Module.bsl", change_type="added")
        assert bsl_file.is_bsl is True

        py_file = FileChange(file_path="script.py", change_type="added")
        assert py_file.is_bsl is False

        upper_bsl = FileChange(file_path="Module.BSL", change_type="added")
        assert upper_bsl.is_bsl is True

    def test_total_changes(self):
        """Test total changes calculation."""
        fc = FileChange(
            file_path="test.bsl",
            change_type="modified",
            additions=10,
            deletions=3
        )
        assert fc.total_changes == 13

    def test_changes_from_hunks(self):
        """Test changes calculated from hunks."""
        hunk = DiffHunk(
            old_start=1, old_count=5, new_start=1, new_count=8,
            content="",
            added_lines=["a", "b", "c"],
            removed_lines=["x", "y"]
        )
        fc = FileChange(
            file_path="test.bsl",
            change_type="modified",
            hunks=[hunk]
        )
        assert fc.additions == 3
        assert fc.deletions == 2


class TestReviewIssue:
    """Tests for ReviewIssue dataclass."""

    def test_creation(self):
        """Test issue creation."""
        issue = ReviewIssue(
            id="CR-001",
            title="SQL инъекция",
            description="Обнаружена конкатенация строк",
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.SECURITY
        )
        assert issue.id == "CR-001"
        assert issue.severity == IssueSeverity.CRITICAL

    def test_severity_icon(self):
        """Test severity icons."""
        critical = ReviewIssue(
            id="", title="", description="",
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.SECURITY
        )
        assert critical.severity_icon == "🔴"

        warning = ReviewIssue(
            id="", title="", description="",
            severity=IssueSeverity.WARNING,
            category=IssueCategory.STYLE
        )
        assert warning.severity_icon == "🟡"

        rec = ReviewIssue(
            id="", title="", description="",
            severity=IssueSeverity.RECOMMENDATION,
            category=IssueCategory.OPTIMIZATION
        )
        assert rec.severity_icon == "🔵"

    def test_auto_id_generation(self):
        """Test automatic ID generation."""
        issue = ReviewIssue(
            id="",
            title="Test",
            description="Test",
            severity=IssueSeverity.WARNING,
            category=IssueCategory.STYLE
        )
        assert issue.id == "WRN-001"

    def test_to_markdown(self):
        """Test markdown generation."""
        issue = ReviewIssue(
            id="CR-001",
            title="Критическая ошибка",
            description="Описание проблемы",
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.SECURITY,
            file_path="Module.bsl",
            line_number=42,
            code_snippet="Опасный код",
            recommendation="Исправить"
        )
        md = issue.to_markdown()
        assert "CR-001" in md
        assert "Критическая ошибка" in md
        assert "Module.bsl" in md
        assert "42" in md
        assert "Опасный код" in md
        assert "Исправить" in md


class TestStyleViolation:
    """Tests for StyleViolation dataclass."""

    def test_creation(self):
        """Test violation creation."""
        v = StyleViolation(
            rule_id="N001",
            rule_name="Неинформативное имя",
            file_path="test.bsl",
            line_number=10,
            message="Короткое имя переменной"
        )
        assert v.rule_id == "N001"
        assert v.line_number == 10

    def test_to_review_issue(self):
        """Test conversion to ReviewIssue."""
        v = StyleViolation(
            rule_id="SEC001",
            rule_name="SQL инъекция",
            file_path="test.bsl",
            line_number=25,
            message="Конкатенация строк",
            severity=IssueSeverity.CRITICAL
        )
        issue = v.to_review_issue()
        assert issue.title == "SQL инъекция"
        assert issue.severity == IssueSeverity.CRITICAL
        assert issue.category == IssueCategory.STYLE


class TestArchIssue:
    """Tests for ArchIssue dataclass."""

    def test_creation(self):
        """Test architecture issue creation."""
        ai = ArchIssue(
            component="МодульОбработки",
            issue_type="missing",
            description="Компонент не реализован"
        )
        assert ai.component == "МодульОбработки"
        assert ai.issue_type == "missing"

    def test_to_review_issue(self):
        """Test conversion to ReviewIssue."""
        ai = ArchIssue(
            component="БизнесЛогика",
            issue_type="wrong_structure",
            description="Нарушение структуры",
            severity=IssueSeverity.WARNING,
            related_files=["form.bsl", "module.bsl"]
        )
        issue = ai.to_review_issue()
        assert "БизнесЛогика" in issue.title
        assert issue.category == IssueCategory.MAINTAINABILITY
        assert issue.file_path == "form.bsl"


class TestStandardCheck:
    """Tests for StandardCheck dataclass."""

    def test_creation(self):
        """Test standard check creation."""
        sc = StandardCheck(
            standard_name="Именование переменных",
            passed=True,
            status="✅",
            comment="Все имена корректны"
        )
        assert sc.passed is True
        assert sc.status == "✅"

    def test_to_dict(self):
        """Test serialization."""
        sc = StandardCheck(
            standard_name="Транзакции",
            passed=False,
            status="❌",
            comment="Несбалансированные транзакции"
        )
        d = sc.to_dict()
        assert d["standard_name"] == "Транзакции"
        assert d["passed"] is False


class TestReviewReport:
    """Tests for ReviewReport dataclass."""

    def test_creation(self):
        """Test report creation."""
        report = ReviewReport(
            project_id="PROJECT",
            task_id="TASK-123"
        )
        assert report.project_id == "PROJECT"
        assert report.verdict == ReviewVerdict.APPROVED

    def test_issue_filtering(self):
        """Test issue filtering by severity."""
        report = ReviewReport(
            project_id="P",
            task_id="T",
            issues=[
                ReviewIssue(
                    id="CR-001", title="", description="",
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.SECURITY
                ),
                ReviewIssue(
                    id="WRN-001", title="", description="",
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.STYLE
                ),
                ReviewIssue(
                    id="WRN-002", title="", description="",
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.NAMING
                ),
                ReviewIssue(
                    id="REC-001", title="", description="",
                    severity=IssueSeverity.RECOMMENDATION,
                    category=IssueCategory.OPTIMIZATION
                ),
            ]
        )
        assert len(report.critical_issues) == 1
        assert len(report.warnings) == 2
        assert len(report.recommendations) == 1

    def test_determine_verdict_blocked(self):
        """Test verdict determination - blocked."""
        report = ReviewReport(
            project_id="P", task_id="T",
            issues=[
                ReviewIssue(
                    id="CR-001", title="", description="",
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.SECURITY
                )
            ]
        )
        assert report.determine_verdict() == ReviewVerdict.BLOCKED

    def test_determine_verdict_changes_requested(self):
        """Test verdict determination - changes requested."""
        warnings = [
            ReviewIssue(
                id=f"WRN-{i}", title="", description="",
                severity=IssueSeverity.WARNING,
                category=IssueCategory.STYLE
            )
            for i in range(5)
        ]
        report = ReviewReport(
            project_id="P", task_id="T",
            issues=warnings
        )
        assert report.determine_verdict() == ReviewVerdict.CHANGES_REQUESTED

    def test_determine_verdict_approved(self):
        """Test verdict determination - approved."""
        report = ReviewReport(
            project_id="P", task_id="T",
            issues=[
                ReviewIssue(
                    id="REC-001", title="", description="",
                    severity=IssueSeverity.RECOMMENDATION,
                    category=IssueCategory.OPTIMIZATION
                )
            ]
        )
        assert report.determine_verdict() == ReviewVerdict.APPROVED

    def test_calculate_quality_score(self):
        """Test quality score calculation."""
        report = ReviewReport(project_id="P", task_id="T")
        assert report.calculate_quality_score() == 10.0

        report.issues.append(ReviewIssue(
            id="CR-001", title="", description="",
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.SECURITY
        ))
        assert report.calculate_quality_score() == 7.0  # 10 - 3

        report.issues.append(ReviewIssue(
            id="WRN-001", title="", description="",
            severity=IssueSeverity.WARNING,
            category=IssueCategory.STYLE
        ))
        assert report.calculate_quality_score() == 6.5  # 10 - 3 - 0.5

    def test_verdict_icon(self):
        """Test verdict icons."""
        report = ReviewReport(project_id="P", task_id="T")

        report.verdict = ReviewVerdict.APPROVED
        assert report.verdict_icon == "✅"

        report.verdict = ReviewVerdict.CHANGES_REQUESTED
        assert report.verdict_icon == "⚠️"

        report.verdict = ReviewVerdict.BLOCKED
        assert report.verdict_icon == "🔴"

    def test_to_markdown(self):
        """Test markdown report generation."""
        report = ReviewReport(
            project_id="PROJECT-X",
            task_id="TASK-456",
            issues=[
                ReviewIssue(
                    id="CR-001",
                    title="Критическая ошибка",
                    description="Описание",
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.SECURITY
                )
            ],
            standard_checks=[
                StandardCheck(
                    standard_name="Транзакции",
                    passed=True,
                    status="✅"
                )
            ],
            files_reviewed=[
                FileChange(file_path="test.bsl", change_type="modified")
            ]
        )
        report.verdict = report.determine_verdict()
        report.quality_score = report.calculate_quality_score()

        md = report.to_markdown()
        assert "PROJECT-X" in md
        assert "TASK-456" in md
        assert "Критическая ошибка" in md
        assert "Транзакции" in md
        assert "test.bsl" in md
        assert "🔴" in md  # Blocked due to critical

    def test_file_counts(self):
        """Test file count properties."""
        report = ReviewReport(
            project_id="P", task_id="T",
            files_reviewed=[
                FileChange(file_path="a.bsl", change_type="modified"),
                FileChange(file_path="b.bsl", change_type="added"),
                FileChange(file_path="c.py", change_type="modified"),
            ]
        )
        assert report.total_files == 3
        assert report.bsl_files == 2
