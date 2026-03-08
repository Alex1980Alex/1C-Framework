#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL Configuration Comparer - сравнение двух конфигураций 1С
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum
import json
from datetime import datetime

# Импорты локальных модулей
from semantic_diff_poc import BslSemanticDiffer, BslDiffResult
from metadata_analyzer import BslMetadataAnalyzer, MetadataObject
from dependency_analyzer import BslDependencyAnalyzer, DependencyGraph
from parallel_processor import BslParallelProcessor, BatchResult
from bsl_deep_analyzer import BslDeepAnalyzer, FunctionAnalysis


class ChangeType(Enum):
    """Типы изменений"""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class FileChange:
    """Изменение файла"""
    relative_path: str
    change_type: ChangeType
    old_path: Optional[Path] = None
    new_path: Optional[Path] = None
    diff_result: Optional[BslDiffResult] = None
    metadata_changes: Optional[Dict] = None


@dataclass
class ModuleChange:
    """Изменение модуля"""
    module_name: str
    module_type: str
    change_type: ChangeType
    file_changes: List[FileChange] = field(default_factory=list)
    added_functions: List[str] = field(default_factory=list)
    removed_functions: List[str] = field(default_factory=list)
    modified_functions: List[str] = field(default_factory=list)


@dataclass
class ConfigComparisonResult:
    """Результат сравнения конфигураций"""
    config1_path: Path
    config2_path: Path
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Статистика
    total_modules: int = 0
    added_modules: int = 0
    removed_modules: int = 0
    modified_modules: int = 0

    total_files: int = 0
    added_files: int = 0
    removed_files: int = 0
    modified_files: int = 0

    # Детали изменений
    module_changes: List[ModuleChange] = field(default_factory=list)
    file_changes: List[FileChange] = field(default_factory=list)

    # Зависимости
    dependency_changes: Dict = field(default_factory=dict)

    # Метаданные
    metadata_changes: Dict = field(default_factory=dict)

    # Предупреждения
    warnings: List[str] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)


