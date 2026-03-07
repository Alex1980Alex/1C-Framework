"""
Codebase Scanner for INITIALIZER Agent.

Scans 1C project directory structure and collects file information.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.initializer.models import (
    FileType,
    ProjectType,
    ObjectType,
    FileInfo,
    DirectoryInfo,
    ModuleInfo,
    PatternInfo,
    ProjectStructure,
    InitializerConfig,
)


class CodebaseScanner:
    """
    Scans 1C project codebase and builds structure.

    Features:
    - Recursive directory scanning
    - File type detection
    - 1C object type recognition
    - Module extraction
    - Pattern detection
    """

    # Standard 1C object directories
    OBJECT_DIRECTORIES = {
        "Catalogs",
        "Documents",
        "AccumulationRegisters",
        "InformationRegisters",
        "CalculationRegisters",
        "AccountingRegisters",
        "CommonModules",
        "DataProcessors",
        "Reports",
        "Enums",
        "Constants",
        "ChartsOfAccounts",
        "ChartsOfCharacteristicTypes",
        "Sequences",
        "ScheduledJobs",
        "WebServices",
        "HTTPServices",
        "ExchangePlans",
        "FilterCriteria",
        "Roles",
        "Subsystems",
        "Styles",
        "Languages",
        "Interfaces",
        "FunctionalOptions",
        "DefinedTypes",
        "CommonForms",
        "CommonCommands",
        "CommonTemplates",
        "CommonPictures",
        "SessionParameters",
        "XDTOPackages",
    }

    # Files/directories to skip
    # NOTE: Do NOT skip 1C system directories like "Ext", "Manager" - they contain module code!
    SKIP_PATTERNS = {
        ".git",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".idea",
        ".vscode",
    }

    def __init__(self, config: Optional[InitializerConfig] = None) -> None:
        """Initialize scanner with config."""
        self.config = config or InitializerConfig()
        self._file_count = 0
        self._depth = 0

    def scan(self, root_path: str | Path) -> ProjectStructure:
        """
        Scan project directory and build structure.

        Args:
            root_path: Path to project root directory

        Returns:
            ProjectStructure with all collected information
        """
        root_path = Path(root_path)
        if not root_path.exists():
            raise FileNotFoundError(f"Project path not found: {root_path}")

        self._file_count = 0
        self._depth = 0

        # Detect project type
        project_type = self._detect_project_type(root_path)

        # Scan directory structure
        directories = self._scan_directory(root_path)

        # Extract modules
        modules = self._extract_modules(directories)

        # Detect patterns
        patterns = self._detect_patterns(modules)

        # Build structure
        structure = ProjectStructure(
            root_path=root_path,
            project_type=project_type,
            name=root_path.name,
            directories=directories,
            modules=modules,
            patterns=patterns,
            scanned_at=datetime.now(),
        )

        return structure

    def _detect_project_type(self, root_path: Path) -> ProjectType:
        """Detect type of 1C project."""
        # Check for configuration markers
        config_markers = ["Configuration.xml", "Configuration.mdo"]
        for marker in config_markers:
            if (root_path / marker).exists():
                return ProjectType.CONFIGURATION

        # Check for extension markers
        if (root_path / "Extension.xml").exists():
            return ProjectType.EXTENSION

        # Check for DataProcessor markers
        if (root_path / "DataProcessor.xml").exists():
            return ProjectType.EXTERNAL_DATAPROCESSOR

        # Check for Report markers
        if (root_path / "Report.xml").exists():
            return ProjectType.EXTERNAL_REPORT

        # Check for standard 1C directories
        for obj_dir in self.OBJECT_DIRECTORIES:
            if (root_path / obj_dir).is_dir():
                return ProjectType.CONFIGURATION

        # Check parent directories for subsystem
        parent = root_path.parent
        if parent.name == "Subsystems":
            return ProjectType.SUBSYSTEM

        return ProjectType.UNKNOWN

    def _scan_directory(
        self,
        path: Path,
        depth: int = 0
    ) -> list[DirectoryInfo]:
        """Recursively scan directory."""
        if depth > self.config.max_depth:
            return []

        if self._file_count > self.config.max_files:
            return []

        directories = []

        try:
            entries = list(path.iterdir())
        except PermissionError:
            return []

        # Separate files and directories
        files = []
        subdirs = []

        for entry in entries:
            if entry.name in self.SKIP_PATTERNS:
                continue

            if entry.is_file():
                file_info = self._get_file_info(entry)
                if file_info:
                    files.append(file_info)
                    self._file_count += 1
            elif entry.is_dir():
                subdirs.append(entry)

        # Determine object type from directory name
        object_type = None
        if path.name in self.OBJECT_DIRECTORIES:
            object_type = ObjectType.from_directory(path.name)

        # Create directory info
        dir_info = DirectoryInfo(
            path=path,
            name=path.name,
            object_type=object_type,
            files=files,
            subdirectories=[],
        )

        # Recursively scan subdirectories
        for subdir in subdirs:
            sub_dirs = self._scan_directory(subdir, depth + 1)
            dir_info.subdirectories.extend(sub_dirs)

        directories.append(dir_info)

        return directories

    def _get_file_info(self, path: Path) -> Optional[FileInfo]:
        """Get information about a file."""
        try:
            stat = path.stat()
            file_type = FileType.from_extension(path.suffix)

            # Count lines for BSL files
            line_count = 0
            if file_type == FileType.BSL:
                try:
                    with open(path, "r", encoding="utf-8-sig") as f:
                        line_count = sum(1 for _ in f)
                except (UnicodeDecodeError, IOError):
                    # Try different encoding
                    try:
                        with open(path, "r", encoding="cp1251") as f:
                            line_count = sum(1 for _ in f)
                    except Exception:
                        pass

            return FileInfo(
                path=path,
                name=path.name,
                file_type=file_type,
                size_bytes=stat.st_size,
                line_count=line_count,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
            )
        except Exception:
            return None

    def _extract_modules(
        self,
        directories: list[DirectoryInfo]
    ) -> list[ModuleInfo]:
        """Extract 1C modules from directory structure."""
        modules = []

        for dir_info in directories:
            # Check if this is an object directory
            if dir_info.object_type:
                # Each subdirectory is a module
                for subdir in dir_info.subdirectories:
                    module = self._create_module_info(subdir, dir_info.object_type)
                    if module:
                        modules.append(module)
            else:
                # Recursively check subdirectories
                for subdir in dir_info.subdirectories:
                    sub_modules = self._extract_modules([subdir])
                    modules.extend(sub_modules)

        return modules

    def _create_module_info(
        self,
        dir_info: DirectoryInfo,
        object_type: ObjectType
    ) -> Optional[ModuleInfo]:
        """Create ModuleInfo from directory."""
        # Collect all BSL files from module directory
        all_files = self._collect_all_files(dir_info)
        bsl_files = [f for f in all_files if f.is_bsl]

        if not all_files:
            return None

        # Count exports in BSL files
        exports_count = 0
        for bsl_file in bsl_files:
            exports_count += self._count_exports(bsl_file.path)

        return ModuleInfo(
            name=dir_info.name,
            object_type=object_type,
            path=dir_info.path,
            files=all_files,
            exports_count=exports_count,
        )

    def _collect_all_files(self, dir_info: DirectoryInfo) -> list[FileInfo]:
        """Collect all files from directory including subdirectories."""
        files = list(dir_info.files)
        for subdir in dir_info.subdirectories:
            files.extend(self._collect_all_files(subdir))
        return files

    def _count_exports(self, bsl_path: Path) -> int:
        """Count exported functions/procedures in BSL file."""
        try:
            with open(bsl_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            try:
                with open(bsl_path, "r", encoding="cp1251") as f:
                    content = f.read()
            except Exception:
                return 0

        # Pattern for export declarations
        pattern = r"(?:Функция|Процедура|Function|Procedure)\s+\w+\s*\([^)]*\)\s+Экспорт"
        matches = re.findall(pattern, content, re.IGNORECASE)
        return len(matches)

    def _detect_patterns(self, modules: list[ModuleInfo]) -> list[PatternInfo]:
        """Detect coding patterns in project."""
        patterns = []

        # Detect naming pattern (prefix)
        prefixes = self._detect_naming_prefix(modules)
        if prefixes:
            most_common = max(prefixes.items(), key=lambda x: x[1])
            patterns.append(PatternInfo(
                name="Naming Prefix",
                description=f"Используется префикс '{most_common[0]}' для объектов",
                examples=[m.name for m in modules if m.name.startswith(most_common[0])][:5],
                occurrences=most_common[1],
            ))

        # Detect common module usage
        common_modules = [m for m in modules if m.object_type == ObjectType.COMMON_MODULE]
        if common_modules:
            patterns.append(PatternInfo(
                name="Common Modules",
                description=f"Используется {len(common_modules)} общих модулей",
                examples=[m.name for m in common_modules][:5],
                occurrences=len(common_modules),
            ))

        # Detect register usage
        registers = [
            m for m in modules
            if m.object_type in (
                ObjectType.ACCUMULATION_REGISTER,
                ObjectType.INFORMATION_REGISTER,
            )
        ]
        if registers:
            patterns.append(PatternInfo(
                name="Registers",
                description=f"Используется {len(registers)} регистров",
                examples=[m.name for m in registers][:5],
                occurrences=len(registers),
            ))

        return patterns

    def _detect_naming_prefix(self, modules: list[ModuleInfo]) -> dict[str, int]:
        """Detect common naming prefixes."""
        prefixes: dict[str, int] = {}

        for module in modules:
            name = module.name
            # Check for prefixes like "гкс_", "ут_", "erp_"
            if "_" in name:
                prefix = name.split("_")[0] + "_"
                prefixes[prefix] = prefixes.get(prefix, 0) + 1
            # Check for CamelCase prefixes (2-4 uppercase letters)
            match = re.match(r"^([A-ZА-Я]{2,4})[a-zа-я]", name)
            if match:
                prefix = match.group(1)
                prefixes[prefix] = prefixes.get(prefix, 0) + 1

        return prefixes


# Convenience functions

def scan_directory(path: str | Path, config: Optional[InitializerConfig] = None) -> ProjectStructure:
    """Scan directory and return project structure."""
    scanner = CodebaseScanner(config)
    return scanner.scan(path)


def detect_project_type(path: str | Path) -> ProjectType:
    """Detect project type from path."""
    scanner = CodebaseScanner()
    return scanner._detect_project_type(Path(path))


def get_file_stats(structure: ProjectStructure) -> dict:
    """Get file statistics from project structure."""
    bsl_lines = sum(m.total_lines for m in structure.modules)

    stats = {
        "total_files": structure.total_files,
        "bsl_files": structure.total_bsl_files,
        "total_modules": structure.total_modules,
        "bsl_lines": bsl_lines,
        "project_type": structure.project_type.value,
        "project_type_ru": structure.project_type.ru_name,
    }

    # Count by object type
    type_counts = {}
    for module in structure.modules:
        type_name = module.object_type.ru_name
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    stats["by_type"] = type_counts

    return stats
