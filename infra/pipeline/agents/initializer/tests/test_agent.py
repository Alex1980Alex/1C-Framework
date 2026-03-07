"""Tests for InitializerAgent."""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from ..agent import (
    InitializerResult,
    InitializerAgent,
    create_initializer,
    run_initializer,
    initialize_project,
    get_project_context,
)
from models import (
    InitializerConfig,
    InitializerInput,
    InitializerOutput,
    ProjectStructure,
    ProjectType,
    ContextReport,
)


def create_test_project(tmpdir: Path) -> Path:
    """Create a test 1C project structure."""
    project_dir = tmpdir / "TestProject"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create Configuration.xml marker
    (project_dir / "Configuration.xml").touch()

    # Create CommonModules structure
    common_modules = project_dir / "CommonModules"
    common_modules.mkdir()

    test_module = common_modules / "ТестовыйМодуль"
    test_module.mkdir()
    ext_dir = test_module / "Ext"
    ext_dir.mkdir()

    module_path = ext_dir / "Module.bsl"
    module_path.write_text(
        "Функция ТестоваяФункция() Экспорт\n    Возврат 1;\nКонецФункции",
        encoding="utf-8-sig",
    )

    return project_dir


class TestInitializerResult:
    """Tests for InitializerResult dataclass."""

    def test_result_success(self):
        """Test successful result."""
        result = InitializerResult(
            success=True,
            cache_hit=False,
            scan_time_ms=100,
            total_time_ms=150,
        )

        assert result.success is True
        assert result.error_message is None

    def test_result_failure(self):
        """Test failure result."""
        result = InitializerResult(
            success=False,
            error_message="Test error",
        )

        assert result.success is False
        assert result.error_message == "Test error"

    def test_summary_error(self):
        """Test summary for error result."""
        result = InitializerResult(
            success=False,
            error_message="Project not found",
        )

        assert "Error:" in result.summary
        assert "Project not found" in result.summary

    def test_summary_success_requires_context(self):
        """Test summary for success without context."""
        result = InitializerResult(
            success=True,
            cache_hit=True,
            total_time_ms=50,
        )

        # Without context_report, accessing summary would raise
        # because it tries to access context_report.project_structure
        with pytest.raises(AttributeError):
            _ = result.summary


class TestInitializerAgent:
    """Tests for InitializerAgent class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        agent = InitializerAgent()

        assert agent.config is not None
        assert agent.scanner is not None
        assert agent.selector is not None
        assert agent.generator is not None
        assert agent.cache is not None

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = InitializerConfig(max_relevant_files=5)
        agent = InitializerAgent(config)

        assert agent.config.max_relevant_files == 5

    def test_run_nonexistent_path(self):
        """Test run on nonexistent path."""
        agent = InitializerAgent()

        result = agent.run(
            project_id="TEST",
            project_path="/nonexistent/path",
            task_description="Test task",
        )

        assert result.success is False
        assert "not found" in result.error_message.lower()

    def test_run_success(self):
        """Test successful run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            agent = InitializerAgent()

            result = agent.run(
                project_id="TEST-001",
                project_path=str(project_path),
                task_description="Тестовая задача",
            )

            assert result.success is True
            assert result.context_report is not None
            assert result.cache_hit is False
            assert result.scan_time_ms >= 0
            assert result.total_time_ms >= 0

    def test_run_with_output_dir(self):
        """Test run with output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            output_dir = Path(tmpdir) / "output"

            agent = InitializerAgent()

            result = agent.run(
                project_id="TEST-001",
                project_path=str(project_path),
                task_description="Test",
                output_dir=str(output_dir),
            )

            assert result.success is True
            assert (output_dir / "context.md").exists()

    def test_run_force_rescan(self):
        """Test force rescan ignores cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            agent = InitializerAgent()

            # First run
            result1 = agent.run(
                project_id="TEST",
                project_path=str(project_path),
                task_description="Test",
            )

            assert result1.success is True
            assert result1.cache_hit is False

            # Second run with force_rescan
            result2 = agent.run(
                project_id="TEST",
                project_path=str(project_path),
                task_description="Test",
                force_rescan=True,
            )

            assert result2.success is True
            assert result2.cache_hit is False  # Should rescan

    def test_run_from_input(self):
        """Test run from structured input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            agent = InitializerAgent()

            input_data = InitializerInput(
                project_id="TEST-001",
                project_path=str(project_path),
                task_description="Добавить документ",
            )

            output = agent.run_from_input(input_data)

            assert isinstance(output, InitializerOutput)
            assert output.success is True
            assert output.context_markdown != ""
            assert output.processing_time_ms >= 0

    def test_run_from_input_failure(self):
        """Test run from input with invalid path."""
        agent = InitializerAgent()

        input_data = InitializerInput(
            project_id="TEST",
            project_path="/nonexistent/path",
            task_description="Test",
        )

        output = agent.run_from_input(input_data)

        assert output.success is False
        assert output.error_message is not None
        assert output.context_markdown == ""
        assert output.relevant_files == []

    def test_invalidate_cache(self):
        """Test cache invalidation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            agent = InitializerAgent()

            # First run to populate cache
            agent.run(
                project_id="TEST",
                project_path=str(project_path),
                task_description="Test",
            )

            # Invalidate cache
            result = agent.invalidate_cache(str(project_path))

            assert result is True

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        agent = InitializerAgent()

        stats = agent.get_cache_stats()

        assert "total_entries" in stats
        assert "expired_entries" in stats
        assert "valid_entries" in stats


