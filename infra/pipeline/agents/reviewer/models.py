"""
Models for REVIEWER Agent.

Data structures for code review workflow.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class IssueSeverity(Enum):
    """Severity levels for review issues."""
    CRITICAL = "critical"      # 🔴 Blocks release
    WARNING = "warning"        # 🟡 Should fix
    RECOMMENDATION = "recommendation"  # 🔵 Nice to have
    INFO = "info"              # ⚪ Informational


class IssueCategory(Enum):
    """Categories of review issues."""
    # Critical categories
    SECURITY = "security"
    DATA_INTEGRITY = "data_integrity"
    LOGIC_ERROR = "logic_error"
    PERFORMANCE = "performance"

    # Warning categories
    STYLE = "style"
    NAMING = "naming"
    COMPLEXITY = "complexity"
    MAINTAINABILITY = "maintainability"

    # Recommendation categories
    OPTIMIZATION = "optimization"
    BEST_PRACTICE = "best_practice"
    DOCUMENTATION = "documentation"


class ReviewVerdict(Enum):
    """Final review verdict."""
    APPROVED = "approved"                    # ✅ Can deploy
    CHANGES_REQUESTED = "changes_requested"  # ⚠️ Needs work
    BLOCKED = "blocked"                      # 🔴 Cannot proceed


@dataclass
class DiffHunk:
    """A single hunk in a diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str
    added_lines: List[str] = field(default_factory=list)
    removed_lines: List[str] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if hunk has actual changes."""
        return len(self.added_lines) > 0 or len(self.removed_lines) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "old_start": self.old_start,
            "old_count": self.old_count,
            "new_start": self.new_start,
            "new_count": self.new_count,
            "added_lines": len(self.added_lines),
            "removed_lines": len(self.removed_lines),
        }


@dataclass
class FileChange:
    """Represents changes to a single file."""
    file_path: str
    change_type: str  # added, modified, deleted, renamed
    old_path: Optional[str] = None  # for renames
    hunks: List[DiffHunk] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    is_bsl: bool = False

    def __post_init__(self):
        """Calculate metrics after init."""
        self.is_bsl = self.file_path.lower().endswith('.bsl')
        if self.hunks and self.additions == 0 and self.deletions == 0:
            self.additions = sum(len(h.added_lines) for h in self.hunks)
            self.deletions = sum(len(h.removed_lines) for h in self.hunks)

    @property
    def total_changes(self) -> int:
        """Total lines changed."""
        return self.additions + self.deletions

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "file_path": self.file_path,
            "change_type": self.change_type,
            "additions": self.additions,
            "deletions": self.deletions,
            "is_bsl": self.is_bsl,
            "hunks_count": len(self.hunks),
        }


@dataclass
class ReviewIssue:
    """A single issue found during review."""
    id: str
    title: str
    description: str
    severity: IssueSeverity
    category: IssueCategory
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    recommendation: Optional[str] = None

    def __post_init__(self):
        """Generate ID if not provided."""
        if not self.id:
            prefix = {
                IssueSeverity.CRITICAL: "CR",
                IssueSeverity.WARNING: "WRN",
                IssueSeverity.RECOMMENDATION: "REC",
                IssueSeverity.INFO: "INFO",
            }.get(self.severity, "ISS")
            self.id = f"{prefix}-001"

    @property
    def severity_icon(self) -> str:
        """Get severity icon."""
        return {
            IssueSeverity.CRITICAL: "🔴",
            IssueSeverity.WARNING: "🟡",
            IssueSeverity.RECOMMENDATION: "🔵",
            IssueSeverity.INFO: "⚪",
        }.get(self.severity, "⚪")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "category": self.category.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "recommendation": self.recommendation,
        }

    def to_markdown(self) -> str:
        """Format as markdown."""
        lines = [
            f"### {self.id}: {self.title}",
            f"- **Серьёзность:** {self.severity_icon} {self.severity.value.title()}",
            f"- **Категория:** {self.category.value}",
        ]

        if self.file_path:
            lines.append(f"- **Файл:** `{self.file_path}`")
        if self.line_number:
            lines.append(f"- **Строка:** {self.line_number}")

        lines.append(f"- **Описание:** {self.description}")

        if self.code_snippet:
            lines.extend([
                "- **Код:**",
                "```bsl",
                self.code_snippet,
                "```",
            ])

        if self.recommendation:
            lines.append(f"- **Рекомендация:** {self.recommendation}")

        return "\n".join(lines)


@dataclass
class StyleViolation:
    """Code style violation."""
    rule_id: str
    rule_name: str
    file_path: str
    line_number: int
    column: Optional[int] = None
    message: str = ""
    severity: IssueSeverity = IssueSeverity.WARNING
    code_line: Optional[str] = None

    def to_review_issue(self) -> ReviewIssue:
        """Convert to ReviewIssue."""
        return ReviewIssue(
            id="",  # Will be assigned
            title=self.rule_name,
            description=self.message,
            severity=self.severity,
            category=IssueCategory.STYLE,
            file_path=self.file_path,
            line_number=self.line_number,
            code_snippet=self.code_line,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "message": self.message,
            "severity": self.severity.value,
        }


@dataclass
class ArchIssue:
    """Architecture issue."""
    component: str
    issue_type: str  # missing, wrong_interface, wrong_structure, circular_dep
    description: str
    severity: IssueSeverity = IssueSeverity.WARNING
    related_files: List[str] = field(default_factory=list)
    recommendation: Optional[str] = None

    def to_review_issue(self) -> ReviewIssue:
        """Convert to ReviewIssue."""
        return ReviewIssue(
            id="",
            title=f"Архитектура: {self.component}",
            description=self.description,
            severity=self.severity,
            category=IssueCategory.MAINTAINABILITY,
            file_path=self.related_files[0] if self.related_files else None,
            recommendation=self.recommendation,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "component": self.component,
            "issue_type": self.issue_type,
            "description": self.description,
            "severity": self.severity.value,
            "related_files": self.related_files,
        }


@dataclass
class StandardCheck:
    """Result of a standard compliance check."""
    standard_name: str
    passed: bool
    status: str  # ✅, ⚠️, ❌
    comment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "standard_name": self.standard_name,
            "passed": self.passed,
            "status": self.status,
            "comment": self.comment,
        }


@dataclass
class ReviewReport:
    """Complete review report."""
    project_id: str
    task_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Analyzed items
    files_reviewed: List[FileChange] = field(default_factory=list)

    # Issues
    issues: List[ReviewIssue] = field(default_factory=list)

    # Standard checks
    standard_checks: List[StandardCheck] = field(default_factory=list)

    # Verdict
    verdict: ReviewVerdict = ReviewVerdict.APPROVED
    quality_score: float = 10.0  # 0-10

    @property
    def critical_issues(self) -> List[ReviewIssue]:
        """Get critical issues."""
        return [i for i in self.issues if i.severity == IssueSeverity.CRITICAL]

    @property
    def warnings(self) -> List[ReviewIssue]:
        """Get warnings."""
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    @property
    def recommendations(self) -> List[ReviewIssue]:
        """Get recommendations."""
        return [i for i in self.issues if i.severity == IssueSeverity.RECOMMENDATION]

    @property
    def total_files(self) -> int:
        """Total files reviewed."""
        return len(self.files_reviewed)

    @property
    def bsl_files(self) -> int:
        """BSL files reviewed."""
        return len([f for f in self.files_reviewed if f.is_bsl])

    @property
    def verdict_icon(self) -> str:
        """Get verdict icon."""
        return {
            ReviewVerdict.APPROVED: "✅",
            ReviewVerdict.CHANGES_REQUESTED: "⚠️",
            ReviewVerdict.BLOCKED: "🔴",
        }.get(self.verdict, "❓")

    def determine_verdict(self) -> ReviewVerdict:
        """Determine verdict based on issues."""
        if self.critical_issues:
            return ReviewVerdict.BLOCKED
        elif len(self.warnings) > 3:
            return ReviewVerdict.CHANGES_REQUESTED
        else:
            return ReviewVerdict.APPROVED

    def calculate_quality_score(self) -> float:
        """Calculate quality score (0-10)."""
        score = 10.0

        # Deduct for critical issues
        score -= len(self.critical_issues) * 3.0

        # Deduct for warnings
        score -= len(self.warnings) * 0.5

        # Deduct for recommendations
        score -= len(self.recommendations) * 0.1

        # Ensure bounds
        return max(0.0, min(10.0, score))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "files_reviewed": len(self.files_reviewed),
            "bsl_files": self.bsl_files,
            "critical_count": len(self.critical_issues),
            "warning_count": len(self.warnings),
            "recommendation_count": len(self.recommendations),
            "verdict": self.verdict.value,
            "quality_score": round(self.quality_score, 1),
        }

    def to_markdown(self) -> str:
        """Generate full markdown report."""
        lines = [
            "# Code Review Report",
            "",
            f"> **Проект:** {self.project_id}",
            f"> **Задача:** {self.task_id}",
            f"> **Ревьюер:** REVIEWER Agent",
            f"> **Дата:** {self.timestamp.strftime('%Y-%m-%d %H:%M')}",
            f"> **Вердикт:** {self.verdict_icon} {self.verdict.value.upper().replace('_', ' ')}",
            "",
            "---",
            "",
            "## Сводка",
            "",
            "| Метрика | Значение |",
            "|---------|----------|",
            f"| Файлов проверено | {self.total_files} |",
            f"| BSL файлов | {self.bsl_files} |",
            f"| Критических замечаний | {len(self.critical_issues)} |",
            f"| Предупреждений | {len(self.warnings)} |",
            f"| Рекомендаций | {len(self.recommendations)} |",
            f"| Оценка качества | {self.quality_score:.1f}/10 |",
            "",
        ]

        # Critical issues
        if self.critical_issues:
            lines.extend([
                "---",
                "",
                "## 🔴 Критические замечания",
                "",
            ])
            for issue in self.critical_issues:
                lines.append(issue.to_markdown())
                lines.append("")

        # Warnings
        if self.warnings:
            lines.extend([
                "---",
                "",
                "## 🟡 Предупреждения",
                "",
            ])
            for issue in self.warnings:
                lines.append(issue.to_markdown())
                lines.append("")

        # Recommendations
        if self.recommendations:
            lines.extend([
                "---",
                "",
                "## 🔵 Рекомендации",
                "",
            ])
            for issue in self.recommendations:
                lines.append(issue.to_markdown())
                lines.append("")

        # Standard checks
        if self.standard_checks:
            lines.extend([
                "---",
                "",
                "## Проверка стандартов",
                "",
                "| Стандарт | Статус | Комментарий |",
                "|----------|--------|-------------|",
            ])
            for check in self.standard_checks:
                comment = check.comment or "-"
                lines.append(f"| {check.standard_name} | {check.status} | {comment} |")
            lines.append("")

        # Files reviewed
        if self.files_reviewed:
            lines.extend([
                "---",
                "",
                "## Проверенные файлы",
                "",
                "| Файл | Тип | +/- |",
                "|------|-----|-----|",
            ])
            for f in self.files_reviewed[:20]:  # Limit to 20
                lines.append(f"| `{f.file_path}` | {f.change_type} | +{f.additions}/-{f.deletions} |")
            if len(self.files_reviewed) > 20:
                lines.append(f"| ... и ещё {len(self.files_reviewed) - 20} файлов | | |")
            lines.append("")

        # Conclusion
        lines.extend([
            "---",
            "",
            "## Заключение",
            "",
        ])

        if self.verdict == ReviewVerdict.APPROVED:
            lines.append("✅ Код проверен и одобрен. Можно продолжать.")
        elif self.verdict == ReviewVerdict.CHANGES_REQUESTED:
            lines.append("⚠️ Требуются доработки. Исправьте предупреждения перед продолжением.")
        else:
            lines.append("🔴 Код заблокирован. Исправьте критические замечания.")

        # Next steps
        lines.extend([
            "",
            "---",
            "",
            "## Следующие шаги",
            "",
        ])

        if self.critical_issues:
            lines.append("- [ ] Исправить критические замечания (CR-*)")
        if self.warnings:
            lines.append("- [ ] Рассмотреть предупреждения (WRN-*)")
        if self.recommendations:
            lines.append("- [ ] Учесть рекомендации (REC-*)")
        if not self.issues:
            lines.append("- [x] Код готов к следующему этапу")

        lines.append("")
        return "\n".join(lines)
