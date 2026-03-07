"""Tests for CodebaseScanner."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from ..codebase_scanner import (
    CodebaseScanner,
    scan_directory,
    detect_project_type,
    get_file_stats,
)
from models import (
    ProjectType,
    ObjectType,
    FileType,
    InitializerConfig,
)


class TestCodebaseScanner:
    """Tests for CodebaseScanner class."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        scanner = CodebaseScanner()
        assert scanner.config is not None
        assert scanner.config.max_files == 10000

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = InitializerConfig(max_files=100, max_depth=5)
        scanner = CodebaseScanner(config)
        assert scanner.config.max_files == 100
        assert scanner.config.max_depth == 5

    def test_scan_nonexistent_path(self):
        """Test scanning non-existent path raises error."""
        scanner = CodebaseScanner()
        with pytest.raises(FileNotFoundError):
            scanner.scan("/nonexistent/path")


class TestProjectTypeDetection:
    """Tests for project type detection."""

    def test_detect_configuration_by_xml(self):
        """Test detection of configuration by Configuration.xml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Configuration.xml marker
            Path(tmpdir, "Configuration.xml").touch()

            scanner = CodebaseScanner()
            project_type = scanner._detect_project_type(Path(tmpdir))

            assert project_type == ProjectType.CONFIGURATION

    def test_detect_configuration_by_mdo(self):
        """Test detection of configuration by Configuration.mdo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Configuration.mdo marker
            Path(tmpdir, "Configuration.mdo").touch()

            scanner = CodebaseScanner()
            project_type = scanner._detect_project_type(Path(tmpdir))

            assert project_type == ProjectType.CONFIGURATION

    def test_detect_extension(self):
        """Test detection of extension project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Extension.xml marker
            Path(tmpdir, "Extension.xml").touch()

            scanner = CodebaseScanner()
            project_type = scanner._detect_project_type(Path(tmpdir))

            assert project_type == ProjectType.EXTENSION

    def test_detect_external_dataprocessor(self):
        """Test detection of external data processor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create DataProcessor.xml marker
            Path(tmpdir, "DataProcessor.xml").touch()

            scanner = CodebaseScanner()
            project_type = scanner._detect_project_type(Path(tmpdir))

            assert project_type == ProjectType.EXTERNAL_DATAPROCESSOR

    def test_detect_external_report(self):
        """Test detection of external report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Report.xml marker
            Path(tmpdir, "Report.xml").touch()

            scanner = CodebaseScanner()
            project_type = scanner._detect_project_type(Path(tmpdir))

            assert project_type == ProjectType.EXTERNAL_REPORT

    def test_detect_by_standard_directories(self):
        """Test detection by standard 1C directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Catalogs directory
            Path(tmpdir, "Catalogs").mkdir()

            scanner = CodebaseScanner()
            project_type = scanner._detect_project_type(Path(tmpdir))

            assert project_type == ProjectType.CONFIGURATION

    def test_detect_unknown(self):
        """Test detection of unknown project type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory
            scanner = CodebaseScanner()
            project_type = scanner._detect_project_type(Path(tmpdir))

            assert project_type == ProjectType.UNKNOWN


class TestFileScanning:
    """Tests for file scanning."""

    def test_scan_bsl_file(self):
        """Test scanning BSL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create BSL file
            bsl_path = Path(tmpdir, "Module.bsl")
            bsl_path.write_text(
                "Процедура Тест()\n    Сообщить(\"Тест\");\nКонецПроцедуры",
                encoding="utf-8-sig",
            )

            scanner = CodebaseScanner()
            file_info = scanner._get_file_info(bsl_path)

            assert file_info is not None
            assert file_info.file_type == FileType.BSL
            assert file_info.line_count == 3

    def test_skip_patterns(self):
        """Test that skip patterns are respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directories to skip
            Path(tmpdir, ".git").mkdir()
            Path(tmpdir, "node_modules").mkdir()
            Path(tmpdir, "__pycache__").mkdir()

            # Create regular directory
            Path(tmpdir, "CommonModules").mkdir()
            Path(tmpdir, "CommonModules", "Module.bsl").write_text(
                "// Test",
                encoding="utf-8",
            )

            scanner = CodebaseScanner()
            directories = scanner._scan_directory(Path(tmpdir))

            # Should find CommonModules but not skip directories
            dir_names = [d.name for d in directories]
            assert "CommonModules" in str(directories)
            assert ".git" not in dir_names
            assert "node_modules" not in dir_names


class TestModuleExtraction:
    """Tests for module extraction."""

    def test_extract_common_module(self):
        """Test extraction of common module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create CommonModules structure
            common_modules = Path(tmpdir, "CommonModules")
            common_modules.mkdir()

            test_module = common_modules / "ТестовыйМодуль"
            test_module.mkdir()

            ext_dir = test_module / "Ext"
            ext_dir.mkdir()

            # Create module file with export
            module_path = ext_dir / "Module.bsl"
            module_path.write_text(
                "Функция ТестоваяФункция() Экспорт\n    Возврат 1;\nКонецФункции",
                encoding="utf-8-sig",
            )

            scanner = CodebaseScanner()
            structure = scanner.scan(tmpdir)

            assert len(structure.modules) == 1
            assert structure.modules[0].name == "ТестовыйМодуль"
            assert structure.modules[0].object_type == ObjectType.COMMON_MODULE
            assert structure.modules[0].exports_count == 1


class TestPatternDetection:
    """Tests for pattern detection."""

    def test_detect_naming_prefix(self):
        """Test detection of naming prefix pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create CommonModules with prefix
            common_modules = Path(tmpdir, "CommonModules")
            common_modules.mkdir()

            for name in ["гкс_Модуль1", "гкс_Модуль2", "гкс_Модуль3"]:
                mod_dir = common_modules / name
                mod_dir.mkdir()
                ext_dir = mod_dir / "Ext"
                ext_dir.mkdir()
                (ext_dir / "Module.bsl").write_text("// Test", encoding="utf-8")

            scanner = CodebaseScanner()
            structure = scanner.scan(tmpdir)

            # Should detect "гкс_" prefix
            prefix_patterns = [
                p for p in structure.patterns
                if "Naming Prefix" in p.name
            ]
            assert len(prefix_patterns) == 1


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_scan_directory_function(self):
        """Test scan_directory convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "Configuration.xml").touch()

            structure = scan_directory(tmpdir)

            assert structure is not None
            assert structure.project_type == ProjectType.CONFIGURATION

    def test_detect_project_type_function(self):
        """Test detect_project_type convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "Extension.xml").touch()

            project_type = detect_project_type(tmpdir)

            assert project_type == ProjectType.EXTENSION

    def test_get_file_stats(self):
        """Test get_file_stats function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simple structure
            common_modules = Path(tmpdir, "CommonModules")
            common_modules.mkdir()
            mod_dir = common_modules / "TestModule"
            mod_dir.mkdir()
            ext_dir = mod_dir / "Ext"
            ext_dir.mkdir()
            (ext_dir / "Module.bsl").write_text(
                "// Line 1\n// Line 2\n// Line 3",
                encoding="utf-8",
            )

            structure = scan_directory(tmpdir)
            stats = get_file_stats(structure)

            assert "total_files" in stats
            assert "bsl_files" in stats
            assert "total_modules" in stats
            assert "by_type" in stats