class TestContextReportGeneration:
    """Tests for context report generation within agent."""

    def test_report_contains_project_id(self):
        """Test that report contains project ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            agent = InitializerAgent()

            result = agent.run(
                project_id="UNIQUE-PROJECT-123",
                project_path=str(project_path),
                task_description="Test",
            )

            assert result.success is True
            assert "UNIQUE-PROJECT-123" in result.context_report.markdown_content

    def test_report_contains_task_description(self):
        """Test that report contains task description."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            agent = InitializerAgent()

            result = agent.run(
                project_id="TEST",
                project_path=str(project_path),
                task_description="Добавить регистр накопления",
            )

            assert result.success is True
            assert "Добавить регистр накопления" in result.context_report.markdown_content

    def test_report_contains_structure(self):
        """Test that report contains project structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            agent = InitializerAgent()

            result = agent.run(
                project_id="TEST",
                project_path=str(project_path),
                task_description="Test",
            )

            assert result.success is True
            assert "ТестовыйМодуль" in result.context_report.markdown_content


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_initializer_default(self):
        """Test create_initializer with defaults."""
        agent = create_initializer()

        assert isinstance(agent, InitializerAgent)
        assert agent.config is not None

    def test_create_initializer_with_config(self):
        """Test create_initializer with custom config."""
        config = InitializerConfig(max_files=500)
        agent = create_initializer(config)

        assert agent.config.max_files == 500

    def test_run_initializer(self):
        """Test run_initializer function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))

            result = run_initializer(
                project_id="TEST",
                project_path=str(project_path),
                task_description="Test task",
            )

            assert isinstance(result, InitializerResult)
            assert result.success is True

    def test_run_initializer_with_config(self):
        """Test run_initializer with custom config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            config = InitializerConfig(max_relevant_files=3)

            result = run_initializer(
                project_id="TEST",
                project_path=str(project_path),
                task_description="Test",
                config=config,
            )

            assert result.success is True

    def test_initialize_project(self):
        """Test initialize_project function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))

            report = initialize_project(
                project_path=str(project_path),
                task_description="Test",
            )

            assert report is not None
            assert isinstance(report, ContextReport)

    def test_initialize_project_uses_path_as_id(self):
        """Test that initialize_project uses path name as project ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))

            report = initialize_project(str(project_path))

            assert report is not None
            assert "TestProject" in report.markdown_content

    def test_initialize_project_failure(self):
        """Test initialize_project with invalid path."""
        report = initialize_project("/nonexistent/path")

        assert report is None

    def test_get_project_context(self):
        """Test get_project_context function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))

            context = get_project_context(str(project_path))

            assert isinstance(context, str)
            assert "# Контекст" in context

    def test_get_project_context_failure(self):
        """Test get_project_context with invalid path."""
        context = get_project_context("/nonexistent/path")

        assert "# Error" in context
        assert "Could not initialize" in context


class TestErrorHandling:
    """Tests for error handling."""

    def test_permission_error(self):
        """Test handling of permission errors."""
        agent = InitializerAgent()

        with patch.object(agent.scanner, "scan") as mock_scan:
            mock_scan.side_effect = PermissionError("Access denied")

            result = agent.run(
                project_id="TEST",
                project_path="/some/path",
                task_description="Test",
            )

            assert result.success is False
            assert "Permission denied" in result.error_message

    def test_unexpected_error(self):
        """Test handling of unexpected errors."""
        agent = InitializerAgent()

        with patch.object(agent.scanner, "scan") as mock_scan:
            mock_scan.side_effect = RuntimeError("Unexpected error")

            result = agent.run(
                project_id="TEST",
                project_path="/some/path",
                task_description="Test",
            )

            assert result.success is False
            assert "Unexpected error" in result.error_message


class TestCacheIntegration:
    """Tests for cache integration."""

    def test_cache_populated_after_run(self):
        """Test that cache is populated after run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = create_test_project(Path(tmpdir))
            agent = InitializerAgent()

            # Clear cache first
            agent.cache.invalidate_all()

            # Run
            result = agent.run(
                project_id="TEST",
                project_path=str(project_path),
                task_description="Test",
            )

            assert result.success is True

            # Check cache stats
            stats = agent.get_cache_stats()
            assert stats["total_entries"] >= 1

    def test_multiple_projects_cached(self):
        """Test caching of multiple projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two projects
            project1 = create_test_project(Path(tmpdir) / "proj1")
            project2 = create_test_project(Path(tmpdir) / "proj2")

            agent = InitializerAgent()
            agent.cache.invalidate_all()

            # Run for both
            agent.run(
                project_id="PROJ1",
                project_path=str(project1),
                task_description="Test",
            )

            agent.run(
                project_id="PROJ2",
                project_path=str(project2),
                task_description="Test",
            )

            # Check stats
            stats = agent.get_cache_stats()
            assert stats["total_entries"] >= 2
