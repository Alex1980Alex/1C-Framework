"""
Tests for CLI configuration module.

Тесты для модуля конфигурации CLI.

Версия: 1.1.0
Дата: 2025-12-23
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import os

from cli.config import (
    CLIConfig,
    ProjectConfig,
    ConfigManager,
    OutputFormat,
    VerbosityLevel,
)


class TestCLIConfig:
    """Тесты для CLIConfig."""

    def test_default_config(self):
        """Тест создания конфигурации по умолчанию."""
        config = CLIConfig()

        assert config.project_root == Path.cwd()
        assert config.artifacts_dir == Path("artifacts")
        assert config.logs_dir == Path("logs")
        assert config.output_format == OutputFormat.TEXT
        assert config.verbosity == VerbosityLevel.NORMAL
        assert config.max_parallel_tasks == 4
        assert config.timeout_seconds == 3600

    def test_custom_config(self):
        """Тест создания конфигурации с параметрами."""
        config = CLIConfig(
            project_root=Path("/custom/path"),
            max_parallel_tasks=8,
            timeout_seconds=7200,
            output_format=OutputFormat.JSON
        )

        assert config.project_root == Path("/custom/path")
        assert config.max_parallel_tasks == 8
        assert config.timeout_seconds == 7200
        assert config.output_format == OutputFormat.JSON

    def test_enabled_agents_default(self):
        """Тест списка агентов по умолчанию."""
        config = CLIConfig()

        assert "initializer" in config.enabled_agents
        assert "pm-spec" in config.enabled_agents
        assert "architect" in config.enabled_agents
        assert "implementer" in config.enabled_agents

    def test_to_dict(self):
        """Тест конвертации в словарь."""
        config = CLIConfig(
            project_root=Path("/test"),
            max_parallel_tasks=2
        )

        data = config.to_dict()

        assert isinstance(data, dict)
        # Platform-agnostic path comparison
        assert Path(data["project_root"]) == Path("/test")
        assert data["max_parallel_tasks"] == 2

    def test_from_file_missing(self):
        """Тест загрузки из несуществующего файла."""
        config = CLIConfig.from_file(Path("/nonexistent/config.json"))

        # Должен вернуть конфигурацию по умолчанию
        assert config.max_parallel_tasks == 4
        assert config.output_format == OutputFormat.TEXT

    def test_from_file_existing(self):
        """Тест загрузки из существующего файла."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text(json.dumps({
                "project_root": "/from/file",
                "max_parallel_tasks": 6,
                "output_format": "json"
            }))

            config = CLIConfig.from_file(config_file)

            assert config.project_root == Path("/from/file")
            assert config.max_parallel_tasks == 6
            assert config.output_format == OutputFormat.JSON

    def test_from_env(self):
        """Тест загрузки из переменных окружения."""
        # Сохраняем оригинальные значения
        original = {
            "PIPELINE_PROJECT_ROOT": os.environ.get("PIPELINE_PROJECT_ROOT"),
            "PIPELINE_MAX_PARALLEL": os.environ.get("PIPELINE_MAX_PARALLEL"),
        }

        try:
            os.environ["PIPELINE_PROJECT_ROOT"] = "/env/path"
            os.environ["PIPELINE_MAX_PARALLEL"] = "12"

            config = CLIConfig.from_env()

            assert config.project_root == Path("/env/path")
            assert config.max_parallel_tasks == 12
        finally:
            # Восстанавливаем оригинальные значения
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_save(self):
        """Тест сохранения конфигурации."""
        with TemporaryDirectory() as tmpdir:
            config = CLIConfig(
                project_root=Path(tmpdir),
                max_parallel_tasks=5
            )
            config_file = Path(tmpdir) / "test_config.json"

            config.save(config_file)

            assert config_file.exists()
            data = json.loads(config_file.read_text())
            assert data["max_parallel_tasks"] == 5

    def test_merge(self):
        """Тест слияния конфигураций."""
        config1 = CLIConfig(max_parallel_tasks=4, timeout_seconds=1000)
        config2 = CLIConfig(max_parallel_tasks=8, auto_commit=True)

        merged = config1.merge(config2)

        assert merged.max_parallel_tasks == 8  # От config2
        assert merged.auto_commit is True  # От config2
        assert merged.timeout_seconds == 1000  # От config1

    def test_get_absolute_path(self):
        """Тест получения абсолютного пути."""
        config = CLIConfig(project_root=Path("/project"))

        # Относительный путь
        abs_path = config.get_absolute_path(Path("subdir/file.txt"))
        assert abs_path == Path("/project/subdir/file.txt")

        # Абсолютный путь
        abs_path = config.get_absolute_path(Path("/absolute/path"))
        assert abs_path == Path("/absolute/path")

    def test_ensure_dirs(self):
        """Тест создания директорий."""
        with TemporaryDirectory() as tmpdir:
            config = CLIConfig(
                project_root=Path(tmpdir),
                artifacts_dir=Path("artifacts"),
                logs_dir=Path("logs")
            )

            config.ensure_dirs()

            assert (Path(tmpdir) / "artifacts").exists()
            assert (Path(tmpdir) / "logs").exists()

    def test_color_enabled_default(self):
        """Тест что цвета включены по умолчанию."""
        config = CLIConfig()
        assert config.color_enabled is True

    def test_unicode_enabled_default(self):
        """Тест что unicode включен по умолчанию."""
        config = CLIConfig()
        assert config.unicode_enabled is True

    def test_post_init_string_conversion(self):
        """Тест конвертации строк в Path и Enum в __post_init__."""
        config = CLIConfig(
            project_root="/string/path",
            output_format="json",
            verbosity=2
        )

        assert isinstance(config.project_root, Path)
        assert config.output_format == OutputFormat.JSON
        assert config.verbosity == VerbosityLevel.VERBOSE


