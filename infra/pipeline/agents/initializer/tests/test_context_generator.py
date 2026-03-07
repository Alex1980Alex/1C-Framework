"""Tests for ContextGenerator."""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from ..context_generator import (
    ContextGenerator,
    generate_context,
    generate_context_markdown,
)
from models import (
    ObjectType,
    ProjectType,
    FileType,
    FileInfo,
    ModuleInfo,
    ProjectStructure,
    RelevantFile,
    PatternInfo,
    DependencyInfo,
    InitializerConfig,
)


def create_test_file(name: str = "Module.bsl") -> FileInfo:
    """Helper to create test file info."""
    return FileInfo(
        path=Path(f"test/{name}"),
        name=name,
        file_type=FileType.BSL,
        line_count=100,
    )


def create_test_module(
    name: str,
    object_type: ObjectType,
    exports_count: int = 0,
    line_count: int = 100,
) -> ModuleInfo:
    """Helper to create test module."""
    return ModuleInfo(
        name=name,
        object_type=object_type,
        path=Path(f"{object_type.value}/{name}"),
        files=[
            FileInfo(
                path=Path(f"{object_type.value}/{name}/Ext/Module.bsl"),
                name="Module.bsl",
                file_type=FileType.BSL,
                line_count=line_count,
            )
        ],
        exports_count=exports_count,
    )


def create_test_structure(
    modules: list[ModuleInfo] = None,
    patterns: list[PatternInfo] = None,
    dependencies: list[DependencyInfo] = None,
) -> ProjectStructure:
    """Helper to create test structure."""
    return ProjectStructure(
        root_path=Path("/test/project"),
        project_type=ProjectType.CONFIGURATION,
        name="TestProject",
        modules=modules or [],
        patterns=patterns or [],
        dependencies=dependencies or [],
        scanned_at=datetime.now(),
    )


def create_relevant_file(
    score: float,
    name: str = "Module.bsl",
    module_name: str = None,
) -> RelevantFile:
    """Helper to create relevant file."""
    return RelevantFile(
        file_info=create_test_file(name),
        relevance_score=score,
        relevance_reason="Test reason",
        module_name=module_name,
    )


