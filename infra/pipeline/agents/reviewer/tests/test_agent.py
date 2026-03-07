"""
Tests for REVIEWER Agent (main orchestrator).
"""

import pytest
from pathlib import Path
from datetime import datetime

from agents.reviewer.agent import (
    ReviewerConfig,
    ReviewInput,
    ReviewOutput,
    ReviewerAgent,
    create_reviewer,
    create_strict_reviewer,
    create_lenient_reviewer,
    run_review,
    quick_review,
)
from agents.reviewer.models import (
    ReviewReport,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
    ReviewVerdict,
)


# Sample content for testing
SAMPLE_BSL_GOOD = """
// Модуль обработки данных
//
// Обеспечивает безопасную обработку данных с транзакциями

Процедура ОбработатьДанные() Экспорт
    Перем Результат;

    НачатьТранзакцию();
    Попытка
        Результат = ВыполнитьОперацию();
        ЗафиксироватьТранзакцию();
    Исключение
        ОтменитьТранзакцию();
        ЗаписьЖурналаРегистрации(
            НСтр("ru = 'Ошибка обработки'"),
            УровеньЖурналаРегистрации.Ошибка
        );
        ВызватьИсключение;
    КонецПопытки;

    Возврат Результат;
КонецПроцедуры
"""

SAMPLE_BSL_BAD = """
Процедура Тест()
    Перем а;
    Попытка
        Запрос.Текст = "ВЫБРАТЬ * ГДЕ Код = '" + Параметр + "'";
    Исключение
    КонецПопытки;
КонецПроцедуры
"""

SAMPLE_DIFF = """diff --git a/src/Module.bsl b/src/Module.bsl
index 1234567..abcdefg 100644
--- a/src/Module.bsl
+++ b/src/Module.bsl
@@ -1,5 +1,7 @@
 Процедура Тест()
+    Перем Счетчик;
+    Счетчик = 0;
     Сообщить("Тест");
 КонецПроцедуры
"""

SAMPLE_DESIGN = """
# Архитектура

## Компоненты

### МодульОбработки
- Тип: ОбщийМодуль
- Обязательный: да
"""


