#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестирование BSL Semantic Diff MCP Server

Скрипт для тестирования функциональности MCP сервера
без необходимости настройки полного MCP окружения.
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем путь к MCP серверу
sys.path.insert(0, str(Path(__file__).parent))

async def test_mcp_tools():
    """
    Тестирование инструментов MCP сервера
    """
    print("ТЕСТИРОВАНИЕ BSL SEMANTIC DIFF MCP SERVER")
    print("=" * 70)

    try:
        # Импортируем функции обработчиков напрямую для тестирования
        from mcp_server import (
            _handle_compare_files,
            _handle_analyze_metadata,
            _handle_get_performance_stats
        )

        # Тест 1: Получение статистики сервера
        print("\nТест 1: Статистика производительности сервера")
        print("-" * 50)

        stats_result = await _handle_get_performance_stats({})
        print(stats_result[0].text)

        # Тест 2: Анализ метаданных (если конфигурация существует)
        config_path = Path("D:/1C-Enterprise_Framework/src/projects/configuration/250926_GKSTCPLK-1697")

        if config_path.exists():
            print("\nТест 2: Анализ метаданных конфигурации")
            print("-" * 50)

            metadata_args = {
                "config_path": str(config_path),
                "object_types": ["InformationRegister", "Catalog"],
                "summary_only": True
            }

            metadata_result = await _handle_analyze_metadata(metadata_args)
            print(metadata_result[0].text)
        else:
            print(f"\nТест 2 пропущен: конфигурация не найдена по пути {config_path}")

        # Тест 3: Сравнение BSL файлов (если файлы существуют)
        bsl_files = list(config_path.rglob("*.bsl")) if config_path.exists() else []

        if len(bsl_files) >= 2:
            print("\nТест 3: Сравнение BSL файлов")
            print("-" * 50)

            # Берем два первых файла для тестирования
            compare_args = {
                "file1_path": str(bsl_files[0]),
                "file2_path": str(bsl_files[1]),
                "detailed": False
            }

            compare_result = await _handle_compare_files(compare_args)
            print(compare_result[0].text)
        else:
            print(f"\nТест 3 пропущен: недостаточно BSL файлов для сравнения")

        print("\nТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО")
        print("=" * 70)
        print("\nMCP Server готов к интеграции с Claude Code!")
        print("   Используйте конфигурацию из mcp_server_config.json")

    except Exception as e:
        print(f"\nОШИБКА ТЕСТИРОВАНИЯ: {e}")
        print("=" * 70)
        return False

    return True

def test_mcp_configuration():
    """
    Тестирование конфигурации MCP сервера
    """
    print("\nПРОВЕРКА КОНФИГУРАЦИИ MCP")
    print("-" * 50)

    config_file = Path(__file__).parent / "mcp_server_config.json"

    if not config_file.exists():
        print(f"❌ Файл конфигурации не найден: {config_file}")
        return False

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        server_config = config.get('mcpServers', {}).get('bsl-semantic-diff', {})

        if not server_config:
            print("❌ Конфигурация сервера 'bsl-semantic-diff' не найдена")
            return False

        print("✅ Конфигурация MCP сервера:")
        print(f"   Команда: {server_config.get('command')}")
        print(f"   Аргументы: {server_config.get('args')}")
        print(f"   Версия: {server_config.get('version')}")
        print(f"   Возможности: {len(server_config.get('capabilities', []))}")

        return True

    except Exception as e:
        print(f"❌ Ошибка чтения конфигурации: {e}")
        return False

def print_integration_instructions():
    """
    Выводит инструкции по интеграции MCP сервера с Claude Code
    """
    print("\nИНСТРУКЦИИ ПО ИНТЕГРАЦИИ С CLAUDE CODE")
    print("=" * 70)
    print("""
НАСТРОЙКА MCP СЕРВЕРА:

1. Скопируйте содержимое mcp_server_config.json в конфигурацию Claude Code
2. Или добавьте сервер через команду:
   claude mcp add bsl-semantic-diff scripts/bsl-semantic-diff/mcp_server.py

ИСПОЛЬЗОВАНИЕ В CLAUDE CODE:

• Сравнение BSL файлов:
  mcp__bsl-semantic-diff__bsl_compare_files({
    "file1_path": "path/to/file1.bsl",
    "file2_path": "path/to/file2.bsl",
    "detailed": true
  })

• Сравнение конфигураций:
  mcp__bsl-semantic-diff__bsl_compare_configurations({
    "config1_path": "path/to/config1",
    "config2_path": "path/to/config2",
    "use_parallel": true
  })

• Анализ зависимостей:
  mcp__bsl-semantic-diff__bsl_analyze_dependencies({
    "config_path": "path/to/config",
    "find_circular": true
  })

• Анализ метаданных:
  mcp__bsl-semantic-diff__bsl_analyze_metadata({
    "config_path": "path/to/config",
    "object_types": ["InformationRegister", "Catalog", "Document"]
  })

ПРЕИМУЩЕСТВА:
• Семантическое сравнение BSL кода в реальном времени
• Анализ XML метаданных (24 типа объектов поддерживаются)
• Поиск циклических зависимостей между модулями
• Параллельная обработка для больших конфигураций
• Интеграция в рабочий процесс Claude Code

ПРАКТИЧЕСКИЕ СЦЕНАРИИ:
• Code Review: автоматическое сравнение веток разработки
• Анализ качества: поиск проблем архитектуры и зависимостей
• Миграция: сравнение конфигураций до и после обновления
• Рефакторинг: отслеживание изменений в процессе оптимизации
""")

async def main():
    """Основная функция тестирования"""

    # Проверка конфигурации
    config_ok = test_mcp_configuration()

    if not config_ok:
        print("❌ Ошибка в конфигурации MCP сервера")
        return

    # Тестирование функциональности
    test_ok = await test_mcp_tools()

    if test_ok:
        print_integration_instructions()

    return test_ok

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)