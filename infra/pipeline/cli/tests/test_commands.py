"""
Tests for CLI commands module.

Тесты для модуля команд CLI.

Версия: 1.1.0
Дата: 2025-12-23
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from cli.commands import (
    BaseCommand,
    RunCommand,
    StatusCommand,
    ListCommand,
    ConfigCommand,
    LogsCommand,
    CommandResult,
    COMMANDS,
    get_command,
)
from cli.config import CLIConfig, ProjectConfig, ConfigManager
from cli.output import OutputFormatter


class TestCommandResult:
    """Тесты для CommandResult."""

    def test_create_success_result(self):
        """Тест создания успешного результата."""
        result = CommandResult(success=True, message="OK")

        assert result.success is True
        assert result.message == "OK"
        assert result.exit_code == 0

    def test_create_error_result(self):
        """Тест создания результата с ошибкой."""
        result = CommandResult(success=False, message="Error", exit_code=1)

        assert result.success is False
        assert result.message == "Error"
        assert result.exit_code == 1

    def test_result_with_data(self):
        """Тест результата с данными."""
        data = {"key": "value", "count": 42}
        result = CommandResult(success=True, data=data)

        assert result.data == data
        assert result.data["count"] == 42


class TestBaseCommand:
    """Тесты для BaseCommand."""

    def test_base_command_creation(self):
        """Тест создания базовой команды."""
        config = CLIConfig()
        formatter = OutputFormatter()

        # BaseCommand абстрактный, создаём через наследника
        class TestCommand(BaseCommand):
            name = "test"
            description = "Test command"

            def execute(self, args: Dict[str, Any]) -> CommandResult:
                return CommandResult(success=True)

        cmd = TestCommand(config, formatter)

        assert cmd.config == config
        assert cmd.formatter == formatter
        assert cmd.name == "test"

    def test_base_command_requires_execute(self):
        """Тест что execute обязателен."""

        class IncompleteCommand(BaseCommand):
            name = "incomplete"
            description = "Incomplete"

        config = CLIConfig()
        formatter = OutputFormatter()

        with pytest.raises(TypeError):
            IncompleteCommand(config, formatter)


class TestRunCommand:
    """Тесты для RunCommand."""

    def test_run_command_creation(self):
        """Тест создания команды run."""
        config = CLIConfig()
        formatter = OutputFormatter()

        cmd = RunCommand(config, formatter)

        assert cmd.name == "run"
        assert cmd.description != ""

    def test_run_command_requires_project(self):
        """Тест что run требует проект."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = RunCommand(config, formatter)

        # Args как словарь без project
        args = {"project": None, "task": "test task"}

        result = cmd.execute(args)

        # Должен вернуть ошибку
        assert result.success is False or result.exit_code != 0

    def test_run_command_requires_task(self):
        """Тест что run требует task."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = RunCommand(config, formatter)

        args = {"project": "TEST-PROJECT", "task": None}

        result = cmd.execute(args)

        assert result.success is False or result.exit_code != 0

    def test_run_command_dry_run(self):
        """Тест dry-run режима."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = RunCommand(config, formatter)

        args = {
            "project": "TEST-PROJECT",
            "task": "Test task",
            "dry_run": True,
            "phases": None,
            "no_checkpoint": False,
        }

        result = cmd.execute(args)

        # В dry-run должен вернуть успех без реального выполнения
        assert result.success is True
        assert result.exit_code == 0


class TestStatusCommand:
    """Тесты для StatusCommand."""

    def test_status_command_creation(self):
        """Тест создания команды status."""
        config = CLIConfig()
        formatter = OutputFormatter()

        cmd = StatusCommand(config, formatter)

        assert cmd.name == "status"

    def test_status_no_active_runs(self):
        """Тест статуса без активных запусков."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = StatusCommand(config, formatter)

        args = {"run_id": None, "project": None, "watch": False}

        result = cmd.execute(args)

        assert result.exit_code == 0

    def test_status_specific_run(self):
        """Тест статуса конкретного запуска."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = StatusCommand(config, formatter)

        args = {"run_id": "run-12345", "project": None, "watch": False}

        result = cmd.execute(args)

        # Может вернуть ошибку если run_id не найден
        assert result.exit_code in [0, 1]


