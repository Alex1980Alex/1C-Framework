"""
REVIEWER Agent - Main Orchestrator.

Integrates with pipeline artifact store and coordinates
all review components for automated code review.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json

from agents.reviewer.models import (
    ReviewReport,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
    ReviewVerdict,
    FileChange,
)
from agents.reviewer.diff_analyzer import DiffAnalyzer, AnalysisResult
from agents.reviewer.style_checker import StyleChecker, StyleCheckResult
from agents.reviewer.arch_checker import ArchChecker, ArchCheckResult
from agents.reviewer.report_generator import ReviewGenerator, ReviewContext


@dataclass
class ReviewerConfig:
    """Configuration for REVIEWER agent."""
    # Severity thresholds
    max_critical_for_approval: int = 0
    max_warnings_for_approval: int = 5

    # Feature flags
    check_style: bool = True
    check_architecture: bool = True
    check_security: bool = True
    check_performance: bool = True

    # Output options
    include_recommendations: bool = True
    include_code_snippets: bool = True
    max_issues_per_category: int = 20

    # Quality thresholds
    min_quality_score: float = 6.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "max_critical_for_approval": self.max_critical_for_approval,
            "max_warnings_for_approval": self.max_warnings_for_approval,
            "check_style": self.check_style,
            "check_architecture": self.check_architecture,
            "check_security": self.check_security,
            "check_performance": self.check_performance,
            "min_quality_score": self.min_quality_score,
        }


@dataclass
class ReviewInput:
    """Input for REVIEWER agent."""
    project_id: str
    task_id: str

    # Artifacts from previous pipeline stages
    spec_path: Optional[str] = None      # spec.md from PM-SPEC
    design_path: Optional[str] = None    # design.md from ARCHITECT
    result_path: Optional[str] = None    # result.md from IMPLEMENTER

    # Code to review
    diff_text: Optional[str] = None      # Git diff
    bsl_files: Dict[str, str] = field(default_factory=dict)  # path -> content

    # Optional: paths to load from
    bsl_paths: List[str] = field(default_factory=list)

    def load_artifacts(self) -> "ReviewInput":
        """Load artifacts from file paths."""
        # Load spec.md
        if self.spec_path and Path(self.spec_path).exists():
            pass  # Content loaded by agent

        # Load BSL files from paths
        for path in self.bsl_paths:
            p = Path(path)
            if p.exists() and p.suffix.lower() == '.bsl':
                try:
                    content = p.read_text(encoding='utf-8')
                    self.bsl_files[str(p)] = content
                except Exception:
                    pass

        return self


@dataclass
class ReviewOutput:
    """Output from REVIEWER agent."""
    report: ReviewReport
    review_path: str
    success: bool
    errors: List[str] = field(default_factory=list)
    execution_time_ms: int = 0

    @property
    def verdict(self) -> ReviewVerdict:
        """Get review verdict."""
        return self.report.verdict

    @property
    def approved(self) -> bool:
        """Check if review approved."""
        return self.report.verdict == ReviewVerdict.APPROVED

    @property
    def blocked(self) -> bool:
        """Check if review blocked."""
        return self.report.verdict == ReviewVerdict.BLOCKED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "verdict": self.verdict.value,
            "approved": self.approved,
            "quality_score": self.report.quality_score,
            "critical_count": len(self.report.critical_issues),
            "warning_count": len(self.report.warnings),
            "recommendation_count": len(self.report.recommendations),
            "review_path": self.review_path,
            "execution_time_ms": self.execution_time_ms,
            "errors": self.errors,
        }


class ReviewerAgent:
    """
    REVIEWER Agent - Automated code review for BSL/1C.

    Orchestrates:
    - DiffAnalyzer for change analysis
    - StyleChecker for code style
    - ArchChecker for architecture
    - ReviewGenerator for report generation

    Usage:
        agent = ReviewerAgent()

        input = ReviewInput(
            project_id="PROJECT",
            task_id="TASK-123",
            diff_text=diff,
            bsl_files={"path.bsl": content}
        )

        output = agent.run(input)

        if output.approved:
            print("Code approved!")
        else:
            print(f"Issues found: {len(output.report.issues)}")
    """

    # Agent metadata
    NAME = "REVIEWER"
    VERSION = "1.0.0"
    ARTIFACT_INPUT = ["spec.md", "design.md", "result.md"]
    ARTIFACT_OUTPUT = "review.md"

    def __init__(
        self,
        config: Optional[ReviewerConfig] = None,
        artifact_store_path: Optional[str] = None,
    ):
        """
        Initialize REVIEWER agent.

        Args:
            config: Agent configuration
            artifact_store_path: Path to pipeline artifact store
        """
        self.config = config or ReviewerConfig()
        self.artifact_store_path = artifact_store_path

        # Initialize components
        self.diff_analyzer = DiffAnalyzer()
        self.style_checker = StyleChecker()
        self.arch_checker = ArchChecker()
        self.generator = ReviewGenerator()

        # Execution state
        self._current_input: Optional[ReviewInput] = None
        self._start_time: Optional[datetime] = None

    def run(self, input: ReviewInput) -> ReviewOutput:
        """
        Run code review.

        Args:
            input: Review input with code and artifacts

        Returns:
            ReviewOutput with report and verdict
        """
        self._start_time = datetime.now()
        self._current_input = input
        errors: List[str] = []

        try:
            # Phase 1: Load artifacts
            artifacts = self._load_artifacts(input)

            # Phase 2: Build review context
            context = self._build_context(input, artifacts)

            # Phase 3: Generate review
            report = self.generator.generate(context)

            # Phase 4: Apply config overrides
            report = self._apply_config(report)

            # Phase 5: Save review.md
            review_path = self._save_review(report, input)

            # Calculate execution time
            execution_time = int(
                (datetime.now() - self._start_time).total_seconds() * 1000
            )

            return ReviewOutput(
                report=report,
                review_path=review_path,
                success=True,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            errors.append(str(e))

            # Create minimal report on error
            report = ReviewReport(
                project_id=input.project_id,
                task_id=input.task_id,
                verdict=ReviewVerdict.BLOCKED,
                quality_score=0.0,
            )
            report.issues.append(ReviewIssue(
                id="ERR-001",
                title="Ошибка выполнения ревью",
                description=str(e),
                severity=IssueSeverity.CRITICAL,
                category=IssueCategory.LOGIC_ERROR,
            ))

            return ReviewOutput(
                report=report,
                review_path="",
                success=False,
                errors=errors,
                execution_time_ms=int(
                    (datetime.now() - self._start_time).total_seconds() * 1000
                ) if self._start_time else 0,
            )

    def _load_artifacts(self, input: ReviewInput) -> Dict[str, str]:
        """Load pipeline artifacts."""
        artifacts = {}

        # Load from artifact store if configured
        if self.artifact_store_path:
            store_path = Path(self.artifact_store_path)
            project_path = store_path / input.project_id / input.task_id

            for artifact in self.ARTIFACT_INPUT:
                artifact_file = project_path / artifact
                if artifact_file.exists():
                    try:
                        artifacts[artifact] = artifact_file.read_text(encoding='utf-8')
                    except Exception:
                        pass

        # Load from explicit paths
        if input.spec_path and Path(input.spec_path).exists():
            try:
                artifacts["spec.md"] = Path(input.spec_path).read_text(encoding='utf-8')
            except Exception:
                pass

        if input.design_path and Path(input.design_path).exists():
            try:
                artifacts["design.md"] = Path(input.design_path).read_text(encoding='utf-8')
            except Exception:
                pass

        if input.result_path and Path(input.result_path).exists():
            try:
                artifacts["result.md"] = Path(input.result_path).read_text(encoding='utf-8')
            except Exception:
                pass

        # Load BSL files from paths
        input.load_artifacts()

        return artifacts

    def _build_context(
        self,
        input: ReviewInput,
        artifacts: Dict[str, str]
    ) -> ReviewContext:
        """Build review context from input and artifacts."""
        return ReviewContext(
            project_id=input.project_id,
            task_id=input.task_id,
            spec_content=artifacts.get("spec.md"),
            design_content=artifacts.get("design.md"),
            result_content=artifacts.get("result.md"),
            diff_text=input.diff_text,
            bsl_files=input.bsl_files,
        )

    def _apply_config(self, report: ReviewReport) -> ReviewReport:
        """Apply configuration to report."""
        # Limit issues per category
        if self.config.max_issues_per_category > 0:
            limited_issues = []
            category_counts: Dict[IssueCategory, int] = {}

            for issue in report.issues:
                count = category_counts.get(issue.category, 0)
                if count < self.config.max_issues_per_category:
                    limited_issues.append(issue)
                    category_counts[issue.category] = count + 1

            report.issues = limited_issues

        # Filter recommendations if disabled
        if not self.config.include_recommendations:
            report.issues = [
                i for i in report.issues
                if i.severity != IssueSeverity.RECOMMENDATION
            ]

        # Remove code snippets if disabled
        if not self.config.include_code_snippets:
            for issue in report.issues:
                issue.code_snippet = None

        # Override verdict based on config thresholds
        critical_count = len(report.critical_issues)
        warning_count = len(report.warnings)

        if critical_count > self.config.max_critical_for_approval:
            report.verdict = ReviewVerdict.BLOCKED
        elif warning_count > self.config.max_warnings_for_approval:
            report.verdict = ReviewVerdict.CHANGES_REQUESTED
        elif report.quality_score < self.config.min_quality_score:
            report.verdict = ReviewVerdict.CHANGES_REQUESTED
        else:
            report.verdict = ReviewVerdict.APPROVED

        return report

    def _save_review(self, report: ReviewReport, input: ReviewInput) -> str:
        """Save review.md to artifact store."""
        # Determine output path
        if self.artifact_store_path:
            output_dir = Path(self.artifact_store_path) / input.project_id / input.task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / self.ARTIFACT_OUTPUT
        else:
            output_path = Path(f"review_{input.task_id}.md")

        # Generate and save markdown
        markdown = self.generator.generate_markdown(report)
        output_path.write_text(markdown, encoding='utf-8')

        return str(output_path)

    def validate_input(self, input: ReviewInput) -> List[str]:
        """
        Validate review input.

        Args:
            input: Review input to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not input.project_id:
            errors.append("project_id is required")

        if not input.task_id:
            errors.append("task_id is required")

        if not input.diff_text and not input.bsl_files and not input.bsl_paths:
            errors.append("No code to review: provide diff_text, bsl_files, or bsl_paths")

        return errors

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "name": self.NAME,
            "version": self.VERSION,
            "config": self.config.to_dict(),
            "artifact_store": self.artifact_store_path,
            "components": {
                "diff_analyzer": True,
                "style_checker": True,
                "arch_checker": True,
                "report_generator": True,
            }
        }


