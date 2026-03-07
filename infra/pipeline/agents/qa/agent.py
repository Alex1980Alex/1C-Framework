"""
QA Agent - Main orchestrator for testing and quality assurance.

Coordinates:
- ResultAnalyzer - parsing implementation results
- TestGenerator - creating test cases
- TestRunner - executing tests
- ReportGenerator - producing qa_report.md
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from agents.qa.models import QAReport, TestSuite
from agents.qa.result_analyzer import ResultAnalyzer, AnalysisResult
from agents.qa.test_generator import TestGenerator
from agents.qa.test_runner import TestRunner, RunConfig
from agents.qa.report_generator import ReportGenerator


@dataclass
class QAAgentConfig:
    """Configuration for QA Agent."""
    stop_on_failure: bool = False
    timeout_ms: int = 30000
    generate_bsl_tests: bool = True
    min_pass_rate: float = 70.0
    output_dir: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "stop_on_failure": self.stop_on_failure,
            "timeout_ms": self.timeout_ms,
            "generate_bsl_tests": self.generate_bsl_tests,
            "min_pass_rate": self.min_pass_rate,
            "output_dir": self.output_dir,
        }


@dataclass
class QAContext:
    """Context for QA Agent execution."""
    project_id: str
    task_id: str
    result_content: str
    spec_content: str
    design_content: Optional[str] = None
    artifacts_dir: Optional[str] = None


class QAAgent:
    """
    QA Agent - Testing and Quality Assurance.

    Orchestrates the complete QA workflow:
    1. Analyze result.md from IMPLEMENTER
    2. Generate test cases from spec.md
    3. Execute tests
    4. Generate qa_report.md

    Usage:
        agent = QAAgent()
        report = agent.run(
            project_id="PROJECT",
            task_id="TASK-001",
            result_content=result_md,
            spec_content=spec_md,
        )
        print(f"Verdict: {report.verdict}")

    Alternative usage with context:
        context = QAContext(
            project_id="PROJECT",
            task_id="TASK-001",
            result_content=result_md,
            spec_content=spec_md,
        )
        report = agent.run_with_context(context)
    """

    def __init__(self, config: Optional[QAAgentConfig] = None) -> None:
        """
        Initialize QA Agent.

        Args:
            config: Optional configuration
        """
        self.config = config or QAAgentConfig()

        # Initialize components
        self.analyzer = ResultAnalyzer()
        self.generator = TestGenerator()
        self.runner = TestRunner(RunConfig(
            timeout_ms=self.config.timeout_ms,
            stop_on_failure=self.config.stop_on_failure,
        ))
        self.reporter = ReportGenerator()

        # State
        self._analysis: Optional[AnalysisResult] = None
        self._test_suite: Optional[TestSuite] = None
        self._report: Optional[QAReport] = None

    def run(
        self,
        project_id: str,
        task_id: str,
        result_content: str,
        spec_content: str,
        design_content: Optional[str] = None,
    ) -> QAReport:
        """
        Run QA workflow.

        Args:
            project_id: Project identifier
            task_id: Task identifier
            result_content: Content of result.md
            spec_content: Content of spec.md
            design_content: Optional content of design.md

        Returns:
            QAReport with results
        """
        context = QAContext(
            project_id=project_id,
            task_id=task_id,
            result_content=result_content,
            spec_content=spec_content,
            design_content=design_content,
        )
        return self.run_with_context(context)

    def run_with_context(self, context: QAContext) -> QAReport:
        """
        Run QA workflow with context.

        Args:
            context: QAContext with all inputs

        Returns:
            QAReport
        """
        # Step 1: Analyze result.md
        self._analysis = self.analyzer.analyze(context.result_content)

        # Step 2: Generate tests from spec
        self.generator.load_spec(context.spec_content)
        self.generator.load_analysis(self._analysis)

        suite_name = f"QA Suite - {context.task_id}"
        self._test_suite = self.generator.generate(suite_name)

        # Step 3: Run tests
        self.runner.run(self._test_suite)

        # Step 4: Generate report
        requirements = self._analysis.requirements_covered
        coverage = self.runner.get_coverage(requirements)

        self._report = self.reporter.generate(
            project_id=context.project_id,
            task_id=context.task_id,
            test_suite=self._test_suite,
            results=self.runner.results,
            defects=self.runner.defects,
            coverage=coverage,
        )

        # Write report if output dir specified
        if self.config.output_dir or context.artifacts_dir:
            output_dir = self.config.output_dir or context.artifacts_dir
            self._write_report(output_dir)

        return self._report

    def run_from_files(
        self,
        project_id: str,
        task_id: str,
        result_path: str,
        spec_path: str,
        design_path: Optional[str] = None,
    ) -> QAReport:
        """
        Run QA workflow from file paths.

        Args:
            project_id: Project identifier
            task_id: Task identifier
            result_path: Path to result.md
            spec_path: Path to spec.md
            design_path: Optional path to design.md

        Returns:
            QAReport
        """
        result_content = Path(result_path).read_text(encoding='utf-8')
        spec_content = Path(spec_path).read_text(encoding='utf-8')

        design_content = None
        if design_path:
            design_content = Path(design_path).read_text(encoding='utf-8')

        return self.run(
            project_id=project_id,
            task_id=task_id,
            result_content=result_content,
            spec_content=spec_content,
            design_content=design_content,
        )

    def _write_report(self, output_dir: str) -> str:
        """Write report to output directory."""
        if not self._report:
            raise ValueError("No report generated yet")

        output_path = Path(output_dir) / "qa_report.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        content = self._report.to_markdown()
        output_path.write_text(content, encoding='utf-8')

        return str(output_path)

    # Properties for accessing internal state
    @property
    def analysis(self) -> Optional[AnalysisResult]:
        """Get last analysis result."""
        return self._analysis

    @property
    def test_suite(self) -> Optional[TestSuite]:
        """Get generated test suite."""
        return self._test_suite

    @property
    def report(self) -> Optional[QAReport]:
        """Get last generated report."""
        return self._report

    @property
    def passed(self) -> bool:
        """Check if last run passed."""
        if not self._report:
            return False
        return "PASSED" in self._report.verdict

    @property
    def pass_rate(self) -> float:
        """Get pass rate from last run."""
        if not self._report:
            return 0.0
        return self._report.pass_rate

    # Convenience methods
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of last run."""
        if not self._report:
            return {"error": "No report generated"}

        return {
            "project_id": self._report.project_id,
            "task_id": self._report.task_id,
            "verdict": self._report.verdict,
            "total_tests": self._report.total_tests,
            "passed": self._report.passed_tests,
            "failed": self._report.failed_tests,
            "pass_rate": round(self._report.pass_rate, 2),
            "defects": len(self._report.defects),
            "critical_defects": len(self._report.critical_defects),
        }

    def get_defects_markdown(self) -> str:
        """Get defects as markdown."""
        if not self._report or not self._report.defects:
            return "No defects found."

        lines = []
        for defect in self._report.defects:
            lines.append(defect.to_markdown())
            lines.append("")

        return "\n".join(lines)


# Factory functions
def create_qa_agent(
    stop_on_failure: bool = False,
    min_pass_rate: float = 70.0,
) -> QAAgent:
    """
    Create QA Agent with common settings.

    Args:
        stop_on_failure: Stop on first failure
        min_pass_rate: Minimum acceptable pass rate

    Returns:
        Configured QAAgent
    """
    config = QAAgentConfig(
        stop_on_failure=stop_on_failure,
        min_pass_rate=min_pass_rate,
    )
    return QAAgent(config)


def run_qa(
    project_id: str,
    task_id: str,
    result_content: str,
    spec_content: str,
) -> QAReport:
    """
    Convenience function to run QA.

    Args:
        project_id: Project identifier
        task_id: Task identifier
        result_content: Content of result.md
        spec_content: Content of spec.md

    Returns:
        QAReport
    """
    agent = QAAgent()
    return agent.run(
        project_id=project_id,
        task_id=task_id,
        result_content=result_content,
        spec_content=spec_content,
    )