class TestProjectConfig:
    """Тесты для ProjectConfig."""

    def test_create_project_config(self):
        """Тест создания конфигурации проекта."""
        project = ProjectConfig(
            name="TEST-PROJECT",
            path=Path("/path/to/project"),
            config_type="configuration"
        )

        assert project.name == "TEST-PROJECT"
        assert project.path == Path("/path/to/project")
        assert project.config_type == "configuration"

    def test_project_to_dict(self):
        """Тест конвертации проекта в словарь."""
        project = ProjectConfig(
            name="TEST",
            path=Path("/test"),
            config_type="extension"
        )

        data = project.to_dict()

        assert data["name"] == "TEST"
        # Platform-agnostic path comparison
        assert Path(data["path"]) == Path("/test")
        assert data["config_type"] == "extension"

    def test_project_from_dict(self):
        """Тест создания проекта из словаря."""
        data = {
            "name": "MY-PROJECT",
            "path": "/my/path",
            "config_type": "data_processor",
            "description": "Test project"
        }

        project = ProjectConfig.from_dict(data)

        assert project.name == "MY-PROJECT"
        assert project.config_type == "data_processor"
        assert project.description == "Test project"

    def test_project_default_phases(self):
        """Тест фаз по умолчанию."""
        project = ProjectConfig(name="TEST", path=Path("/test"))

        assert "init" in project.enabled_phases
        assert "spec" in project.enabled_phases
        assert "design" in project.enabled_phases
        assert "implement" in project.enabled_phases
        assert "test" in project.enabled_phases
        assert "review" in project.enabled_phases

    def test_project_metadata(self):
        """Тест метаданных проекта."""
        project = ProjectConfig(
            name="TEST",
            path=Path("/test"),
            created_at="2025-12-23",
            total_runs=5
        )

        assert project.created_at == "2025-12-23"
        assert project.total_runs == 5


class TestConfigManager:
    """Тесты для ConfigManager."""

    def test_create_manager(self):
        """Тест создания менеджера конфигурации."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))

            assert manager.base_path == Path(tmpdir)
            assert manager.config_dir == Path(tmpdir) / ".pipeline"

    def test_cli_config_property(self):
        """Тест получения CLI конфигурации."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))
            config = manager.cli_config

            assert config is not None
            assert isinstance(config, CLIConfig)

    def test_save_and_load_cli_config(self):
        """Тест сохранения и загрузки CLI конфигурации."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))

            # Создаём и сохраняем конфигурацию
            config = CLIConfig(max_parallel_tasks=10, timeout_seconds=9000)
            manager.save_cli_config(config)

            # Создаём новый менеджер и загружаем
            manager2 = ConfigManager(base_path=Path(tmpdir))
            loaded_config = manager2.cli_config

            assert loaded_config.max_parallel_tasks == 10
            assert loaded_config.timeout_seconds == 9000

    def test_register_project(self):
        """Тест регистрации проекта."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))

            project = ProjectConfig(
                name="NEW-PROJECT",
                path=Path("/new/project"),
                config_type="configuration"
            )

            manager.register_project(project)
            projects = manager.list_projects()

            assert "NEW-PROJECT" in projects
            # Path is stored as string in JSON, compare as Path objects
            assert Path(projects["NEW-PROJECT"].path) == Path("/new/project")

    def test_remove_project(self):
        """Тест удаления проекта."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))

            # Регистрируем проект
            project = ProjectConfig(
                name="TO-REMOVE",
                path=Path("/remove"),
                config_type="configuration"
            )
            manager.register_project(project)

            # Удаляем
            result = manager.remove_project("TO-REMOVE")

            assert result is True
            projects = manager.list_projects()
            assert "TO-REMOVE" not in projects

    def test_remove_nonexistent_project(self):
        """Тест удаления несуществующего проекта."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))

            result = manager.remove_project("NONEXISTENT")

            assert result is False

    def test_get_project(self):
        """Тест получения проекта."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))

            project = ProjectConfig(
                name="GET-TEST",
                path=Path("/get/test"),
                config_type="extension"
            )
            manager.register_project(project)

            found = manager.get_project("GET-TEST")

            assert found is not None
            assert found.name == "GET-TEST"

    def test_get_nonexistent_project(self):
        """Тест получения несуществующего проекта."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))

            found = manager.get_project("NONEXISTENT")

            assert found is None

    def test_list_projects_empty(self):
        """Тест списка проектов когда нет проектов."""
        with TemporaryDirectory() as tmpdir:
            manager = ConfigManager(base_path=Path(tmpdir))

            projects = manager.list_projects()

            assert projects == {}