# Factory functions
def create_reviewer(
    config: Optional[ReviewerConfig] = None,
    artifact_store_path: Optional[str] = None,
) -> ReviewerAgent:
    """
    Create REVIEWER agent.

    Args:
        config: Agent configuration
        artifact_store_path: Path to artifact store

    Returns:
        Configured ReviewerAgent
    """
    return ReviewerAgent(
        config=config,
        artifact_store_path=artifact_store_path,
    )


def create_strict_reviewer(artifact_store_path: Optional[str] = None) -> ReviewerAgent:
    """Create strict REVIEWER (no warnings allowed)."""
    config = ReviewerConfig(
        max_critical_for_approval=0,
        max_warnings_for_approval=0,
        min_quality_score=8.0,
    )
    return ReviewerAgent(config=config, artifact_store_path=artifact_store_path)


def create_lenient_reviewer(artifact_store_path: Optional[str] = None) -> ReviewerAgent:
    """Create lenient REVIEWER (more tolerant)."""
    config = ReviewerConfig(
        max_critical_for_approval=0,
        max_warnings_for_approval=10,
        min_quality_score=5.0,
        include_recommendations=False,
    )
    return ReviewerAgent(config=config, artifact_store_path=artifact_store_path)


# Convenience functions
def run_review(
    project_id: str,
    task_id: str,
    diff_text: Optional[str] = None,
    bsl_files: Optional[Dict[str, str]] = None,
    design_path: Optional[str] = None,
    artifact_store_path: Optional[str] = None,
) -> ReviewOutput:
    """
    Run code review (convenience function).

    Args:
        project_id: Project identifier
        task_id: Task identifier
        diff_text: Git diff text
        bsl_files: Dict of file_path -> content
        design_path: Path to design.md
        artifact_store_path: Path to artifact store

    Returns:
        ReviewOutput
    """
    agent = create_reviewer(artifact_store_path=artifact_store_path)

    input = ReviewInput(
        project_id=project_id,
        task_id=task_id,
        diff_text=diff_text,
        bsl_files=bsl_files or {},
        design_path=design_path,
    )

    return agent.run(input)


def quick_review(
    bsl_code: str,
    file_name: str = "module.bsl"
) -> ReviewReport:
    """
    Quick review of BSL code snippet.

    Args:
        bsl_code: BSL source code
        file_name: Virtual file name

    Returns:
        ReviewReport
    """
    agent = create_reviewer()

    input = ReviewInput(
        project_id="QUICK",
        task_id="REVIEW",
        bsl_files={file_name: bsl_code},
    )

    output = agent.run(input)
    return output.report
