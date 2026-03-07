"""Tests for INITIALIZER models."""

import pytest
from datetime import datetime
from pathlib import Path

from models import (
    FileType,
    ProjectType,
    ObjectType,
    FileInfo,
    DirectoryInfo,
    ModuleInfo,
    DependencyInfo,
    PatternInfo,
    ProjectStructure,
    RelevantFile,
    ContextReport,
    InitializerConfig,
    InitializerInput,
    InitializerOutput,
)


class TestFileType:
    """Tests for FileType enum."""

    def test_from_extension_bsl(self):
        """Test BSL extension detection."""
        assert FileType.from_extension(".bsl") == FileType.BSL
        assert FileType.from_extension(".BSL") == FileType.BSL

    def test_from_extension_xml(self):
        """Test XML extension detection."""
        assert FileType.from_extension(".xml") == FileType.XML

    def test_from_extension_json(self):
        """Test JSON extension detection."""
        assert FileType.from_extension(".json") == FileType.JSON

    def test_from_extension_mdo(self):
        """Test MDO extension detection."""
        assert FileType.from_extension(".mdo") == FileType.MDO

    def test_from_extension_unknown(self):
        """Test unknown extension."""
        assert FileType.from_extension(".txt") == FileType.OTHER
        assert FileType.from_extension(".py") == FileType.OTHER


class TestProjectType:
    """Tests for ProjectType enum."""

    def test_ru_name(self):
        """Test Russian names."""
        assert ProjectType.CONFIGURATION.ru_name == "Конфигурация"
        assert ProjectType.EXTENSION.ru_name == "Расширение"
        assert ProjectType.EXTERNAL_DATAPROCESSOR.ru_name == "Внешняя обработка"


class TestObjectType:
    """Tests for ObjectType enum."""

    def test_from_directory(self):
        """Test object type detection from directory name."""
        assert ObjectType.from_directory("Catalogs") == ObjectType.CATALOG
        assert ObjectType.from_directory("Documents") == ObjectType.DOCUMENT
        assert ObjectType.from_directory("AccumulationRegisters") == ObjectType.ACCUMULATION_REGISTER
        assert ObjectType.from_directory("CommonModules") == ObjectType.COMMON_MODULE

    def test_from_directory_unknown(self):
        """Test unknown directory."""
        assert ObjectType.from_directory("Unknown") == ObjectType.OTHER

    def test_ru_name(self):
        """Test Russian names."""
        assert ObjectType.CATALOG.ru_name == "Справочник"
        assert ObjectType.DOCUMENT.ru_name == "Документ"
        assert ObjectType.COMMON_MODULE.ru_name == "Общий модуль"


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_is_bsl(self):
        """Test BSL file detection."""
        bsl_file = FileInfo(
            path=Path("test.bsl"),
            name="test.bsl",
            file_type=FileType.BSL,
        )
        assert bsl_file.is_bsl is True

        xml_file = FileInfo(
            path=Path("test.xml"),
            name="test.xml",
            file_type=FileType.XML,
        )
        assert xml_file.is_bsl is False

    def test_is_metadata(self):
        """Test metadata file detection."""
        xml_file = FileInfo(
            path=Path("test.xml"),
            name="test.xml",
            file_type=FileType.XML,
        )
        assert xml_file.is_metadata is True

        mdo_file = FileInfo(
            path=Path("test.mdo"),
            name="test.mdo",
            file_type=FileType.MDO,
        )
        assert mdo_file.is_metadata is True


class TestModuleInfo:
    """Tests for ModuleInfo dataclass."""

    def test_total_lines(self):
        """Test total lines calculation."""
        files = [
            FileInfo(
                path=Path("f1.bsl"),
                name="f1.bsl",
                file_type=FileType.BSL,
                line_count=100,
            ),
            FileInfo(
                path=Path("f2.bsl"),
                name="f2.bsl",
                file_type=FileType.BSL,
                line_count=200,
            ),
        ]

        module = ModuleInfo(
            name="TestModule",
            object_type=ObjectType.COMMON_MODULE,
            path=Path("CommonModules/TestModule"),
            files=files,
        )

        assert module.total_lines == 300


class TestProjectStructure:
    """Tests for ProjectStructure dataclass."""

    def test_total_files(self):
        """Test total files calculation."""
        files = [
            FileInfo(path=Path("f1.bsl"), name="f1.bsl", file_type=FileType.BSL),
            FileInfo(path=Path("f2.xml"), name="f2.xml", file_type=FileType.XML),
        ]

        module = ModuleInfo(
            name="TestModule",
            object_type=ObjectType.COMMON_MODULE,
            path=Path("CommonModules/TestModule"),
            files=files,
        )

        structure = ProjectStructure(
            root_path=Path("/project"),
            project_type=ProjectType.CONFIGURATION,
            name="TestProject",
            modules=[module],
            scanned_at=datetime.now(),
        )

        assert structure.total_files == 2
        assert structure.total_bsl_files == 1
        assert structure.total_modules == 1


class TestInitializerConfig:
    """Tests for InitializerConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = InitializerConfig()

        assert config.max_files == 10000
        assert config.max_depth == 10
        assert config.scan_timeout == 60
        assert config.cache_ttl == 3600
        assert config.max_relevant_files == 20


class TestRelevantFile:
    """Tests for RelevantFile dataclass."""

    def test_relevance_category(self):
        """Test relevance category property."""
        file_info = FileInfo(
            path=Path("test.bsl"),
            name="test.bsl",
            file_type=FileType.BSL,
        )

        high = RelevantFile(
            file_info=file_info,
            relevance_score=0.9,
            relevance_reason="test",
        )
        assert high.relevance_category == "high"

        medium = RelevantFile(
            file_info=file_info,
            relevance_score=0.6,
            relevance_reason="test",
        )
        assert medium.relevance_category == "medium"

        low = RelevantFile(
            file_info=file_info,
            relevance_score=0.3,
            relevance_reason="test",
        )
        assert low.relevance_category == "low"
