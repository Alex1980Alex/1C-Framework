#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL Dependency Analyzer - анализ зависимостей между модулями BSL
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
import re
from collections import defaultdict


@dataclass
class ModuleInfo:
    """Информация о модуле BSL"""
    name: str
    module_type: str  # CommonModule, ManagerModule, ObjectModule, FormModule
    file_path: Path = None
    exported_functions: List[str] = field(default_factory=list)
    exported_procedures: List[str] = field(default_factory=list)
    line_count: int = 0


@dataclass
class Dependency:
    """Зависимость между модулями"""
    from_module: str
    to_module: str
    dependency_type: str  # 'call', 'reference', 'type'
    locations: List[int] = field(default_factory=list)  # Номера строк


@dataclass
class DependencyGraph:
    """Граф зависимостей модулей"""
    modules: Dict[str, ModuleInfo] = field(default_factory=dict)
    dependencies: List[Dependency] = field(default_factory=list)


class BslDependencyAnalyzer:
    """Анализатор зависимостей BSL модулей"""

    # Паттерны для анализа
    MODULE_CALL_PATTERN = re.compile(
        r'(\w+)\s*\.\s*(\w+)\s*\(',
        re.MULTILINE
    )

    COMMON_MODULE_PATTERN = re.compile(
        r'(Процедура|Функция|Procedure|Function)\s+(\w+)\s*\([^)]*\)\s*(Экспорт|Export)',
        re.IGNORECASE | re.MULTILINE
    )

    # Известные глобальные контексты 1С (не модули)
    GLOBAL_CONTEXTS = {
        'Справочники', 'Catalogs',
        'Документы', 'Documents',
        'РегистрыСведений', 'InformationRegisters',
        'РегистрыНакопления', 'AccumulationRegisters',
        'Обработки', 'DataProcessors',
        'Отчеты', 'Reports',
        'ПланыВидовХарактеристик', 'ChartsOfCharacteristicTypes',
        'ПланыСчетов', 'ChartsOfAccounts',
        'Перечисления', 'Enums',
        'ОбщиеМодули', 'CommonModules',
        'Константы', 'Constants',
        'Задачи', 'Tasks',
        'БизнесПроцессы', 'BusinessProcesses',
        'ПланыОбмена', 'ExchangePlans',
        'Последовательности', 'Sequences',
        'ЭтотОбъект', 'ThisObject',
        'Элементы', 'Items',
        'Объект', 'Object',
        'Запись', 'Record',
        'ТекущаяДата', 'CurrentDate',
        'ТекущееВремя', 'CurrentTime',
    }

    def analyze_configuration_dependencies(self, config_path: Path) -> DependencyGraph:
        """Анализ зависимостей всей конфигурации"""
        graph = DependencyGraph()

        # Поиск общих модулей
        common_modules_path = config_path / 'src' / 'CommonModules'
        if not common_modules_path.exists():
            common_modules_path = config_path / 'CommonModules'

        if common_modules_path.exists():
            for module_dir in common_modules_path.iterdir():
                if module_dir.is_dir():
                    module_file = module_dir / 'Module.bsl'
                    if module_file.exists():
                        module_info = self._analyze_module(module_file, 'CommonModule')
                        graph.modules[module_info.name] = module_info

        # Поиск модулей объектов
        for obj_type in ['Catalogs', 'Documents', 'DataProcessors', 'Reports',
                         'InformationRegisters', 'AccumulationRegisters']:
            obj_path = config_path / 'src' / obj_type
            if not obj_path.exists():
                obj_path = config_path / obj_type

            if obj_path.exists():
                for obj_dir in obj_path.iterdir():
                    if obj_dir.is_dir():
                        # ObjectModule
                        obj_module = obj_dir / 'Ext' / 'ObjectModule.bsl'
                        if not obj_module.exists():
                            obj_module = obj_dir / 'ObjectModule.bsl'
                        if obj_module.exists():
                            info = self._analyze_module(obj_module, 'ObjectModule')
                            info.name = f"{obj_dir.name}_ObjectModule"
                            graph.modules[info.name] = info

                        # ManagerModule
                        mgr_module = obj_dir / 'Ext' / 'ManagerModule.bsl'
                        if not mgr_module.exists():
                            mgr_module = obj_dir / 'ManagerModule.bsl'
                        if mgr_module.exists():
                            info = self._analyze_module(mgr_module, 'ManagerModule')
                            info.name = f"{obj_dir.name}_ManagerModule"
                            graph.modules[info.name] = info

        # Анализ зависимостей между модулями
        graph.dependencies = self._analyze_dependencies(graph.modules)

        return graph

    def _analyze_module(self, file_path: Path, module_type: str) -> ModuleInfo:
        """Анализ отдельного модуля"""
        content = file_path.read_text(encoding='utf-8')

        info = ModuleInfo(
            name=file_path.parent.name,
            module_type=module_type,
            file_path=file_path,
            line_count=content.count('\n') + 1
        )

        # Поиск экспортных функций и процедур
        for match in self.COMMON_MODULE_PATTERN.finditer(content):
            keyword = match.group(1).lower()
            name = match.group(2)

            if keyword in ('функция', 'function'):
                info.exported_functions.append(name)
            else:
                info.exported_procedures.append(name)

        return info

    def _analyze_dependencies(self, modules: Dict[str, ModuleInfo]) -> List[Dependency]:
        """Анализ зависимостей между модулями"""
        dependencies = []
        module_names = set(modules.keys())

        # Собираем все экспортные символы
        exports_map = {}
        for name, info in modules.items():
            for func in info.exported_functions:
                exports_map[func] = name
            for proc in info.exported_procedures:
                exports_map[proc] = name

        # Анализируем каждый модуль
        for module_name, module_info in modules.items():
            if module_info.file_path and module_info.file_path.exists():
                content = module_info.file_path.read_text(encoding='utf-8')
                lines = content.split('\n')

                # Поиск вызовов модулей
                for line_num, line in enumerate(lines, 1):
                    for match in self.MODULE_CALL_PATTERN.finditer(line):
                        called_module = match.group(1)
                        called_func = match.group(2)

                        # Пропускаем глобальные контексты
                        if called_module in self.GLOBAL_CONTEXTS:
                            continue

                        # Проверяем, является ли это вызовом модуля
                        if called_module in module_names:
                            dep = Dependency(
                                from_module=module_name,
                                to_module=called_module,
                                dependency_type='call',
                                locations=[line_num]
                            )
                            dependencies.append(dep)
                        elif called_func in exports_map:
                            # Неявный вызов через экспортную функцию
                            target = exports_map[called_func]
                            if target != module_name:
                                dep = Dependency(
                                    from_module=module_name,
                                    to_module=target,
                                    dependency_type='call',
                                    locations=[line_num]
                                )
                                dependencies.append(dep)

        # Агрегируем дублирующиеся зависимости
        return self._aggregate_dependencies(dependencies)

    def _aggregate_dependencies(self, deps: List[Dependency]) -> List[Dependency]:
        """Агрегация дублирующихся зависимостей"""
        agg = defaultdict(list)

        for dep in deps:
            key = (dep.from_module, dep.to_module, dep.dependency_type)
            agg[key].extend(dep.locations)

        result = []
        for (from_m, to_m, dep_type), locations in agg.items():
            result.append(Dependency(
                from_module=from_m,
                to_module=to_m,
                dependency_type=dep_type,
                locations=sorted(set(locations))
            ))

        return result

    def find_circular_dependencies(self, graph: DependencyGraph) -> List[List[str]]:
        """Поиск циклических зависимостей"""
        # Строим граф смежности
        adj = defaultdict(set)
        for dep in graph.dependencies:
            adj[dep.from_module].add(dep.to_module)

        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Нашли цикл
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)
            return False

        for module in graph.modules:
            if module not in visited:
                dfs(module)

        return cycles

    def get_module_dependencies(self, graph: DependencyGraph, module_name: str) -> Tuple[Set[str], Set[str]]:
        """Получение входящих и исходящих зависимостей модуля"""
        outgoing = set()
        incoming = set()

        for dep in graph.dependencies:
            if dep.from_module == module_name:
                outgoing.add(dep.to_module)
            if dep.to_module == module_name:
                incoming.add(dep.from_module)

        return incoming, outgoing

    def calculate_coupling_metrics(self, graph: DependencyGraph) -> Dict[str, Dict]:
        """Расчёт метрик связности модулей"""
        metrics = {}

        for module_name in graph.modules:
            incoming, outgoing = self.get_module_dependencies(graph, module_name)

            metrics[module_name] = {
                'afferent_coupling': len(incoming),   # Ca - кто зависит от модуля
                'efferent_coupling': len(outgoing),   # Ce - от кого зависит модуль
                'instability': len(outgoing) / (len(incoming) + len(outgoing) + 1),
                'incoming_modules': list(incoming),
                'outgoing_modules': list(outgoing)
            }

        return metrics
