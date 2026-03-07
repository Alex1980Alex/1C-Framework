"""
Pipeline CLI Main - главный модуль CLI.

Точка входа для командной строки pipeline.
Использование:
    pipeline run --project MyProject --task "Описание задачи"
    pipeline status
    pipeline list
    pipeline config show
    pipeline logs
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .config import CLIConfig, ConfigManager, OutputFormat, VerbosityLevel
from .output import OutputFormatter
from .commands import (
    COMMANDS,
    get_command,
    CommandResult,
    RunCommand,
    StatusCommand,
    ListCommand,
    ConfigCommand,
    LogsCommand,
)


class PipelineCLI:
    """Главный класс CLI."""

    VERSION = "1.0.0"

    def __init__(self, config: Optional[CLIConfig] = None) -> None:
        self.config = config or CLIConfig()
        self.formatter = OutputFormatter(
            format=self.config.output_format,
            color_enabled=self.config.color_enabled,
            unicode_enabled=self.config.unicode_enabled,
        )

    def create_parser(self) -> argparse.ArgumentParser:
        """Создание парсера аргументов."""
        parser = argparse.ArgumentParser(
            prog="pipeline",
            description="Development Pipeline CLI для многоагентной разработки 1С",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Примеры использования:

  # Запуск pipeline для проекта
  pipeline run --project GKSTCPLK-1996 --task "Добавить справочник Контрагенты"

  # Проверка статуса
  pipeline status

  # Список проектов
  pipeline list

  # Добавление проекта
  pipeline config add-project --name MyProject --path /path/to/project

  # Просмотр логов
  pipeline logs --lines 100

Документация: https://github.com/1c-enterprise-framework/pipeline
            """
        )

        # Глобальные опции
        parser.add_argument(
            "-v", "--version",
            action="version",
            version=f"%(prog)s {self.VERSION}"
        )
        parser.add_argument(
            "-q", "--quiet",
            action="store_true",
            help="Минимальный вывод"
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Подробный вывод"
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Отладочный вывод"
        )
        parser.add_argument(
            "--format",
            choices=["text", "json", "markdown", "table"],
            default="text",
            help="Формат вывода (default: text)"
        )
        parser.add_argument(
            "--no-color",
            action="store_true",
            help="Отключить цветной вывод"
        )
        parser.add_argument(
            "--config",
            type=Path,
            help="Путь к файлу конфигурации"
        )

        # Подкоманды
        subparsers = parser.add_subparsers(
            dest="command",
            title="Команды",
            description="Доступные команды"
        )

        # === run ===
        run_parser = subparsers.add_parser(
            "run",
            aliases=["r", "start"],
            help="Запуск pipeline"
        )
        run_parser.add_argument(
            "-p", "--project",
            help="Имя проекта"
        )
        run_parser.add_argument(
            "-t", "--task",
            help="Описание задачи"
        )
        run_parser.add_argument(
            "--phases",
            nargs="+",
            help="Фазы для выполнения"
        )
        run_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать план без выполнения"
        )
        run_parser.add_argument(
            "--no-checkpoint",
            action="store_true",
            help="Отключить checkpoint'ы"
        )

        # === status ===
        status_parser = subparsers.add_parser(
            "status",
            aliases=["s", "st"],
            help="Статус выполнения"
        )
        status_parser.add_argument(
            "-p", "--project",
            help="Фильтр по проекту"
        )
        status_parser.add_argument(
            "--run-id",
            help="ID конкретного запуска"
        )
        status_parser.add_argument(
            "-w", "--watch",
            action="store_true",
            help="Режим отслеживания"
        )

        # === list ===
        list_parser = subparsers.add_parser(
            "list",
            aliases=["ls", "l"],
            help="Списки проектов/запусков"
        )
        list_parser.add_argument(
            "type",
            nargs="?",
            choices=["projects", "runs", "artifacts"],
            default="projects",
            help="Тип списка (default: projects)"
        )
        list_parser.add_argument(
            "-p", "--project",
            help="Фильтр по проекту"
        )

        # === config ===
        config_parser = subparsers.add_parser(
            "config",
            aliases=["cfg", "c"],
            help="Управление конфигурацией"
        )
        config_subparsers = config_parser.add_subparsers(
            dest="action",
            title="Действия"
        )

        # config show
        config_subparsers.add_parser(
            "show",
            help="Показать конфигурацию"
        )

        # config set
        config_set = config_subparsers.add_parser(
            "set",
            help="Установить значение"
        )
        config_set.add_argument("key", help="Ключ конфигурации")
        config_set.add_argument("value", help="Значение")

        # config init
        config_subparsers.add_parser(
            "init",
            help="Инициализировать конфигурацию"
        )

        # config add-project
        add_project = config_subparsers.add_parser(
            "add-project",
            help="Добавить проект"
        )
        add_project.add_argument("--name", required=True, help="Имя проекта")
        add_project.add_argument("--path", required=True, help="Путь к проекту")
        add_project.add_argument(
            "--type",
            dest="config_type",
            choices=["configuration", "extension", "data_processor"],
            default="configuration",
            help="Тип конфигурации"
        )

        # config remove-project
        remove_project = config_subparsers.add_parser(
            "remove-project",
            help="Удалить проект"
        )
        remove_project.add_argument("name", help="Имя проекта")

        # === logs ===
        logs_parser = subparsers.add_parser(
            "logs",
            aliases=["log"],
            help="Просмотр логов"
        )
        logs_parser.add_argument(
            "--run-id",
            help="ID запуска"
        )
        logs_parser.add_argument(
            "-n", "--lines",
            type=int,
            default=50,
            help="Количество строк (default: 50)"
        )
        logs_parser.add_argument(
            "-f", "--follow",
            action="store_true",
            help="Режим отслеживания"
        )
        logs_parser.add_argument(
            "--level",
            choices=["all", "debug", "info", "warning", "error"],
            default="all",
            help="Фильтр по уровню"
        )

        return parser

    def run(self, args: Optional[List[str]] = None) -> int:
        """Запуск CLI."""
        parser = self.create_parser()
        parsed = parser.parse_args(args)

        # Обработка глобальных опций
        self._apply_global_options(parsed)

        # Проверка команды
        if not parsed.command:
            parser.print_help()
            return 0

        # Получение класса команды
        command_class = get_command(parsed.command)

        if not command_class:
            self.formatter.error(f"Неизвестная команда: {parsed.command}")
            return 1

        # Создание и выполнение команды
        command = command_class(self.config, self.formatter)

        # Подготовка аргументов для команды
        cmd_args = vars(parsed).copy()
        cmd_args.pop("command", None)

        # Валидация
        validation_error = command.validate_args(cmd_args)
        if validation_error:
            self.formatter.error(validation_error)
            return 1

        try:
            result = command.execute(cmd_args)

            if not result.success:
                self.formatter.error(result.message)

            return result.exit_code

        except Exception as e:
            self.formatter.error(f"Ошибка выполнения команды: {e}")
            if self.config.verbosity == VerbosityLevel.DEBUG:
                import traceback
                traceback.print_exc()
            return 1

    def _apply_global_options(self, args: argparse.Namespace) -> None:
        """Применение глобальных опций."""
        # Verbosity
        if args.quiet:
            self.config.verbosity = VerbosityLevel.QUIET
        elif args.debug:
            self.config.verbosity = VerbosityLevel.DEBUG
        elif args.verbose:
            self.config.verbosity = VerbosityLevel.VERBOSE

        # Format
        if hasattr(args, "format") and args.format:
            self.config.output_format = OutputFormat(args.format)

        # Color
        if hasattr(args, "no_color") and args.no_color:
            self.config.color_enabled = False

        # Обновление форматтера
        self.formatter = OutputFormatter(
            format=self.config.output_format,
            color_enabled=self.config.color_enabled,
            unicode_enabled=self.config.unicode_enabled,
        )

        # Config file
        if hasattr(args, "config") and args.config:
            self.config = CLIConfig.from_file(args.config)


def main(args: Optional[List[str]] = None) -> int:
    """Точка входа."""
    cli = PipelineCLI()
    return cli.run(args)


if __name__ == "__main__":
    sys.exit(main())
