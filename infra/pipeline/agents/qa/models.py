"""
QA Agent Models.

Data classes for test cases, results, and reports.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class TestType(Enum):
    """Types of tests."""
    UNIT = "unit"
    INTEGRATION = "integration"
    FUNCTIONAL = "functional"
    REGRESSION = "regression"
    SMOKE = "smoke"
    BSL_SYNTAX = "bsl_syntax"
    BSL_RUNTIME = "bsl_runtime"


class TestStatus(Enum):
    """Test execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class Severity(Enum):
    """Defect severity levels."""
    CRITICAL = "critical"  # Blocking, system crash
    MAJOR = "major"        # Major functionality broken
    MINOR = "minor"        # Minor issues, workarounds exist
    TRIVIAL = "trivial"    # Cosmetic issues


@dataclass
class TestCase:
    """
    Represents a single test case.

    Attributes:
        id: Unique identifier (e.g., "TC-001")
        name: Test case name
        description: What this test verifies
        test_type: Type of test (unit, integration, etc.)
        requirement_id: Related requirement (e.g., "REQ-001")
        preconditions: Setup requirements
        steps: Test steps to execute
        expected_result: Expected outcome
        priority: Test priority (1-5, 1 is highest)
    """
    id: str
    name: str
    description: str
    test_type: TestType
    requirement_id: Optional[str] = None
    preconditions: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    expected_result: str = ""
    priority: int = 3
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "test_type": self.test_type.value,
            "requirement_id": self.requirement_id,
            "preconditions": self.preconditions,
            "steps": self.steps,
            "expected_result": self.expected_result,
            "priority": self.priority,
            "tags": self.tags,
        }

    def to_markdown(self) -> str:
        """Format as markdown."""
        lines = [
            f"### {self.id}: {self.name}",
            "",
            f"**Тип:** {self.test_type.value}",
            f"**Приоритет:** {self.priority}",
        ]

        if self.requirement_id:
            lines.append(f"**Требование:** {self.requirement_id}")

        lines.append("")
        lines.append(f"**Описание:** {self.description}")

        if self.preconditions:
            lines.append("")
            lines.append("**Предусловия:**")
            for pre in self.preconditions:
                lines.append(f"- {pre}")

        if self.steps:
            lines.append("")
            lines.append("**Шаги:**")
            for i, step in enumerate(self.steps, 1):
                lines.append(f"{i}. {step}")

        lines.append("")
        lines.append(f"**Ожидаемый результат:** {self.expected_result}")

        return "\n".join(lines)


@dataclass
class TestResult:
    """
    Result of executing a single test case.

    Attributes:
        test_case: The executed test case
        status: Execution status
        actual_result: What actually happened
        error_message: Error details if failed
        execution_time_ms: Time taken in milliseconds
        screenshots: Paths to screenshots if any
        logs: Execution logs
    """
    test_case: TestCase
    status: TestStatus
    actual_result: str = ""
    error_message: Optional[str] = None
    execution_time_ms: int = 0
    screenshots: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def passed(self) -> bool:
        """Check if test passed."""
        return self.status == TestStatus.PASSED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "test_id": self.test_case.id,
            "test_name": self.test_case.name,
            "status": self.status.value,
            "actual_result": self.actual_result,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_markdown(self) -> str:
        """Format as markdown row."""
        status_icon = {
            TestStatus.PASSED: "✅",
            TestStatus.FAILED: "❌",
            TestStatus.SKIPPED: "⏭️",
            TestStatus.ERROR: "💥",
            TestStatus.PENDING: "⏳",
            TestStatus.RUNNING: "🔄",
        }.get(self.status, "❓")

        return f"| {self.test_case.id} | {self.test_case.name} | {status_icon} {self.status.value} | {self.execution_time_ms}ms |"


@dataclass
class Defect:
    """
    Represents a found defect.

    Attributes:
        id: Unique identifier (e.g., "BUG-001")
        title: Short description
        description: Detailed description
        severity: Defect severity
        test_case_id: Related test case
        steps_to_reproduce: How to reproduce
        actual_behavior: What happens
        expected_behavior: What should happen
        status: Current status
    """
    id: str
    title: str
    description: str
    severity: Severity
    test_case_id: Optional[str] = None
    steps_to_reproduce: List[str] = field(default_factory=list)
    actual_behavior: str = ""
    expected_behavior: str = ""
    status: str = "open"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "test_case_id": self.test_case_id,
            "steps_to_reproduce": self.steps_to_reproduce,
            "actual_behavior": self.actual_behavior,
            "expected_behavior": self.expected_behavior,
            "status": self.status,
        }

    def to_markdown(self) -> str:
        """Format as markdown."""
        severity_icon = {
            Severity.CRITICAL: "🔴",
            Severity.MAJOR: "🟠",
            Severity.MINOR: "🟡",
            Severity.TRIVIAL: "🟢",
        }.get(self.severity, "⚪")

        lines = [
            f"### {severity_icon} {self.id}: {self.title}",
            "",
            f"**Severity:** {self.severity.value}",
            f"**Status:** {self.status}",
        ]

        if self.test_case_id:
            lines.append(f"**Test Case:** {self.test_case_id}")

        lines.append("")
        lines.append(f"**Description:** {self.description}")

        if self.steps_to_reproduce:
            lines.append("")
            lines.append("**Steps to Reproduce:**")
            for i, step in enumerate(self.steps_to_reproduce, 1):
                lines.append(f"{i}. {step}")

        if self.actual_behavior:
            lines.append("")
            lines.append(f"**Actual Behavior:** {self.actual_behavior}")

        if self.expected_behavior:
            lines.append(f"**Expected Behavior:** {self.expected_behavior}")

        return "\n".join(lines)


