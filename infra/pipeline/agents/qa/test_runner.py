"""
Test Runner for QA Agent.

Executes tests and collects results.
Note: This is a simulation layer - actual BSL test execution
requires 1C:Enterprise runtime.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import time
import random

from agents.qa.models import (
    TestCase,
    TestResult,
    TestStatus,
    TestSuite,
    TestType,
    Defect,
    Severity,
)


@dataclass
class RunConfig:
    """Configuration for test run."""
    parallel: bool = False
    timeout_ms: int = 30000
    stop_on_failure: bool = False
    skip_tags: List[str] = field(default_factory=list)
    only_tags: List[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "parallel": self.parallel,
            "timeout_ms": self.timeout_ms,
            "stop_on_failure": self.stop_on_failure,
            "skip_tags": self.skip_tags,
            "only_tags": self.only_tags,
            "dry_run": self.dry_run,
        }


@dataclass
class RunSummary:
    """Summary of test run."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        executed = self.total - self.skipped
        if executed == 0:
            return 0.0
        return (self.passed / executed) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "pass_rate": round(self.pass_rate, 2),
        }


class TestRunner:
    """
    Executes tests and collects results.

    In production, this would integrate with:
    - 1C:Enterprise test runner
    - OneScript test framework (xUnit)
    - Custom BSL test harness

    For now, it simulates test execution for demonstration.

    Usage:
        runner = TestRunner()
        results = runner.run(test_suite)
        print(f"Pass rate: {runner.summary.pass_rate}%")
    """

    def __init__(self, config: Optional[RunConfig] = None) -> None:
        """
        Initialize runner.

        Args:
            config: Run configuration
        """
        self.config = config or RunConfig()
        self.results: List[TestResult] = []
        self.defects: List[Defect] = []
        self.summary = RunSummary()
        self._defect_counter = 0

        # Callbacks
        self._on_test_start: Optional[Callable[[TestCase], None]] = None
        self._on_test_end: Optional[Callable[[TestResult], None]] = None

    def on_test_start(self, callback: Callable[[TestCase], None]) -> None:
        """Register callback for test start."""
        self._on_test_start = callback

    def on_test_end(self, callback: Callable[[TestResult], None]) -> None:
        """Register callback for test end."""
        self._on_test_end = callback

    def run(self, suite: TestSuite) -> List[TestResult]:
        """
        Run all tests in suite.

        Args:
            suite: TestSuite to run

        Returns:
            List of TestResults
        """
        self.results = []
        self.defects = []
        self.summary = RunSummary()
        self.summary.start_time = datetime.now()

        # Filter tests
        tests_to_run = self._filter_tests(suite.test_cases)
        self.summary.total = len(tests_to_run)

        start_time = time.time()

        for test_case in tests_to_run:
            if self._on_test_start:
                self._on_test_start(test_case)

            result = self._run_single(test_case)
            self.results.append(result)

            # Update summary
            self._update_summary(result)

            # Create defect if failed
            if result.status == TestStatus.FAILED:
                defect = self._create_defect(result)
                self.defects.append(defect)

            if self._on_test_end:
                self._on_test_end(result)

            # Stop on failure if configured
            if self.config.stop_on_failure and result.status == TestStatus.FAILED:
                # Mark remaining as skipped
                remaining = tests_to_run[tests_to_run.index(test_case) + 1:]
                for remaining_test in remaining:
                    self.results.append(TestResult(
                        test_case=remaining_test,
                        status=TestStatus.SKIPPED,
                        actual_result="Skipped due to previous failure",
                    ))
                    self.summary.skipped += 1
                break

        self.summary.duration_ms = int((time.time() - start_time) * 1000)
        self.summary.end_time = datetime.now()

        return self.results

    def run_single(self, test_case: TestCase) -> TestResult:
        """
        Run a single test case.

        Args:
            test_case: Test to run

        Returns:
            TestResult
        """
        return self._run_single(test_case)

    def _filter_tests(self, tests: List[TestCase]) -> List[TestCase]:
        """Filter tests based on config."""
        filtered = []

        for test in tests:
            # Check skip tags
            if self.config.skip_tags:
                if any(tag in test.tags for tag in self.config.skip_tags):
                    continue

            # Check only tags
            if self.config.only_tags:
                if not any(tag in test.tags for tag in self.config.only_tags):
                    continue

            filtered.append(test)

        return filtered

    def _run_single(self, test_case: TestCase) -> TestResult:
        """
        Run a single test.

        In production, this would:
        1. Set up test environment
        2. Execute BSL test code
        3. Collect results

        For now, simulates execution.
        """
        if self.config.dry_run:
            return TestResult(
                test_case=test_case,
                status=TestStatus.SKIPPED,
                actual_result="Dry run - not executed",
            )

        start_time = time.time()

        # Simulate test execution
        result = self._simulate_execution(test_case)

        execution_time = int((time.time() - start_time) * 1000)
        result.execution_time_ms = execution_time

        return result

    def _simulate_execution(self, test_case: TestCase) -> TestResult:
        """
        Simulate test execution.

        Uses heuristics based on test type and priority.
        In production, would execute actual BSL code.
        """
        # Simulate some execution time
        time.sleep(random.uniform(0.01, 0.05))

        # Determine outcome based on test characteristics
        # Higher priority tests are more likely to pass (simulating well-tested code)
        pass_probability = 0.9 - (test_case.priority - 1) * 0.1

        # Negative tests have lower pass probability (simulating missing error handling)
        if "negative" in test_case.tags:
            pass_probability -= 0.2

        # Boundary tests have medium pass probability
        if "boundary" in test_case.tags:
            pass_probability -= 0.1

        if random.random() < pass_probability:
            return TestResult(
                test_case=test_case,
                status=TestStatus.PASSED,
                actual_result=test_case.expected_result,
            )
        else:
            # Generate failure
            error_messages = [
                "Assertion failed: expected value does not match actual",
                "Ошибка: Неопределено не является допустимым значением",
                "Runtime error: Division by zero",
                "Timeout: Test exceeded maximum execution time",
                "Ошибка при обращении к базе данных",
            ]

            return TestResult(
                test_case=test_case,
                status=TestStatus.FAILED,
                actual_result="Тест провален",
                error_message=random.choice(error_messages),
            )

    def _update_summary(self, result: TestResult) -> None:
        """Update summary with result."""
        if result.status == TestStatus.PASSED:
            self.summary.passed += 1
        elif result.status == TestStatus.FAILED:
            self.summary.failed += 1
        elif result.status == TestStatus.SKIPPED:
            self.summary.skipped += 1
        elif result.status == TestStatus.ERROR:
            self.summary.errors += 1

    def _next_defect_id(self) -> str:
        """Generate next defect ID."""
        self._defect_counter += 1
        return f"BUG-{self._defect_counter:03d}"

    def _create_defect(self, result: TestResult) -> Defect:
        """Create defect from failed test."""
        # Determine severity based on test characteristics
        severity = Severity.MINOR

        if result.test_case.priority == 1:
            severity = Severity.CRITICAL
        elif result.test_case.priority == 2:
            severity = Severity.MAJOR
        elif "negative" in result.test_case.tags:
            severity = Severity.MINOR

        return Defect(
            id=self._next_defect_id(),
            title=f"Ошибка в тесте: {result.test_case.name}",
            description=result.error_message or "Тест провален",
            severity=severity,
            test_case_id=result.test_case.id,
            steps_to_reproduce=result.test_case.steps,
            actual_behavior=result.actual_result,
            expected_behavior=result.test_case.expected_result,
        )

    def get_failed_tests(self) -> List[TestResult]:
        """Get list of failed tests."""
        return [r for r in self.results if r.status == TestStatus.FAILED]

    def get_defects(self) -> List[Defect]:
        """Get list of created defects."""
        return self.defects

    def get_coverage(self, requirements: List[str]) -> Dict[str, Any]:
        """
        Calculate requirement coverage.

        Args:
            requirements: List of requirement IDs from spec

        Returns:
            Coverage information
        """
        covered = set()
        req_tests: Dict[str, List[str]] = {}

        for result in self.results:
            if result.test_case.requirement_id:
                req_id = result.test_case.requirement_id
                if req_id not in req_tests:
                    req_tests[req_id] = []
                req_tests[req_id].append(result.test_case.id)

                if result.status == TestStatus.PASSED:
                    covered.add(req_id)

        total = len(requirements) if requirements else len(req_tests)
        covered_count = len(covered)

        return {
            "total": total,
            "covered": covered_count,
            "percentage": (covered_count / total * 100) if total > 0 else 0,
            "by_requirement": req_tests,
        }


# Factory functions
def create_runner(
    timeout_ms: int = 30000,
    stop_on_failure: bool = False,
) -> TestRunner:
    """
    Create runner with common settings.

    Args:
        timeout_ms: Timeout per test
        stop_on_failure: Whether to stop on first failure

    Returns:
        Configured TestRunner
    """
    config = RunConfig(
        timeout_ms=timeout_ms,
        stop_on_failure=stop_on_failure,
    )
    return TestRunner(config)


def create_dry_runner() -> TestRunner:
    """
    Create runner for dry runs (no actual execution).

    Returns:
        TestRunner configured for dry run
    """
    config = RunConfig(dry_run=True)
    return TestRunner(config)