class TestReviewerConfig:
    """Tests for ReviewerConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ReviewerConfig()

        assert config.max_critical_for_approval == 0
        assert config.max_warnings_for_approval == 5
        assert config.check_style is True
        assert config.check_architecture is True
        assert config.check_security is True
        assert config.check_performance is True
        assert config.min_quality_score == 6.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ReviewerConfig(
            max_critical_for_approval=1,
            max_warnings_for_approval=10,
            check_style=False,
            min_quality_score=5.0
        )

        assert config.max_critical_for_approval == 1
        assert config.max_warnings_for_approval == 10
        assert config.check_style is False
        assert config.min_quality_score == 5.0

    def test_to_dict(self):
        """Test serialization."""
        config = ReviewerConfig()
        d = config.to_dict()

        assert "max_critical_for_approval" in d
        assert "max_warnings_for_approval" in d
        assert "check_style" in d
        assert "min_quality_score" in d


class TestReviewInput:
    """Tests for ReviewInput dataclass."""

    def test_minimal_input(self):
        """Test minimal input creation."""
        inp = ReviewInput(
            project_id="PROJECT",
            task_id="TASK-123"
        )

        assert inp.project_id == "PROJECT"
        assert inp.task_id == "TASK-123"
        assert inp.diff_text is None
        assert inp.bsl_files == {}

    def test_full_input(self):
        """Test full input creation."""
        inp = ReviewInput(
            project_id="PROJECT",
            task_id="TASK-123",
            spec_path="/path/to/spec.md",
            design_path="/path/to/design.md",
            result_path="/path/to/result.md",
            diff_text=SAMPLE_DIFF,
            bsl_files={"module.bsl": SAMPLE_BSL_GOOD},
            bsl_paths=["/path/to/files"]
        )

        assert inp.spec_path == "/path/to/spec.md"
        assert inp.diff_text == SAMPLE_DIFF
        assert len(inp.bsl_files) == 1

    def test_load_artifacts(self, tmp_path):
        """Test loading artifacts from paths."""
        # Create a test BSL file
        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text(SAMPLE_BSL_GOOD, encoding='utf-8')

        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_paths=[str(bsl_file)]
        )

        inp.load_artifacts()

        assert str(bsl_file) in inp.bsl_files
        assert SAMPLE_BSL_GOOD in inp.bsl_files[str(bsl_file)]


class TestReviewOutput:
    """Tests for ReviewOutput dataclass."""

    def test_creation(self):
        """Test output creation."""
        report = ReviewReport(project_id="P", task_id="T")
        output = ReviewOutput(
            report=report,
            review_path="/path/to/review.md",
            success=True
        )

        assert output.success is True
        assert output.review_path == "/path/to/review.md"

    def test_verdict_property(self):
        """Test verdict property."""
        report = ReviewReport(project_id="P", task_id="T")
        report.verdict = ReviewVerdict.APPROVED

        output = ReviewOutput(report=report, review_path="", success=True)

        assert output.verdict == ReviewVerdict.APPROVED

    def test_approved_property(self):
        """Test approved property."""
        report = ReviewReport(project_id="P", task_id="T")
        report.verdict = ReviewVerdict.APPROVED

        output = ReviewOutput(report=report, review_path="", success=True)

        assert output.approved is True
        assert output.blocked is False

    def test_blocked_property(self):
        """Test blocked property."""
        report = ReviewReport(project_id="P", task_id="T")
        report.verdict = ReviewVerdict.BLOCKED

        output = ReviewOutput(report=report, review_path="", success=True)

        assert output.blocked is True
        assert output.approved is False

    def test_to_dict(self):
        """Test serialization."""
        report = ReviewReport(project_id="P", task_id="T")
        report.verdict = ReviewVerdict.APPROVED
        report.quality_score = 8.5

        output = ReviewOutput(
            report=report,
            review_path="/path/review.md",
            success=True,
            execution_time_ms=150
        )

        d = output.to_dict()
        assert d["success"] is True
        assert d["verdict"] == "approved"
        assert d["approved"] is True
        assert d["quality_score"] == 8.5
        assert d["execution_time_ms"] == 150


class TestReviewerAgent:
    """Tests for ReviewerAgent class."""

    def test_initialization_default(self):
        """Test default initialization."""
        agent = ReviewerAgent()

        assert agent.config is not None
        assert agent.diff_analyzer is not None
        assert agent.style_checker is not None
        assert agent.arch_checker is not None
        assert agent.generator is not None

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = ReviewerConfig(max_warnings_for_approval=10)
        agent = ReviewerAgent(config=config)

        assert agent.config.max_warnings_for_approval == 10

    def test_initialization_with_artifact_store(self, tmp_path):
        """Test initialization with artifact store path."""
        agent = ReviewerAgent(artifact_store_path=str(tmp_path))

        assert agent.artifact_store_path == str(tmp_path)

    def test_metadata(self):
        """Test agent metadata."""
        assert ReviewerAgent.NAME == "REVIEWER"
        assert ReviewerAgent.VERSION == "1.0.0"
        assert ReviewerAgent.ARTIFACT_OUTPUT == "review.md"
        assert "spec.md" in ReviewerAgent.ARTIFACT_INPUT

    def test_run_minimal(self):
        """Test running with minimal input."""
        agent = ReviewerAgent()
        inp = ReviewInput(project_id="P", task_id="T")

        output = agent.run(inp)

        assert output.success is True
        assert output.report.project_id == "P"
        assert output.report.task_id == "T"

    def test_run_with_bsl_files(self):
        """Test running with BSL files."""
        agent = ReviewerAgent()
        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"module.bsl": SAMPLE_BSL_GOOD}
        )

        output = agent.run(inp)

        assert output.success is True
        assert len(output.report.files_reviewed) >= 1

    def test_run_with_diff(self):
        """Test running with diff text."""
        agent = ReviewerAgent()
        inp = ReviewInput(
            project_id="P",
            task_id="T",
            diff_text=SAMPLE_DIFF
        )

        output = agent.run(inp)

        assert output.success is True
        assert len(output.report.files_reviewed) >= 1

    def test_run_with_design(self):
        """Test running with design content."""
        agent = ReviewerAgent()
        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"МодульОбработки.bsl": SAMPLE_BSL_GOOD}
        )
        # Manually set design via artifact loading simulation

        output = agent.run(inp)

        assert output.success is True

    def test_run_saves_review(self, tmp_path):
        """Test that run saves review.md."""
        agent = ReviewerAgent(artifact_store_path=str(tmp_path))
        inp = ReviewInput(
            project_id="PROJECT",
            task_id="TASK-123",
            bsl_files={"module.bsl": SAMPLE_BSL_GOOD}
        )

        output = agent.run(inp)

        assert output.success is True
        assert output.review_path != ""
        assert Path(output.review_path).exists()

    def test_run_execution_time(self):
        """Test execution time is recorded."""
        agent = ReviewerAgent()
        inp = ReviewInput(project_id="P", task_id="T")

        output = agent.run(inp)

        assert output.execution_time_ms >= 0

    def test_run_with_bad_code(self):
        """Test running with problematic code."""
        agent = ReviewerAgent()
        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"bad.bsl": SAMPLE_BSL_BAD}
        )

        output = agent.run(inp)

        assert output.success is True
        # Should have issues detected
        assert len(output.report.issues) > 0

    def test_validate_input_valid(self):
        """Test input validation - valid."""
        agent = ReviewerAgent()
        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": "code"}
        )

        errors = agent.validate_input(inp)

        assert len(errors) == 0

    def test_validate_input_missing_project(self):
        """Test input validation - missing project_id."""
        agent = ReviewerAgent()
        inp = ReviewInput(
            project_id="",
            task_id="T",
            bsl_files={"test.bsl": "code"}
        )

        errors = agent.validate_input(inp)

        assert len(errors) > 0
        assert any("project_id" in e for e in errors)

    def test_validate_input_no_code(self):
        """Test input validation - no code to review."""
        agent = ReviewerAgent()
        inp = ReviewInput(
            project_id="P",
            task_id="T"
        )

        errors = agent.validate_input(inp)

        assert len(errors) > 0
        assert any("code" in e.lower() for e in errors)

    def test_get_status(self):
        """Test get_status method."""
        agent = ReviewerAgent()
        status = agent.get_status()

        assert status["name"] == "REVIEWER"
        assert status["version"] == "1.0.0"
        assert "config" in status
        assert "components" in status


class TestConfigApplication:
    """Tests for configuration application."""

    def test_max_issues_per_category(self):
        """Test limiting issues per category."""
        config = ReviewerConfig(max_issues_per_category=2)
        agent = ReviewerAgent(config=config)

        # Create input with code that generates many issues
        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_BAD * 5}
        )

        output = agent.run(inp)

        # Count issues per category
        from collections import Counter
        categories = Counter(i.category for i in output.report.issues)
        # Each category should have at most max_issues_per_category
        for count in categories.values():
            assert count <= 2

    def test_exclude_recommendations(self):
        """Test excluding recommendations."""
        config = ReviewerConfig(include_recommendations=False)
        agent = ReviewerAgent(config=config)

        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_GOOD}
        )

        output = agent.run(inp)

        # Should not have recommendations
        recs = [i for i in output.report.issues
                if i.severity == IssueSeverity.RECOMMENDATION]
        assert len(recs) == 0

    def test_exclude_code_snippets(self):
        """Test excluding code snippets."""
        config = ReviewerConfig(include_code_snippets=False)
        agent = ReviewerAgent(config=config)

        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_BAD}
        )

        output = agent.run(inp)

        # No issue should have code snippet
        for issue in output.report.issues:
            assert issue.code_snippet is None

    def test_verdict_override_by_warnings(self):
        """Test verdict override based on warning count."""
        config = ReviewerConfig(max_warnings_for_approval=1)
        agent = ReviewerAgent(config=config)

        # Code with multiple warnings
        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_BAD}
        )

        output = agent.run(inp)

        # If more than 1 warning, should request changes
        if len(output.report.warnings) > 1:
            assert output.report.verdict in [
                ReviewVerdict.CHANGES_REQUESTED,
                ReviewVerdict.BLOCKED
            ]

    def test_quality_score_threshold(self):
        """Test quality score threshold."""
        config = ReviewerConfig(min_quality_score=9.0)
        agent = ReviewerAgent(config=config)

        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_BAD}
        )

        output = agent.run(inp)

        # Bad code won't meet high quality threshold
        if output.report.quality_score < 9.0:
            assert output.report.verdict != ReviewVerdict.APPROVED


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_reviewer(self):
        """Test create_reviewer function."""
        agent = create_reviewer()

        assert isinstance(agent, ReviewerAgent)
        assert agent.config is not None

    def test_create_reviewer_with_config(self):
        """Test create_reviewer with config."""
        config = ReviewerConfig(max_warnings_for_approval=10)
        agent = create_reviewer(config=config)

        assert agent.config.max_warnings_for_approval == 10

    def test_create_strict_reviewer(self):
        """Test create_strict_reviewer function."""
        agent = create_strict_reviewer()

        assert agent.config.max_warnings_for_approval == 0
        assert agent.config.min_quality_score == 8.0

    def test_create_lenient_reviewer(self):
        """Test create_lenient_reviewer function."""
        agent = create_lenient_reviewer()

        assert agent.config.max_warnings_for_approval == 10
        assert agent.config.min_quality_score == 5.0
        assert agent.config.include_recommendations is False


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_run_review(self):
        """Test run_review function."""
        output = run_review(
            project_id="PROJECT",
            task_id="TASK-123",
            bsl_files={"module.bsl": SAMPLE_BSL_GOOD}
        )

        assert isinstance(output, ReviewOutput)
        assert output.success is True
        assert output.report.project_id == "PROJECT"

    def test_run_review_with_diff(self):
        """Test run_review with diff."""
        output = run_review(
            project_id="P",
            task_id="T",
            diff_text=SAMPLE_DIFF
        )

        assert output.success is True

    def test_quick_review(self):
        """Test quick_review function."""
        report = quick_review(SAMPLE_BSL_GOOD)

        assert isinstance(report, ReviewReport)
        assert report.project_id == "QUICK"
        assert report.task_id == "REVIEW"

    def test_quick_review_with_filename(self):
        """Test quick_review with custom filename."""
        report = quick_review(SAMPLE_BSL_GOOD, file_name="custom.bsl")

        assert isinstance(report, ReviewReport)
        # File should be in reviewed list
        paths = [f.file_path for f in report.files_reviewed]
        assert "custom.bsl" in paths


class TestErrorHandling:
    """Tests for error handling."""

    def test_run_handles_exception(self):
        """Test that run handles exceptions gracefully."""
        agent = ReviewerAgent()

        # Create an input that might cause issues
        inp = ReviewInput(
            project_id="P",
            task_id="T",
            spec_path="/nonexistent/path/spec.md"
        )

        # Should not raise, should return output with success=True or False
        output = agent.run(inp)

        # Either succeeds or fails gracefully
        assert output is not None
        assert output.report is not None

    def test_artifact_loading_missing_files(self, tmp_path):
        """Test artifact loading with missing files."""
        agent = ReviewerAgent(artifact_store_path=str(tmp_path))

        inp = ReviewInput(
            project_id="P",
            task_id="T",
            spec_path="/nonexistent/spec.md",
            design_path="/nonexistent/design.md",
            bsl_files={"test.bsl": SAMPLE_BSL_GOOD}
        )

        output = agent.run(inp)

        # Should still succeed
        assert output.success is True


class TestIntegration:
    """Integration tests."""

    def test_full_review_workflow(self, tmp_path):
        """Test complete review workflow."""
        # Setup artifact store
        agent = ReviewerAgent(artifact_store_path=str(tmp_path))

        # Create input
        inp = ReviewInput(
            project_id="PROJECT-X",
            task_id="TASK-456",
            diff_text=SAMPLE_DIFF,
            bsl_files={
                "good.bsl": SAMPLE_BSL_GOOD,
                "bad.bsl": SAMPLE_BSL_BAD,
            }
        )

        # Run review
        output = agent.run(inp)

        # Verify output
        assert output.success is True
        assert output.report.project_id == "PROJECT-X"
        assert output.report.task_id == "TASK-456"
        assert len(output.report.files_reviewed) >= 2
        assert output.report.verdict is not None
        assert output.report.quality_score is not None

        # Verify file was saved
        assert output.review_path != ""
        assert Path(output.review_path).exists()

        # Verify content
        content = Path(output.review_path).read_text(encoding='utf-8')
        assert "PROJECT-X" in content or "TASK-456" in content

    def test_strict_vs_lenient(self):
        """Test difference between strict and lenient reviewers."""
        strict = create_strict_reviewer()
        lenient = create_lenient_reviewer()

        inp = ReviewInput(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_BAD}
        )

        strict_output = strict.run(inp)
        lenient_output = lenient.run(inp)

        # Both should succeed
        assert strict_output.success is True
        assert lenient_output.success is True

        # Lenient should be more likely to approve
        # (depends on actual issues, but principle holds)
        if len(strict_output.report.warnings) > 0:
            # Strict should be harder to pass
            assert strict_output.report.verdict != ReviewVerdict.APPROVED or \
                   lenient_output.report.verdict in [ReviewVerdict.APPROVED, ReviewVerdict.CHANGES_REQUESTED]

