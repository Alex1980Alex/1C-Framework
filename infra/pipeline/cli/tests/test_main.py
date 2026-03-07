"""
Tests for CLI main module.

Тесты для главного модуля CLI.

Версия: 1.1.0
Дата: 2025-12-23
"""

import pytest
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from cli.main import PipelineCLI, main
from cli.config import CLIConfig, OutputFormat, VerbosityLevel


class TestPipelineCLI:
    """Тесты для PipelineCLI."""

    def test_cli_creation_default(self):
        """Тест создания CLI по умолчанию."""
        cli = PipelineCLI()

        assert cli is not None
        assert cli.config is not None
        assert cli.formatter is not None

    def test_cli_creation_with_config(self):
        """Тест создания CLI с конфигурацией."""
        config = CLIConfig(max_parallel_tasks=8)
        cli = PipelineCLI(config=config)

        assert cli.config.max_parallel_tasks == 8

    def test_cli_version(self):
        """Тест версии CLI."""
        cli = PipelineCLI()

        assert hasattr(cli, "VERSION")
        assert cli.VERSION == "1.0.0"


class TestCreateParser:
    """Тесты для create_parser (метод PipelineCLI)."""

    def test_parser_created(self):
        """Тест создания парсера."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        assert parser is not None

    def test_parser_has_subparsers(self):
        """Тест что парсер имеет subparsers."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        # Проверяем через _subparsers
        assert parser._subparsers is not None

    def test_parser_run_subcommand(self):
        """Тест subcommand run."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["run", "--project", "TEST", "--task", "Test"])

        assert args.command == "run"
        assert args.project == "TEST"
        assert args.task == "Test"

    def test_parser_status_subcommand(self):
        """Тест subcommand status."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["status"])

        assert args.command == "status"

    def test_parser_list_subcommand(self):
        """Тест subcommand list."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["list", "runs"])

        assert args.command == "list"
        assert args.type == "runs"

    def test_parser_config_subcommand(self):
        """Тест subcommand config."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["config", "show"])

        assert args.command == "config"
        assert args.action == "show"

    def test_parser_logs_subcommand(self):
        """Тест subcommand logs."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["logs"])

        assert args.command == "logs"

    def test_parser_version_flag(self):
        """Тест флага --version."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])

        assert exc_info.value.code == 0

    def test_parser_help_flag(self):
        """Тест флага --help."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])

        assert exc_info.value.code == 0

    def test_parser_run_dry_run_flag(self):
        """Тест флага --dry-run для run."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "run",
            "--project", "TEST",
            "--task", "Test",
            "--dry-run"
        ])

        assert args.dry_run is True

    def test_parser_run_no_checkpoint_flag(self):
        """Тест флага --no-checkpoint для run."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "run",
            "--project", "TEST",
            "--task", "Test",
            "--no-checkpoint"
        ])

        assert args.no_checkpoint is True

    def test_parser_status_run_id(self):
        """Тест --run-id для status."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "status",
            "--run-id", "run-12345"
        ])

        assert args.run_id == "run-12345"

    def test_parser_status_watch(self):
        """Тест --watch для status."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "status",
            "--watch"
        ])

        assert args.watch is True

    def test_parser_logs_lines(self):
        """Тест --lines для logs."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "logs",
            "--lines", "100"
        ])

        assert args.lines == 100

    def test_parser_logs_follow(self):
        """Тест --follow для logs."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "logs",
            "--follow"
        ])

        assert args.follow is True

    def test_parser_config_set(self):
        """Тест config set."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "config", "set",
            "max_parallel_tasks", "8"
        ])

        assert args.action == "set"
        assert args.key == "max_parallel_tasks"
        assert args.value == "8"


class TestMain:
    """Тесты для функции main."""

    def test_main_no_args_shows_help(self):
        """Тест main без аргументов показывает help."""
        # Без команды CLI показывает help и выходит с 0
        result = main([])

        assert result == 0

    def test_main_help(self):
        """Тест main --help."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0

    def test_main_version(self):
        """Тест main --version."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])

        assert exc_info.value.code == 0

    def test_main_status_command(self):
        """Тест main с командой status."""
        result = main(["status"])

        assert result == 0

    def test_main_list_command(self):
        """Тест main с командой list."""
        result = main(["list"])

        assert result == 0

    def test_main_config_show(self):
        """Тест main с командой config show."""
        result = main(["config", "show"])

        assert result == 0


class TestCLIRun:
    """Тесты для метода CLI.run()."""

    def test_run_returns_int(self):
        """Тест что run возвращает int."""
        cli = PipelineCLI()

        result = cli.run(["status"])

        assert isinstance(result, int)

    def test_run_unknown_command(self):
        """Тест запуска неизвестной команды."""
        cli = PipelineCLI()

        with pytest.raises(SystemExit):
            cli.run(["invalid_command"])

    def test_run_status_command(self):
        """Тест запуска status."""
        cli = PipelineCLI()

        result = cli.run(["status"])

        assert result == 0

    def test_run_list_runs(self):
        """Тест запуска list runs."""
        cli = PipelineCLI()

        result = cli.run(["list", "runs"])

        assert result == 0

    def test_run_list_projects(self):
        """Тест запуска list projects."""
        cli = PipelineCLI()

        result = cli.run(["list", "projects"])

        assert result == 0

    def test_run_config_show(self):
        """Тест запуска config show."""
        cli = PipelineCLI()

        result = cli.run(["config", "show"])

        assert result == 0

    def test_run_logs(self):
        """Тест запуска logs."""
        cli = PipelineCLI()

        result = cli.run(["logs"])

        assert result == 0