@dataclass
class TestSuite:
    """
    Collection of test cases.

    Attributes:
        name: Suite name
        description: Suite description
        test_cases: List of test cases
        tags: Suite tags
    """
    name: str
    description: str = ""
    test_cases: List[TestCase] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def add_test(self, test_case: TestCase) -> None:
        """Add a test case to the suite."""
        self.test_cases.append(test_case)

    @property
    def total_tests(self) -> int:
        """Get total number of tests."""
        return len(self.test_cases)

    def get_by_requirement(self, requirement_id: str) -> List[TestCase]:
        """Get all tests for a specific requirement."""
        return [tc for tc in self.test_cases if tc.requirement_id == requirement_id]

    def get_by_type(self, test_type: TestType) -> List[TestCase]:
        """Get all tests of a specific type."""
        return [tc for tc in self.test_cases if tc.test_type == test_type]

    def get_test(self, test_id: str) -> Optional[TestCase]:
        """Get test case by ID."""
        for tc in self.test_cases:
            if tc.id == test_id:
                return tc
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "total_tests": self.total_tests,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "tags": self.tags,
        }


@dataclass
class QAReport:
    """
    Complete QA report (qa_report.md content).

    Attributes:
        project_id: Project identifier
        task_id: Task identifier
        test_suite: Executed test suite
        results: Test execution results
        defects: Found defects
        coverage: Code/requirement coverage info
        recommendations: QA recommendations
        verdict: Overall QA verdict
    """
    project_id: str
    task_id: str
    test_suite: TestSuite
    results: List[TestResult] = field(default_factory=list)
    defects: List[Defect] = field(default_factory=list)
    coverage: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    verdict: str = "PENDING"
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_tests(self) -> int:
        """Total number of tests."""
        return len(self.results)

    @property
    def passed_tests(self) -> int:
        """Number of passed tests."""
        return len([r for r in self.results if r.status == TestStatus.PASSED])

    @property
    def failed_tests(self) -> int:
        """Number of failed tests."""
        return len([r for r in self.results if r.status == TestStatus.FAILED])

    @property
    def skipped_tests(self) -> int:
        """Number of skipped tests."""
        return len([r for r in self.results if r.status == TestStatus.SKIPPED])

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def critical_defects(self) -> List[Defect]:
        """Get critical defects."""
        return [d for d in self.defects if d.severity == Severity.CRITICAL]

    @property
    def major_defects(self) -> List[Defect]:
        """Get major defects."""
        return [d for d in self.defects if d.severity == Severity.MAJOR]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "verdict": self.verdict,
            "summary": {
                "total_tests": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
                "skipped": self.skipped_tests,
                "pass_rate": round(self.pass_rate, 2),
            },
            "defects": {
                "total": len(self.defects),
                "critical": len(self.critical_defects),
                "major": len(self.major_defects),
            },
            "coverage": self.coverage,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        """Generate qa_report.md content."""
        lines = [
            "# QA Report",
            "",
            f"**Проект:** {self.project_id}",
            f"**Задача:** {self.task_id}",
            f"**Дата:** {self.timestamp.strftime('%Y-%m-%d %H:%M')}",
            f"**Вердикт:** {self.verdict}",
            "",
            "---",
            "",
            "## 📊 Сводка",
            "",
            "| Метрика | Значение |",
            "|---------|----------|",
            f"| Всего тестов | {self.total_tests} |",
            f"| Пройдено | ✅ {self.passed_tests} |",
            f"| Провалено | ❌ {self.failed_tests} |",
            f"| Пропущено | ⏭️ {self.skipped_tests} |",
            f"| Процент прохождения | {self.pass_rate:.1f}% |",
            "",
        ]

        # Results table
        if self.results:
            lines.extend([
                "## 📋 Результаты тестирования",
                "",
                "| ID | Название | Статус | Время |",
                "|----|----------|--------|-------|",
            ])
            for result in self.results:
                lines.append(result.to_markdown())
            lines.append("")

        # Defects section
        if self.defects:
            lines.extend([
                "## 🐛 Найденные дефекты",
                "",
                f"**Всего:** {len(self.defects)} "
                f"(🔴 Критических: {len(self.critical_defects)}, "
                f"🟠 Важных: {len(self.major_defects)})",
                "",
            ])
            for defect in self.defects:
                lines.append(defect.to_markdown())
                lines.append("")

        # Coverage section
        if self.coverage:
            lines.extend([
                "## 📈 Покрытие",
                "",
            ])
            if "requirements" in self.coverage:
                req_cov = self.coverage["requirements"]
                lines.append(f"**Покрытие требований:** {req_cov.get('covered', 0)}/{req_cov.get('total', 0)} "
                           f"({req_cov.get('percentage', 0):.1f}%)")
            if "code" in self.coverage:
                code_cov = self.coverage["code"]
                lines.append(f"**Покрытие кода:** {code_cov.get('percentage', 0):.1f}%")
            lines.append("")

        # Recommendations
        if self.recommendations:
            lines.extend([
                "## 💡 Рекомендации",
                "",
            ])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        # Footer
        lines.extend([
            "---",
            "",
            f"*Отчёт сгенерирован QA Agent*",
        ])

        return "\n".join(lines)
