"""
Report Generator for QA Agent.

Generates qa_report.md artifact with test results.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from agents.qa.models import (
    TestCase,
    TestResult,
    TestStatus,
    TestSuite,
    Defect,
    Severity,
    QAReport,
)
from agents.qa.test_runner import RunSummary


class ReportGenerator:
    """
    Generates QA report in markdown format.

    Creates qa_report.md artifact containing:
    - Test summary
    - Detailed results
    - Defects found
    - Coverage information
    - Recommendations

    Usage:
        generator = ReportGenerator()
        report = generator.generate(
            project_id="PROJECT",
            task_id="TASK-001",
            results=test_results,
            defects=defects,
        )
        markdown = report.to_markdown()
    """

    def __init__(self) -> None:
        """Initialize generator."""
        self._recommendations: List[str] = []

    def generate(
        self,
        project_id: str,
        task_id: str,
        test_suite: TestSuite,
        results: List[TestResult],
        defects: List[Defect],
        coverage: Optional[Dict[str, Any]] = None,
    ) -> QAReport:
        """
        Generate QA report.

        Args:
            project_id: Project identifier
            task_id: Task identifier
            test_suite: The test suite that was run
            results: Test execution results
            defects: Found defects
            coverage: Optional coverage information

        Returns:
            QAReport instance
        """
        # Generate recommendations based on results
        recommendations = self._generate_recommendations(results, defects, coverage)

        # Determine verdict
        verdict = self._determine_verdict(results, defects)

        report = QAReport(
            project_id=project_id,
            task_id=task_id,
            test_suite=test_suite,
            results=results,
            defects=defects,
            coverage=coverage or {},
            recommendations=recommendations,
            verdict=verdict,
        )

        return report

    def generate_from_runner(
        self,
        project_id: str,
        task_id: str,
        test_suite: TestSuite,
        runner,  # TestRunner - avoid circular import
        requirements: Optional[List[str]] = None,
    ) -> QAReport:
        """
        Generate report directly from TestRunner.

        Args:
            project_id: Project identifier
            task_id: Task identifier
            test_suite: The test suite
            runner: TestRunner instance after run
            requirements: Optional list of requirement IDs

        Returns:
            QAReport
        """
        coverage = runner.get_coverage(requirements or [])

        return self.generate(
            project_id=project_id,
            task_id=task_id,
            test_suite=test_suite,
            results=runner.results,
            defects=runner.defects,
            coverage=coverage,
        )

    def _generate_recommendations(
        self,
        results: List[TestResult],
        defects: List[Defect],
        coverage: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        # Calculate metrics
        total = len(results)
        passed = len([r for r in results if r.status == TestStatus.PASSED])
        failed = len([r for r in results if r.status == TestStatus.FAILED])
        pass_rate = (passed / total * 100) if total > 0 else 0

        # Critical defects recommendation
        critical_defects = [d for d in defects if d.severity == Severity.CRITICAL]
        if critical_defects:
            recommendations.append(
                f"🔴 КРИТИЧНО: Обнаружено {len(critical_defects)} критических дефектов. "
                "Требуется немедленное исправление перед релизом."
            )

        # Pass rate recommendations
        if pass_rate < 70:
            recommendations.append(
                f"⚠️ Низкий процент прохождения тестов ({pass_rate:.1f}%). "
                "Рекомендуется провести дополнительную отладку."
            )
        elif pass_rate < 90:
            recommendations.append(
                f"📊 Процент прохождения тестов {pass_rate:.1f}%. "
                "Рекомендуется исправить оставшиеся дефекты."
            )

        # Coverage recommendations
        if coverage:
            cov_percentage = coverage.get("percentage", 0)
            if cov_percentage < 80:
                recommendations.append(
                    f"📈 Покрытие требований {cov_percentage:.1f}%. "
                    "Рекомендуется добавить тесты для непокрытых требований."
                )

        # Negative tests recommendation
        negative_failed = [
            r for r in results
            if r.status == TestStatus.FAILED and "negative" in r.test_case.tags
        ]
        if negative_failed:
            recommendations.append(
                f"⚡ Провалено {len(negative_failed)} негативных тестов. "
                "Рекомендуется улучшить обработку ошибок."
            )

        # If all good
        if not recommendations:
            recommendations.append(
                "✅ Все тесты пройдены успешно. Код готов к релизу."
            )

        return recommendations

    def _determine_verdict(
        self,
        results: List[TestResult],
        defects: List[Defect],
    ) -> str:
        """Determine overall verdict."""
        # Check for critical defects
        critical = [d for d in defects if d.severity == Severity.CRITICAL]
        if critical:
            return "❌ FAILED"

        # Calculate pass rate
        total = len(results)
        passed = len([r for r in results if r.status == TestStatus.PASSED])
        pass_rate = (passed / total * 100) if total > 0 else 0

        if pass_rate >= 90:
            return "✅ PASSED"
        elif pass_rate >= 70:
            return "⚠️ PASSED WITH WARNINGS"
        else:
            return "❌ FAILED"

    def write_report(
        self,
        report: QAReport,
        output_path: str,
    ) -> str:
        """
        Write report to file.

        Args:
            report: QAReport to write
            output_path: Path to write qa_report.md

        Returns:
            Path to written file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        content = report.to_markdown()
        path.write_text(content, encoding='utf-8')

        return str(path)


