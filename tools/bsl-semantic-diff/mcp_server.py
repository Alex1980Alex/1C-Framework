#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL Semantic Diff MCP Server для Claude Code

MCP Server предоставляет инструменты для сравнения BSL файлов и конфигураций 1С
через Model Context Protocol, что позволяет интегрировать семантическое сравнение
прямо в рабочий процесс Claude Code.
"""

import asyncio
import json
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from dataclasses import asdict

# Добавляем путь к модулям BSL Semantic Diff
sys.path.insert(0, str(Path(__file__).parent))

from semantic_diff_poc import BslSemanticDiffer
from metadata_analyzer import BslMetadataAnalyzer
from dependency_analyzer import BslDependencyAnalyzer
from parallel_processor import BslParallelProcessor
from bsl_deep_analyzer import BslDeepAnalyzer
from bsl_logic_analyzer import BslLogicAnalyzer
from bsl_html_visualizer import BslHtmlVisualizer

try:
    import mcp.server.stdio
    import mcp.types as types
    from mcp.server import NotificationOptions, Server
    from mcp.server.models import InitializationOptions
except ImportError:
    print("Ошибка: mcp пакет не установлен. Установите: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bsl-semantic-diff-mcp.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создание MCP сервера
server = Server("bsl-semantic-diff")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    Возвращает список доступных инструментов MCP сервера
    """
    return [
        types.Tool(
            name="bsl_compare_files",
            description="Сравнение двух BSL файлов с семантическим анализом",
            inputSchema={
                "type": "object",
                "properties": {
                    "file1_path": {
                        "type": "string",
                        "description": "Путь к первому BSL файлу"
                    },
                    "file2_path": {
                        "type": "string",
                        "description": "Путь ко второму BSL файлу"
                    },
                    "detailed": {
                        "type": "boolean",
                        "description": "Детальный анализ различий (по умолчанию: false)",
                        "default": False
                    }
                },
                "required": ["file1_path", "file2_path"]
            }
        ),
        types.Tool(
            name="bsl_compare_configurations",
            description="Полное сравнение двух конфигураций 1С (BSL + метаданные)",
            inputSchema={
                "type": "object",
                "properties": {
                    "config1_path": {
                        "type": "string",
                        "description": "Путь к первой конфигурации"
                    },
                    "config2_path": {
                        "type": "string",
                        "description": "Путь ко второй конфигурации"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Путь к файлу отчета (опционально)",
                        "default": ""
                    },
                    "use_parallel": {
                        "type": "boolean",
                        "description": "Использовать параллельную обработку для больших конфигураций",
                        "default": True
                    },
                    "metadata_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список типов метаданных для анализа (по умолчанию: все)",
                        "default": []
                    }
                },
                "required": ["config1_path", "config2_path"]
            }
        ),
        types.Tool(
            name="bsl_analyze_dependencies",
            description="Анализ зависимостей между модулями BSL конфигурации",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_path": {
                        "type": "string",
                        "description": "Путь к конфигурации для анализа зависимостей"
                    },
                    "find_circular": {
                        "type": "boolean",
                        "description": "Поиск циклических зависимостей",
                        "default": True
                    },
                    "module_filter": {
                        "type": "string",
                        "description": "Фильтр модулей (CommonModule, ManagerModule, ObjectModule, FormModule)",
                        "default": ""
                    }
                },
                "required": ["config_path"]
            }
        ),
        types.Tool(
            name="bsl_analyze_metadata",
            description="Анализ XML метаданных конфигурации 1С",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_path": {
                        "type": "string",
                        "description": "Путь к конфигурации"
                    },
                    "object_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Типы объектов метаданных для анализа",
                        "default": ["InformationRegister", "Catalog", "Document"]
                    },
                    "summary_only": {
                        "type": "boolean",
                        "description": "Только сводная информация без деталей",
                        "default": True
                    }
                },
                "required": ["config_path"]
            }
        ),
        types.Tool(
            name="bsl_get_performance_stats",
            description="Получение статистики производительности последних операций",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="bsl_deep_analyze_file",
            description="Глубокий семантический анализ BSL файла с метриками сложности и качества",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к BSL файлу для анализа"
                    },
                    "include_suggestions": {
                        "type": "boolean",
                        "description": "Включить рекомендации по улучшению (по умолчанию: true)",
                        "default": True
                    },
                    "analyze_complexity": {
                        "type": "boolean",
                        "description": "Анализ сложности функций (по умолчанию: true)",
                        "default": True
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="bsl_analyze_logic_flow",
            description="Анализ логических потоков и управляющих конструкций в BSL файле",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к BSL файлу для анализа логики"
                    },
                    "function_name": {
                        "type": "string",
                        "description": "Имя конкретной функции для анализа (опционально)",
                        "default": ""
                    },
                    "detect_patterns": {
                        "type": "boolean",
                        "description": "Обнаружение алгоритмических паттернов (по умолчанию: true)",
                        "default": True
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="bsl_create_html_report",
            description="Создание HTML отчета с визуализацией различий и анализа BSL файлов",
            inputSchema={
                "type": "object",
                "properties": {
                    "file1_path": {
                        "type": "string",
                        "description": "Путь к первому BSL файлу"
                    },
                    "file2_path": {
                        "type": "string",
                        "description": "Путь ко второму BSL файлу (опционально для одиночного анализа)",
                        "default": ""
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Путь для сохранения HTML отчета"
                    },
                    "report_title": {
                        "type": "string",
                        "description": "Заголовок отчета (по умолчанию: 'BSL Analysis Report')",
                        "default": "BSL Analysis Report"
                    },
                    "include_deep_analysis": {
                        "type": "boolean",
                        "description": "Включить глубокий анализ в отчет (по умолчанию: true)",
                        "default": True
                    }
                },
                "required": ["file1_path", "output_path"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """
    Обработка вызовов инструментов MCP сервера
    """
    try:
        if name == "bsl_compare_files":
            return await _handle_compare_files(arguments)
        elif name == "bsl_compare_configurations":
            return await _handle_compare_configurations(arguments)
        elif name == "bsl_analyze_dependencies":
            return await _handle_analyze_dependencies(arguments)
        elif name == "bsl_analyze_metadata":
            return await _handle_analyze_metadata(arguments)
        elif name == "bsl_get_performance_stats":
            return await _handle_get_performance_stats(arguments)
        elif name == "bsl_deep_analyze_file":
            return await _handle_deep_analyze_file(arguments)
        elif name == "bsl_analyze_logic_flow":
            return await _handle_analyze_logic_flow(arguments)
        elif name == "bsl_create_html_report":
            return await _handle_create_html_report(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [types.TextContent(
            type="text",
            text=f"Ошибка выполнения {name}: {str(e)}"
        )]

async def _handle_compare_files(arguments: dict) -> list[types.TextContent]:
    """Сравнение двух BSL файлов"""
    file1_path = Path(arguments["file1_path"])
    file2_path = Path(arguments["file2_path"])
    detailed = arguments.get("detailed", False)

    if not file1_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file1_path}")
    if not file2_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file2_path}")

    logger.info(f"Сравнение файлов: {file1_path} vs {file2_path}")

    differ = BslSemanticDiffer()
    diff = differ.compare_files(file1_path, file2_path)

    if not diff.has_differences:
        return [types.TextContent(
            type="text",
            text="Файлы идентичны - различий не обнаружено"
        )]

    # Формируем отчет
    report_lines = [
        f"СРАВНЕНИЕ BSL ФАЙЛОВ",
        f"=" * 60,
        f"Файл 1: {file1_path.name}",
        f"Файл 2: {file2_path.name}",
        f"",
        f"СТАТИСТИКА РАЗЛИЧИЙ:",
        f"Символов добавлено:  {len(diff.added_symbols)}",
        f"Символов удалено:    {len(diff.removed_symbols)}",
        f"Символов изменено:   {len(diff.modified_symbols)}",
        f""
    ]

    if detailed:
        # Детальная информация о различиях
        if diff.added_symbols:
            report_lines.extend([
                f"ДОБАВЛЕННЫЕ СИМВОЛЫ ({len(diff.added_symbols)}):",
                *[f"  + {symbol.symbol_type}: {symbol.name}" for symbol in diff.added_symbols],
                f""
            ])

        if diff.removed_symbols:
            report_lines.extend([
                f"УДАЛЕННЫЕ СИМВОЛЫ ({len(diff.removed_symbols)}):",
                *[f"  - {symbol.symbol_type}: {symbol.name}" for symbol in diff.removed_symbols],
                f""
            ])

        if diff.modified_symbols:
            report_lines.extend([
                f"ИЗМЕНЕННЫЕ СИМВОЛЫ ({len(diff.modified_symbols)}):",
                *[f"  ~ {symbol.symbol_type}: {symbol.name}" for symbol in diff.modified_symbols],
                f""
            ])

    return [types.TextContent(
        type="text",
        text="\n".join(report_lines)
    )]

async def _handle_compare_configurations(arguments: dict) -> list[types.TextContent]:
    """Полное сравнение конфигураций"""
    config1_path = Path(arguments["config1_path"])
    config2_path = Path(arguments["config2_path"])
    output_file = arguments.get("output_file", "")
    use_parallel = arguments.get("use_parallel", True)
    metadata_types = arguments.get("metadata_types", [])

    if not config1_path.exists():
        raise FileNotFoundError(f"Конфигурация не найдена: {config1_path}")
    if not config2_path.exists():
        raise FileNotFoundError(f"Конфигурация не найдена: {config2_path}")

    logger.info(f"Сравнение конфигураций: {config1_path.name} vs {config2_path.name}")

    # Импортируем функцию сравнения конфигураций
    from compare_configs import compare_configurations_with_metadata

    # Выполняем сравнение
    result = compare_configurations_with_metadata(
        config1_path,
        config2_path,
        output_file=output_file if output_file else None,
        use_parallel_processing=use_parallel,
        metadata_types=metadata_types if metadata_types else None
    )

    # Формируем краткий отчет для MCP
    report_lines = [
        f"СРАВНЕНИЕ КОНФИГУРАЦИЙ 1С",
        f"=" * 60,
        f"Конфигурация 1: {config1_path.name}",
        f"Конфигурация 2: {config2_path.name}",
        f"",
        f"BSL КОД:",
        f"Всего файлов:        {result.get('total_files', 0)}",
        f"Идентичных:          {result.get('identical_files', 0)}",
        f"С различиями:        {result.get('different_files', 0)}",
        f"",
        f"Символов добавлено:  {result.get('symbols_added', 0)}",
        f"Символов удалено:    {result.get('symbols_removed', 0)}",
        f"Символов изменено:   {result.get('symbols_modified', 0)}",
        f"",
        f"МЕТАДАННЫЕ:",
        f"Объектов изменено:   {result.get('metadata_changed', 0)}",
        f""
    ]

    if output_file:
        report_lines.append(f"Полный отчет сохранен: {output_file}")

    return [types.TextContent(
        type="text",
        text="\n".join(report_lines)
    )]

async def _handle_analyze_dependencies(arguments: dict) -> list[types.TextContent]:
    """Анализ зависимостей модулей"""
    config_path = Path(arguments["config_path"])
    find_circular = arguments.get("find_circular", True)
    module_filter = arguments.get("module_filter", "")

    if not config_path.exists():
        raise FileNotFoundError(f"Конфигурация не найдена: {config_path}")

    logger.info(f"Анализ зависимостей: {config_path}")

    analyzer = BslDependencyAnalyzer()
    graph = analyzer.analyze_configuration_dependencies(config_path)

    report_lines = [
        f"АНАЛИЗ ЗАВИСИМОСТЕЙ МОДУЛЕЙ",
        f"=" * 60,
        f"Конфигурация: {config_path.name}",
        f"",
        f"ОБЩАЯ СТАТИСТИКА:",
        f"Всего модулей:       {len(graph.modules)}",
        f"Всего зависимостей:  {len(graph.dependencies)}",
        f""
    ]

    # Фильтрация модулей если указан фильтр
    filtered_modules = graph.modules
    if module_filter:
        filtered_modules = {name: info for name, info in graph.modules.items()
                          if module_filter.lower() in info.module_type.lower()}
        report_lines.append(f"Фильтр '{module_filter}': {len(filtered_modules)} модулей")
        report_lines.append("")

    # Поиск циклических зависимостей
    if find_circular:
        circular_deps = analyzer.find_circular_dependencies(graph)
        if circular_deps:
            report_lines.extend([
                f"ЦИКЛИЧЕСКИЕ ЗАВИСИМОСТИ ({len(circular_deps)}):",
                *[f"  {' -> '.join(cycle)}" for cycle in circular_deps],
                f""
            ])
        else:
            report_lines.extend([
                f"Циклических зависимостей не обнаружено",
                f""
            ])

    # Топ модулей с наибольшим количеством зависимостей
    dep_counts = {}
    for dep in graph.dependencies:
        dep_counts[dep.from_module] = dep_counts.get(dep.from_module, 0) + 1

    if dep_counts:
        top_modules = sorted(dep_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        report_lines.extend([
            f"ТОП МОДУЛЕЙ ПО ИСХОДЯЩИМ ЗАВИСИМОСТЯМ:",
            *[f"  {i:2d}. {module} ({count} зависимостей)"
              for i, (module, count) in enumerate(top_modules, 1)],
            f""
        ])

    return [types.TextContent(
        type="text",
        text="\n".join(report_lines)
    )]

async def _handle_analyze_metadata(arguments: dict) -> list[types.TextContent]:
    """Анализ метаданных конфигурации"""
    config_path = Path(arguments["config_path"])
    object_types = arguments.get("object_types", ["InformationRegister", "Catalog", "Document"])
    summary_only = arguments.get("summary_only", True)

    if not config_path.exists():
        raise FileNotFoundError(f"Конфигурация не найдена: {config_path}")

    logger.info(f"Анализ метаданных: {config_path}")

    analyzer = BslMetadataAnalyzer()

    report_lines = [
        f"АНАЛИЗ МЕТАДАННЫХ 1С",
        f"=" * 60,
        f"Конфигурация: {config_path.name}",
        f"Анализируемые типы: {', '.join(object_types)}",
        f""
    ]

    total_objects = 0

    # Анализ каждого типа метаданных
    for obj_type in object_types:
        objects = analyzer.find_metadata_objects(config_path, obj_type)
        total_objects += len(objects)

        report_lines.append(f"{obj_type}: {len(objects)} объектов")

        if not summary_only and objects:
            # Детальная информация (первые 5 объектов)
            for obj in objects[:5]:
                report_lines.append(f"  • {obj.name}")
                if hasattr(obj, 'attributes') and obj.attributes:
                    report_lines.append(f"    Реквизиты: {len(obj.attributes)}")
                if hasattr(obj, 'dimensions') and obj.dimensions:
                    report_lines.append(f"    Измерения: {len(obj.dimensions)}")
                if hasattr(obj, 'resources') and obj.resources:
                    report_lines.append(f"    Ресурсы: {len(obj.resources)}")

            if len(objects) > 5:
                report_lines.append(f"  ... и еще {len(objects) - 5} объектов")

        report_lines.append("")

    report_lines.extend([
        f"ИТОГО: {total_objects} объектов метаданных",
        f""
    ])

    return [types.TextContent(
        type="text",
        text="\n".join(report_lines)
    )]

async def _handle_get_performance_stats(arguments: dict) -> list[types.TextContent]:
    """Получение статистики производительности"""

    # Простая статистика (в реальной реализации можно собирать метрики)
    stats = {
        "server_status": "active",
        "tools_available": 8,
        "version": "2.0.0",
        "features": [
            "BSL файлов сравнение",
            "Сравнение конфигураций",
            "Анализ зависимостей",
            "Анализ метаданных",
            "Параллельная обработка",
            "Глубокий семантический анализ",
            "Анализ логических потоков",
            "HTML визуализация отчетов"
        ]
    }

    report_lines = [
        f"BSL SEMANTIC DIFF MCP SERVER",
        f"=" * 60,
        f"Статус:              {stats['server_status']}",
        f"Версия:              {stats['version']}",
        f"Доступно инструментов: {stats['tools_available']}",
        f"",
        f"ВОЗМОЖНОСТИ:",
        *[f"  • {feature}" for feature in stats['features']],
        f"",
        f"Используйте инструменты:",
        f"  • bsl_compare_files - сравнение BSL файлов",
        f"  • bsl_compare_configurations - полное сравнение конфигураций",
        f"  • bsl_analyze_dependencies - анализ зависимостей",
        f"  • bsl_analyze_metadata - анализ метаданных",
        f"  • bsl_deep_analyze_file - глубокий анализ BSL файла",
        f"  • bsl_analyze_logic_flow - анализ логических потоков",
        f"  • bsl_create_html_report - создание HTML отчетов",
        f""
    ]

    return [types.TextContent(
        type="text",
        text="\n".join(report_lines)
    )]

async def _handle_deep_analyze_file(arguments: dict) -> list[types.TextContent]:
    """Глубокий анализ BSL файла"""
    file_path = Path(arguments["file_path"])
    include_suggestions = arguments.get("include_suggestions", True)
    analyze_complexity = arguments.get("analyze_complexity", True)

    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    logger.info(f"Глубокий анализ файла: {file_path}")

    analyzer = BslDeepAnalyzer()
    analysis = analyzer.analyze_file_deep(file_path)

    report_lines = [
        f"ГЛУБОКИЙ АНАЛИЗ BSL ФАЙЛА",
        f"=" * 60,
        f"Файл: {file_path.name}",
        f"Размер: {file_path.stat().st_size} байт",
        f"",
        f"ОБЩАЯ СТАТИСТИКА:",
        f"Функций/процедур:    {len(analysis)}",
        f""
    ]

    if analysis:
        # Анализ функций
        total_lines = sum(func.line_count for func in analysis.values())
        total_complexity = sum(func.complexity_metrics.cyclomatic_complexity for func in analysis.values())
        avg_complexity = total_complexity / len(analysis) if analysis else 0

        report_lines.extend([
            f"Общее количество строк: {total_lines}",
            f"Средняя сложность:      {avg_complexity:.1f}",
            f"Максимальная сложность: {max((func.complexity_metrics.cyclomatic_complexity for func in analysis.values()), default=0)}",
            f""
        ])

        # Топ функций по сложности
        complex_functions = sorted(
            analysis.items(),
            key=lambda x: x[1].complexity_metrics.cyclomatic_complexity,
            reverse=True
        )[:5]

        if complex_functions:
            report_lines.extend([
                f"ФУНКЦИИ С ВЫСОКОЙ СЛОЖНОСТЬЮ:",
                *[f"  {i:2d}. {name} (сложность: {func.complexity_metrics.cyclomatic_complexity})"
                  for i, (name, func) in enumerate(complex_functions, 1)],
                f""
            ])

        # Детектор проблем
        problems_found = []
        for name, func in analysis.items():
            if func.complexity_metrics.cyclomatic_complexity > 10:
                problems_found.append(f"Высокая сложность в {name}")
            if len(func.variables) > 20:
                problems_found.append(f"Много переменных в {name}")
            if func.line_count > 100:
                problems_found.append(f"Длинная функция {name}")

        if problems_found:
            report_lines.extend([
                f"ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ ({len(problems_found)}):",
                *[f"  ⚠ {problem}" for problem in problems_found],
                f""
            ])

        if include_suggestions:
            report_lines.extend([
                f"РЕКОМЕНДАЦИИ:",
                f"  • Разбейте функции со сложностью > 10 на более мелкие",
                f"  • Используйте осмысленные имена переменных",
                f"  • Добавьте комментарии к сложным участкам кода",
                f"  • Рассмотрите рефакторинг длинных функций",
                f""
            ])

    return [types.TextContent(
        type="text",
        text="\n".join(report_lines)
    )]

async def _handle_analyze_logic_flow(arguments: dict) -> list[types.TextContent]:
    """Анализ логических потоков"""
    file_path = Path(arguments["file_path"])
    function_name = arguments.get("function_name", "")
    detect_patterns = arguments.get("detect_patterns", True)

    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    logger.info(f"Анализ логики файла: {file_path}")

    analyzer = BslLogicAnalyzer()

    # Читаем содержимое файла
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    report_lines = [
        f"АНАЛИЗ ЛОГИЧЕСКИХ ПОТОКОВ",
        f"=" * 60,
        f"Файл: {file_path.name}",
        f""
    ]

    if function_name:
        # Анализ конкретной функции
        # Простая экстракция функции (в реальности нужен более сложный парсер)
        function_pattern = rf"(?:Функция|Процедура)\s+{function_name}.*?(?:КонецФункции|КонецПроцедуры)"
        import re
        match = re.search(function_pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            function_content = match.group(0)
            logic_flow = analyzer.analyze_function_logic(function_content, function_name)

            report_lines.extend([
                f"АНАЛИЗ ФУНКЦИИ: {function_name}",
                f"Узлов в графе потока:    {len(logic_flow.nodes)}",
                f"Путей выполнения:        {len(logic_flow.execution_paths)}",
                f"Циклов обнаружено:       {len([n for n in logic_flow.nodes if n.node_type == 'loop'])}",
                f"Условий обнаружено:      {len([n for n in logic_flow.nodes if n.node_type == 'condition'])}",
                f"Сложность алгоритма:     {logic_flow.algorithm_complexity}",
                f""
            ])

            if logic_flow.detected_patterns and detect_patterns:
                report_lines.extend([
                    f"ОБНАРУЖЕННЫЕ ПАТТЕРНЫ:",
                    *[f"  • {pattern.pattern_type}: {pattern.confidence:.0%} уверенности"
                      for pattern in logic_flow.detected_patterns],
                    f""
                ])
        else:
            report_lines.append(f"Функция '{function_name}' не найдена в файле")
    else:
        # Общий анализ файла
        functions_found = analyzer.extract_functions_from_content(content)

        report_lines.extend([
            f"ОБЩИЙ АНАЛИЗ ЛОГИКИ:",
            f"Найдено функций/процедур: {len(functions_found)}",
            f""
        ])

        if functions_found:
            for i, func_name in enumerate(functions_found[:5], 1):  # Показываем первые 5
                report_lines.append(f"  {i:2d}. {func_name}")

            if len(functions_found) > 5:
                report_lines.append(f"  ... и еще {len(functions_found) - 5} функций")

            report_lines.append(f"")
            report_lines.append(f"Используйте параметр 'function_name' для детального анализа")

    return [types.TextContent(
        type="text",
        text="\n".join(report_lines)
    )]

async def _handle_create_html_report(arguments: dict) -> list[types.TextContent]:
    """Создание HTML отчета"""
    file1_path = Path(arguments["file1_path"])
    file2_path_str = arguments.get("file2_path", "")
    output_path = Path(arguments["output_path"])
    report_title = arguments.get("report_title", "BSL Analysis Report")
    include_deep_analysis = arguments.get("include_deep_analysis", True)

    if not file1_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file1_path}")

    # Создаем директорию для отчета если не существует
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Создание HTML отчета: {output_path}")

    visualizer = BslHtmlVisualizer()

    if file2_path_str:
        # Сравнительный отчет
        file2_path = Path(file2_path_str)
        if not file2_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file2_path}")

        success = visualizer.create_diff_report(
            file1_path, file2_path, output_path, report_title
        )

        report_type = "сравнительный отчет"
        files_info = f"{file1_path.name} vs {file2_path.name}"
    else:
        # Одиночный анализ
        success = visualizer.create_single_file_report(
            file1_path, output_path, report_title
        )

        report_type = "анализ файла"
        files_info = file1_path.name

    if success:
        report_lines = [
            f"HTML ОТЧЕТ СОЗДАН УСПЕШНО",
            f"=" * 60,
            f"Тип отчета:    {report_type}",
            f"Файлы:         {files_info}",
            f"Заголовок:     {report_title}",
            f"Сохранен в:    {output_path}",
            f"Размер файла:  {output_path.stat().st_size if output_path.exists() else 0} байт",
            f"",
            f"СОДЕРЖИМОЕ ОТЧЕТА:",
            f"  • Подсветка синтаксиса BSL",
            f"  • Сравнение изменений (если два файла)",
            f"  • Метрики сложности" if include_deep_analysis else "",
            f"  • Интерактивная навигация",
            f"  • Встроенные стили и JavaScript",
            f"",
            f"Откройте файл в браузере для просмотра"
        ]
    else:
        report_lines = [
            f"ОШИБКА СОЗДАНИЯ HTML ОТЧЕТА",
            f"=" * 60,
            f"Не удалось создать отчет в {output_path}",
            f"Проверьте права доступа и корректность путей"
        ]

    return [types.TextContent(
        type="text",
        text="\n".join(report_lines)
    )]

async def main():
    """Запуск MCP сервера"""
    # Настройка инициализации
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("Запуск BSL Semantic Diff MCP Server")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="bsl-semantic-diff",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())