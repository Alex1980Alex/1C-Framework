#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Простое тестирование BSL Semantic Diff MCP Server
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем путь к MCP серверу
sys.path.insert(0, str(Path(__file__).parent))

async def test_mcp_tools():
    """Тестирование инструментов MCP сервера"""

    print("ТЕСТИРОВАНИЕ BSL SEMANTIC DIFF MCP SERVER")
    print("=" * 70)

    try:
        # Импортируем функции обработчиков напрямую для тестирования
        from mcp_server import (
            _handle_get_performance_stats,
            _handle_analyze_metadata
        )

        # Тест 1: Получение статистики сервера
        print("\nТест 1: Статистика производительности сервера")
        print("-" * 50)

        stats_result = await _handle_get_performance_stats({})
        print(stats_result[0].text)

        # Тест 2: Проверка конфигурации
        config_file = Path(__file__).parent / "mcp_server_config.json"

        if config_file.exists():
            print("\nТест 2: Конфигурация MCP сервера")
            print("-" * 50)

            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            server_config = config.get('mcpServers', {}).get('bsl-semantic-diff', {})

            print("Конфигурация MCP сервера:")
            print(f"   Команда: {server_config.get('command')}")
            print(f"   Аргументы: {server_config.get('args')}")
            print(f"   Версия: {server_config.get('version')}")
            print(f"   Возможности: {len(server_config.get('capabilities', []))}")

        else:
            print("\nТест 2 пропущен: файл конфигурации не найден")

        print("\nТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО")
        print("=" * 70)
        print("\nMCP Server готов к интеграции с Claude Code!")
        print("Используйте конфигурацию из mcp_server_config.json")

    except Exception as e:
        print(f"\nОШИБКА ТЕСТИРОВАНИЯ: {e}")
        print("=" * 70)
        return False

    return True

def print_integration_instructions():
    """Выводит инструкции по интеграции MCP сервера с Claude Code"""

    print("\nИНСТРУКЦИИ ПО ИНТЕГРАЦИИ С CLAUDE CODE")
    print("=" * 70)

    print("\nНАСТРОЙКА MCP СЕРВЕРА:")
    print("1. Скопируйте содержимое mcp_server_config.json в конфигурацию Claude Code")
    print("2. Или добавьте сервер через команду:")
    print("   claude mcp add bsl-semantic-diff scripts/bsl-semantic-diff/mcp_server.py")

    print("\nИСПОЛЬЗОВАНИЕ В CLAUDE CODE:")
    print("• Сравнение BSL файлов:")
    print('  mcp__bsl-semantic-diff__bsl_compare_files({"file1_path": "path/to/file1.bsl", "file2_path": "path/to/file2.bsl"})')

    print("• Сравнение конфигураций:")
    print('  mcp__bsl-semantic-diff__bsl_compare_configurations({"config1_path": "path/to/config1", "config2_path": "path/to/config2"})')

    print("• Анализ зависимостей:")
    print('  mcp__bsl-semantic-diff__bsl_analyze_dependencies({"config_path": "path/to/config"})')

    print("• Анализ метаданных:")
    print('  mcp__bsl-semantic-diff__bsl_analyze_metadata({"config_path": "path/to/config"})')

    print("\nПРЕИМУЩЕСТВА:")
    print("• Семантическое сравнение BSL кода в реальном времени")
    print("• Анализ XML метаданных (24 типа объектов)")
    print("• Поиск циклических зависимостей между модулями")
    print("• Параллельная обработка для больших конфигураций")
    print("• Интеграция в рабочий процесс Claude Code")

    print("\nПРАКТИЧЕСКИЕ СЦЕНАРИИ:")
    print("• Code Review: автоматическое сравнение веток разработки")
    print("• Анализ качества: поиск проблем архитектуры и зависимостей")
    print("• Миграция: сравнение конфигураций до и после обновления")
    print("• Рефакторинг: отслеживание изменений в процессе оптимизации")

async def main():
    """Основная функция тестирования"""

    # Тестирование функциональности
    test_ok = await test_mcp_tools()

    if test_ok:
        print_integration_instructions()

    return test_ok

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)