# Extended report with additional sections
class ExtendedReportGenerator(ReportGenerator):
    """
    Extended report generator with additional analysis.

    Adds:
    - Performance metrics
    - Trend analysis (if historical data available)
    - BSL-specific checks
    """

    def generate_extended(
        self,
        project_id: str,
        task_id: str,
        test_suite: TestSuite,
        results: List[TestResult],
        defects: List[Defect],
        coverage: Optional[Dict[str, Any]] = None,
        bsl_analysis: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate extended markdown report.

        Args:
            project_id: Project identifier
            task_id: Task identifier
            test_suite: Test suite
            results: Test results
            defects: Defects
            coverage: Coverage info
            bsl_analysis: Optional BSL-specific analysis

        Returns:
            Extended markdown content
        """
        # Generate base report
        report = self.generate(
            project_id=project_id,
            task_id=task_id,
            test_suite=test_suite,
            results=results,
            defects=defects,
            coverage=coverage,
        )

        # Start with base markdown
        lines = [report.to_markdown()]

        # Add BSL analysis section if provided
        if bsl_analysis:
            lines.extend(self._generate_bsl_section(bsl_analysis))

        # Add performance section
        lines.extend(self._generate_performance_section(results))

        return "\n".join(lines)

    def _generate_bsl_section(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate BSL-specific analysis section."""
        lines = [
            "",
            "## 🔍 Анализ BSL кода",
            "",
        ]

        if "functions_count" in analysis:
            lines.append(f"**Функций проанализировано:** {analysis['functions_count']}")

        if "procedures_count" in analysis:
            lines.append(f"**Процедур проанализировано:** {analysis['procedures_count']}")

        if "issues" in analysis:
            lines.append("")
            lines.append("### Найденные проблемы")
            lines.append("")
            for issue in analysis["issues"]:
                severity = issue.get("severity", "info")
                icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")
                lines.append(f"- {icon} {issue.get('message', 'Unknown issue')}")

        lines.append("")
        return lines

    def _generate_performance_section(self, results: List[TestResult]) -> List[str]:
        """Generate performance metrics section."""
        lines = [
            "",
            "## ⏱️ Метрики производительности",
            "",
        ]

        # Calculate metrics
        execution_times = [r.execution_time_ms for r in results if r.execution_time_ms > 0]

        if execution_times:
            avg_time = sum(execution_times) / len(execution_times)
            max_time = max(execution_times)
            min_time = min(execution_times)
            total_time = sum(execution_times)

            lines.append("| Метрика | Значение |")
            lines.append("|---------|----------|")
            lines.append(f"| Общее время | {total_time}ms |")
            lines.append(f"| Среднее время теста | {avg_time:.1f}ms |")
            lines.append(f"| Самый быстрый | {min_time}ms |")
            lines.append(f"| Самый медленный | {max_time}ms |")

            # Flag slow tests
            slow_tests = [r for r in results if r.execution_time_ms > avg_time * 2]
            if slow_tests:
                lines.append("")
                lines.append("### ⚠️ Медленные тесты")
                lines.append("")
                for test in slow_tests[:5]:  # Top 5 slow tests
                    lines.append(f"- {test.test_case.id}: {test.execution_time_ms}ms")

        lines.append("")
        return lines


# Convenience functions
def generate_report(
    project_id: str,
    task_id: str,
    test_suite: TestSuite,
    results: List[TestResult],
    defects: List[Defect],
    coverage: Optional[Dict[str, Any]] = None,
) -> QAReport:
    """
    Convenience function to generate report.

    Args:
        project_id: Project identifier
        task_id: Task identifier
        test_suite: Test suite
        results: Results
        defects: Defects
        coverage: Coverage

    Returns:
        QAReport
    """
    generator = ReportGenerator()
    return generator.generate(
        project_id=project_id,
        task_id=task_id,
        test_suite=test_suite,
        results=results,
        defects=defects,
        coverage=coverage,
    )


def write_qa_report(
    report: QAReport,
    output_dir: str,
) -> str:
    """
    Write qa_report.md to directory.

    Args:
        report: QAReport to write
        output_dir: Directory to write to

    Returns:
        Path to qa_report.md
    """
    generator = ReportGenerator()
    output_path = Path(output_dir) / "qa_report.md"
    return generator.write_report(report, str(output_path))
