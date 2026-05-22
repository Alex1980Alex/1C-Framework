"""
Pipeline CLI - Command Line Interface для Development Pipeline.

Модуль предоставляет интерфейс командной строки для управления
многоагентным pipeline разработки 1С.

Основные команды:
- run: Запуск pipeline для задачи
- status: Статус текущего выполнения
- list: Список проектов и задач
- config: Управление конфигурацией
- logs: Просмотр логов
"""

from .commands import (
    ConfigCommand,
    ListCommand,
    LogsCommand,
    RunCommand,
    StatusCommand,
)
from .config import CLIConfig
from .main import PipelineCLI, main
from .output import OutputFormat, OutputFormatter

__all__ = [
    "PipelineCLI",
    "main",
    "RunCommand",
    "StatusCommand",
    "ListCommand",
    "ConfigCommand",
    "LogsCommand",
    "CLIConfig",
    "OutputFormatter",
    "OutputFormat",
]

__version__ = "1.0.0"
