"""
Models for INITIALIZER Agent.

Defines data structures for codebase scanning, context generation,
and file selection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Any


class FileType(Enum):
    """Types of files in 1C project."""

    BSL = "bsl"
    XML = "xml"
    JSON = "json"
    MDO = "mdo"  # Metadata Object
    FORM = "form"
    TEMPLATE = "template"
    RIGHTS = "rights"
    OTHER = "other"

    @classmethod
    def from_extension(cls, ext: str) -> "FileType":
        """Get file type from extension."""
        ext = ext.lower().lstrip(".")
        mapping = {
            "bsl": cls.BSL,
            "xml": cls.XML,
            "json": cls.JSON,
            "mdo": cls.MDO,
        }
        return mapping.get(ext, cls.OTHER)


class ProjectType(Enum):
    """Types of 1C projects."""

    CONFIGURATION = "configuration"      # Full 1C configuration
    EXTENSION = "extension"              # Configuration extension (cfe)
    EXTERNAL_DATAPROCESSOR = "external_dataprocessor"  # External processing (epf)
    EXTERNAL_REPORT = "external_report"  # External report (erf)
    SUBSYSTEM = "subsystem"              # Part of configuration
    UNKNOWN = "unknown"

    @property
    def ru_name(self) -> str:
        """Russian name of project type."""
        names = {
            self.CONFIGURATION: "Конфигурация",
            self.EXTENSION: "Расширение",
            self.EXTERNAL_DATAPROCESSOR: "Внешняя обработка",
            self.EXTERNAL_REPORT: "Внешний отчёт",
            self.SUBSYSTEM: "Подсистема",
            self.UNKNOWN: "Неизвестный",
        }
        return names.get(self, "Неизвестный")


class ObjectType(Enum):
    """Types of 1C metadata objects."""

    CATALOG = "Catalog"                     # Справочник
    DOCUMENT = "Document"                   # Документ
    ACCUMULATION_REGISTER = "AccumulationRegister"  # Регистр накопления
    INFORMATION_REGISTER = "InformationRegister"    # Регистр сведений
    CALCULATION_REGISTER = "CalculationRegister"    # Регистр расчёта
    ACCOUNTING_REGISTER = "AccountingRegister"      # Регистр бухгалтерии
    COMMON_MODULE = "CommonModule"          # Общий модуль
    DATA_PROCESSOR = "DataProcessor"        # Обработка
    REPORT = "Report"                       # Отчёт
    ENUM = "Enum"                           # Перечисление
    CONSTANT = "Constant"                   # Константа
    CHART_OF_ACCOUNTS = "ChartOfAccounts"   # План счетов
    CHART_OF_CCS = "ChartOfCharacteristicTypes"  # План видов характеристик
    SEQUENCE = "Sequence"                   # Последовательность
    SCHEDULED_JOB = "ScheduledJob"          # Регламентное задание
    WEB_SERVICE = "WebService"              # Веб-сервис
    HTTP_SERVICE = "HTTPService"            # HTTP-сервис
    EXCHANGE_PLAN = "ExchangePlan"          # План обмена
    FILTER_CRITERION = "FilterCriterion"    # Критерий отбора
    ROLE = "Role"                           # Роль
    SUBSYSTEM = "Subsystem"                 # Подсистема
    STYLE = "Style"                         # Стиль
    LANGUAGE = "Language"                   # Язык
    INTERFACE = "Interface"                 # Интерфейс
    FORM = "Form"                           # Форма
    COMMAND = "Command"                     # Команда
    FUNCTIONAL_OPTION = "FunctionalOption"  # Функциональная опция
    DEFINED_TYPE = "DefinedType"            # Определяемый тип
    OTHER = "Other"                         # Другое

    @property
    def ru_name(self) -> str:
        """Russian name of object type (singular)."""
        names = {
            self.CATALOG: "Справочник",
            self.DOCUMENT: "Документ",
            self.ACCUMULATION_REGISTER: "Регистр накопления",
            self.INFORMATION_REGISTER: "Регистр сведений",
            self.CALCULATION_REGISTER: "Регистр расчёта",
            self.ACCOUNTING_REGISTER: "Регистр бухгалтерии",
            self.COMMON_MODULE: "Общий модуль",
            self.DATA_PROCESSOR: "Обработка",
            self.REPORT: "Отчёт",
            self.ENUM: "Перечисление",
            self.CONSTANT: "Константа",
            self.CHART_OF_ACCOUNTS: "План счетов",
            self.CHART_OF_CCS: "План видов характеристик",
            self.SEQUENCE: "Последовательность",
            self.SCHEDULED_JOB: "Регламентное задание",
            self.WEB_SERVICE: "Веб-сервис",
            self.HTTP_SERVICE: "HTTP-сервис",
            self.EXCHANGE_PLAN: "План обмена",
            self.FILTER_CRITERION: "Критерий отбора",
            self.ROLE: "Роль",
            self.SUBSYSTEM: "Подсистема",
            self.STYLE: "Стиль",
            self.LANGUAGE: "Язык",
            self.INTERFACE: "Интерфейс",
            self.FORM: "Форма",
            self.COMMAND: "Команда",
            self.FUNCTIONAL_OPTION: "Функциональная опция",
            self.DEFINED_TYPE: "Определяемый тип",
            self.OTHER: "Другое",
        }
        return names.get(self, "Другое")

    @property
    def ru_name_plural(self) -> str:
        """Russian name of object type (plural)."""
        names = {
            self.CATALOG: "Справочники",
            self.DOCUMENT: "Документы",
            self.ACCUMULATION_REGISTER: "Регистры накопления",
            self.INFORMATION_REGISTER: "Регистры сведений",
            self.CALCULATION_REGISTER: "Регистры расчёта",
            self.ACCOUNTING_REGISTER: "Регистры бухгалтерии",
            self.COMMON_MODULE: "Общие модули",
            self.DATA_PROCESSOR: "Обработки",
            self.REPORT: "Отчёты",
            self.ENUM: "Перечисления",
            self.CONSTANT: "Константы",
            self.CHART_OF_ACCOUNTS: "Планы счетов",
            self.CHART_OF_CCS: "Планы видов характеристик",
            self.SEQUENCE: "Последовательности",
            self.SCHEDULED_JOB: "Регламентные задания",
            self.WEB_SERVICE: "Веб-сервисы",
            self.HTTP_SERVICE: "HTTP-сервисы",
            self.EXCHANGE_PLAN: "Планы обмена",
            self.FILTER_CRITERION: "Критерии отбора",
            self.ROLE: "Роли",
            self.SUBSYSTEM: "Подсистемы",
            self.STYLE: "Стили",
            self.LANGUAGE: "Языки",
            self.INTERFACE: "Интерфейсы",
            self.FORM: "Формы",
            self.COMMAND: "Команды",
            self.FUNCTIONAL_OPTION: "Функциональные опции",
            self.DEFINED_TYPE: "Определяемые типы",
            self.OTHER: "Другие",
        }
        return names.get(self, "Другие")

    @classmethod
    def from_directory(cls, dir_name: str) -> "ObjectType":
        """Detect object type from directory name."""
        mapping = {
            "Catalogs": cls.CATALOG,
            "Documents": cls.DOCUMENT,
            "AccumulationRegisters": cls.ACCUMULATION_REGISTER,
            "InformationRegisters": cls.INFORMATION_REGISTER,
            "CalculationRegisters": cls.CALCULATION_REGISTER,
            "AccountingRegisters": cls.ACCOUNTING_REGISTER,
            "CommonModules": cls.COMMON_MODULE,
            "DataProcessors": cls.DATA_PROCESSOR,
            "Reports": cls.REPORT,
            "Enums": cls.ENUM,
            "Constants": cls.CONSTANT,
            "ChartsOfAccounts": cls.CHART_OF_ACCOUNTS,
            "ChartsOfCharacteristicTypes": cls.CHART_OF_CCS,
            "Sequences": cls.SEQUENCE,
            "ScheduledJobs": cls.SCHEDULED_JOB,
            "WebServices": cls.WEB_SERVICE,
            "HTTPServices": cls.HTTP_SERVICE,
            "ExchangePlans": cls.EXCHANGE_PLAN,
            "FilterCriteria": cls.FILTER_CRITERION,
            "Roles": cls.ROLE,
            "Subsystems": cls.SUBSYSTEM,
            "Styles": cls.STYLE,
            "Languages": cls.LANGUAGE,
            "Interfaces": cls.INTERFACE,
            "FunctionalOptions": cls.FUNCTIONAL_OPTION,
            "DefinedTypes": cls.DEFINED_TYPE,
        }
        return mapping.get(dir_name, cls.OTHER)


@dataclass
class FileInfo:
    """Information about a single file."""

    path: Path
    name: str
    file_type: FileType
    size_bytes: int = 0
    line_count: int = 0
    last_modified: Optional[datetime] = None
    encoding: str = "utf-8"

    @property
    def extension(self) -> str:
        """Get file extension."""
        return self.path.suffix.lower()

    @property
    def is_bsl(self) -> bool:
        """Check if file is BSL."""
        return self.file_type == FileType.BSL

    @property
    def is_metadata(self) -> bool:
        """Check if file is metadata (XML or MDO)."""
        return self.file_type in (FileType.XML, FileType.MDO)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "path": str(self.path),
            "name": self.name,
            "file_type": self.file_type.value,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
        }


@dataclass
class DirectoryInfo:
    """Information about a directory."""

    path: Path
    name: str
    object_type: Optional[ObjectType] = None
    files: list[FileInfo] = field(default_factory=list)
    subdirectories: list["DirectoryInfo"] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        """Total file count including subdirectories."""
        count = len(self.files)
        for subdir in self.subdirectories:
            count += subdir.file_count
        return count

    @property
    def bsl_files(self) -> list[FileInfo]:
        """Get all BSL files."""
        return [f for f in self.files if f.is_bsl]

    @property
    def bsl_count(self) -> int:
        """Count BSL files including subdirectories."""
        count = len(self.bsl_files)
        for subdir in self.subdirectories:
            count += subdir.bsl_count
        return count

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "path": str(self.path),
            "name": self.name,
            "object_type": self.object_type.value if self.object_type else None,
            "file_count": self.file_count,
            "bsl_count": self.bsl_count,
        }


@dataclass
class ModuleInfo:
    """Information about a 1C module/object."""

    name: str
    object_type: ObjectType
    path: Path
    files: list[FileInfo] = field(default_factory=list)
    exports_count: int = 0
    description: str = ""

    @property
    def bsl_files(self) -> list[FileInfo]:
        """Get BSL files of the module."""
        return [f for f in self.files if f.is_bsl]

    @property
    def total_lines(self) -> int:
        """Total line count in BSL files."""
        return sum(f.line_count for f in self.bsl_files)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "object_type": self.object_type.value,
            "object_type_ru": self.object_type.ru_name,
            "path": str(self.path),
            "files_count": len(self.files),
            "bsl_count": len(self.bsl_files),
            "exports_count": self.exports_count,
            "total_lines": self.total_lines,
            "description": self.description,
        }


@dataclass
class DependencyInfo:
    """Information about dependency between modules."""

    source: str          # Module that depends on target
    target: str          # Module being depended on
    dependency_type: str  # "uses", "extends", "implements", etc.
    references: list[str] = field(default_factory=list)  # Specific references

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "type": self.dependency_type,
            "references_count": len(self.references),
        }


@dataclass
class PatternInfo:
    """Information about coding patterns in project."""

    name: str                    # Pattern name
    description: str             # Pattern description
    examples: list[str] = field(default_factory=list)
    occurrences: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "examples": self.examples[:3],  # First 3 examples
            "occurrences": self.occurrences,
        }


@dataclass
class ProjectStructure:
    """Complete project structure."""

    root_path: Path
    project_type: ProjectType
    name: str = ""
    directories: list[DirectoryInfo] = field(default_factory=list)
    modules: list[ModuleInfo] = field(default_factory=list)
    dependencies: list[DependencyInfo] = field(default_factory=list)
    patterns: list[PatternInfo] = field(default_factory=list)
    scanned_at: datetime = field(default_factory=datetime.now)

    @property
    def total_files(self) -> int:
        """Total file count."""
        # Count from directories and modules
        dir_files = sum(d.file_count for d in self.directories)
        module_files = sum(len(m.files) for m in self.modules)
        return dir_files + module_files

    @property
    def total_bsl_files(self) -> int:
        """Total BSL file count."""
        dir_bsl = sum(d.bsl_count for d in self.directories)
        module_bsl = sum(len(m.bsl_files) for m in self.modules)
        return dir_bsl + module_bsl

    @property
    def total_modules(self) -> int:
        """Total module count."""
        return len(self.modules)

    def get_modules_by_type(self, obj_type: ObjectType) -> list[ModuleInfo]:
        """Get modules by object type."""
        return [m for m in self.modules if m.object_type == obj_type]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "root_path": str(self.root_path),
            "project_type": self.project_type.value,
            "project_type_ru": self.project_type.ru_name,
            "name": self.name,
            "total_files": self.total_files,
            "total_bsl_files": self.total_bsl_files,
            "total_modules": self.total_modules,
            "scanned_at": self.scanned_at.isoformat(),
        }


@dataclass
class RelevantFile:
    """File with relevance score for a task."""

    file_info: FileInfo
    relevance_score: float  # 0.0 - 1.0
    relevance_reason: str
    module_name: Optional[str] = None

    @property
    def relevance_category(self) -> str:
        """Get relevance category from score."""
        if self.relevance_score >= 0.7:
            return "high"
        elif self.relevance_score >= 0.4:
            return "medium"
        else:
            return "low"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "path": str(self.file_info.path),
            "name": self.file_info.name,
            "score": round(self.relevance_score, 2),
            "reason": self.relevance_reason,
            "module": self.module_name,
        }


@dataclass
class ContextReport:
    """Generated context report."""

    project_id: str
    project_structure: ProjectStructure
    task_description: str
    relevant_files: list[RelevantFile] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    markdown_content: str = ""

    @property
    def high_relevance_files(self) -> list[RelevantFile]:
        """Files with high relevance (> 0.8)."""
        return [f for f in self.relevant_files if f.relevance_score > 0.8]

    @property
    def medium_relevance_files(self) -> list[RelevantFile]:
        """Files with medium relevance (0.5 - 0.8)."""
        return [
            f for f in self.relevant_files
            if 0.5 <= f.relevance_score <= 0.8
        ]

    @property
    def low_relevance_files(self) -> list[RelevantFile]:
        """Files with low relevance (< 0.5)."""
        return [f for f in self.relevant_files if f.relevance_score < 0.5]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "task_description": self.task_description,
            "total_files": self.project_structure.total_files,
            "relevant_files_count": len(self.relevant_files),
            "high_relevance": len(self.high_relevance_files),
            "medium_relevance": len(self.medium_relevance_files),
            "low_relevance": len(self.low_relevance_files),
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class InitializerConfig:
    """Configuration for INITIALIZER agent."""

    max_files: int = 10000          # Maximum files to scan
    max_depth: int = 10             # Maximum directory depth
    scan_timeout: int = 60          # Scan timeout in seconds
    cache_ttl: int = 3600           # Cache TTL in seconds
    max_relevant_files: int = 20    # Maximum relevant files to return
    min_relevance_score: float = 0.3  # Minimum relevance score
    include_patterns: list[str] = field(default_factory=lambda: ["*.bsl", "*.xml"])
    exclude_patterns: list[str] = field(default_factory=lambda: ["*.log", "*.tmp"])

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "max_files": self.max_files,
            "max_depth": self.max_depth,
            "scan_timeout": self.scan_timeout,
            "cache_ttl": self.cache_ttl,
            "max_relevant_files": self.max_relevant_files,
            "min_relevance_score": self.min_relevance_score,
        }


@dataclass
class InitializerInput:
    """Input for INITIALIZER agent."""

    project_id: str
    project_path: str
    task_description: str
    force_rescan: bool = False
    output_dir: Optional[str] = None  # Directory for context.md output
    config: InitializerConfig = field(default_factory=InitializerConfig)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "project_path": self.project_path,
            "task_description": self.task_description,
            "force_rescan": self.force_rescan,
            "output_dir": self.output_dir,
            "config": self.config.to_dict(),
        }


@dataclass
class InitializerOutput:
    """Output from INITIALIZER agent."""

    success: bool
    context_report: Optional[ContextReport] = None
    context_file_path: Optional[str] = None
    error_message: Optional[str] = None
    scan_duration_ms: int = 0
    cached: bool = False
    # Additional fields used by agent.run_from_input
    context_markdown: str = ""
    relevant_files: List[Any] = field(default_factory=list)
    project_structure: Optional[Any] = None
    cache_hit: bool = False
    processing_time_ms: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "context_file_path": self.context_file_path,
            "error_message": self.error_message,
            "scan_duration_ms": self.scan_duration_ms,
            "cached": self.cached,
            "cache_hit": self.cache_hit,
            "processing_time_ms": self.processing_time_ms,
            "report_summary": self.context_report.to_dict() if self.context_report else None,
        }