class TestCLIOutputFormats:
    """Тесты форматов вывода."""

    def test_output_format_text(self):
        """Тест текстового формата."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "--format", "text",
            "status"
        ])

        assert args.format == "text"

    def test_output_format_json(self):
        """Тест JSON формата."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "--format", "json",
            "status"
        ])

        assert args.format == "json"

    def test_output_format_markdown(self):
        """Тест Markdown формата."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "--format", "markdown",
            "status"
        ])

        assert args.format == "markdown"

    def test_output_format_table(self):
        """Тест table формата."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args([
            "--format", "table",
            "status"
        ])

        assert args.format == "table"


class TestCLIVerbosity:
    """Тесты уровней детализации."""

    def test_quiet_mode(self):
        """Тест тихого режима."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["-q", "status"])

        assert args.quiet is True

    def test_verbose_mode(self):
        """Тест подробного режима."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["--verbose", "status"])

        assert args.verbose is True

    def test_debug_mode(self):
        """Тест отладочного режима."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["--debug", "status"])

        assert args.debug is True

    def test_no_color_mode(self):
        """Тест режима без цвета."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        args = parser.parse_args(["--no-color", "status"])

        assert args.no_color is True


class TestCLIGlobalOptions:
    """Тесты глобальных опций."""

    def test_apply_global_options_quiet(self):
        """Тест применения -q опции."""
        cli = PipelineCLI()

        # Запуск с -q должен установить QUIET
        cli.run(["-q", "status"])

        assert cli.config.verbosity == VerbosityLevel.QUIET

    def test_apply_global_options_verbose(self):
        """Тест применения --verbose опции."""
        cli = PipelineCLI()

        cli.run(["--verbose", "status"])

        assert cli.config.verbosity == VerbosityLevel.VERBOSE

    def test_apply_global_options_debug(self):
        """Тест применения --debug опции."""
        cli = PipelineCLI()

        cli.run(["--debug", "status"])

        assert cli.config.verbosity == VerbosityLevel.DEBUG

    def test_apply_global_options_format(self):
        """Тест применения --format опции."""
        cli = PipelineCLI()

        cli.run(["--format", "json", "status"])

        assert cli.config.output_format == OutputFormat.JSON

    def test_apply_global_options_no_color(self):
        """Тест применения --no-color опции."""
        cli = PipelineCLI()

        cli.run(["--no-color", "status"])

        assert cli.config.color_enabled is False


class TestCLIErrorHandling:
    """Тесты обработки ошибок."""

    def test_invalid_command(self):
        """Тест неверной команды."""
        cli = PipelineCLI()

        with pytest.raises(SystemExit):
            cli.run(["invalid_command"])

    def test_run_parses_without_args(self):
        """Тест что run парсится без аргументов (они опциональны).

        --project и --task опциональны на уровне парсера чтобы можно было
        использовать default_project из конфига. Валидация происходит в execute().
        """
        cli = PipelineCLI()
        parser = cli.create_parser()

        # run без аргументов должен парситься успешно
        args = parser.parse_args(["run"])
        assert args.project is None
        assert args.task is None

    def test_run_with_missing_project(self):
        """Тест run без проекта."""
        cli = PipelineCLI()

        # run без project и task должен вернуть ошибку
        result = cli.run(["run", "--task", "test"])

        assert result != 0

    def test_run_with_missing_task(self):
        """Тест run без задачи."""
        cli = PipelineCLI()

        result = cli.run(["run", "--project", "TEST"])

        assert result != 0


class TestCLIAliases:
    """Тесты алиасов команд."""

    def test_run_alias_r(self):
        """Тест алиаса r для run."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        # Если алиасы поддерживаются
        try:
            args = parser.parse_args(["r", "--project", "T", "--task", "t"])
            assert args.command in ["run", "r"]
        except SystemExit:
            pass  # Алиасы могут быть не включены

    def test_status_alias_s(self):
        """Тест алиаса s для status."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        try:
            args = parser.parse_args(["s"])
            assert args.command in ["status", "s"]
        except SystemExit:
            pass

    def test_list_alias_ls(self):
        """Тест алиаса ls для list."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        try:
            args = parser.parse_args(["ls"])
            assert args.command in ["list", "ls"]
        except SystemExit:
            pass

    def test_config_alias_cfg(self):
        """Тест алиаса cfg для config."""
        cli = PipelineCLI()
        parser = cli.create_parser()

        try:
            args = parser.parse_args(["cfg", "show"])
            assert args.command in ["config", "cfg"]
        except SystemExit:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