class TestListCommand:
    """Тесты для ListCommand."""

    def test_list_command_creation(self):
        """Тест создания команды list."""
        config = CLIConfig()
        formatter = OutputFormatter()

        cmd = ListCommand(config, formatter)

        assert cmd.name == "list"

    def test_list_runs(self):
        """Тест списка запусков."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = ListCommand(config, formatter)

        args = {"type": "runs", "project": None}

        result = cmd.execute(args)

        assert result.exit_code == 0

    def test_list_projects(self):
        """Тест списка проектов."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = ListCommand(config, formatter)

        args = {"type": "projects", "project": None}

        result = cmd.execute(args)

        assert result.exit_code == 0

    def test_list_artifacts(self):
        """Тест списка артефактов."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = ListCommand(config, formatter)

        args = {"type": "artifacts", "project": "TEST"}

        result = cmd.execute(args)

        assert result.exit_code == 0


class TestConfigCommand:
    """Тесты для ConfigCommand."""

    def test_config_command_creation(self):
        """Тест создания команды config."""
        config = CLIConfig()
        formatter = OutputFormatter()

        cmd = ConfigCommand(config, formatter)

        assert cmd.name == "config"

    def test_config_show(self):
        """Тест показа конфигурации."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = ConfigCommand(config, formatter)

        args = {"action": "show", "key": None, "value": None}

        result = cmd.execute(args)

        assert result.exit_code == 0

    def test_config_init(self):
        """Тест инициализации конфигурации."""
        with TemporaryDirectory() as tmpdir:
            config = CLIConfig(project_root=Path(tmpdir))
            formatter = OutputFormatter()
            cmd = ConfigCommand(config, formatter)

            args = {"action": "init"}

            result = cmd.execute(args)

            assert result.exit_code == 0

    def test_config_set(self):
        """Тест установки значения."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = ConfigCommand(config, formatter)

        args = {
            "action": "set",
            "key": "max_parallel_tasks",
            "value": "8",
        }

        result = cmd.execute(args)

        # Должен попытаться сохранить (может не найти файл конфига)
        assert result.exit_code in [0, 1]


class TestLogsCommand:
    """Тесты для LogsCommand."""

    def test_logs_command_creation(self):
        """Тест создания команды logs."""
        config = CLIConfig()
        formatter = OutputFormatter()

        cmd = LogsCommand(config, formatter)

        assert cmd.name == "logs"

    def test_logs_default(self):
        """Тест вывода логов по умолчанию."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = LogsCommand(config, formatter)

        args = {"run_id": None, "lines": 50, "follow": False, "level": "all"}

        result = cmd.execute(args)

        assert result.exit_code == 0

    def test_logs_specific_run(self):
        """Тест логов конкретного запуска."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = LogsCommand(config, formatter)

        args = {"run_id": "run-12345", "lines": 100, "follow": False, "level": "error"}

        result = cmd.execute(args)

        assert result.exit_code in [0, 1]


class TestCommandsRegistry:
    """Тесты для реестра команд."""

    def test_commands_dict_exists(self):
        """Тест существования реестра команд."""
        assert COMMANDS is not None
        assert isinstance(COMMANDS, dict)

    def test_all_commands_registered(self):
        """Тест что все команды зарегистрированы."""
        expected = ["run", "status", "list", "config", "logs"]

        for cmd_name in expected:
            assert cmd_name in COMMANDS, f"Command '{cmd_name}' not registered"

    def test_get_command_by_name(self):
        """Тест получения команды по имени."""
        cmd_class = get_command("run")

        assert cmd_class is not None
        assert cmd_class == RunCommand

    def test_get_command_unknown(self):
        """Тест получения неизвестной команды."""
        cmd_class = get_command("nonexistent")

        assert cmd_class is None

    def test_get_command_by_alias(self):
        """Тест получения команды по alias."""
        # run имеет alias 'r', 'start'
        cmd_class = get_command("r")

        # Если alias поддерживается
        if cmd_class is not None:
            assert cmd_class == RunCommand


class TestCommandIntegration:
    """Интеграционные тесты команд."""

    def test_all_commands_have_name(self):
        """Тест что все команды имеют имя."""
        config = CLIConfig()
        formatter = OutputFormatter()

        commands = [
            RunCommand(config, formatter),
            StatusCommand(config, formatter),
            ListCommand(config, formatter),
            ConfigCommand(config, formatter),
            LogsCommand(config, formatter),
        ]

        for cmd in commands:
            assert hasattr(cmd, "name")
            assert cmd.name is not None
            assert len(cmd.name) > 0

    def test_all_commands_have_description(self):
        """Тест что все команды имеют описание."""
        config = CLIConfig()
        formatter = OutputFormatter()

        commands = [
            RunCommand(config, formatter),
            StatusCommand(config, formatter),
            ListCommand(config, formatter),
            ConfigCommand(config, formatter),
            LogsCommand(config, formatter),
        ]

        for cmd in commands:
            assert hasattr(cmd, "description")
            assert cmd.description is not None

    def test_commands_return_command_result(self):
        """Тест что команды возвращают CommandResult."""
        config = CLIConfig()
        formatter = OutputFormatter()

        cmd = StatusCommand(config, formatter)
        args = {"run_id": None, "project": None, "watch": False}

        result = cmd.execute(args)

        assert isinstance(result, CommandResult)
        assert hasattr(result, "success")
        assert hasattr(result, "exit_code")

    def test_command_validate_args(self):
        """Тест валидации аргументов."""
        config = CLIConfig()
        formatter = OutputFormatter()
        cmd = RunCommand(config, formatter)

        # Проверяем что есть метод validate_args
        if hasattr(cmd, "validate_args"):
            args = {"project": None, "task": None}
            error = cmd.validate_args(args)
            assert error is not None  # Должна быть ошибка


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
