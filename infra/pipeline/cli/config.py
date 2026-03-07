"""
CLI Configuration - конфигурация командной строки.

Управление настройками CLI, путями, форматами вывода.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
import json
import os


class OutputFormat(Enum):
    """Формат вывода CLI."""

    TEXT = "text"       # Человекочитаемый текст
    JSON = "json"       # JSON для автоматизации
    MARKDOWN = "markdown"  # Markdown для документации
    TABLE = "table"     # Табличный формат


class VerbosityLevel(Enum):
    """Уровень детализации вывода."""

    QUIET = 0      # Только ошибки
    NORMAL = 1     # Стандартный вывод
    VERBOSE = 2    # Подробный вывод
    DEBUG = 3      # Отладочный вывод


@dataclass
class CLIConfig:
    """Конфигурация CLI."""

    # Пути
    project_root: Path = field(default_factory=lambda: Path.cwd())
    artifacts_dir: Path = field(default_factory=lambda: Path("artifacts"))
    logs_dir: Path = field(default_factory=lambda: Path("logs"))
    config_file: Path = field(default_factory=lambda: Path(".pipeline/config.json"))

    # Вывод
    output_format: OutputFormat = OutputFormat.TEXT
    verbosity: VerbosityLevel = VerbosityLevel.NORMAL
    color_enabled: bool = True
    unicode_enabled: bool = True

    # Pipeline настройки
    default_project: Optional[str] = None
    max_parallel_tasks: int = 4
    timeout_seconds: int = 3600  # 1 час
    auto_commit: bool = False

    # Агенты
    enabled_agents: list = field(default_factory=lambda: [
        "initializer", "pm-spec", "architect", "implementer", "qa", "reviewer"
    ])

    # Интеграции
    memory_backend: str = "unified-memory"
    observability_enabled: bool = True

    def __post_init__(self):
        """Конвертация путей."""
        if isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)
        if isinstance(self.artifacts_dir, str):
            self.artifacts_dir = Path(self.artifacts_dir)
        if isinstance(self.logs_dir, str):
            self.logs_dir = Path(self.logs_dir)
        if isinstance(self.config_file, str):
            self.config_file = Path(self.config_file)
        if isinstance(self.output_format, str):
            self.output_format = OutputFormat(self.output_format)
        if isinstance(self.verbosity, int):
            self.verbosity = VerbosityLevel(self.verbosity)

    @classmethod
    def from_file(cls, path: Path) -> "CLIConfig":
        """Загрузка конфигурации из файла."""
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(**data)

    @classmethod
    def from_env(cls) -> "CLIConfig":
        """Загрузка конфигурации из переменных окружения."""
        config = cls()

        # Пути
        if root := os.environ.get("PIPELINE_PROJECT_ROOT"):
            config.project_root = Path(root)
        if artifacts := os.environ.get("PIPELINE_ARTIFACTS_DIR"):
            config.artifacts_dir = Path(artifacts)
        if logs := os.environ.get("PIPELINE_LOGS_DIR"):
            config.logs_dir = Path(logs)

        # Вывод
        if fmt := os.environ.get("PIPELINE_OUTPUT_FORMAT"):
            config.output_format = OutputFormat(fmt)
        if verbosity := os.environ.get("PIPELINE_VERBOSITY"):
            config.verbosity = VerbosityLevel(int(verbosity))
        if color := os.environ.get("PIPELINE_COLOR"):
            config.color_enabled = color.lower() in ("true", "1", "yes")

        # Pipeline
        if project := os.environ.get("PIPELINE_DEFAULT_PROJECT"):
            config.default_project = project
        if parallel := os.environ.get("PIPELINE_MAX_PARALLEL"):
            config.max_parallel_tasks = int(parallel)
        if timeout := os.environ.get("PIPELINE_TIMEOUT"):
            config.timeout_seconds = int(timeout)

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "project_root": str(self.project_root),
            "artifacts_dir": str(self.artifacts_dir),
            "logs_dir": str(self.logs_dir),
            "config_file": str(self.config_file),
            "output_format": self.output_format.value,
            "verbosity": self.verbosity.value,
            "color_enabled": self.color_enabled,
            "unicode_enabled": self.unicode_enabled,
            "default_project": self.default_project,
            "max_parallel_tasks": self.max_parallel_tasks,
            "timeout_seconds": self.timeout_seconds,
            "auto_commit": self.auto_commit,
            "enabled_agents": self.enabled_agents,
            "memory_backend": self.memory_backend,
            "observability_enabled": self.observability_enabled,
        }

    def save(self, path: Optional[Path] = None) -> None:
        """Сохранение конфигурации в файл."""
        path = path or self.config_file
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def merge(self, other: "CLIConfig") -> "CLIConfig":
        """Слияние с другой конфигурацией (other имеет приоритет для non-default values)."""
        # Get default values for comparison
        defaults = CLIConfig()
        defaults_dict = defaults.to_dict()

        data = self.to_dict()
        other_data = other.to_dict()

        for key, value in other_data.items():
            # Only override if other has a non-default value
            if value is not None and value != defaults_dict.get(key):
                data[key] = value

        return CLIConfig(**data)

    def get_absolute_path(self, relative: Path) -> Path:
        """Получение абсолютного пути относительно project_root."""
        if relative.is_absolute():
            return relative
        return self.project_root / relative

    def ensure_dirs(self) -> None:
        """Создание необходимых директорий."""
        self.get_absolute_path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)
        self.get_absolute_path(self.logs_dir).mkdir(parents=True, exist_ok=True)


@dataclass
class ProjectConfig:
    """Конфигурация проекта 1С."""

    name: str
    path: Path
    config_type: str = "configuration"  # configuration, extension, data_processor
    description: str = ""

    # Настройки pipeline
    enabled_phases: list = field(default_factory=lambda: [
        "init", "spec", "design", "implement", "test", "review"
    ])

    # Метаданные
    created_at: Optional[str] = None
    last_run: Optional[str] = None
    total_runs: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        """Создание из словаря."""
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "name": self.name,
            "path": str(self.path),
            "config_type": self.config_type,
            "description": self.description,
            "enabled_phases": self.enabled_phases,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "total_runs": self.total_runs,
        }


class ConfigManager:
    """Менеджер конфигураций."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.config_dir = base_path / ".pipeline"
        self._cli_config: Optional[CLIConfig] = None
        self._projects: Dict[str, ProjectConfig] = {}

    @property
    def cli_config(self) -> CLIConfig:
        """Получение CLI конфигурации с ленивой загрузкой."""
        if self._cli_config is None:
            self._cli_config = self._load_cli_config()
        return self._cli_config

    def _load_cli_config(self) -> CLIConfig:
        """Загрузка CLI конфигурации."""
        # Приоритет: env -> file -> defaults
        file_config = CLIConfig.from_file(self.config_dir / "config.json")
        env_config = CLIConfig.from_env()
        return file_config.merge(env_config)

    def save_cli_config(self, config: Optional[CLIConfig] = None) -> None:
        """Сохранение CLI конфигурации."""
        config = config or self._cli_config
        if config:
            config.save(self.config_dir / "config.json")

    def list_projects(self) -> Dict[str, ProjectConfig]:
        """Список зарегистрированных проектов."""
        projects_file = self.config_dir / "projects.json"

        if not projects_file.exists():
            return {}

        with open(projects_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            name: ProjectConfig.from_dict(proj)
            for name, proj in data.items()
        }

    def get_project(self, name: str) -> Optional[ProjectConfig]:
        """Получение проекта по имени."""
        projects = self.list_projects()
        return projects.get(name)

    def register_project(self, config: ProjectConfig) -> None:
        """Регистрация проекта."""
        projects = self.list_projects()
        projects[config.name] = config

        projects_file = self.config_dir / "projects.json"
        projects_file.parent.mkdir(parents=True, exist_ok=True)

        with open(projects_file, "w", encoding="utf-8") as f:
            json.dump(
                {name: proj.to_dict() for name, proj in projects.items()},
                f,
                indent=2,
                ensure_ascii=False
            )

    def remove_project(self, name: str) -> bool:
        """Удаление проекта."""
        projects = self.list_projects()

        if name not in projects:
            return False

        del projects[name]

        projects_file = self.config_dir / "projects.json"
        with open(projects_file, "w", encoding="utf-8") as f:
            json.dump(
                {name: proj.to_dict() for name, proj in projects.items()},
                f,
                indent=2,
                ensure_ascii=False
            )

        return True
