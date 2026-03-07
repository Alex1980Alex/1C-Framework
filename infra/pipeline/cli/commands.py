"""
CLI Commands - команды для Pipeline CLI.

Реализация основных команд: run, status, list, config, logs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from .config import CLIConfig, ConfigManager, ProjectConfig
from .output import OutputFormatter, TableColumn, Symbol


class CommandError(Exception):
    """Ошибка выполнения команды."""
    pass


@dataclass
class CommandResult:
    """Результат выполнения команды."""

    success: bool
    message: str = ""
    data: Any = None
    exit_code: int = 0

    @classmethod
    def ok(cls, message: str = "", data: Any = None) -> "CommandResult":
        """Успешный результат."""
        return cls(success=True, message=message, data=data, exit_code=0)

    @classmethod
    def error(cls, message: str, exit_code: int = 1) -> "CommandResult":
        """Результат с ошибкой."""
        return cls(success=False, message=message, exit_code=exit_code)


class BaseCommand(ABC):
    """Базовый класс команды."""

    name: str = ""
    description: str = ""
    aliases: List[str] = []

    def __init__(self, config: CLIConfig, formatter: OutputFormatter) -> None:
        self.config = config
        self.formatter = formatter

    @abstractmethod
    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """Выполнение команды."""
        pass

    def validate_args(self, args: Dict[str, Any]) -> Optional[str]:
        """Валидация аргументов. Возвращает сообщение об ошибке или None."""
        return None


class RunCommand(BaseCommand):
    """Команда запуска pipeline."""

    name = "run"
    description = "Запуск pipeline для проекта"
    aliases = ["r", "start"]

    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """Запуск pipeline."""
        project = args.get("project") or self.config.default_project
        task = args.get("task", "")
        phases = args.get("phases") or self.config.enabled_agents
        dry_run = args.get("dry_run", False)

        if not project:
            return CommandResult.error("Не указан проект. Используйте --project или установите default_project")

        # В dry_run режиме пропускаем проверку существования проекта
        if dry_run:
            self.formatter.header(f"Pipeline Run: {project} (dry-run)")
            self.formatter.print()
            self.formatter.info(f"Проект: {project}")
            self.formatter.info(f"Задача: {task or '(не указана)'}")
            self.formatter.info(f"Фазы: {', '.join(phases)}")
            self.formatter.warning("Режим dry-run: pipeline не будет запущен")
            return CommandResult.ok("Dry run completed", data={
                "project": project,
                "task": task,
                "phases": phases,
                "dry_run": True
            })

        # Проверка существования проекта (только для реального запуска)
        manager = ConfigManager(self.config.project_root)
        project_config = manager.get_project(project)

        if not project_config:
            return CommandResult.error(f"Проект '{project}' не найден. Используйте 'pipeline list' для списка проектов")

        self.formatter.header(f"Pipeline Run: {project}")
        self.formatter.print()

        # Информация о запуске
        self.formatter.info(f"Проект: {project}")
        self.formatter.info(f"Путь: {project_config.path}")
        self.formatter.info(f"Задача: {task or '(не указана)'}")
        self.formatter.info(f"Фазы: {', '.join(phases)}")

        self.formatter.print()
        self.formatter.section("Выполнение")

        # Эмуляция выполнения (реальная интеграция с orchestrator будет позже)
        pipeline_phases = [
            {"name": "Initializer", "agent": "initializer", "status": "pending"},
            {"name": "PM-Spec", "agent": "pm-spec", "status": "pending"},
            {"name": "Architect", "agent": "architect", "status": "pending"},
            {"name": "Implementer", "agent": "implementer", "status": "pending"},
            {"name": "QA", "agent": "qa", "status": "pending"},
            {"name": "Reviewer", "agent": "reviewer", "status": "pending"},
        ]

        self.formatter.pipeline_status(pipeline_phases)

        return CommandResult.ok(
            f"Pipeline запущен для проекта '{project}'",
            data={
                "project": project,
                "task": task,
                "phases": phases,
                "status": "running"
            }
        )

    def validate_args(self, args: Dict[str, Any]) -> Optional[str]:
        """Валидация аргументов."""
        if not args.get("project") and not self.config.default_project:
            return "Требуется указать проект (--project) или установить default_project"
        return None


class StatusCommand(BaseCommand):
    """Команда проверки статуса."""

    name = "status"
    description = "Статус текущего выполнения pipeline"
    aliases = ["s", "st"]

    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """Получение статуса."""
        project = args.get("project")
        run_id = args.get("run_id")
        watch = args.get("watch", False)

        self.formatter.header("Pipeline Status")
        self.formatter.print()

        # Проверка состояния (из файла или базы)
        state_file = self.config.get_absolute_path(
            self.config.artifacts_dir / "pipeline_state.json"
        )

        if not state_file.exists():
            self.formatter.info("Нет активных запусков pipeline")
            return CommandResult.ok("No active runs")

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

        # Вывод статуса
        phases = state.get("phases", [])
        current = state.get("current_phase")

        self.formatter.pipeline_status(phases, current)

        self.formatter.print()
        self.formatter.section("Детали")

        details = [
            {"name": "Проект", "value": state.get("project", "N/A")},
            {"name": "Запущен", "value": state.get("started_at", "N/A")},
            {"name": "Статус", "value": state.get("status", "N/A")},
            {"name": "Текущая фаза", "value": current or "N/A"},
        ]

        for d in details:
            self.formatter.print(f"  {d['name']}: {d['value']}")

        # Артефакты
        artifacts = state.get("artifacts", [])
        if artifacts:
            self.formatter.artifact_summary(artifacts)

        return CommandResult.ok(data=state)


class ListCommand(BaseCommand):
    """Команда списка проектов."""

    name = "list"
    description = "Список проектов и запусков"
    aliases = ["ls", "l"]

    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """Список проектов."""
        list_type = args.get("type", "projects")  # projects, runs, artifacts

        manager = ConfigManager(self.config.project_root)

        if list_type == "projects":
            return self._list_projects(manager)
        elif list_type == "runs":
            return self._list_runs(manager)
        elif list_type == "artifacts":
            return self._list_artifacts(args.get("project"))

        return CommandResult.error(f"Неизвестный тип списка: {list_type}")

    def _list_projects(self, manager: ConfigManager) -> CommandResult:
        """Список проектов."""
        projects = manager.list_projects()

        self.formatter.header("Зарегистрированные проекты")
        self.formatter.print()

        if not projects:
            self.formatter.info("Нет зарегистрированных проектов")
            self.formatter.print()
            self.formatter.print("Используйте 'pipeline config add-project' для добавления проекта")
            return CommandResult.ok("No projects", data=[])

        columns = [
            TableColumn("Имя", "name"),
            TableColumn("Тип", "config_type"),
            TableColumn("Путь", "path"),
            TableColumn("Запусков", "total_runs", align="right"),
        ]

        data = [
            {
                "name": name,
                "config_type": proj.config_type,
                "path": str(proj.path),
                "total_runs": proj.total_runs,
            }
            for name, proj in projects.items()
        ]

        self.formatter.table(data, columns)

        return CommandResult.ok(data=data)

    def _list_runs(self, manager: ConfigManager) -> CommandResult:
        """Список запусков."""
        runs_dir = self.config.get_absolute_path(self.config.artifacts_dir / "runs")

        self.formatter.header("История запусков")
        self.formatter.print()

        if not runs_dir.exists():
            self.formatter.info("Нет истории запусков")
            return CommandResult.ok("No runs", data=[])

        runs = []
        for run_file in sorted(runs_dir.glob("*.json"), reverse=True)[:20]:
            with open(run_file, "r", encoding="utf-8") as f:
                run_data = json.load(f)
                runs.append({
                    "id": run_file.stem,
                    "project": run_data.get("project", "N/A"),
                    "status": run_data.get("status", "N/A"),
                    "started": run_data.get("started_at", "N/A"),
                    "duration": run_data.get("duration", "N/A"),
                })

        if not runs:
            self.formatter.info("Нет истории запусков")
            return CommandResult.ok("No runs", data=[])

        columns = [
            TableColumn("ID", "id"),
            TableColumn("Проект", "project"),
            TableColumn("Статус", "status"),
            TableColumn("Запущен", "started"),
            TableColumn("Время", "duration", align="right"),
        ]

        self.formatter.table(runs, columns)

        return CommandResult.ok(data=runs)

    def _list_artifacts(self, project: Optional[str]) -> CommandResult:
        """Список артефактов."""
        artifacts_dir = self.config.get_absolute_path(self.config.artifacts_dir)

        self.formatter.header("Артефакты")
        self.formatter.print()

        if not artifacts_dir.exists():
            self.formatter.info("Нет артефактов")
            return CommandResult.ok("No artifacts", data=[])

        artifacts = []
        for artifact_file in artifacts_dir.rglob("*.md"):
            stat = artifact_file.stat()
            artifacts.append({
                "name": artifact_file.name,
                "type": artifact_file.parent.name,
                "size": f"{stat.st_size / 1024:.1f} KB",
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })

        if not artifacts:
            self.formatter.info("Нет артефактов")
            return CommandResult.ok("No artifacts", data=[])

        columns = [
            TableColumn("Имя", "name"),
            TableColumn("Тип", "type"),
            TableColumn("Размер", "size", align="right"),
            TableColumn("Изменён", "modified"),
        ]

        self.formatter.table(artifacts, columns)

        return CommandResult.ok(data=artifacts)


class ConfigCommand(BaseCommand):
    """Команда управления конфигурацией."""

    name = "config"
    description = "Управление конфигурацией"
    aliases = ["cfg", "c"]

    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """Управление конфигурацией."""
        action = args.get("action", "show")

        if action == "show":
            return self._show_config()
        elif action == "set":
            return self._set_config(args.get("key"), args.get("value"))
        elif action == "add-project":
            return self._add_project(args)
        elif action == "remove-project":
            return self._remove_project(args.get("name"))
        elif action == "init":
            return self._init_config()

        return CommandResult.error(f"Неизвестное действие: {action}")

    def _show_config(self) -> CommandResult:
        """Показ конфигурации."""
        self.formatter.header("Конфигурация Pipeline")
        self.formatter.print()

        config_data = self.config.to_dict()

        self.formatter.tree(config_data)

        return CommandResult.ok(data=config_data)

    def _set_config(self, key: Optional[str], value: Optional[str]) -> CommandResult:
        """Установка значения конфигурации."""
        if not key:
            return CommandResult.error("Не указан ключ конфигурации")

        manager = ConfigManager(self.config.project_root)

        # Проверка валидности ключа
        valid_keys = [
            "default_project", "max_parallel_tasks", "timeout_seconds",
            "auto_commit", "output_format", "verbosity", "color_enabled"
        ]

        if key not in valid_keys:
            return CommandResult.error(
                f"Неизвестный ключ: {key}. Доступные: {', '.join(valid_keys)}"
            )

        # Преобразование типов
        if key in ("max_parallel_tasks", "timeout_seconds", "verbosity"):
            value = int(value)
        elif key in ("auto_commit", "color_enabled"):
            value = value.lower() in ("true", "1", "yes")

        # Обновление
        setattr(self.config, key, value)
        manager.save_cli_config(self.config)

        self.formatter.success(f"Установлено: {key} = {value}")

        return CommandResult.ok(f"Config updated: {key} = {value}")

    def _add_project(self, args: Dict[str, Any]) -> CommandResult:
        """Добавление проекта."""
        name = args.get("name")
        path = args.get("path")
        config_type = args.get("config_type", "configuration")

        if not name:
            return CommandResult.error("Не указано имя проекта (--name)")
        if not path:
            return CommandResult.error("Не указан путь к проекту (--path)")

        path = Path(path)
        if not path.exists():
            return CommandResult.error(f"Путь не существует: {path}")

        manager = ConfigManager(self.config.project_root)

        project = ProjectConfig(
            name=name,
            path=path,
            config_type=config_type,
            created_at=datetime.now().isoformat(),
        )

        manager.register_project(project)

        self.formatter.success(f"Проект '{name}' добавлен")

        return CommandResult.ok(f"Project '{name}' added", data=project.to_dict())

    def _remove_project(self, name: Optional[str]) -> CommandResult:
        """Удаление проекта."""
        if not name:
            return CommandResult.error("Не указано имя проекта")

        manager = ConfigManager(self.config.project_root)

        if manager.remove_project(name):
            self.formatter.success(f"Проект '{name}' удалён")
            return CommandResult.ok(f"Project '{name}' removed")
        else:
            return CommandResult.error(f"Проект '{name}' не найден")

    def _init_config(self) -> CommandResult:
        """Инициализация конфигурации."""
        manager = ConfigManager(self.config.project_root)

        # Создание директорий
        self.config.ensure_dirs()

        # Сохранение дефолтной конфигурации
        manager.save_cli_config(self.config)

        self.formatter.success("Конфигурация инициализирована")
        self.formatter.info(f"Файл конфигурации: {self.config.config_file}")
        self.formatter.info(f"Директория артефактов: {self.config.artifacts_dir}")
        self.formatter.info(f"Директория логов: {self.config.logs_dir}")

        return CommandResult.ok("Config initialized")


class LogsCommand(BaseCommand):
    """Команда просмотра логов."""

    name = "logs"
    description = "Просмотр логов pipeline"
    aliases = ["log"]

    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """Просмотр логов."""
        run_id = args.get("run_id")
        follow = args.get("follow", False)
        lines = args.get("lines", 50)
        level = args.get("level", "all")

        logs_dir = self.config.get_absolute_path(self.config.logs_dir)

        self.formatter.header("Pipeline Logs")
        self.formatter.print()

        if run_id:
            log_file = logs_dir / f"{run_id}.log"
        else:
            # Последний лог
            log_files = sorted(logs_dir.glob("*.log"), reverse=True)
            if not log_files:
                self.formatter.info("Нет файлов логов")
                return CommandResult.ok("No logs")
            log_file = log_files[0]

        if not log_file.exists():
            return CommandResult.error(f"Файл логов не найден: {log_file}")

        self.formatter.info(f"Файл: {log_file.name}")
        self.formatter.print()

        # Чтение логов
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # Фильтрация по уровню
        if level != "all":
            all_lines = [
                line for line in all_lines
                if level.upper() in line
            ]

        # Последние N строк
        display_lines = all_lines[-lines:]

        for line in display_lines:
            line = line.rstrip()

            # Подсветка уровней
            if "ERROR" in line:
                self.formatter.error(line)
            elif "WARNING" in line:
                self.formatter.warning(line)
            elif "INFO" in line:
                self.formatter.info(line)
            else:
                self.formatter.print(line)

        return CommandResult.ok(data={"lines": len(display_lines), "file": str(log_file)})


# Реестр команд
COMMANDS: Dict[str, type] = {
    "run": RunCommand,
    "status": StatusCommand,
    "list": ListCommand,
    "config": ConfigCommand,
    "logs": LogsCommand,
}


def get_command(name: str) -> Optional[type]:
    """Получение класса команды по имени или алиасу."""
    # Прямое совпадение
    if name in COMMANDS:
        return COMMANDS[name]

    # Поиск по алиасам
    for cmd_class in COMMANDS.values():
        if name in cmd_class.aliases:
            return cmd_class

    return None