class BslConfigComparer:
    """Сравнение конфигураций 1С"""

    # Типы объектов метаданных
    METADATA_TYPES = [
        'Catalogs', 'Documents', 'InformationRegisters', 'AccumulationRegisters',
        'Reports', 'DataProcessors', 'CommonModules', 'Enums',
        'ChartsOfCharacteristicTypes', 'ChartsOfAccounts', 'Tasks', 'BusinessProcesses',
        'ExchangePlans', 'Constants', 'WebServices', 'HTTPServices',
        'ScheduledJobs', 'Roles', 'CommonForms', 'CommonCommands'
    ]

    def __init__(self, max_workers: int = None):
        """
        Args:
            max_workers: Максимальное количество потоков для параллельной обработки
        """
        self.differ = BslSemanticDiffer()
        self.metadata_analyzer = BslMetadataAnalyzer()
        self.dependency_analyzer = BslDependencyAnalyzer()
        self.deep_analyzer = BslDeepAnalyzer()
        self.parallel_processor = BslParallelProcessor(max_workers)

    def compare_configurations(
        self,
        config1_path: Path,
        config2_path: Path,
        include_dependencies: bool = True,
        include_metadata: bool = True
    ) -> ConfigComparisonResult:
        """
        Полное сравнение двух конфигураций

        Args:
            config1_path: Путь к первой (старой) конфигурации
            config2_path: Путь ко второй (новой) конфигурации
            include_dependencies: Включить анализ зависимостей
            include_metadata: Включить анализ метаданных

        Returns:
            ConfigComparisonResult с полным отчётом
        """
        result = ConfigComparisonResult(
            config1_path=config1_path,
            config2_path=config2_path
        )

        # Сравнение BSL файлов
        self._compare_bsl_files(config1_path, config2_path, result)

        # Сравнение по типам метаданных
        self._compare_metadata_types(config1_path, config2_path, result)

        # Анализ зависимостей
        if include_dependencies:
            self._analyze_dependency_changes(config1_path, config2_path, result)

        # Анализ метаданных XML
        if include_metadata:
            self._compare_xml_metadata(config1_path, config2_path, result)

        # Поиск breaking changes
        self._find_breaking_changes(result)

        return result

    def _compare_bsl_files(
        self,
        config1_path: Path,
        config2_path: Path,
        result: ConfigComparisonResult
    ):
        """Сравнение BSL файлов между конфигурациями"""
        # Собираем все BSL файлы
        files1 = self._collect_bsl_files(config1_path)
        files2 = self._collect_bsl_files(config2_path)

        all_relative_paths = set(files1.keys()) | set(files2.keys())
        result.total_files = len(all_relative_paths)

        for rel_path in all_relative_paths:
            f1 = files1.get(rel_path)
            f2 = files2.get(rel_path)

            file_change = FileChange(relative_path=rel_path)

            if f1 is None:
                # Файл добавлен
                file_change.change_type = ChangeType.ADDED
                file_change.new_path = f2
                result.added_files += 1

            elif f2 is None:
                # Файл удалён
                file_change.change_type = ChangeType.REMOVED
                file_change.old_path = f1
                result.removed_files += 1

            else:
                # Файл существует в обеих конфигурациях
                file_change.old_path = f1
                file_change.new_path = f2

                # Семантическое сравнение
                try:
                    diff_result = self.differ.compare_files(f1, f2)
                    file_change.diff_result = diff_result

                    if diff_result.has_differences:
                        file_change.change_type = ChangeType.MODIFIED
                        result.modified_files += 1
                    else:
                        file_change.change_type = ChangeType.UNCHANGED
                except Exception as e:
                    file_change.change_type = ChangeType.MODIFIED
                    result.warnings.append(f"Ошибка сравнения {rel_path}: {e}")
                    result.modified_files += 1

            result.file_changes.append(file_change)

    def _collect_bsl_files(self, config_path: Path) -> Dict[str, Path]:
        """Сбор всех BSL файлов конфигурации"""
        files = {}

        # Ищем в src/ или в корне
        src_path = config_path / 'src'
        if not src_path.exists():
            src_path = config_path

        for bsl_file in src_path.rglob('*.bsl'):
            try:
                rel_path = bsl_file.relative_to(src_path)
                files[str(rel_path)] = bsl_file
            except ValueError:
                files[bsl_file.name] = bsl_file

        return files

    def _compare_metadata_types(
        self,
        config1_path: Path,
        config2_path: Path,
        result: ConfigComparisonResult
    ):
        """Сравнение по типам объектов метаданных"""
        for meta_type in self.METADATA_TYPES:
            modules1 = self._find_modules_of_type(config1_path, meta_type)
            modules2 = self._find_modules_of_type(config2_path, meta_type)

            all_modules = set(modules1.keys()) | set(modules2.keys())

            for module_name in all_modules:
                m1 = modules1.get(module_name)
                m2 = modules2.get(module_name)

                module_change = ModuleChange(
                    module_name=module_name,
                    module_type=meta_type
                )

                if m1 is None:
                    module_change.change_type = ChangeType.ADDED
                    result.added_modules += 1
                elif m2 is None:
                    module_change.change_type = ChangeType.REMOVED
                    result.removed_modules += 1
                else:
                    # Сравниваем содержимое модуля
                    has_changes = self._compare_module_content(m1, m2, module_change)
                    module_change.change_type = ChangeType.MODIFIED if has_changes else ChangeType.UNCHANGED
                    if has_changes:
                        result.modified_modules += 1

                result.module_changes.append(module_change)

        result.total_modules = len(result.module_changes)

    def _find_modules_of_type(self, config_path: Path, meta_type: str) -> Dict[str, Path]:
        """Поиск модулей определённого типа метаданных"""
        modules = {}

        src_path = config_path / 'src' / meta_type
        if not src_path.exists():
            src_path = config_path / meta_type

        if src_path.exists():
            for item in src_path.iterdir():
                if item.is_dir():
                    modules[item.name] = item

        return modules

    def _compare_module_content(
        self,
        module1_path: Path,
        module2_path: Path,
        module_change: ModuleChange
    ) -> bool:
        """Сравнение содержимого модуля"""
        has_changes = False

        # Сравниваем BSL файлы модуля
        bsl_files1 = list(module1_path.rglob('*.bsl'))
        bsl_files2 = list(module2_path.rglob('*.bsl'))

        files1_map = {f.name: f for f in bsl_files1}
        files2_map = {f.name: f for f in bsl_files2}

        all_bsl = set(files1_map.keys()) | set(files2_map.keys())

        for bsl_name in all_bsl:
            f1 = files1_map.get(bsl_name)
            f2 = files2_map.get(bsl_name)

            if f1 and f2:
                try:
                    diff = self.differ.compare_files(f1, f2)
                    if diff.has_differences:
                        has_changes = True

                        for sym in diff.added_symbols:
                            name = sym.name if hasattr(sym, 'name') else str(sym)
                            module_change.added_functions.append(name)

                        for sym in diff.removed_symbols:
                            name = sym.name if hasattr(sym, 'name') else str(sym)
                            module_change.removed_functions.append(name)

                        for sym in diff.modified_symbols:
                            name = sym.name if hasattr(sym, 'name') else str(sym)
                            module_change.modified_functions.append(name)

                except Exception:
                    has_changes = True

            elif f1 or f2:
                has_changes = True

        return has_changes

    def _analyze_dependency_changes(
        self,
        config1_path: Path,
        config2_path: Path,
        result: ConfigComparisonResult
    ):
        """Анализ изменений в зависимостях"""
        try:
            graph1 = self.dependency_analyzer.analyze_configuration_dependencies(config1_path)
            graph2 = self.dependency_analyzer.analyze_configuration_dependencies(config2_path)

            # Модули
            modules1 = set(graph1.modules.keys())
            modules2 = set(graph2.modules.keys())

            # Зависимости
            deps1 = {(d.from_module, d.to_module) for d in graph1.dependencies}
            deps2 = {(d.from_module, d.to_module) for d in graph2.dependencies}

            result.dependency_changes = {
                'added_modules': list(modules2 - modules1),
                'removed_modules': list(modules1 - modules2),
                'added_dependencies': [{'from': f, 'to': t} for f, t in deps2 - deps1],
                'removed_dependencies': [{'from': f, 'to': t} for f, t in deps1 - deps2],
                'circular_dependencies_old': self.dependency_analyzer.find_circular_dependencies(graph1),
                'circular_dependencies_new': self.dependency_analyzer.find_circular_dependencies(graph2)
            }

            # Предупреждения о новых циклических зависимостях
            old_cycles = set(tuple(c) for c in result.dependency_changes['circular_dependencies_old'])
            new_cycles = set(tuple(c) for c in result.dependency_changes['circular_dependencies_new'])

            for cycle in new_cycles - old_cycles:
                result.warnings.append(f"Новая циклическая зависимость: {' -> '.join(cycle)}")

        except Exception as e:
            result.warnings.append(f"Ошибка анализа зависимостей: {e}")

    def _compare_xml_metadata(
        self,
        config1_path: Path,
        config2_path: Path,
        result: ConfigComparisonResult
    ):
        """Сравнение XML метаданных"""
        for meta_type in ['Catalog', 'Document', 'InformationRegister', 'AccumulationRegister']:
            try:
                objects1 = self.metadata_analyzer.find_metadata_objects(config1_path, meta_type)
                objects2 = self.metadata_analyzer.find_metadata_objects(config2_path, meta_type)

                obj1_map = {o.name: o for o in objects1}
                obj2_map = {o.name: o for o in objects2}

                all_names = set(obj1_map.keys()) | set(obj2_map.keys())

                for name in all_names:
                    o1 = obj1_map.get(name)
                    o2 = obj2_map.get(name)

                    key = f"{meta_type}.{name}"

                    if o1 is None:
                        result.metadata_changes[key] = {'status': 'added'}
                    elif o2 is None:
                        result.metadata_changes[key] = {'status': 'removed'}
                    else:
                        changes = self.metadata_analyzer.compare_metadata(o1, o2)
                        if changes.get('has_changes'):
                            result.metadata_changes[key] = {
                                'status': 'modified',
                                'details': changes
                            }

            except Exception as e:
                result.warnings.append(f"Ошибка анализа метаданных {meta_type}: {e}")

    def _find_breaking_changes(self, result: ConfigComparisonResult):
        """Поиск критических изменений (breaking changes)"""
        for module_change in result.module_changes:
            # Удаление экспортных функций - breaking change
            for func in module_change.removed_functions:
                # Проверяем, была ли функция экспортной (упрощённо - по имени)
                result.breaking_changes.append(
                    f"Удалена функция {func} из модуля {module_change.module_name}"
                )

        # Удаление реквизитов из метаданных
        for key, changes in result.metadata_changes.items():
            if changes.get('status') == 'modified':
                details = changes.get('details', {})
                if details.get('attributes_removed'):
                    result.breaking_changes.append(
                        f"Удалены реквизиты из {key}: {details['attributes_removed']}"
                    )
                if details.get('dimensions_removed'):
                    result.breaking_changes.append(
                        f"Удалены измерения из {key}: {details['dimensions_removed']}"
                    )

    def compare_quick(self, config1_path: Path, config2_path: Path) -> Dict:
        """
        Быстрое сравнение (только статистика)

        Returns:
            Словарь со статистикой изменений
        """
        files1 = self._collect_bsl_files(config1_path)
        files2 = self._collect_bsl_files(config2_path)

        all_files = set(files1.keys()) | set(files2.keys())

        added = len(files2.keys() - files1.keys())
        removed = len(files1.keys() - files2.keys())

        # Быстрая проверка на изменения (по размеру файла)
        modified = 0
        for rel_path in files1.keys() & files2.keys():
            f1 = files1[rel_path]
            f2 = files2[rel_path]
            if f1.stat().st_size != f2.stat().st_size:
                modified += 1

        return {
            'total_files': len(all_files),
            'added': added,
            'removed': removed,
            'modified': modified,
            'unchanged': len(all_files) - added - removed - modified,
            'config1_files': len(files1),
            'config2_files': len(files2)
        }

    def export_to_json(self, result: ConfigComparisonResult, output_path: Path):
        """Экспорт результатов в JSON"""
        data = {
            'config1': str(result.config1_path),
            'config2': str(result.config2_path),
            'timestamp': result.timestamp,
            'statistics': {
                'total_modules': result.total_modules,
                'added_modules': result.added_modules,
                'removed_modules': result.removed_modules,
                'modified_modules': result.modified_modules,
                'total_files': result.total_files,
                'added_files': result.added_files,
                'removed_files': result.removed_files,
                'modified_files': result.modified_files
            },
            'module_changes': [
                {
                    'name': mc.module_name,
                    'type': mc.module_type,
                    'change_type': mc.change_type.value,
                    'added_functions': mc.added_functions,
                    'removed_functions': mc.removed_functions,
                    'modified_functions': mc.modified_functions
                }
                for mc in result.module_changes
                if mc.change_type != ChangeType.UNCHANGED
            ],
            'dependency_changes': result.dependency_changes,
            'metadata_changes': result.metadata_changes,
            'warnings': result.warnings,
            'breaking_changes': result.breaking_changes
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def compare_configs(
    config1_path: str,
    config2_path: str,
    output_json: str = None
) -> Dict:
    """
    Утилитная функция для сравнения конфигураций

    Args:
        config1_path: Путь к первой конфигурации
        config2_path: Путь ко второй конфигурации
        output_json: Путь для сохранения JSON отчёта

    Returns:
        Словарь с результатами сравнения
    """
    comparer = BslConfigComparer()

    result = comparer.compare_configurations(
        Path(config1_path),
        Path(config2_path)
    )

    if output_json:
        comparer.export_to_json(result, Path(output_json))

    return {
        'total_modules': result.total_modules,
        'added_modules': result.added_modules,
        'removed_modules': result.removed_modules,
        'modified_modules': result.modified_modules,
        'total_files': result.total_files,
        'added_files': result.added_files,
        'removed_files': result.removed_files,
        'modified_files': result.modified_files,
        'warnings': result.warnings,
        'breaking_changes': result.breaking_changes
    }