class TestContextGenerator:
    """Tests for ContextGenerator class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        generator = ContextGenerator()
        assert generator.config is not None

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = InitializerConfig(max_relevant_files=50)
        generator = ContextGenerator(config)
        assert generator.config.max_relevant_files == 50

    def test_generate_returns_context_report(self):
        """Test that generate returns ContextReport."""
        generator = ContextGenerator()
        structure = create_test_structure()

        result = generator.generate(
            project_id="TEST-001",
            structure=structure,
            task_description="Test task",
            relevant_files=[],
        )

        assert result.project_id == "TEST-001"
        assert result.task_description == "Test task"
        assert result.markdown_content != ""

    def test_generate_includes_project_id(self):
        """Test that markdown includes project ID."""
        generator = ContextGenerator()
        structure = create_test_structure()

        result = generator.generate(
            project_id="PROJ-123",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "PROJ-123" in result.markdown_content

    def test_generate_includes_task_description(self):
        """Test that markdown includes task description."""
        generator = ContextGenerator()
        structure = create_test_structure()

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Добавить документ",
            relevant_files=[],
        )

        assert "Добавить документ" in result.markdown_content


class TestOverviewSection:
    """Tests for overview section generation."""

    def test_overview_includes_project_type(self):
        """Test that overview includes project type."""
        generator = ContextGenerator()
        structure = create_test_structure()

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "Конфигурация" in result.markdown_content

    def test_overview_includes_file_counts(self):
        """Test that overview includes file counts."""
        generator = ContextGenerator()
        modules = [
            create_test_module("Модуль1", ObjectType.COMMON_MODULE),
            create_test_module("Модуль2", ObjectType.COMMON_MODULE),
        ]
        structure = create_test_structure(modules)

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "Всего файлов" in result.markdown_content
        assert "BSL модулей" in result.markdown_content
        assert "Объектов" in result.markdown_content


class TestStructureSection:
    """Tests for structure section generation."""

    def test_structure_groups_by_type(self):
        """Test that modules are grouped by type."""
        generator = ContextGenerator()
        modules = [
            create_test_module("Товары", ObjectType.CATALOG),
            create_test_module("Услуги", ObjectType.CATALOG),
            create_test_module("ПриходТоваров", ObjectType.DOCUMENT),
        ]
        structure = create_test_structure(modules)

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "Справочники" in result.markdown_content
        assert "Документы" in result.markdown_content

    def test_structure_includes_module_info(self):
        """Test that structure includes module information."""
        generator = ContextGenerator()
        modules = [
            create_test_module("ТестМодуль", ObjectType.COMMON_MODULE, exports_count=10, line_count=500),
        ]
        structure = create_test_structure(modules)

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "ТестМодуль" in result.markdown_content
        assert "10" in result.markdown_content  # exports_count
        assert "500" in result.markdown_content  # line_count

    def test_structure_uses_table_format(self):
        """Test that structure uses table format."""
        generator = ContextGenerator()
        modules = [
            create_test_module("Товары", ObjectType.CATALOG),
        ]
        structure = create_test_structure(modules)

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        # Table header markers
        assert "| Модуль |" in result.markdown_content
        assert "|--------|" in result.markdown_content


class TestRelevantFilesSection:
    """Tests for relevant files section generation."""

    def test_relevant_files_empty(self):
        """Test handling of empty relevant files."""
        generator = ContextGenerator()
        structure = create_test_structure()

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "не определены" in result.markdown_content

    def test_relevant_files_high_score(self):
        """Test high relevance files are listed."""
        generator = ContextGenerator()
        structure = create_test_structure()
        relevant = [create_relevant_file(0.9, "HighScore.bsl")]

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=relevant,
        )

        assert "Высокая релевантность" in result.markdown_content
        assert "HighScore.bsl" in result.markdown_content

    def test_relevant_files_medium_score(self):
        """Test medium relevance files are listed."""
        generator = ContextGenerator()
        structure = create_test_structure()
        relevant = [create_relevant_file(0.6, "MediumScore.bsl")]

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=relevant,
        )

        assert "Средняя релевантность" in result.markdown_content
        assert "MediumScore.bsl" in result.markdown_content

    def test_relevant_files_low_score(self):
        """Test low relevance files are listed."""
        generator = ContextGenerator()
        structure = create_test_structure()
        relevant = [create_relevant_file(0.3, "LowScore.bsl")]

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=relevant,
        )

        assert "Низкая релевантность" in result.markdown_content
        assert "LowScore.bsl" in result.markdown_content

    def test_relevant_files_includes_module_name(self):
        """Test that module name is included when available."""
        generator = ContextGenerator()
        structure = create_test_structure()
        relevant = [create_relevant_file(0.9, "Module.bsl", module_name="ТестМодуль")]

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=relevant,
        )

        assert "ТестМодуль" in result.markdown_content


class TestDependenciesSection:
    """Tests for dependencies section generation."""

    def test_dependencies_empty(self):
        """Test handling of empty dependencies."""
        generator = ContextGenerator()
        structure = create_test_structure()

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "Зависимости" in result.markdown_content

    def test_dependencies_includes_mermaid(self):
        """Test that Mermaid graph is included."""
        generator = ContextGenerator()
        structure = create_test_structure()
        relevant = [create_relevant_file(0.9)]

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=relevant,
        )

        assert "```mermaid" in result.markdown_content
        assert "graph TD" in result.markdown_content

    def test_dependencies_includes_dependency_list(self):
        """Test that dependency list is included."""
        generator = ContextGenerator()
        deps = [
            DependencyInfo(
                source="Модуль1",
                target="Модуль2",
                dependency_type="calls",
            )
        ]
        structure = create_test_structure(dependencies=deps)

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "Модуль1" in result.markdown_content
        assert "Модуль2" in result.markdown_content


class TestPatternsSection:
    """Tests for patterns section generation."""

    def test_patterns_empty(self):
        """Test handling of empty patterns."""
        generator = ContextGenerator()
        structure = create_test_structure()

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "Паттерны" in result.markdown_content
        assert "не обнаружены" in result.markdown_content

    def test_patterns_included(self):
        """Test that patterns are included."""
        generator = ContextGenerator()
        patterns = [
            PatternInfo(
                name="Naming Prefix",
                description="Префикс для объектов",
                examples=["гкс_Модуль1", "гкс_Модуль2"],
                occurrences=2,
            )
        ]
        structure = create_test_structure(patterns=patterns)

        result = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        assert "Naming Prefix" in result.markdown_content
        assert "Префикс для объектов" in result.markdown_content
        assert "гкс_Модуль1" in result.markdown_content


class TestSaveToFile:
    """Tests for file saving."""

    def test_save_to_file_creates_file(self):
        """Test that save creates file."""
        generator = ContextGenerator()
        structure = create_test_structure()
        report = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = generator.save_to_file(report, Path(tmpdir))

            assert file_path.exists()
            assert file_path.name == "context.md"

    def test_save_to_file_creates_directory(self):
        """Test that save creates parent directory."""
        generator = ContextGenerator()
        structure = create_test_structure()
        report = generator.generate(
            project_id="TEST",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "path"
            file_path = generator.save_to_file(report, nested_path)

            assert file_path.exists()
            assert file_path.parent.exists()

    def test_save_to_file_writes_content(self):
        """Test that file contains correct content."""
        generator = ContextGenerator()
        structure = create_test_structure()
        report = generator.generate(
            project_id="UNIQUE-ID-123",
            structure=structure,
            task_description="Test",
            relevant_files=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = generator.save_to_file(report, Path(tmpdir))

            content = file_path.read_text(encoding="utf-8")
            assert "UNIQUE-ID-123" in content


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_generate_context(self):
        """Test generate_context function."""
        structure = create_test_structure()

        result = generate_context(
            project_id="TEST",
            structure=structure,
            task_description="Test task",
            relevant_files=[],
        )

        assert result.project_id == "TEST"
        assert result.markdown_content != ""

    def test_generate_context_markdown(self):
        """Test generate_context_markdown function."""
        structure = create_test_structure()

        result = generate_context_markdown(
            project_id="TEST",
            structure=structure,
            task_description="Test task",
            relevant_files=[],
        )

        assert isinstance(result, str)
        assert "TEST" in result
        assert "# Контекст" in result