class TestOutputFormat:
    """Тесты для OutputFormat enum."""

    def test_output_formats(self):
        """Тест значений формата вывода."""
        assert OutputFormat.TEXT.value == "text"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.TABLE.value == "table"

    def test_from_string(self):
        """Тест создания из строки."""
        assert OutputFormat("text") == OutputFormat.TEXT
        assert OutputFormat("json") == OutputFormat.JSON
        assert OutputFormat("markdown") == OutputFormat.MARKDOWN
        assert OutputFormat("table") == OutputFormat.TABLE


class TestVerbosityLevel:
    """Тесты для VerbosityLevel enum."""

    def test_verbosity_levels(self):
        """Тест уровней детализации."""
        assert VerbosityLevel.QUIET.value == 0
        assert VerbosityLevel.NORMAL.value == 1
        assert VerbosityLevel.VERBOSE.value == 2
        assert VerbosityLevel.DEBUG.value == 3

    def test_from_int(self):
        """Тест создания из числа."""
        assert VerbosityLevel(0) == VerbosityLevel.QUIET
        assert VerbosityLevel(1) == VerbosityLevel.NORMAL
        assert VerbosityLevel(2) == VerbosityLevel.VERBOSE
        assert VerbosityLevel(3) == VerbosityLevel.DEBUG


class TestConfigIntegration:
    """Интеграционные тесты конфигурации."""

    def test_full_workflow(self):
        """Тест полного рабочего процесса."""
        with TemporaryDirectory() as tmpdir:
            # Создаём менеджер
            manager = ConfigManager(base_path=Path(tmpdir))

            # Регистрируем несколько проектов
            for i in range(3):
                project = ProjectConfig(
                    name=f"PROJECT-{i}",
                    path=Path(f"/project/{i}"),
                    config_type="configuration"
                )
                manager.register_project(project)

            # Проверяем список
            projects = manager.list_projects()
            assert len(projects) == 3

            # Сохраняем CLI конфигурацию
            config = CLIConfig(max_parallel_tasks=8)
            manager.save_cli_config(config)

            # Проверяем что всё сохранено
            assert (Path(tmpdir) / ".pipeline" / "config.json").exists()
            assert (Path(tmpdir) / ".pipeline" / "projects.json").exists()

    def test_config_persistence(self):
        """Тест персистентности конфигурации."""
        with TemporaryDirectory() as tmpdir:
            # Первый менеджер - создаём данные
            manager1 = ConfigManager(base_path=Path(tmpdir))

            project = ProjectConfig(
                name="PERSISTENT",
                path=Path("/persistent"),
                config_type="configuration"
            )
            manager1.register_project(project)

            config = CLIConfig(max_parallel_tasks=16, auto_commit=True)
            manager1.save_cli_config(config)

            # Второй менеджер - читаем данные
            manager2 = ConfigManager(base_path=Path(tmpdir))

            # Проверяем проекты
            loaded_project = manager2.get_project("PERSISTENT")
            assert loaded_project is not None
            assert loaded_project.name == "PERSISTENT"

            # Проверяем CLI конфиг
            loaded_config = manager2.cli_config
            assert loaded_config.max_parallel_tasks == 16
            assert loaded_config.auto_commit is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
